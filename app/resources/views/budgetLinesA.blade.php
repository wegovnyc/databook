@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects Budget Lines." />
	<meta rel="canonical" href="{!! route('budgetLines') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/rowgroup/1.1.4/js/dataTables.rowGroup.min.js"></script>
	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>

	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<style>
		select.filter {width: 46%;}
	</style>
	<script>
		var table = null
		
		var data = {!! json_encode($data) !!}
		var colors = ['#1f5673', '#759FBC', '#90C3C8', '#B9B8D3', '#463730']

		$(document).ready(function() {
			table = $('#budgLines').DataTable( {
				pageLength: 20,
				deferRender: true,
				order: [[1, 'asc']],
				dom: '<"toolbar container-flex"<"row ml-4">>frtip',
				ajax: function (url, cb) {
					fapireq("{!! $dataUrl !!}", cb);
			    },
				columns: [
					{data: 'Published Date', visible: false},
					{data: function (r) {
							return '<a href="/projects/budget-lines/' + r['Budget Line'] + '">' + r['Budget Line'] + '</a>'
						},
						type: 'html'
					},
					{data: 'wegov-prjtype-name', visible: false},
					{data: 'Budget Line Title', type: 'html'},
					{data: 'Funding Type', type: 'html'},
					{data: 'First Fiscal Year'},
					{data: function (r) { return toFin(r['Fiscal Year 4 Amount']) }, type: 'html'},
					{data: null, visible: false},
                ],
				rowGroup: { dataSrc: 'wegov-prjtype-name' },
				@if ($defSearch ?? null)
					search: {
						'search': '{{ $defSearch }}'
				    },
				@endif	

				initComplete: function () {
					this.api().columns([2,4]).every(function () {						// pubdate
						var tt = {2: 'Project Type Name', 4: 'Funding Type'}
						var column = this;
						var select = $('<select class="filter" id="filter-' + column[0][0] + '" aria-controls="budgLines"><option value="">- ' + $(column.header()).text() + ' -</option></select>')
							.appendTo($('div.toolbar .row'))
							.on('change', function () {
								var val = $.fn.dataTable.util.escapeRegex(
									$(this).val()
								);
								column
									.search(val ? val : '', false, false)
									.draw();
							});
						var tt = []

						rg = />([^<]+)</g;
						column.data().each(function (d, j) {
							tt.push(d)
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							select.append( '<option value="'+d+'">'+d+'</option>' )
						});
					});

					this.api().columns([0]).every(function () {						// pubdate
						var column = this;
						var select = $('<select class="filter" style="width: 100%;" id="filter-' + column[0][0] + '" aria-controls="budgLines"><option value="">- Published Date -</option></select>')
							//.appendTo($('div.toolbar .row'))
							.appendTo($('#pub_date_filter'))
							.on('change', function () {
								var val = $.fn.dataTable.util.escapeRegex(
									$(this).val()
								);
								column
									.search(val ? val : '', false, false)
									.draw();
								graphsUpdate();
							});
						var tt = []

						rg = />([^<]+)</g;
						column.data().each(function (d, j) {
							//while ((t = rg.exec(d)) !== null) {
							//	tt.push(t[1])
							//}
							tt.push(d)
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							select.append( '<option value="'+d+'">'+toDashDate(d)+'</option>' )
						});

						setTimeout(function(){
							select.val(tt[tt.length-1]).trigger('change')
							//select.val('20210426').trigger('change')
						}, 700);
					});
					
				}
			});
			
			
			var canvas1 = document.getElementById("byPrgTypeChart");

			var config1 = {
			  type: 'pie',
			  data: {
				  labels: [],
				  datasets: [{
					label: 'Dataset',
					data: [],
					fill: false,
					backgroundColor: (window.DBChart ? DBChart.palette.concat(DBChart.palette, DBChart.palette) : ['#162e51']),
					borderColor: 'rgba(0, 0, 0, 0.2)',
					hoverBorderColor: 'rgba(0, 0, 0, 0.7)',
					borderWidth: 1,
					hoverOffset: 3,
					datalabels: {
					  color: 'rgba(0, 0, 0, 0.8)',
					  align: 'center',
					  anchor: 'end',
					  //display: 'auto',
					  clip: false,
					  font: {
						  size: 12,
					  }
					}
				  }]
				},
				options: {
					layout: {
						autoPadding: true,
						padding: 5,
					},
					responsive: false,
					radius: '96%',
					showAllTooltips: true,
					onHover: function(evt, elements, chart) {
						if (elements.length) {
							pie_label_on('.byPrgTypeChart', elements[0].index)
						} else {
							pie_labels_off('.byPrgTypeChart')
						}
					},
					plugins: {
					  legend: {
						display: false,
					  },
					  tooltip: {
						enabled: false,
					  },
					  /*
					  datalabels: {
						formatter: function(value, context) {
						  var perc = (value / context.dataset.data.reduce((partialSum, a) => partialSum + a, 0) * 100).toFixed(1)
						  return `${context.chart.data.labels[context.dataIndex]}: ${value} (${perc} %)`
						}
					  }
					  */
					  
					},
				}
			}
			window.chart1 = new Chart(canvas1, config1)


			var canvas2 = document.getElementById("byFundSourceChart");

			var config2 = {
			  type: 'pie',
			  data: {
				  labels: [],
				  datasets: [{
					label: 'Dataset',
					data: [],
					fill: false,
					backgroundColor: (window.DBChart ? DBChart.palette.concat(DBChart.palette, DBChart.palette) : ['#162e51']),
					borderColor: 'rgba(0, 0, 0, 0.2)',
					hoverBorderColor: 'rgba(0, 0, 0, 0.7)',
					borderWidth: 1,
					hoverOffset: 3,
					datalabels: {
					  color: 'rgba(0, 0, 0, 0.8)',
					  align: 'center',
					  anchor: 'end',
					  //display: 'auto',
					  clip: false,
					  font: {
						  size: 12,
					  }
					}
				  }]
				},
				options: {
					layout: {
						autoPadding: true,
						padding: 5,
					},
					responsive: false,
					radius: '96%',
					showAllTooltips: true,
					onHover: function(evt, elements, chart) {
						if (elements.length) {
							pie_label_on('.byFundSourceChart', elements[0].index)
						} else {
							pie_labels_off('.byFundSourceChart')
						}
					},
					plugins: {
					  legend: {
						display: false,
					  },
					  tooltip: {
						enabled: false,
					  },
					  /*
					  datalabels: {
						formatter: function(value, context) {
						  var perc = (value / context.dataset.data.reduce((partialSum, a) => partialSum + a, 0) * 100).toFixed(1)
						  return `${context.chart.data.labels[context.dataIndex]}: ${value} (${perc} %)`
						}
					  }
					  */
					  
					},
				}
			}
			window.chart2 = new Chart(canvas2, config2)
	
	
			// budgets dynamics by funding type
			
			var canvas3 = document.getElementById("ftChart");
			
			var config3 = {
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
					  position: 'left',
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
			window.chart3 = new Chart(canvas3, config3);
	
			initPopovers();
		});

		function pie_labels_off(selector) {
			$(selector + ' .pie_legend li').removeAttr('class')
		}
		
		function pie_label_on(selector, i) {
			pie_labels_off(selector)
			$(selector + ` .pie_legend li[idx="${selector}_${i}"]`).attr('class', 'pie_label_h')
		}
		
		function pie_sectors_off(chart, selector) {
			chart.setActiveElements([{datasetIndex: 1, index: 0}])
			chart.update()
		}
		
		function pie_sector_on(chart, selector, i) {
			pie_sectors_off(chart, selector)
			var dd = [{datasetIndex: 0, index: parseInt(i)}]
			res = chart.setActiveElements(dd);
			chart.update()
		}
		
		function pieChartUpd(chart, selector, dd) {
			//$('#positionsChart').attr('width', 280)
			var s = 0
			if (dd.length == 0) {
				$(selector + ' .pie_legend').replaceWith('<p class="my-4 mx-3">No Positions to Display</p>')
				return
			}
			chart.data.labels = []
			chart.data.datasets[0].data = []
			dd.forEach(function (d, i) {
				const [label, value] = d
				chart.data.labels.push(label)
				chart.data.datasets[0].data.push(value)
				s += value
			})
			//chart.data.labels.forEach(function (l, i, ll) {
			l = chart.data.labels.length
			c = chart.data.datasets[0].backgroundColor.length
			$(selector + ' .pie_legend').text('')
			for (let i = 1; i <= l; i++) {
				if (i < 11) {
					var perc = (chart.data.datasets[0].data[l-i] / s * 100).toFixed(1)
					$(`<li idx="${selector}_${l-i}"><i class="bi bi-square-fill" style="color: ${chart.data.datasets[0].backgroundColor[(l-i) % c]};"></i>&nbsp;&nbsp;${chart.data.labels[l-i]}: ${toFinShortK(chart.data.datasets[0].data[l-i])} (${perc} %)</li>`).appendTo(selector + ' .pie_legend')
					console.log(selector + ' .pie_legend', perc)
				}
			}
			if (chart.data.labels.length > 10) {
				$('<li>...</li>').appendTo(selector + ' .pie_legend')
			}

			//$(selector + ' canvas').attr('width', 300)
			chart.update()
			
			$(selector + ' .pie_legend li').mouseover(function (evt) {
				var idx = $(this).attr('idx')
				pie_sectors_off(chart, selector)
				pie_sector_on(chart, selector, idx.split('_')[1])
			}).mouseout(function (evt) {
				pie_sectors_off(chart, selector)
			})
		}

		function graphsUpdate() {
			const tt = {'C': 'City', 'F': 'Federal', 'S': 'State', 'P': 'Private', 'E': 'City'}
			const vv = table.column(7, {search: 'applied'}).data()
			
			var stats = vv.reduce( function (a, b) {
					t = tt[b['Funding Type']]
					a['byprj'][b['Project Type Name']] 			= (a['byprj'][b['Project Type Name']] ?? 0) + b['Fiscal Year 1 Amount']
					a['byfund'][t] 								= (a['byfund'][t] ?? 0) + b['Fiscal Year 1 Amount']
					a['byft4yr'][t][b['First Fiscal Year'] - 3]	= (a['byft4yr'][t][b['First Fiscal Year'] - 3] ?? 0) + b['Fiscal Year 4 Amount']
					a['byft4yr'][t][b['First Fiscal Year'] - 2]	= (a['byft4yr'][t][b['First Fiscal Year'] - 2] ?? 0) + b['Fiscal Year 3 Amount']
					a['byft4yr'][t][b['First Fiscal Year'] - 1]	= (a['byft4yr'][t][b['First Fiscal Year'] - 1] ?? 0) + b['Fiscal Year 2 Amount']
					a['byft4yr'][t][b['First Fiscal Year']]		= (a['byft4yr'][t][b['First Fiscal Year']] ?? 0) + b['Fiscal Year 1 Amount']
					return a
				}, {'byprj': {}, 'byfund': {}, 'byft4yr': {'City': {}, 'Federal': {}, 'State': {}, 'Private': {}}})
			stats = {
					'byprj': Object.entries(stats['byprj']).sort(([,a],[,b]) => a - b),
					'byfund': Object.entries(stats['byfund']).sort(([,a],[,b]) => a - b),
					'byft4yr': {
						'City': 		stats['byft4yr']['City'],
						'Federal': 		stats['byft4yr']['Federal'],
						'State': 		stats['byft4yr']['State'],
						'Private': 		stats['byft4yr']['Private'],
					}
				}

			pieChartUpd(window.chart1, '.byPrgTypeChart', stats['byprj'])
			pieChartUpd(window.chart2, '.byFundSourceChart', stats['byfund'])
			ftChartUpd(window.chart3, stats['byft4yr'])
		}

		function ftChartUpd(chart, data) {
			var datasets = []
			var labels = {}
			var colors = {'City': '#1f5673', 'Federal': '#759FBC', 'State': '#90C3C8', 'Private': '#B9B8D3'}
			for (const [label, dd] of Object.entries(data)) {
				console.log(dd)
				if (dd) {
					labels = Object.keys(dd)
					datasets.push({
						label: label,
						data: Object.values(dd),
						fill: false,
						borderColor: colors[label],
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
			}
			
			chart.data.labels = labels
			chart.data.datasets = datasets
			chart.update()			
		}

				
	</script>
<div class="inner_container">

	<div class="db-eyebrow mt-4">Projects</div>
	<h2>Budget Lines</h2>
	<div class="row justify-content-center">
		<div class="col-md-9 my-4">
			<p class="lead">The Mayor submits an <a target="_blank" href="https://data.cityofnewyork.us/City-Government/Capital-Budget/46m8-77gv/about_data">Executive Capital Budget</a> for approval by the City Council every year. That budget contains budget lines that are used to fund specific capital projects.</p>
		</div>
		<div class="col-md-3 mt-2" id="org_summary">
			<table class="table-sm stats-table" width="100%">
				<thead>
					<tr>
					<th scope="col" width="50%" class="text-center px-0" data-content="See the project info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px; position:relative;"></i></small></th>
					<th scope="col" width="50%" id="pub_date_filter"></th>
					</tr>
				</thead>
			</table>
		</div>
	</div>

	<div class="container">
	
		<div class="row justify-content-center mb-5">
			<div class="col-md-5" id="costChartOuter">
				<h4 class="mb-2" data-content="City Exempt (C) and City Not Except (E) are combined in the chart.">Annual 1st Year Budget Total by Source <i class="bi bi-question-circle-fill ml-1" style="top:-1px; position:relative; font-size:.8rem;"></i></h4>
				<canvas id="ftChart" height="200" style="width:100%; height:200px;"></canvas>
			</div>
			
			<div class="col byPrgTypeChart">
				<h4 class="mb-2">1st Year Budget by Project Type</h4>
				<div height="200" width="400" style="overflow: visible; display: inline-block; vertical-align: top;">
					<ul class="pie_legend">
					</ul>
				</div>
				<div height="200" width="285" style="overflow: visible; display: inline-block; vertical-align: top; right: -40px; position: absolute;">
					<canvas id="byPrgTypeChart" height="200" width="285" style="width:100%; height:200px;"></canvas>
				</div>
			</div>
			
			<div class="col byFundSourceChart">
				<h4 class="mb-2">1st Year Budget by Project Type</h4>
				<div height="200" width="400" style="overflow: visible; display: inline-block; vertical-align: top;">
					<ul class="pie_legend">
					</ul>
				</div>
				<div height="200" width="285" style="overflow: visible; display: inline-block; vertical-align: top; right: -40px; position: absolute;">
					<canvas id="byFundSourceChart" height="200" width="285" style="width:100%; height:200px;"></canvas>
				</div>
			</div>
		</div>

		<div class="row justify-content-center">
			<div class="col-md-12 organization_data">
                <div class="table-responsive">
                    <table id="budgLines" class="db-table display table" style="width:100%; padding-top: 2px;">
                        <thead>
                            <tr>
								<th scope="col"></th>
								<th scope="col">Budget Line ID</th>
								<th scope="col">Project Type Name</th>
								<th scope="col">Budget Line Title</th>
								<th scope="col">Funding Type</th>
								<th scope="col">First Fiscal Year</th>
								<th scope="col">4 Year Budget Value</th>
                            </tr>
                        </thead>
                    </table>
                </div>
			</div>
		</div>
		
		<div class="row justify-content-center">
			<div class="col-md-12">
				<div class="bottom_lastupdate">
		@if ($dataset)
					<p class="lead"><img src="/img/info.png" alt=""> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span></p>
				</div>
			</div>
		</div>
		@endif

    </div>
</div>
@endsection
