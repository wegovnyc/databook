	<div class="chartCard">
		<ul class="nav nav-tabs mb-2" id="graphs-tab" role="tablist">
		  <li class="nav-item" role="presentation">
			<a class="nav-link active" id="headcount-tab" data-bs-toggle="pill" href="#pills-headcount" role="tab" aria-controls="pills-headcount" aria-selected="true">Position Schedule</a>
		  </li>
		</ul>
		<div class="tab-content" id="pills-tabContent">
		  <div class="tab-pane fade show active" id="pills-headcount" role="tabpanel" aria-labelledby="headcount-tab">
			<div id="pos-header" class="org-header row">
			    <div class="col row" id="spending_by_name">
					<div class="col px-0">
					  <h4 class="ml-5">Total Spendings by UA Name</h4>
					  <div height="200" width="400" style="overflow: visible; display: inline-block; vertical-align: top; max-width:330px;">
						<ul id="spending_by_name_legend" class="pie_legend">
						</ul>
					  </div>
				    </div>
				    <div class="col px-0">
					  <div height="200" width="285" style="overflow: visible; display: inline-block; vertical-align: top;">
						  <canvas id="nameSpendingChart" height="200" width="285" style="width:100%; height:200px;"></canvas>
					  </div>
				    </div>
			    </div>
			    <div class="col row px-0" id="spending_by_title">
					<div class="col px-0">
					  <h4 class="ml-5">Total Spendings by Title Code</h4>
					  <div height="200" width="400" style="overflow: visible; display: inline-block; vertical-align: top; max-width:480px;">
						<ul id="spending_by_title_legend" class="pie_legend">
						</ul>
					  </div>
					</div>
					<div class="col px-0">
					  <div height="200" width="285" style="overflow: visible; display: inline-block; vertical-align: top;">
						  <canvas id="titleSpendingChart" height="200" width="285" style="width:100%; height:200px;"></canvas>
					  </div>
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
		function pubDateFilterChange() {}

		function pie_labels_off() {
			$('.pie_legend li').removeClass('pie_label_h')
		}
		
		function pie_label_on(i, sel) {
			pie_labels_off()
			$(`${sel} .pie_legend li[idx=${i}]`).addClass('pie_label_h')
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
		

		var config1 = {
		  type: 'pie',
		  data: {
			  labels: [],
			  datasets: [{
				label: 'spending_by_name',
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
						pie_label_on(elements[0].index, '#spending_by_name')
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
				  }
				  
				},
			}
		}

		var config2 = {
		  type: 'pie',
		  data: {
			  labels: [],
			  datasets: [{
				label: 'spending_by_title',
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
						pie_label_on(elements[0].index, '#spending_by_title')
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
				  }
				  
				},
			}
		}


		$(document).ready(function() {
			
			var canvas1 = document.getElementById("nameSpendingChart");
			window.chart1 = new Chart(canvas1, config1)

			var canvas2 = document.getElementById("titleSpendingChart");
			window.chart2 = new Chart(canvas2, config2)
			
			datatable.on('draw.dt', function () {
				setTimeout(function(){
					graphsUpdate()
				}, 1000);
			})

		})


		function graphsUpdate() {
			const vv = datatable.rows('', {search: 'applied'}).data()
			
			var tmprr = vv.reduce( function (a, b) {
					s = parseInt(b['ANNUAL RATE'])
					a['by_uaname'][b['UA NAME']] = 
						(a['by_uaname'][b['UA NAME']] ?? null) 
							? a['by_uaname'][b['UA NAME']] + s 
							: s
					a['by_titlecode'][b['TITLE CODE NAME']] = 
						(a['by_titlecode'][b['TITLE CODE NAME']] ?? null) 
							? a['by_titlecode'][b['TITLE CODE NAME']] + s 
							: s
					return a
				}, {'by_uaname': {}, 'by_titlecode': {}})
				
			var rr = {}
			for (var k in tmprr) {
				let sortable = []
				for (var f in tmprr[k]) {
					sortable.push([f, tmprr[k][f]]);
				}
				rr[k] = sortable.sort((a,b) => b[1] - a[1])
			}
			/*
				console.log(rr)
				{"by_uaname": [["PERSONAL SERVICES",290776325],["ADMINISTRATIVE-PS",89153960],...],			// 5
				 "by_titlecode": [["CHILD PROTECTIVE SPECIALIST",112622321],["CHILD PROTECTIVE SPECIALIST SUPERVISOR",42968616],...]   // 145
				}
			*/
				
			pieUpd(window.chart1, config1, '#spending_by_name', rr['by_uaname'])
			pieUpd(window.chart2, config2, '#spending_by_title', rr['by_titlecode'])
		}

		
		function pieUpd(chart, conf, sel, dd) {
			$(sel + ' canvas').attr('width', 280)
			var s = 0
			if (dd.length == 0) {
				$(sel + ' .pie_legend').replaceWith('<p class="my-4 mx-3">No Positions to Display</p>')
				return
			}
			conf.data.labels = []
			conf.data.datasets[0].data = []
			$(sel + ' .pie_legend').html('')
			dd.forEach(function (d, i, vv) {
				conf.data.labels.push(d[0])
				conf.data.datasets[0].data.push(d[1])
				s += d[1]
			})
			conf.data.labels.forEach(function (l, i, ll) {
				if (i <= 11) {
					var perc = (conf.data.datasets[0].data[i] / s * 100).toFixed(1)
					$(`<li idx="${i}" class="cut-text"><i class="bi bi-square-fill" style="color: ${conf.data.datasets[0].backgroundColor[i]};"></i>&nbsp;&nbsp;${l}: ${toFin(conf.data.datasets[0].data[i])} (${perc} %)</li>`).appendTo(sel + ' .pie_legend')
				}
			})
			if (conf.data.labels.length > 11) {
				$('<li>...</li>').appendTo(sel + ' .pie_legend')
			}			
			chart.update()

			$(sel + ' .pie_legend li').mouseover(function (evt) {
				var i = $(this).attr('idx')
				pie_sectors_off(chart)
				pie_sector_on(chart, i)
			}).mouseout(function (evt) {
				var i = $(this).attr('idx')
				pie_sectors_off(chart)
			})

		}
	</script>
