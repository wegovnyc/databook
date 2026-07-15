@extends('layout')


@section('head')
	<meta name="description" content="{-- $snippet --}" />
	<meta rel="canonical" href="{--!! $canonicalUrl !!--}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	@include('sub.schoolprofile', ['active' => $section])

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

	<script>
		var datasets = {!! json_encode(array_values($datasets)) !!}
		var tblStatsUrls = {!! json_encode($tblStatsUrls) !!}
		var dsstats_table = null


		function loadTableStat(dsName, url) {
			var dsstats_table = $('#dsStatsTable').DataTable();
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


		function details(r) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  @foreach ((array)$details['details'] as $h=>$f)
				'<tr><td>{{ $h }}:</td><td>' + {!! $f !!} + '</td></tr>' +
			  @endforeach
			'</table>';
		}


		var datatable = null
		$(document).ready(function() {
			
			datatable = $('#myTable').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $url !!}", cb);
			    },
					
				/*	
				ajax: {
					url: '{!! $url !!}',
					dataSrc: 'rows'
				},
				*/
				buttons: [{
                    extend: 'colvis',
                    "className": 'btn_eyeicon',
                    columnText: function ( dt, idx, title ) {
                        return (idx+1)+': '+(title ? title : 'details');
                    }
                }],
				deferRender: true,
				language: { emptyTable: '<div class="db-empty"><div class="db-empty-icon"><i class="bi bi-inbox"></i></div><div class="db-empty-title">No data for this school</div><div class="db-empty-text">This dataset has no records for the selected school.</div></div>' },
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
							$('div.toolbar').insertAfter('#myTable_filter');

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
							initPopovers();
						}, 1000);
						
					}
				@endif

				@if ($details['order'] ?? null)
					,
					order: {!! json_encode($details['order']) !!}
				@endif
			});


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
					@foreach($tblStatsUrls as $tbl=>$statsUrl)
						loadTableStat(
							"{{ $tbl }}", 
							"{!! $statsUrl !!}"
						);
					@endforeach
				}
			});



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

			$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));

			// if map is displayed updates and draws projects from GEO_JSON field
			/*
			datatable.on('draw', function () {
				drawProjects('current');
            });
			*/
			
			$('#myTable tbody').on('click', 'td:not(.details-control)', function () {
				var mapIsActive = !$('#map_container').attr('style')
				if (!mapIsActive) 
					return;
				var tr = $(this).closest('tr');
				var row = datatable.row(tr);
				r = row.data()
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


			// school on map
			@if ($school['LATITUDE'])
				
				//var bounds = [[feature.properties.W, feature.properties.S], [feature.properties.E, feature.properties.N]]
				var bounds = [[{{ $school['LONGITUDE'] - 0.04 }}, {{ $school['LATITUDE'] - 0.04 }}], [{{ $school['LONGITUDE'] + 0.04 }}, {{ $school['LATITUDE'] + 0.04 }}]]
				var features = [{"type":"Feature","geometry":{"type":"Point","coordinates":[{{ $school['LONGITUDE'] }},{{ $school['LATITUDE'] }}]}}]
				//console.log(features)
			
				mapboxgl.accessToken = 'pk.REPLACE_WITH_YOUR_MAPBOX_TOKEN';

				map = new mapboxgl.Map({
					container: 'map',
					style: 'mapbox://styles/mapbox/light-v10',
					center: [{{ $school['LONGITUDE'] }},{{ $school['LATITUDE'] }}],
					zoom: 10
				});
				
				map.addControl(new mapboxgl.NavigationControl());

				map.on('load', function () {
					map.addSource('route', {
							"type": "geojson",
							"data": {
								"type": "FeatureCollection",
								"features": features
							}
						});

					map.addLayer({
						'id': 'streets',
						'type': 'line',
						'source': 'route',
						'layout': {
							'line-join': 'round',
							'line-cap': 'round'
						},
						'paint': {
							'line-color': '#53777a',
							'line-width': 6
						},
						'filter': ['==', '$type', 'LineString']
					});

					map.addLayer({
						'id': 'markers',
						'type': 'circle',
						'source': 'route',
						'paint': {
							'circle-radius': 6,
							'circle-color': '#53777a'
						},
						'filter': ['==', '$type', 'Point']
					});

					map.addLayer({
						'id': 'areas',
						'type': 'fill',
						'source': 'route',
						'paint': {
							'fill-color': '#53777a',
							'fill-opacity': 1
						},
						'filter': ['==', '$type', 'Polygon']
					});
					
					for (const [code, clr] of Object.entries(zones)) {
						setBoundary(code, clr, clr);
					}
					$('#toggles').show();

					map.fitBounds(bounds);
				});
				
			@endif

			
			@if($schoolStatsUrl ?? null)
				fapireq('{!! $schoolStatsUrl !!}', function (resp) {
					$('#povetry_perc').text(resp.data[0].povetry_perc != null ? resp.data[0].povetry_perc : 'NaN')
					$('#students_no').text(resp.data[0].students_no != null ? commaThousands(resp.data[0].students_no) : 'NaN')
					$('#prj_no').text(resp.data[0].prj_no != null ? commaThousands(resp.data[0].prj_no) : 'NaN')
					$('#prj_budget').text(resp.data[0].prj_budget != null ? toFinShortK(resp.data[0].prj_budget) : 'NaN')
					$('#prj_costs').text(resp.data[0].prj_costs != null ? toFinShortK(resp.data[0].prj_costs) : 'NaN')
					$('#pcosts_per_student').text(resp.data[0].pcosts_per_student != null ? toFinShortK(resp.data[0].pcosts_per_student) : 'NaN')
				})
			@endif	

			
		});
	
	</script>



	<div class="inner_container">
		<div class="container mb-5" style="padding-top: var(--db-space-3);">
			<div class="organization_data">
				@if(array_search($section, $menu) === false)
					<h2 class="db-card-title">{{ $dataset['Name'] ?? '' }}</h2>
				@endif
				@if (trim($details['description'] ?? ($dataset['Descripton'] ?? '')))
					<p class="db-page-lead">{!! nl2br($details['description'] ?? ($dataset['Descripton'] ?? '')) !!}</p>
				@endif
			</div>

			<div class="db-table-wrap mt-3">
				<div id="data_container" class="table-responsive">
					<div class="filter_icon">
						<i class="bi bi-funnel-fill"></i>
					</div>
					<table id="myTable" class="db-table display table-striped table-hover" style="width:100%;">
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

		@if ($dataset && ($dataset['Public Note'] ?? null))
			<div class="container mb-3">
				<p class="note_bottom db-page-lead">{{ nl2br($dataset['Public Note'] ?? '') }}</p>
			</div>
		@endif

		{{--
			<div class="col-md-12" style="display:none">
				<div class="bottom_lastupdate">
		@if ($dataset)
					<p class="lead"><img src="/img/info.png"> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span></p>
				</div>
			</div>
		@endif
		--}}
		
		<div class="container">
			<div class="row mb-4">
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