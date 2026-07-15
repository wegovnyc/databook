	<div class="chartCard">
		<ul class="nav nav-tabs mb-2" id="graphs-tab" role="tablist">
		  <li class="nav-item" role="presentation">
			<a class="nav-link active" id="pastheadcount-tab" data-bs-toggle="pill" href="#pills-pastheadcount" role="tab" aria-controls="pills-pastheadcount" aria-selected="true">Headcount Funding</a>
		  </li>
		</ul>
		<div class="tab-content" id="pills-tabContent">
		  <div class="tab-pane fade show active" id="pills-pastheadcount" role="tabpanel" aria-labelledby="pastheadcount-tab">
			  <canvas id="pastheadcountChart" height="200" style="width:100%; height:200px;"></canvas>
		  </div>
		</div>		
	</div>


	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>
	
	<script>
		function pubDateFilterChange() {}

		$(document).ready(function() {
			var canvas1 = document.getElementById("pastheadcountChart");
			
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
			const vv = datatable.column(4, {search: 'applied'}).data()
			
			var tmpR = vv.reduce( function (a, b) {
					//d = toDashDateNowrap(b['Publication Date'])
					d = toUsDateNowrap(b['PUBLICATION DATE'])
					a['years'].add(b['FISCAL YEAR'])
					a['pubdates'].add(d)
					a['results'][d] = a['results'][d] ?? {}
					a['results'][d][b['FISCAL YEAR']] = b['HEADCOUNT']
					a['results'][d][b['FUNDING']] = b['HEADCOUNT']
					return a
				}, {'years': new Set(), 'pubdates': new Set(), 'results': {}})

			rr = {
					'years': Array.from(tmpR['years']).sort(),
					'pubdates': Array.from(tmpR['pubdates']).sort((a,b) => b - a).filter(function (_, i) { return i >= Array.from(tmpR['pubdates']).length - 4; }),
					'results': {}
				}
			rr.pubdates.forEach(function (p, i) {
                rr.years.forEach(function (y, i) {
                    if(tmpR['results'][p].hasOwnProperty(y)) {
                        rr.results[p] = rr.results[p] ?? {}
                        rr.results[p][y] = rr.results[p][y] ?? {}
                        rr.results[p][y]['City'] = tmpR['results'][p]['City'] ?? 0
                        rr.results[p][y]['Non-City'] = tmpR['results'][p]['Non-City'] ?? 0
                    }
				})
			})
			chartUpd(window.chart1, rr.results)
		}


		function chartUpd(chart, data) {
			var datasets = []
			var labels = []
			var labelsTemp = []
			var datas = []
			var colors = ['#1f5673', '#759FBC', '#90C3C8', '#B9B8D3']
			var i = 0
            let $i = 0;
			for (const [label, dd] of Object.entries(data)) {
                if (dd) {
                    // This logic for create data array for city and non-city
                    for (const [label, value] of Object.entries(dd)){
                        datas['City'] = datas['City'] ?? {}
                        datas['Non-City'] = datas['Non-City'] ?? {}
                        labelsTemp['label'] = labelsTemp['label'] ?? {}
                        datas['City'][label] = value.City
                        datas['Non-City'][label] = value['Non-City']
                        labelsTemp['label'][$i] = label
                        $i++;
                    };
				}
			}
            labels = Object.values(labelsTemp['label'])
            // this logic for create two data set for two lines
            for (const [label, value] of Object.entries(datas)){ 
                datasets.push({
                    label: label,
                    data: value,
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
                i++;
            }
			
			chart.data.labels = labels
			chart.data.datasets = datasets
			chart.update()
		}

	
		
	</script>
