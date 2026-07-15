@extends('layout')


@section('head')
	<meta name="description" content="{{ $snippet }}" />
	<meta rel="canonical" href="{!! $canonicalUrl !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	@include('sub.orgheader', ['active' => $section])
	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data">
					<div class="alert alert-primary mr-0" role="alert">
						<strong><i class="bi bi-exclamation-circle-fill ml-0 pb-1 mr-2" style="top:0;position:relative;font-size:1.25rem;"></i></strong>
						This is the pre-2024 version of the capital profile. To see the latest version of the capital project <a href="{!! route('project', ['prjId' => $data['items']['20231026']['#PROJECT_ID'], 'prjslug' => Str::slug($data['name'])]) !!}" class="alert-link">go here</a>
					</div>
				</div>
			</div>
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data py-0">
					<h1>{{ $data['name'] }} <small>(<span id="PROJECT_ID"></span>)</small></h1>
				</div>
			</div>

			<div class="row justify-content-center">
				<div id="capproject_profile" class="col-md-8 col-sm-12">
					<div class="project-bckgnd mb-5">
						<div class="row justify-content-center">
							<div class="col-md-6 col-sm-6 mt-4">
								<h3>Details</h3>
							</div>
							
							<div class="col-md-6 col-sm-6 organization_data justify-content-center row pr-0">
								<div class="col">
									<h5 class="mt-2" data-content="See the project info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1 pb-1" style="top:-1px;position:relative;"></i></small></h5>
								</div>
								<div class="col">
									<select id="pub_date_filter" style="width:100%;" class="filter" onchange="showPrj();">
										@foreach ($data['items'] as $date=>$row)
											<option value="{{ $date }}" @if($date == array_keys($data['items'])[0]) selected @endif>{{ $row['PUB_DATE_F'] }}</option>
										@endforeach
									</select>
								</div>
							</div>
						</div>
					
						<div class="table-responsive">
							<table width="100%" class="mb-5">
								<thead>
									<tr>
										<th scope="col">Summary</th>
										<th scope="col">Original</th>
										<th scope="col">Current</th>
										<th scope="col">Change (#)</th>
									</tr>
								</thead>
								<tbody>
									<tr id="budget">
										<th scope="row">Budget</th>
										<td class="original"></td>
										<td class="current"></td>
										<td class="difference"></td>
									</tr>
									<tr id="start">
										<th scope="row">Start</th>
										<td class="original"></td>
										<td class="current"></td>
										<td class="difference"></td>
									</tr>
									<tr id="end">
										<th scope="row">End</th>
										<td class="original"></td>
										<td class="current"></td>
										<td class="difference"></td>
									</tr>
									<tr id="duration">
										<th scope="row">Duration</th>
										<td class="original"></td>
										<td class="current"></td>
										<td class="difference"></td>
									</tr>
								</tbody>
							</table>
							<table width="100%" class="mb-5" id="project_details">
								<tbody>
								{{--<tr>
										<th scope="row">Project ID</th>
										<td id="PROJECT_ID"></td>
									</tr>
								--}}
									<tr>
										<th scope="row">Borough</th>
										<td id="BORO"></td>
									</tr>
									<tr>
										<th scope="row">Managed By</th>
										<td id="MANAGING_AGCY"></td>
									</tr>
									<tr>
										<th scope="row">Project Type</th>
										<td id="PRJ_TYPE"></td>
									</tr>
									<tr>
										<th scope="row">10-year Plan Category</th>
										<td id="TYP_CATEGORY_NAME"></td>
									</tr>
									<tr>
										<th scope="row">Budget Lines</th>
										<td id="BUDGET_LINE"></td>
									</tr>
									<tr>
										<th scope="row">Community Districts Served</th>
										<td id="COMMUNITY_BOARD"></td>
									</tr>
									<tr>
										<th scope="row">Explanation for Delay</th>
										<td id="DELAY_DESC"></td>
									</tr>
									<tr>
										<th scope="row">Scope Summary</th>
										<td id="SCOPE_TEXT"></td>
									</tr>
									<tr>
										<th scope="row">Site Description</th>
										<td id="SITE_DESCR"></td>
									</tr>
									<tr>
										<th scope="row">City Prior Spending</th>
										<td id="CITY_PRIOR_ACTUAL"></td>
									</tr>
									<tr>
										<th scope="row">Non City Prior Spending</th>
										<td id="NONCITY_PRIOR_ACTUAL"></td>
									</tr>

								</tbody>
							</table>
						</div>

						<h4 class="project_timeline" style="display: none;">Milestones</h4>
						<div class="table-responsive mb-5">
							<table width="100%" id="project_timeline" style="display: none;">
								<thead>
									<tr>
										<th scope="col">Phase</th>
										<th scope="col">Original</th>
										<th scope="col">Current</th>
										<th scope="col">Change</th>
									</tr>
								</thead>
								<tbody>
								</tbody>
							</table>
						</div>

						<div class="col-12 mb-3" id="costChartOuter">
							<p style="float: right;">* <i>All numbers are in the chart are thousands.</i></p>
							<h4 class="mb-2">Next 5 Years of Spending</h4>
							<canvas id="futureSpendingChart" height="200" style="width:100%; height:200px;"></canvas>
						</div>


					</div>
					
					<div class="col-12 mb-5" id="priorChartOuter">
						<p style="float: right;">* <i>All numbers are in the chart are thousands.</i></p>
						<h4 class="mb-2">Prior Spending</h4>
						<canvas id="priorCostChart" height="200" style="width:100%; height:200px;"></canvas>
					</div>

					<div class="col-12 mb-5" id="budgChartOuter">
						<p style="float: right;">* <i>All numbers are in the chart are thousands.</i></p>
						<h4 class="mb-2">Budget Over Time</h4>
						<canvas id="budgPlanChart" height="200" style="width:100%; height:200px;"></canvas>
					</div>


					<h4>Additional Project Information</h4>
					<div class="table-responsive mb-5">
						<table width="100%" class="mb-2 mt-0" id="project_data">
							<thead>
								<tr>
									<th scope="col"></th>
									<th scope="col">Description</th>
									<th scope="col">Total City Planned Commit</th>
									<th scope="col">Max Date</th>
									<th scope="col">Min Date</th>
									<th scope="col">Managing Agency Name</th>
								</tr>
							</thead>
							<tbody>
							</tbody>
						</table>
					</div>


					<h4>Commitments</h4>
					<div class="table-responsive mb-5">
						<table width="100%" class="mb-2 mt-0" id="commitments">
							<thead>
								<tr>
									<th scope="col"></th>
									<th scope="col">Description</th>
									<th scope="col">Date</th>
									<th scope="col">Commitment Description</th>
									<th scope="col">Commitment Type</th>
									<th scope="col">Total Planned Commit</th>
								</tr>
							</thead>
							<tbody>
							</tbody>
						</table>
					</div>



					<div class="my-3">
{{-- 
{{-- 
						<div id="disqus_thread"></div>
						<script>
							/**
							*  RECOMMENDED CONFIGURATION VARIABLES: EDIT AND UNCOMMENT THE SECTION BELOW TO INSERT DYNAMIC VALUES FROM YOUR PLATFORM OR CMS.
							*  LEARN WHY DEFINING THESE VARIABLES IS IMPORTANT: https://disqus.com/admin/universalcode/#configuration-variables    */
							
							var disqus_config = function () {
							this.page.url = '{!! $canonicalUrl !!}';  // Replace PAGE_URL with your page's canonical URL variable
							this.page.identifier = '{{ $prjId }}'; // Replace PAGE_IDENTIFIER with your page's unique identifier variable
							};
							
							(function() { // DON'T EDIT BELOW THIS LINE
							var d = document, s = d.createElement('script');
							s.src = 'https://databook-wegov-nyc.disqus.com/embed.js';
							s.setAttribute('data-timestamp', +new Date());
							(d.head || d.body).appendChild(s);
							})();
						</script>
						<noscript>Please enable JavaScript to view the <a href="https://disqus.com/?ref_noscript" rel="nofollow">comments powered by Disqus.</a></noscript>				
 --}}
 --}}
					</div>
				</div>

				<div class="col-md-4 col-sm-12 p-0">
					<div id="map_container" style="float:none;">
						<!-- toggles -->
						<div class="select_district" id="toggles" style="top:5px; left:0px; display:none;">
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
						<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;border:2px solid #112F4E;"></div>
					</div>
					<p class="mt-4">
						<i class="bi-geo-alt" style="font-weight: 600; font-size: 1.25rem;"></i>&nbsp;&nbsp;Our map uses data from <a href="https://data.cityofnewyork.us/City-Government/Capital-Projects-Database-CPDB-Projects-Polygons-/9jkp-n57r/" target="_blank">Capital&nbsp;Projects Database (CPDB) - Projects (Polygons)</a>, <a href="https://data.cityofnewyork.us/City-Government/Capital-Projects-Database-CPDB-Projects-Points-/h2ic-zdws/" target="_blank">Capital&nbsp;Projects Database (CPDB) - Projects (Points)</a> datasets.
					</p>
					<p class="suggest_button mt-4"><a href="https://airtable.com/shrWWa3rNJFGSFObd?prefill_project_id={{ $prjId }}" class="learn_more" target="_blank" rel="nofollow">Suggest a Change</a></p>
					@if ($data['cLog'])
						<div class="my-3">
							<h4>Change Log</h4>
							<ul style="list-style-type: none; padding-inline-start: 20px;">
								@foreach ($data['cLog'] as $d=>$ll)
									<li>
										<b>{{ implode('/', [substr($d, 4, 2), substr($d, 6, 2), substr($d, 0, 4)]) }}</b>
										<ul>
										@foreach ($ll as $l)
											<li data-content="{{ $l[1] }}">
											{!! $l[0] !!}
											</li>
										@endforeach
									</ul></li>
								@endforeach
							</ul>
						</div>
					@endif
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
									<strong>Data Sources:</strong> this page is using data from the <span id="total_datasets"></span> data sources consisting of <span id="total_records"></span> records. Click here to see the data sources.
								</button>
							</div>
							<div id="collapseThree" class="collapse hide" aria-labelledby="headingOne" data-parent="#accordionThree">
								<div class="card-text table-responsive">
									<table id="dsStatsTable" class="display table-hover table-borderless" style="width:100%;">
									</table>
								</div>
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
		var chartData = null

		function showPrj() {
			var data={!! json_encode($data['items']) !!}
			var pub_date = $('#pub_date_filter option:selected').val()
			var dd = data[pub_date]
			for (k in dd) {
				if (dd.hasOwnProperty(k) && (k[0] == '#'))
					$(k).html(dd[k])
			}
			var timeline = $('#project_timeline tbody')
			timeline.html('')
			dd['milestones'].forEach(function (m) {
				timeline.append(`<tr><th scope="row">${m['TASK_DESCRIPTION']}</th><td class="original">${m['ORIG_DATE_F']}</td><td class="current">${m['CURR_DATE_F']}</td><td class="difference">${m['DATE_DIFF']}</td></tr>`)
				$('.project_timeline, #project_timeline').show()
			})
			initPopovers();
			
			//window.chart1.data.labels = []
			window.chart1.data.datasets[0].data = []
			window.chart1.data.datasets[1].data = []
			dd['costChartData'].forEach(function (v, i, vv) {
				//console.log(v, i)
				//window.chart1.data.labels.push(v[0])
				window.chart1.data.datasets[0].data.push(v[1])
				window.chart1.data.datasets[1].data.push(v[2])
			})
			window.chart1.update()
		}

		function details(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
				(d["maprojid"] 		? '<tr><td>Mapped Project ID:</td><td>'+d["maprojid"]+'</td></tr>' : '') +
				(d["ccnonexempt"] 	? '<tr><td>City Nonexempt:</td><td>'+toFin(d["ccnonexempt"])+'</td></tr>' : '') +
				(d["ccexempt"] 		? '<tr><td>City Exempt:</td><td>'+toFin(d["ccexempt"])+'</td></tr>' : '') +
				(d["nccstate"] 		? '<tr><td>State Cost:</td><td>'+toFin(d["nccstate"])+'</td></tr>' : '') +
				(d["nccfederal"] 	? '<tr><td>Federal Cost:</td><td>'+toFin(d["nccfederal"])+'</td></tr>' : '') +
				(d["nccother"] 		? '<tr><td>Other Cost:</td><td>'+toFin(d["nccother"])+'</td></tr>' : '') +
				(d["totalnoncityplannedcommit"] ? '<tr><td>Total Noncity Planned:</td><td>'+toFin(d["totalnoncityplannedcommit"])+'</td></tr>' : '') +
				(d["totalspend"] 	? '<tr><td>Total Spend:</td><td>'+toFin(d["totalspend"])+'</td></tr>' : '') +
				(d["typecategory"] 	? '<tr><td>Type Category:</td><td>'+d["typecategory"]+'</td></tr>' : '') +
				(d["ccpversion"] 	? '<tr><td>Version:</td><td>'+d["ccpversion"]+'</td></tr>' : '') +
			'</table>';
		}


		function commDetails(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
				(d["maprojid"] 		? '<tr><td>Enhanced Project ID:</td><td>'+d["maprojid"]+'</td></tr>' : '') +
				(d["wegov-prjtype-name"] ? '<tr><td>Project Type:</td><td>'+d["wegov-prjtype-name"]+'</td></tr>' : '') +
				(d["wegov-org-name"] ? '<tr><td>Managing Agency:</td><td><a href="/organization/' +d["wegov-org-id"]+ '">'+d["wegov-org-name"]+'</a></td></tr>' : '') +
				(d["typc"] 			? '<tr><td>Type Code:</td><td>'+d["typc"]+'</td></tr>' : '') +
				(d["typcname"] 		? '<tr><td>Type Code Name:</td><td>'+d["typcname"]+'</td></tr>' : '') +
				(d["ccnonexempt"] 	? '<tr><td>City Nonexempt:</td><td>'+toFin(d["ccnonexempt"])+'</td></tr>' : '') +
				(d["ccexempt"] 		? '<tr><td>City Exempt:</td><td>'+toFin(d["ccexempt"])+'</td></tr>' : '') +
				(d["totalcityplannedcommit"] ? '<tr><td>Total City Planned:</td><td>'+toFin(d["totalcityplannedcommit"])+'</td></tr>' : '') +
				(d["nccstate"] 		? '<tr><td>State Cost:</td><td>'+toFin(d["nccstate"])+'</td></tr>' : '') +
				(d["nccfederal"] 	? '<tr><td>Federal Cost:</td><td>'+toFin(d["nccfederal"])+'</td></tr>' : '') +
				(d["nccother"] 		? '<tr><td>Other Cost:</td><td>'+toFin(d["nccother"])+'</td></tr>' : '') +
				(d["totalnoncityplannedcommit"] ? '<tr><td>Total Noncity Planned:</td><td>'+toFin(d["totalnoncityplannedcommit"])+'</td></tr>' : '') +
				//(d["totalplannedcommit"] ? '<tr><td>Total Planned:</td><td>'+toFin(d["totalplannedcommit"])+'</td></tr>' : '') +
				(d["sagencyname"] 	? '<tr><td>Agency Name:</td><td>'+d["sagencyname"]+'</td></tr>' : '') +
				(d["ccpversion"] 	? '<tr><td>Version:</td><td>'+d["ccpversion"]+'</td></tr>' : '') +
			'</table>';
		}

	</script>
	

	<script>
		var datatable = null
		var commTable = null
		var datasets = {!! json_encode(array_values($datasets)) !!}
		var dsstats_table = null


		$(document).ready(function () {
			
			var canvas1 = document.getElementById("futureSpendingChart");
			
			var config1 = {
				type: 'line',
				data: {
					labels: ['Y1', 'Y2', 'Y3', 'Y4', 'Y5'],
					datasets: [
					  {
						  label: 'City',
						  data: [],
						  fill: false,
						  borderColor: 'rgba(59, 129, 135, 0.85)',
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
						  label: 'Non City',
						  data: [],
						  fill: false,
						  borderColor: 'rgba(0, 156, 167, 0.77)',
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

			showPrj();


			var canvas2 = document.getElementById("priorCostChart");
			
			var config2 = {
				type: 'line',
				data: {
					labels: ['{!! implode("', '", $data['priorSpendingChartData']['pubdates']) !!}'],
					datasets: [
					  {
						  label: 'City',
						  data: [{!! implode(', ', $data['priorSpendingChartData']['CITY_PRIOR_ACTUAL']) !!}],
						  fill: false,
						  borderColor: 'rgba(59, 129, 135, 0.85)',
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
						  label: 'Non City',
						  data: [{!! implode(', ', $data['priorSpendingChartData']['NONCITY_PRIOR_ACTUAL']) !!}],
						  fill: false,
						  borderColor: 'rgba(0, 156, 167, 0.77)',
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




			var canvas3 = document.getElementById("budgPlanChart");
			
			var config3 = {
				type: 'line',
				data: {
					labels: ['{!! implode("', '", $data['budgPlanChartData']['pubdates']) !!}'],
					datasets: [
					  {
						  label: 'City',
						  data: [{!! implode(', ', $data['budgPlanChartData']['CITY_PLAN_TOTAL']) !!}],
						  fill: false,
						  borderColor: 'rgba(59, 129, 135, 0.85)',
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
						  label: 'Non City',
						  data: [{!! implode(', ', $data['budgPlanChartData']['NONCITY_PLAN_TOTAL']) !!}],
						  fill: false,
						  borderColor: 'rgba(0, 156, 167, 0.77)',
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
			window.chart3 = new Chart(canvas3, config3);


			@if ($data['geo_feature'])
				const feature = {!! $data['geo_feature'] !!}
				var bounds = [[feature.properties.W, feature.properties.S], [feature.properties.E, feature.properties.N]]
				var features = []
				if (feature.geometry.type != 'MultiPolygon') 
					features = [feature]
				else {
					feature.geometry.coordinates.forEach(function (c) {
						var subgj = JSON.parse(JSON.stringify(feature))
						subgj.geometry.type = 'Polygon'
						subgj.geometry.coordinates = c
						features.push(subgj)
					})
				}
			
				mapboxgl.accessToken = 'pk.REPLACE_WITH_YOUR_MAPBOX_TOKEN';

				map = new mapboxgl.Map({
					container: 'map',
					style: 'mapbox://styles/mapbox/light-v10',
					center: [-73.99255747855759,40.58992167435116],
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
			@else
				$('#map').attr('class', 'no-geo');
				$('#map').html('<iframe class="airtable-embed" src="https://airtable.com/embed/shreZusmuYwJNl76Q?prefill_project_id={{ $prjId }}&backgroundColor=blue" frameborder="0" onmousewheel="" width="100%" height="100%" style="background: transparent;"></iframe>');
				$('.suggest_button').remove();
			@endif
			
			$('#toggle_boundries').click( function (e) {
				$(this).next('.dropdown-menu').toggleClass('show');
			})
	

			/****** 241 projects, 213 commitments ***************/
			

			datatable = $('#project_data').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $coreUrl !!}", cb);
			    },
				deferRender: true,
				dom: 'rt',
				columns: [
					{
						"className": 'details-control',
						"orderable": false,
						"data":  null,
						"defaultContent": ''
					},
					{data: 'description'},
					{data: function (r) { return toFin(r['totalcityplannedcommit']); }},
					{data: 'maxdate'},
					{data: 'mindate'},
					{data: 'wegov-org-name'},
                ],

			});

			
			$('#project_data tbody').on('click', 'td.details-control', function () {
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
				}
			});



			commTable = $('#commitments').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $commUrl !!}", cb);
			    },
				deferRender: true,
				dom: '<"toolbar container-flex"<"row">>rt',
				columns: [
					{
						"className": 'details-control',
						"orderable": false,
						"data":  null,
						"defaultContent": ''
					},
					{data: 'projectdescription'},
					{data: 'plancommdate'},
					{data: 'commitmentdescription'},
					{data: 'typcname'},
					//{data: function (r) { return toFin(r['ccnonexempt']); }},
					{data: function (r) { return toFin(r['totalplannedcommit']); }},
                ]
			});


			$('#commitments tbody').on('click', 'td.details-control', function () {
				var tr = $(this).closest('tr');
				var row = commTable.row(tr);

				if (row.child.isShown()) {
					row.child.hide();
					tr.removeClass('shown');
                    tr.next('tr').removeClass('child-row');
				}
				else {
					row.child(commDetails(row.data())).show();
					tr.addClass('shown');
                    tr.next('tr').addClass('child-row');
				}
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
					@foreach($datasets as $tbl=>$ds)
						loadTableStat(
							"{{ $tbl }}", 
							"{!! str_replace('tblname', $tbl, $tblStatsUrl) !!}"
						);
					@endforeach
				}
			});
			
		})
	

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
	
	<script type="application/ld+json">{!! json_encode($schema) !!}</script>
<style>
	#map_container #map {height: 800px !important;}
	.badge a {color: #fff; }
	.badge-bl {font-size: .95rem; font-weight: 500; line-height: 1.2; background-color: #005EA2;}
	.badge-cd {font-size: .95rem; font-weight: 500; line-height: 1.2; background-color: #71c4d0;}
	.project-bckgnd {padding:12px; border: 1px dotted black;}
</style>
@endsection


