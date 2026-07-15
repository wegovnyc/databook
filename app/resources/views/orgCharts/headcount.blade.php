	<div class="chartCard">
		<ul class="nav nav-tabs mb-2" id="graphs-tab" role="tablist">
		  <li class="nav-item" role="presentation">
			<a class="nav-link active" id="headcount-tab" data-bs-toggle="pill" href="#pills-headcount" role="tab" aria-controls="pills-headcount" aria-selected="true">Estimated Headcount</a>
		  </li>
		</ul>
		<div class="tab-content" id="pills-tabContent">
		  <div class="tab-pane fade show active" id="pills-headcount" role="tabpanel" aria-labelledby="headcount-tab">
			  <canvas id="headcountChart" height="200" style="width:100%; height:200px;"></canvas>
		  </div>
		</div>		
	</div>


	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>
	
	<script>
		function pubDateFilterChange() {}

		$(document).ready(function() {
			var canvas1 = document.getElementById("headcountChart");
			
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
							return tooltipItems.formattedValue;
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
							return Chart.Ticks.formatters.numeric.apply(this, [value, index, ticks]);
						}
					  }
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
			const vv = datatable.column(8, {search: 'applied'}).data()
			
			var tmpR = vv.reduce( function (a, b) {
					//d = toDashDateNowrap(b['Publication Date'])
					d = toUsDateNowrap(b['Publication Date'])
					a['years'].add(b['Fiscal Year'])
					a['pubdates'].add(d)
					a['results'][d] = a['results'][d] ?? {}
					a['results'][d][b['Fiscal Year']] = b['Total Funds']
					return a
				}, {'years': new Set(), 'pubdates': new Set(), 'results': {}})
			//console.log(tmpR)
			rr = {
					'years': Array.from(tmpR['years']).sort(),
					'pubdates': Array.from(tmpR['pubdates']).sort((a,b) => b - a).filter(function (_, i) { return i >= Array.from(tmpR['pubdates']).length - 4; }),
					'results': {}
				}
			rr.pubdates.forEach(function (p, i) {
				rr.years.forEach(function (y, i) {
					rr.results[p] = rr.results[p] ?? {}
					rr.results[p][y] = tmpR['results'][p][y] ?? 0
				})
			})
			//console.log(rr)
			chartUpd(window.chart1, rr.results)
		}


		function chartUpd(chart, data) {
			var datasets = []
			var labels = {}
			var colors = ['#1f5673', '#759FBC', '#90C3C8', '#B9B8D3']
			var i = 0
			for (const [label, dd] of Object.entries(data)) {
				if (dd) {
					labels = Object.keys(dd)
					datasets.push({
						label: label,
						data: Object.values(dd),
						fill: false,
						borderColor: colors[i],
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
					})
					i += 1
				}
			}
			
			chart.data.labels = labels
			chart.data.datasets = datasets
			chart.update()
		}

	
		
	</script>
