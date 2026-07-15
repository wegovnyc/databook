<div class="db-profile-header" id="pos-header">
	<div class="inner_container">
		<div class="container">
			<div class="db-profile-header-top">
				<div class="db-profile-main">
					<div class="db-profile-kicker">
						<span class="db-type-label">Civil Service Title</span>
						<span class="db-tag">Code {{ $titles[0]['Title Code'] }}</span>
					</div>
					<h1 class="db-profile-title">{{ $titles[0]['Title Description'] }}</h1>
					@if($titles[0]['wegov-org-name'])
						<p class="db-profile-subtitle"><i class="bi bi-people"></i> Bargaining Unit:
							<a href="/o/{{ $titles[0]['wegov-org-id'] }}-{{ Str::slug($titles[0]['wegov-org-name'], '-') }}">{{ $titles[0]['wegov-org-name'] }}</a></p>
					@endif
				</div>
			</div>

			<div class="row">
				<div class="col-12">
					<div class="db-table-wrap">
					<table class="db-table">
					  <thead>
						<tr>
						  <th scope="col">Minimum Salary Rate</th>
						  <th scope="col">Maximum Salary Rate</th>
						  <th scope="col">Standard Hours</th>
						  <th scope="col">Assignment Level</th>
						</tr>
					  </thead>
					  <tbody>
						@foreach ($titles as $title)
							<tr>
							  <td>${{ number_format($title['Minimum Salary Rate']) }}</td>
							  <td>${{ number_format($title['Maximum Salary Rate']) }}</td>
							  <td>{{ $title['Standard Hours'] }}</td>
							  <td>{{ $title['Assignment Level'] }}</td>
							</tr>					
						@endforeach
					  </tbody>
					</table>
				</div>
			</div>
		</div>
		
		<div class="row mt-3"><div class="col-12">
		  <div class="db-chart-card" style="padding: var(--db-space-2);">
			<ul class="nav nav-tabs db-tabs mb-2" id="graphs-tab" role="tablist">
			  <li class="nav-item" role="presentation">
				<a class="nav-link active" id="salary-tab" data-bs-toggle="pill" href="#pills-salary" role="tab" aria-controls="pills-salary" aria-selected="true">Employees & Salaries</a>
			  </li>
			  <li class="nav-item" role="presentation">
				<a class="nav-link" id="positions-tab" data-bs-toggle="pill" href="#pills-positions" role="tab" aria-controls="pills-positions" aria-selected="false">Positions by Agency</a>
			  </li>
			</ul>
			<div class="tab-content" id="pills-tabContent">
			  <div class="tab-pane fade show active" id="pills-salary" role="tabpanel" aria-labelledby="salary-tab">
				  <canvas id="salariesChart" height="200" style="width:100%; height:200px;"></canvas>
			  </div>
			  <div class="tab-pane fade" id="pills-positions" role="tabpanel" aria-labelledby="positions-tab">
				  <div height="200" width="400" style="overflow: visible; display: inline-block; vertical-align: top;">
					<ul id="pie_legend">
					</ul>
				  </div>
				  <div height="200" width="285" style="overflow: visible; display: inline-block; vertical-align: top;">
					  <canvas id="positionsChart" height="200" width="285" style="width:100%; height:200px;"></canvas>
				  </div>
			  </div>
			</div>		
		  </div>		
		</div>
	</div>


	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>
	
	<script>
	
		//Chart.register(ChartDataLabels)
		
		var canvas1 = document.getElementById("salariesChart");

		var config1 = {
			type: 'line',
			data: {
				labels: [],
				datasets: [
				  {
					  data: [],
					  yAxisID: 'y',
					  fill: false,
					  borderColor: (window.DBChart ? DBChart.navy : 'rgba(0,0,0,0.5)'),
					  borderWidth: 2,
					  pointBackgroundColor: 'transparent',
					  pointBorderColor: '#CCCCCC',
					  pointBorderWidth: 3,
					  pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
					  pointHoverBorderWidth: 6,
					  tension: 0.1,
					  datalabels: {
						display: false,
					  },
				  },
				  {
					  data: [],
					  yAxisID: 'ry',
					  fill: false,
					  borderColor: (window.DBChart ? DBChart.accent : 'rgba(30,67,76,.5)'),
					  borderWidth: 2,
					  pointBackgroundColor: 'transparent',
					  pointBorderColor: 'rgba(30, 67, 76, .3)',
					  pointBorderWidth: 3,
					  pointHoverBorderColor: 'rgba(30, 67, 76, .5)',
					  pointHoverBorderWidth: 6,
					  tension: 0.1,
					  datalabels: {
						display: false,
					  },
				  }
				  
				]
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
					display: false,
				  },
				  tooltip: {
					backgroundColor: 'rgba(255, 255, 255, 0.9)',
					сolor: 'black',
					displayColors: false,
					bodyFontSize: 14,
					callbacks: {
					  label: function(tooltipItems, data) { 
						return (tooltipItems.datasetIndex == 0) 
									? '$' + tooltipItems.formattedValue
									: tooltipItems.formattedValue;
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
				},
				ry: {
				  display: true,
				  position: 'right',
				  grid: {display: false},
				  beginAtZero: true,
				}
			  }
			},
		};

		window.chart1 = new Chart(canvas1, config1);
		
		fapireq('{!! $salaryStatsUrl !!}', function (dd) {
			dd.data.forEach(function (v, i, vv) {
				window.chart1.data.labels.push(v.year)
				window.chart1.data.datasets[0].data.push(v.salary)
				window.chart1.data.datasets[1].data.push(v.employees)
			})
			chart1.update()
		})
		
	</script>
	
	{{--
		<script>
			var canvas2 = document.getElementById("employeesChart");

			var config2 = {
				type: 'line',
				data: {
					labels: [],
					datasets: [
					  {
						  data: [],
						  fill: false,
						  borderColor: 'rgba(0, 0, 0, 0.5)',
						  borderWidth: 2,
						  pointBackgroundColor: 'transparent',
						  pointBorderColor: '#CCCCCC',
						  pointBorderWidth: 3,
						  pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						  pointHoverBorderWidth: 6,
						  tension: 0.1,
						  datalabels: {
							display: false,
						  },
					  }
					]
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
						display: false,
					  },
					  tooltip: {
						backgroundColor: 'rgba(255, 255, 255, 0.9)',
						сolor: 'black',
						displayColors: false,
						bodyFontSize: 14,
						callbacks: {
						  //label: function(tooltipItems, data) { 
							//return '$' + tooltipItems.formattedValue;
						  //},
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
					}
				  }
				},
				//plugins: [multiply],
			};

			
			fapireq('{!! $employeesStatsUrl !!}', function (dd) {
				var w = $('#salariesChart').width()
				$('#employeesChart').attr('width', w)
				window.chart2 = new Chart(canvas2, config2);
				dd.data.forEach(function (v, i, vv) {
					//console.log(v, i)
					window.chart2.data.labels.push(v.year)
					window.chart2.data.datasets[0].data.push(v.employees)
				})
				chart2.update()
			})

		</script>
	--}}
	
	<script>
		
		var canvas3 = document.getElementById("positionsChart");

		var config3 = {
		  type: 'pie',
		  data: {
			  labels: [],
			  datasets: [{
				label: 'My First Dataset',
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
						pie_label_on(elements[0].index)
					} else {
						pie_labels_off()
					}
				},
				plugins: {
				  legend: {
					display: false,
				  },
				  tooltip: {
					enabled: false,
				  },
				  
				},
			}
		}

		function pie_labels_off() {
			$('#pie_legend li').removeAttr('class')
		}
		
		function pie_label_on(i) {
			pie_labels_off()
			$(`#pie_legend li[idx=${i}]`).attr('class', 'pie_label_h')
		}
		
		function pie_sectors_off(chart) {
			chart.setActiveElements([{datasetIndex: 1, index: 0}])
			chart.update()
		}
		
		function pie_sector_on(chart, i) {
			pie_sectors_off(chart)
			var dd = [{datasetIndex: 0, index: parseInt(i)}]
			res = chart.setActiveElements(dd);
			chart.update()
		}
		

		fapireq('{!! $positionsStatsUrl !!}', function (dd) {
			//var w = $('#salariesChart').width()
			$('#positionsChart').attr('width', 280)
			var pubdate = ''
			var s = 0
			if (dd.data.length == 0) {
				$('#pie_legend').replaceWith('<p class="my-4 mx-3">No Positions to Display</p>')
				return
			}
					
			dd.data.forEach(function (v, i, vv) {
				if (!pubdate)
					pubdate = v.date
				if (pubdate == v.date) {
					config3.data.labels.push(v.agency)
					config3.data.datasets[0].data.push(v.positions)
					s += v.positions
				}
			})
			config3.data.labels.forEach(function (l, i, ll) {
				if (i <= 11) {
					var perc = (config3.data.datasets[0].data[i] / s * 100).toFixed(1)
					$(`<li idx="${i}"><i class="bi bi-square-fill" style="color: ${config3.data.datasets[0].backgroundColor[i]};"></i>&nbsp;&nbsp;${l}: ${config3.data.datasets[0].data[i]} (${perc} %)</li>`).appendTo('#pie_legend')
				}
			})
			if (config3.data.labels.length > 11) {
				$('<li>...</li>').appendTo('#pie_legend')
			}			
			window.chart3 = new Chart(canvas3, config3)

			$('#pie_legend li').mouseover(function (evt) {
				var i = $(this).attr('idx')
				pie_sectors_off(window.chart3)
				pie_sector_on(window.chart3, i)
			}).mouseout(function (evt) {
				var i = $(this).attr('idx')
				pie_sectors_off(window.chart3)
			})
		})
		
	</script>

			<div class="db-tabs-wrap org_headermenu">
				<nav class="db-tabs submenu_org" aria-label="Title sections">
					@foreach ($menu as $h=>$sect)
						@if (is_string($sect))
							<a class="db-tab @if ($active == $sect) is-active @endif" href="{{ route('titleSection', ['id' => $id, 'tslug' => Str::slug($titles[0]['Title Description'], '-'), 'section' => $sect]) }}">{{ $slist[$sect] }}</a>
						@else
							<div class="db-tab-dd">
								<button type="button" class="db-tab @if (($activeDropDown ?? '') == $h) is-active @endif" data-dd aria-haspopup="true" aria-expanded="false" aria-controls="titledd-{{ $loop->index }}">
									{{ $h }} <i class="bi bi-chevron-down db-caret"></i>
								</button>
								<div class="db-tab-menu" id="titledd-{{ $loop->index }}" role="menu">
									@foreach ($sect as $subsect)
										<a role="menuitem" class="@if ($active == $subsect) is-active @endif" href="{{ route('titleSection', ['id' => $id, 'tslug' => Str::slug($titles[0]['Title Description'], '-'), 'section' => $subsect]) }}">{{ $slist[$subsect] }}</a>
									@endforeach
								</div>
							</div>
						@endif
					@endforeach
				</nav>
			</div>
		</div>
	</div>
</div>



