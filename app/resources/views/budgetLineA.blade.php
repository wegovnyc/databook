@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects strategy | {{ $data[0]['Budget Line Title'] }}" />
	<meta rel="canonical" href="{!! route('budgetLine', ['blcode' => $data[0]['Budget Line']]) !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>

	<script>
		function details(r) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  @foreach ((array)$details['details'] as $h=>$f)
				'<tr><td>{{ $h }}:</td><td>' + {!! $f !!} + '</td></tr>' +
			  @endforeach
			'</table>';
		}


		function commDetails(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
				(d["maprojid"] 		? '<tr><td>Mapped Project ID:</td><td>'+d["maprojid"]+'</td></tr>' : '') +
				(d["typc"] 			? '<tr><td>Type Code:</td><td>'+d["typc"]+'</td></tr>' : '') +
				(d["typcname"] 		? '<tr><td>Type Code Name:</td><td>'+d["typcname"]+'</td></tr>' : '') +
				(d["ccnonexempt"] 	? '<tr><td>City Nonexempt:</td><td>'+toFin(d["ccnonexempt"])+'</td></tr>' : '') +
				(d["ccexempt"] 		? '<tr><td>City Exempt:</td><td>'+d["ccexempt"]+'</td></tr>' : '') +
				(d["totalcityplannedcommit"] ? '<tr><td>Total City Planned:</td><td>'+toFin(d["totalcityplannedcommit"])+'</td></tr>' : '') +
				(d["nccstate"] 		? '<tr><td>State Cost:</td><td>'+d["nccstate"]+'</td></tr>' : '') +
				(d["nccfederal"] 	? '<tr><td>Federal Cost:</td><td>'+d["nccfederal"]+'</td></tr>' : '') +
				(d["nccother"] 		? '<tr><td>Other Cost:</td><td>'+d["nccother"]+'</td></tr>' : '') +
				(d["totalnoncityplannedcommit"] ? '<tr><td>Total Noncity Planned:</td><td>'+toFin(d["totalnoncityplannedcommit"])+'</td></tr>' : '') +
				(d["totalplannedcommit"] ? '<tr><td>Total Planned:</td><td>'+toFin(d["totalplannedcommit"])+'</td></tr>' : '') +
				(d["sagencyname"] 	? '<tr><td>Agency Name:</td><td>'+d["sagencyname"]+'</td></tr>' : '') +
				(d["ccpversion"] 	? '<tr><td>Version:</td><td>'+d["ccpversion"]+'</td></tr>' : '') +
			'</table>';
		}

		var datatable = null
		var commdatatable = null
		var bldata = {!! json_encode($data) !!}
		var capcommdata = {}
		var types = {'C': 'City Exempt', 'F': 'Federal', 'S': 'State', 'P': 'Private', 'E': 'City Not Exempt'}
		var colors = ['#1f5673', '#759FBC', '#90C3C8', '#B9B8D3', '#463730']
		var dsstats_table = null
		var datasets = {!! json_encode(array_values($datasets)) !!}
		
		$(document).ready(function() {

			// top data filter
			
			var select = $('<select class="filter" id="filter-top" style="width: 100%;"></select>')
				.appendTo($("#pub_date_filter"))
				.on('change', function () {
					var val = $(this).val()
					blUpdate(val);
				})
			select.wrap('<div class="drop_dowm_select col"></div>');
			var tt = []
			bldata.forEach(function (d, j) {
				tt.push(d['Published Date'])
			})
			tt = [...new Set(tt)]
			tt.sort().forEach(function (d, j) {
				select.append('<option value="'+d+'">'+toDashDate(d)+'</option>')
			})
			setTimeout(function(){
				select.val(tt[tt.length-1]).trigger('change')
			}, 700)
			
			
			// chart
			
			var canvas1 = document.getElementById("costChart");
			
			var config1 = {
				type: 'line',
				data: {
					labels: [],
					datasets: []
				},
				options: {
					responsive: false,
				  elements: { 
					point: {
					  radius: 4,
					  hitRadius: 3,
					  hoverRadius: 3
					} 
				  },
				  plugins: {
					  legend: {
						display: true,
						position: 'top',
						align: 'end',
						labels: {boxHeight: 2},
						usePointStyle: true,
					  },
					  tooltip: {
						backgroundColor: 'rgba(255, 255, 255, 0.9)',
						сolor: 'black',
						displayColors: false,
						bodyFontSize: 14,
						callbacks: {
						  label: function(tooltipItems, data) { 
							return '$' + tooltipItems.formattedValue;
						  },
						  title: function(tooltipItems, data) { 
							return '';
						  },
						  labelTextColor: function(context) {
							return '#444';
						  }
						}
					  },
				  },
				  scales: {
					x: {
					  display: true,
					  grid: {display: false},
					},
					y: {
					  display: true,
					  grid: {display: false},
					  beginAtZero: true,
					  ticks: {
						callback: function(value, index, ticks) {
							return '$' + Chart.Ticks.formatters.numeric.apply(this, [value, index, ticks]);
						}
					  }
					}
				  }
				},
			};
			window.chart1 = new Chart(canvas1, config1);
			
			
			// capcomm data filter

			var capcommselect = $('<select class="filter" id="filter-comm" style="width: 100%;"></select>')
				.appendTo($("#comm_pub_date_filter"))
				.on('change', function () {
					var val = $(this).val()
					capCommUpdate(val);
				})
			capcommselect.wrap('<div class="drop_dowm_select col"></div>');
			
			
			// chart
			
			var canvas2 = document.getElementById("capCommChart");
			
			var config2 = {
				type: 'line',
				data: {
					labels: [],
					datasets: []
				},
				options: {
					responsive: false,
				  elements: { 
					point: {
					  radius: 4,
					  hitRadius: 3,
					  hoverRadius: 3
					} 
				  },
				  plugins: {
					  legend: {
						display: true,
						position: 'top',
						align: 'end',
						labels: {boxHeight: 2},
						usePointStyle: true,
					  },
					  tooltip: {
						backgroundColor: 'rgba(255, 255, 255, 0.9)',
						сolor: 'black',
						displayColors: false,
						bodyFontSize: 14,
						callbacks: {
						  label: function(tooltipItems, data) { 
							return '$' + tooltipItems.formattedValue;
						  },
						  title: function(tooltipItems, data) { 
							return '';
						  },
						  labelTextColor: function(context) {
							return '#444';
						  }
						}
					  },
				  },
				  scales: {
					x: {
					  display: true,
					  grid: {display: false},
					},
					y: {
					  display: true,
					  grid: {display: false},
					  beginAtZero: true,
					  ticks: {
						callback: function(value, index, ticks) {
							return '$' + Chart.Ticks.formatters.numeric.apply(this, [value, index, ticks]);
						}
					  }
					}
				  }
				},
			};
			window.chart2 = new Chart(canvas2, config2);
			
			
			fapireq("{!! $capCommUrl !!}", function (resp) {
				capcommdata = resp['data']
				var tt = []
				capcommdata.forEach(function (d, j) {
					tt.push(d['Published Date'])
				})
				tt = [...new Set(tt)]
				tt.sort().forEach(function (d, j) {
					capcommselect.append('<option value="'+d+'">'+toDashDate(d)+'</option>')
				})
				setTimeout(function(){
					capcommselect.val(tt[tt.length-1]).trigger('change')
				}, 700)
			});


			// commitments DCP datatable
			
			commdatatable = $('#commDatatable').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $commUrl !!}", cb);
			    },
				deferRender: true,
				dom: '<"toolbar container-flex">rt',
				columns: [
					{
						"className": 'details-control',
						"orderable": false,
						"data":  null,
						"defaultContent": ''
					},
					{data: 'maprojid'},
					{data: 'projectdescription'},
					{data: function (r) {
							var slug = r['wegov-prjtype-name'].toLowerCase().replace(/\W+/g, '-')
							return '<a href="/capital/project-types/' + slug + '">' + r['wegov-prjtype-name'] + '</a>'
						},
						type: 'html'
					},
					{data: 'plancommdate'},
					{data: 'commitmentdescription'},
					{data: 'typcname'},
                    {data: function (r) {
							return '<a href="/organization/' + r['wegov-org-id'] + '">' + r['wegov-org-name'] + '</a>'
						},
						type: 'html'
					}                ]
			});

			$('#commDatatable tbody').on('click', 'td.details-control', function () {
				var tr = $(this).closest('tr');
				var row = commdatatable.row(tr);

				if (row.child.isShown()) {
					row.child.hide();
					tr.removeClass('shown');
                    tr.next('tr').removeClass('child-row');
				}
				else {
					row.child(commDetails(row.data())).show();
					tr.addClass('shown');
                    tr.next('tr').addClass('child-row');
					initPopovers();
				}
			});



			// projects datatable
			
			datatable = $('#myTable').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $prjsUrl !!}", cb);
			    },
				buttons: [{
                    extend: 'colvis',
                    "className": 'btn_eyeicon',
                    columnText: function ( dt, idx, title ) {
                        return (idx+1)+': '+(title ? title : 'details');
                    }
                }],
				deferRender: true,
				dom: '<"toolbar container-flex"<"row">>Blfrtip',
				columns: [
                    @if ($details['detFlag'])
                        {
                            "className": 'details-control',
                            "orderable": false,
                            "data":  null,
                            "defaultContent": ''
                        },
                    @endif
                    @foreach ($details['flds'] as $i=>$f)
                        @if ($i > 0)
                            ,
                        @endif
                        {
                        data: {!! $f !!},
						@if (preg_match('~^function ~i', $f))
							type: 'html',
                        @endif
                        @if ($details['visible'][$i])
                            visible: true
                        @else
                            visible: false
                        @endif
                        }
                    @endforeach
					,
                    {
                        className: 'record',
                        data:  null,
                        defaultContent: null,
                        visible: false,
                        searchable: false
                    }
                ],
				createdRow: function(row, data, dataIndex) {
					if (data.GEO_JSON != '') {
						$(row).addClass('have_coords');
					}
				}

				@if ($details['filters'])
					,
					initComplete: function () {
						this.api().columns([{{ $details['fltsCols'] }}]).every(function (c,a,i) {
							var delim = {!! json_encode($details['fltDelim']) !!};
							var column = this;
							var select = $('<select class="filter" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="myTable"><option value="" selected>- ' + $(column.header()).text() + ' -</option></select>')
								.appendTo($("div.toolbar .row"))
								.on('change', function () {
									var val = $(this).val()
									column
										.search(val ? val : '', false, false)
										.draw();
								});
							select.wrap('<div class="drop_dowm_select col"></div>');
							//$('div.toolbar').insertAfter('#myTable_filter');

							var tt = []
							dd = column.data()

							column.data().each(function (d, j) {
								d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
								if (c in delim && typeof d == 'string') {
									d.split(delim[c]).forEach(function (v, k) {
										tt.push(v)
									})
								}
								else
									tt.push(d)
							})
							tt = [...new Set(tt)]

							tt.sort().forEach(function (d, j) {
								select.append('<option value="'+d+'">'+d+'</option>')
							});
						});


						/* pub_date filter */
						this.api().columns([1]).every(function (c,a,i) {
							var delim = {!! json_encode($details['fltDelim']) !!};
							var column = this;
							var select = $('<select class="filter mt-1" style="width:100%;" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="myTable"><option value="" selected>- ' + $(column.header()).text() + ' -</option></select>')
								.appendTo($("#pub_date_prj_filter"))
								.on('change', function () {
									var val = $(this).val()
									column
										.search(val ? val : '', false, false)
										.draw();
									loadFinStat();
								});
							select.wrap('<div class="drop_dowm_select col"></div>');
							//$('div.toolbar').insertAfter('#myTable_filter');

							var tt = []
							dd = column.data()

							column.data().each(function (d, j) {
								d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
								if (c in delim && typeof d == 'string') {
									d.split(delim[c]).forEach(function (v, k) {
										tt.push(v)
									})
								}
								else
									tt.push(d)
							})
							tt = [...new Set(tt)]

							tt.sort().forEach(function (d, j) {
								select.append('<option value="'+d+'">'+d+'</option>')
							});
						});

						setTimeout(function(){
							$('#filter-1 option:last-child').prop('selected',true).trigger('change')
						}, 500);						
						
						setTimeout(function(){
							initPopovers();
						}, 1000);


						$("div.toolbar .row").append('<button id="map_button" class="btn map_btn col" style="margin:0 20px 0 10px; z-index: 10; max-width: 40px;" onclick="toggleMap();"><img src="/img/map_location.png" alt=""></button>');

						@foreach ($details['filters'] as $i=>$v)
							@if ($v)
								setTimeout(function(){
									$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
								}, 500 + 1000 * {{ $i }});
							@endif
						@endforeach
						
					}
				@endif

				@if ($details['order'])
					,
					order: {!! json_encode($details['order']) !!}
				@endif
			});

			$('.btn_eyeicon').hide();

			$('a.toggle-vis').on('click', function (e) {
				e.preventDefault();
				var column = datatable.column($(this).attr('data-column'));
				column.visible(!column.visible());
			});

			$('#myTable tbody').on('click', 'td.details-control', function () {
				var tr = $(this).closest('tr');
				var row = datatable.row(tr);

				if (row.child.isShown()) {
					row.child.hide();
					tr.removeClass('shown');
                    tr.next('tr').removeClass('child-row');
				}
				else {
					row.child(details(row.data())).show();
					tr.addClass('shown');
                    tr.next('tr').addClass('child-row');
					initPopovers();
				}
			});

			//$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));

			// if map is displayed updates and draws projects from GEO_JSON field
			datatable.on('draw', function () {
				drawProjects('current');
            });
			
			$('#myTable tbody').on('click', 'td:not(.details-control)', function () {
				var mapIsActive = !$('#map_container').attr('style')
				if (!mapIsActive) 
					return;
				var tr = $(this).closest('tr');
				var row = datatable.row(tr);
				r = row.data()
				//console.log(r)
				if (r['GEO_JSON']) {
					var geo_json = JSON.parse(r['GEO_JSON'].replaceAll('""', '"'))
					var pr = geo_json.properties
					fitBounds([[pr.W, pr.S], [pr.E, pr.N]])
				}
			})
			
			// makes sortable html fields like 9.4 years late, $25,764 over, $64.2M over
			$.fn.dataTable.ext.type.order['html-pre'] = function (data) {
				var d = data.replace(/>-</g, '>0<');
				d = d.replace(/<span class="(bad)"[^>]*>/g, '-');
				d = d.replace(/[,$]|years|late|<[^>]+>|earl\S+|%/g, '');
				d = d.replace(/NA|NaN|on time/g, '0');
				//console.log(data, d)
				m = 1
				for (const[rg, tmpM] of [[/K$/g, 1000], [/M$/g, 1000000], [/B$/g, 1000000000]]) {
					if (d.match(rg)) {
						m = tmpM;
						d = d.replace(rg, '');
					}
				}
				d = d.match(/[-\d\.]+/g) ? parseFloat(d) * m : d;
				//console.log(data, d);
				return d;
			};
			
			dsstats_table = $('#dsStatsTable').DataTable({
				data: datasets,
				paging: false,
				columns: [
					{ title: "Name" },
					{ title: "Section" },
					{ title: "Description" },
					{ title: "Last Updated" },
					{ title: "Dataset Records" }
				],
				order: [],
				dom: 'rtp',
				initComplete: function () {
					@foreach($datasets as $tbl=>$ds)
						loadTableStat(
							"{{ $tbl }}", 
							"{!! str_replace('tblname', $tbl, $tblStatsUrl) !!}"
						);
					@endforeach
				}
			});
		});


		function toggleMap() {
			var isActive = !$('#map_container').attr('style')
			var cc = [{{ $details['hide_on_map_open'] }}];
			if (isActive) {
				$('#map_button').show()
				$('#data_container').attr('class', 'col')
				$('.toolbar ').show()
				$('#map_container').hide()
				$('#myTable').dataTable().api().columns(cc).every(function () {
					this.visible(true);
				});
			} else {
				$('#map_button').hide()
				$('#data_container').attr('class', 'col col-6')
				$('#map_container').show()
				projectsMapInit();
				$('#myTable').dataTable().api().columns(cc).every(function () {
					this.visible(false);
				});
				setTimeout(function() {
						drawProjects('all');
					}, 3000
				);
			}
			initPopovers();			
		}
		
		
		function loadFinStat() {
			var ss = {!! json_encode($finStatSelectors) !!}
			//var pubdate = $('#filter-1 option:selected').val().replaceAll('-', '');
			
			var vv = datatable.column(0, {search: 'applied'}).data()
			//console.log(vv)
			
			var stats = vv.reduce( function (a, b) {
					a['#projects_no'] 	= (a['#projects_no'] ?? 0) + 1
					a['#orig_cost'] 	= (a['#orig_cost'] ?? 0) + b['BUDG_ORIG']
					a['#curr_cost'] 	= (a['#curr_cost'] ?? 0) + parseFloat(b['BUDG_CURR'].replace(',', '.'))
					a['#over_budg_am'] 	= (a['#over_budg_am'] ?? 0) - parseFloat(b['BUDG_DIFF'])
					a['#long_no'] 		= (a['#long_no'] ?? 0) + ((parseFloat(b['DURATION_DIFF'].replace(/^-$/g, '0')) >= 0) ? 0 : 1)
					a['#over_budg_no'] 	= (a['#over_budg_no'] ?? 0) + ((parseFloat(b['BUDG_DIFF']) < 0) ? 1 : 0)
					a['#late_start_no'] = (a['#late_start_no'] ?? 0) + ((parseFloat(b['START_DIFF'].replace(/^-$/g, '0').replace(',', '.')) >= 0) ? 0 : 1)
					a['#late_end_no'] 	= (a['#late_end_no'] ?? 0) + ((parseFloat(b['END_DIFF'].replace(/^-$/g, '0').replace(',', '.')) >= 0) ? 0 : 1)
					return a
				}, {})
			//console.log(stats)
			
			for (let sel in stats) {
				var v = stats[sel] ?? '-'
				if ((['#orig_cost', '#curr_cost', '#over_budg_am'].includes(sel)) && (v != '-')) {
					$(sel).text(toFinShortK(v, 1000))
					$(sel).attr('data-content', toFin(v, 1000))
				}
				else 
					$(sel).text(v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","))
			}
			setTimeout(function(){
				initPopovers();
			}, 1000);
		}
		
		
		function drawProjects(pages) {	// 'all',     'current'
			var mapIsActive = !$('#map_container').attr('style')
			if (!mapIsActive) 
				return;
			
			var api = $('#myTable').dataTable().api();
			var modifier = {
				order:  'current',  // 'current', 'applied', 'index',  'original'
				page:   pages,      // 'all',     'current'
				search: 'applied',     // 'none',    'applied', 'removed'
			}
			var features = [];
			api.rows('', modifier).data().each(function (r, i) {
				if (r['GEO_JSON']) {
					try {
						geo_json = JSON.parse(r['GEO_JSON'].replaceAll('""', '"'))
						geo_json.properties['AG_ID'] = r['wegov-org-id']
						features.push(geo_json)
					} catch (error) {
						console.error(error);
					}
				}
			});
			projectsMapDrawFeatures(features);
		}
		
		function blUpdate(date) {
			var datasets = []
			var labels = {}
			$('#costStats tbody').html('')
			bldata.forEach(function (d, i) {
				if (d['Published Date'] == date) {
					$('<tr><td>' + types[d['Funding Type']] + '</td><td>' + d['First Fiscal Year'] + '</td><td>' + toFin(parseInt(d['Fiscal Year 1 Amount']) + parseInt(d['Fiscal Year 2 Amount']) + parseInt(d['Fiscal Year 3 Amount']) + parseInt(d['Fiscal Year 4 Amount'])) + '</td></tr>').appendTo('#costStats tbody');
					
					labels = [d['First Fiscal Year'], parseInt(d['First Fiscal Year']) + 1, parseInt(d['First Fiscal Year']) + 2, parseInt(d['First Fiscal Year']) + 3]
				
					datasets.push({
						label: types[d['Funding Type']],
						data: [d['Fiscal Year 1 Amount'], d['Fiscal Year 2 Amount'], d['Fiscal Year 3 Amount'], d['Fiscal Year 4 Amount']],
						fill: false,
						borderColor: colors[datasets.length],
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
					})
				}
			})
			
			window.chart1.data.labels = labels
			window.chart1.data.datasets = datasets
			window.chart1.update()			
		}
		
		function capCommUpdate(date) {
			var datasets = []
			var labels = {}
			$('#capCommStats tbody').html('')
			capcommdata.forEach(function (d, i) {
				if (d['Published Date'] == date) {
					$('<tr><td>' + d['Funding Type'] + '</td><td>' + d['comm_no'] + '</td><td>' + d['First Fiscal Year'] + '</td><td>' + toFin((d['yr1amount'] + d['yr2amount'] + d['yr3amount'] + d['yr4amount'] + d['yr5amount']) * 1000) + '</td></tr>').appendTo('#capCommStats tbody');
					
					labels = [d['First Fiscal Year'], parseInt(d['First Fiscal Year']) + 1, parseInt(d['First Fiscal Year']) + 2, parseInt(d['First Fiscal Year']) + 3, parseInt(d['First Fiscal Year']) + 4]
				
					datasets.push({
						label: d['Funding Type'],
						data: [d['yr1amount'] * 1000, d['yr2amount'] * 1000, d['yr3amount'] * 1000, d['yr4amount'] * 1000, d['yr5amount'] * 1000],
						fill: false,
						borderColor: colors[datasets.length],
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
					})
				}
			})
			
			window.chart2.data.labels = labels
			window.chart2.data.datasets = datasets
			window.chart2.update()			
		}

		function loadTableStat(dsName, url) {
			dsstats_table = $('#dsStatsTable').DataTable();
			fapireq(url, function (resp) {
				if (resp['data'][0]['res']) {
					$('#stats_'+dsName).text(resp['data'][0]['res'])
					$('#total_records').text(Number($('#total_records').text()) + resp['data'][0]['res'])
					$('#total_datasets').text(Number($('#total_datasets').text()) + 1)
				} else {
					datasets.forEach(function (d, i) {
						if (d[4].indexOf('stats_'+dsName) != -1) {
							datasets.splice(i, 1)
							dsstats_table.row(i).remove()
							dsstats_table.draw();
						}
					})
				}
			})
		}


		
	</script>

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center mb-2">
				<div class="col-md-12 organization_data pb-3">
					<div class="db-eyebrow">Projects</div>
					<h2>{{ $data[0]['Budget Line Title'] }}</h2>
					<div class="row mx-0 my-1">
						<div class="col-2">
							<small class="text-muted">ID</small><br />
							<h6>{{ $data[0]['Budget Line'] }}</h6>
						</div>
						<div class="col-10">
							<small class="text-muted">Project Type</small><br />
							<h6><a href="{{ route('prjType', ['tslug' => Str::slug($data[0]['wegov-prjtype-name'], '-')]) }}">{{ $data[0]['wegov-prjtype-name'] }}</a></h6>
						</div>
					</div>
				</div>
			</div>


			<div class="row justify-content-center">
				<div class="col-md-6 pr-5">
					<div class="row justify-content-center">
						<div class="col-md-6 organization_data">
							<h4 class="mb-2">Budget</h4>
						</div>
						<div class="col-md-6 mt-2">
							<table class="table-sm stats-table" width="100%">
								<thead>
								  <tr>
									<th scope="col" width="50%" class="text-center px-0" data-content="See budget line info published on specific date.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
									<th scope="col" width="50%" id="pub_date_filter"></th>
								  </tr>
								</thead>
							</table>
						</div>
					</div>


					<div class="row justify-content-center mb-4">
						<div class="col-md-12" id="statsOuter">
							<table class="db-table table table-sm" id="costStats">
							  <thead>
								<tr>
								  <th scope="col">Funding Type</th>
								  <th scope="col">First Fiscal Year</th>
								  <th scope="col">4 Year Allocation</th>
								</tr>
							  </thead>
							  <tbody>
							  </tbody>
							</table>
						</div>
					</div>
					<div class="row justify-content-center mb-5">
						<div class="col-md-12" id="costChartOuter">
							<canvas id="costChart" height="200" style="width:100%; height:200px;"></canvas>
						</div>
					</div>
				</div>

				<div class="col-md-6 pl-5">
					<div class="row justify-content-center">
						<div class="col-md-6 organization_data">
							<h4 class="mb-2">Commitments (OMB)</h4>
						</div>
						<div class="col-md-6 mt-2">
							<table class="table-sm stats-table" width="100%">
								<thead>
								  <tr>
									<th scope="col" width="50%" class="text-center px-0" data-content="See commitment info published on specific date.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
									<th scope="col" width="50%" id="comm_pub_date_filter"></th>
								  </tr>
								</thead>
							</table>
						</div>
					</div>

					<div class="row justify-content-center mb-4">
						<div class="col-md-12" id="statsOuter">
							<table class="db-table table table-sm" id="capCommStats">
							  <thead>
								<tr>
								  <th scope="col">Funding Type</th>
								  <th scope="col">Projects No</th>
								  <th scope="col">First Fiscal Year</th>
								  <th scope="col">Total Commitment</th>
								</tr>
							  </thead>
							  <tbody>
							  </tbody>
							</table>
						</div>
					</div>
					<div class="row justify-content-center mb-5">
						<div class="col-md-12" id="capCommChartOuter">
							<canvas id="capCommChart" height="200" style="width:100%; height:200px;"></canvas>
						</div>
					</div>
			

				</div>
			</div>




			<div class="row justify-content-center">
				<div class="col-md-12 organization_data">
					<h4 class="mb-2">Commitments (DCP)</h4>
					<div class="table-responsive">
						<table id="commDatatable" class="db-table mb-2 mt-0" width="100%">
							<thead>
								<tr>
									<th scope="col"></th>
									<th scope="col">Enhanced Project Id</th>
									<th scope="col">Description</th>
									<th scope="col">Project Type</th>
									<th scope="col">Plan Commitment Date</th>
									<th scope="col">Commitment Description</th>
									<th scope="col">Commitment Type</th>
									<th scope="col">Managing Agency Name</th>
								</tr>
							</thead>
						</table>
					</div>
				</div>
			</div>

			
			<div class="row justify-content-center mt-2">
				<div class="col-md-7 organization_data">
					<h1>Projects</h1>
				</div>
				<div class="col-md-5 mt-2" id="org_summary">
					<table class="table-sm stats-table" width="100%">
					<tbody>
						<tr class="align-middle"> 
							<td class="text-center px-0 pt-0" data-content="See the projects info published on specific dates." style="position:relative; top: -2px;">
								Project Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small>
							</td>
							<td class="pt-0" width="40%" id="pub_date_prj_filter" style="position:relative; top: -2px;"></td>
						{{--<td class="text-right px-0 pt-0 pb-3">
								<button class="type-label my-2 dropdown-toggle" data-bs-toggle="collapse" data-bs-target="#stats_collapse" aria-expanded="false" aria-controls="stats_collapse"><small>Show/Hide Stats</small></button>
							</td>
						--}}
						</tr>
					</tbody>
					</table>
				</div>
			</div>
			
			{{--<div id="stats_collapse" class="collapse mt-2 mb-4">--}}
			<div id="stats_collapse" class="mt-2 mb-4">
				<div class="row justify-content-center my-2">
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Number of Projects
									<h2 id="projects_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Original Cost
									<h2 id="orig_cost" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Current Cost
									<h2 id="curr_cost" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									<small>Amount Over Budget</small>
									<h2 id="over_budg_am" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Running Long
									<h2 id="long_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Over Budget
									<h2 id="over_budg_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Starting Late
									<h2 id="late_start_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Ending Late
									<h2 id="late_end_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
				</div>
					
			</div>
					
				
			<div class="row justify-content-center map_right mb-5">
				@if ($map ?? null)
					<div id="map_container" class="col-6" style="display:none;">
						<button id="map_button_alt" class="btn btn-outline map_btn" style="margin:0 20px 20px 10px; z-index: 10; max-width: 40px; float:right;" onclick="toggleMap();"><img src="/img/map_location.png" alt=""></button>
						<!-- toggles -->
						<div class="select_district" id="toggles" style="left:0px;">
							<img src="/img/eyes.png" alt="">
							<ul class="inner_district">
								<li class="dropdown">
									<a class="dropdown-toggle" id="toggle_boundries" role="button" aria-haspopup="true" aria-expanded="true">Show District Boundaries</a>
									<div class="dropdown-menu" style="width:100%;padding:0px 0px 0px 10px;">
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="cd-switch">
											<label class="custom-control-label" for="cd-switch">Community Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="ed-switch">
											<label class="custom-control-label" for="ed-switch">Election Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="pp-switch">
											<label class="custom-control-label" for="pp-switch">Police Precincts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="dsny-switch">
											<label class="custom-control-label" for="dsny-switch">Sanitation Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="fb-switch">
											<label class="custom-control-label" for="fb-switch">Fire Battilion<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="sd-switch">
											<label class="custom-control-label" for="sd-switch">School Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="hc-switch">
											<label class="custom-control-label" for="hc-switch">Health Center Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="cc-switch">
											<label class="custom-control-label" for="cc-switch">City Council Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="nycongress-switch">
											<label class="custom-control-label" for="nycongress-switch">Congressional Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="sa-switch">
											<label class="custom-control-label" for="sa-switch">State Assembly Dist...<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="ss-switch">
											<label class="custom-control-label" for="ss-switch">State Senate Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="bid-switch">
											<label class="custom-control-label" for="bid-switch">Business Improvem...<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="nta-switch">
											<label class="custom-control-label" for="nta-switch">Neighborhood Tab...<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="zipcode-switch">
											<label class="custom-control-label" for="zipcode-switch">Zip Code<hr class="border-sample"></label>
										</div>
									</div>
								</li>
							</ul>
						</div>
						<!-- /toggles -->
						<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;border:4px solid #112F4E; position:relative; min-height:800px;"></div>
						<div id="help_us" class="" style="width:100%;min-height:260px;border:1px solid #112F4E; margin-top:24px; padding: 32px;">
							<h4>Help us locate projects</h4>
							<p>NYC’s government doesn’t publish the locations of capital projects (!?), so volunteers are using the information they do publish to determine where the projects are actually located.</p>
							<p><a href="https://www.notion.so/wegovnyc/Volunteer-d751814ef6374dd9b9d10c989bcfa141" class="learn_more" target="_blank" rel="nofollow">Join Us</a></p>
						</div>
					</div>
				@endif
				<div id="data_container" class="col float-left">
					<div class="table-responsive">
						<div class="filter_icon">
							<i class="bi bi-funnel-fill"></i>
						</div>
						<table id="myTable" class="display table-striped table-hover" style="width:100%;">
							<thead>
								<tr>
									@if ($details['detFlag'])
										<th></th>
									@endif
									@foreach ($details['hdrs'] as $name)
										<th>{{ $name }}</th>
									@endforeach
									<th></th>
								</tr>
							</thead>
						</table>
					</div>
				</div>
			</div>
		</div>

		<div class="container">
			<div class="row my-4">
				<div id="data_container_accordion" class="col-12 accordion">
				
					<div class="accordion social_media" id="accordionThree">
						<div>
							<div id="headingThree">
								<button class="social_btn" type="button" data-bs-toggle="collapse" data-bs-target="#collapseThree" aria-expanded="false" aria-controls="collapseThree">
									We’re using normalized data from <span id="total_datasets"></span> datasets containing <span id="total_records"></span> records. Click here to learn more.
								</button>
							</div>
							<div id="collapseThree" class="collapse hide" aria-labelledby="headingOne" data-parent="#accordionThree">
								<div class="card-text table-responsive">
									<table id="dsStatsTable" class="db-table display table-hover table-borderless" style="width:100%;">
									</table>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>


	<script>
		function changeToggle (e) {
			$('#change_district').html($(e.target).next("label")[0].innerHTML);
		}
		$('#toggle_boundries').click( function (e) {
			$(this).next('.dropdown-menu').toggleClass('show');
		})

		$(".filter_icon").click(function() {
			if(!$('.toolbar').is(':visible')) {
				$('.filter_icon').addClass('position_change');
			}else {
				$('.filter_icon').removeClass('position_change');
			}
			$(".toolbar").toggle();
		});
	</script>

@endsection