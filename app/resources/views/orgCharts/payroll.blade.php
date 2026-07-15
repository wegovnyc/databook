	<div class="chartCard">
		<ul class="nav nav-tabs mb-2" id="graphs-tab" role="tablist">
		  <li class="nav-item" role="presentation">
			<a class="nav-link active" id="chart-tab" data-bs-toggle="pill" href="#pills-chart" role="tab" aria-controls="pills-chart" aria-selected="true">Sum Total Paid per Fiscal Year</a>
		  </li>
		</ul>
		<div class="tab-content" id="pills-tabContent">
		  <div class="tab-pane fade show active" id="pills-chart" role="tabpanel" aria-labelledby="chart-tab">
			  <canvas id="spendingsChart" height="200" style="width:100%; height:200px;"></canvas>
		  </div>
		</div>		
	</div>


	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>
	
	<script>
		function pubDateFilterChange() {}

		$(document).ready(function() {
			var canvas1 = document.getElementById("spendingsChart");
			var config1 = {
				type: 'bar',
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
					  stacked: true,
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
					  },
					  stacked: true
					}
				  }
				},
			};
			window.chart1 = new Chart(canvas1, config1);
			
			datatable.on('draw.dt', function () {
				setTimeout(function(){
					graphsUpdate()
				}, 1000);
			})

		})

		function graphsUpdate() {
			const vv = datatable.rows('', {search: 'applied'}).data()
			
			var tmprr = vv.reduce( function (a, b) {
					a['years'].add(b['Fiscal Year'])
					a['results'][b['Fiscal Year']] = a['results'][b['Fiscal Year']] ?? {'gross': 0.0, 'ot': 0.0, 'other': 0.0}
					a['results'][b['Fiscal Year']]['gross'] += b['Regular Gross Paid']
					a['results'][b['Fiscal Year']]['ot'] += b['Total OT Paid']
					a['results'][b['Fiscal Year']]['other'] += b['Total Other Pay']
					return a
				}, {'years': new Set(), 'results': {}})
			rr = {
					'labels': Array.from(tmprr['years']).sort(),
					'values': {'gross': [], 'ot': [], 'other': []}
				}
			rr.labels.forEach(function (y, i) {
				rr.values['gross'].push(tmprr.results[y]['gross'])
				rr.values['ot'].push(tmprr.results[y]['ot'])
				rr.values['other'].push(tmprr.results[y]['other'])
			})
			chartUpd(window.chart1, rr)
		}


		function chartUpd(chart, data) {
			var colors = ['#90C3C8', '#1f5673', '#759FBC', '#B9B8D3']
			if (data.values['gross'].length) {
				chart.data.labels = data.labels
				chart.data.datasets = [
						{
						  label: 'Sum Gross Paid by Fiscal Year',
						  data: data.values['gross'],
						  backgroundColor: colors[0],
						},
						{
						  label: 'Sum OT Paid by Fiscal Year',
						  data: data.values['ot'],
						  backgroundColor: colors[1],
						},
						{
						  label: 'Sum Total Other Pay by Fiscal Year',
						  data: data.values['other'],
						  backgroundColor: colors[2],
						},
					]
				chart.update();
			} else {
				$('.chartCard').hide();
			}
		}
		
	</script>
