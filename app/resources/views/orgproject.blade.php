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
				<div class="col-md-12 col-sm-12 pr-0">
					<div class="mb-3 mt-4">
						<div class="row mx-0 my-2">
							<div class="col-3">
								<small class="text-muted">Project ID</small><br />
								<h6 id="PRJ_ID"></h6>
							</div>
							<div class="col-3">
								<small class="text-muted">MA Project ID</small><br />
								<h6 id="MA_PRJ_ID"></h6>
							</div>
							<div class="col-3">
								<small class="text-muted">Category</small><br />
								<h6 id="CATEGORY"></h6>
							</div>
							<div class="col-3">
								<small class="text-muted">Type</small><br />
								<h6 id="PRJ_TYPE"></h6>
							</div>
						</div>
					</div>
				</div>
			</div>
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data py-0">
					<h1 class="mb-3">{{ $data['name'] }}</h1>
				</div>
			</div>

			<div class="row justify-content-center">
				<div id="capproject_profile" class="col-md-12 col-sm-12 pr-0">
					<div class="project-bckgnd mb-4">
						<div class="row mx-0 my-2">
							<div class="col">
								<small class="text-muted">Current Phase</small><br />
								<h6 id="CURRENT_PHASE"></h6>
							</div>
							<div class="col">
								<small class="text-muted">Phase Start</small><br />
								<h6 id="PHASE_START"></h6>
							</div>
							<div class="col">
								<small class="text-muted">Phase End</small><br />
								<h6 id="PHASE_END"></h6>
							</div>
							<div class="col">
								<small class="text-muted">Min Date</small><br />
								<h6 id="MIN_DATE"></h6>
							</div>
							<div class="col">
								<small class="text-muted">Max Date</small><br />
								<h6 id="MAX_DATE"></h6>
							</div>
						</div>
						<div class="row mx-0 my-2">
							<div class="col">
								<small class="text-muted">Managing Agency</small><br />
								<h6 id="MANAGING_AGENCY"></h6>
							</div>
							<div class="col">
								<small class="text-muted">Sponsor Agency</small><br />
								<h6 id="SPONSOR_AGENCY"></h6>
							</div>
							<div class="col">
								<small class="text-muted">Budget Lines</small><br />
								<h6 id="BUDGET_LINES"></h6>
							</div>
							<div class="col">
								<small class="text-muted">Type Category</small><br />
								<h6 id="TYPECATEGORY"></h6>
							</div>
							<div class="col">
								<small class="text-muted">CCP Version</small><br />
								<h6 id="CCPVERSION"></h6>
							</div>
						</div>
					</div>
				</div>
			</div>

			<div class="row justify-content-center">
				<div id="capproject_profile" class="col-md-8 col-sm-12">
					<div class="project-bckgnd mb-4">
						<div class="row justify-content-center">
							<div class="col-md-6 col-sm-6 mt-2">
								<h3>Forecasts</h3>
							</div>							
							<div class="col-md-6 col-sm-6 organization_data justify-content-center row pr-0">
							</div>
						</div>
						<div class="table-responsive">
							<table width="100%" class="my-2">
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
									<tr id="end">
										<th scope="row">Project Completion</th>
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
						</div>
					</div>

					<div class="project-bckgnd mb-4">
						<div class="row justify-content-center">
							<div class="col-8 mb-3 text-left">
								<h4 class="mb-2">Agency Project Schedule</h4>
							</div>
							<div class="col-4 mb-3 text-right">
								<h6 id="repdate"></h6>
							</div>
						</div>
						<div class="row justify-content-center">
							<div class="col-12 mb-3" id="costChartOuter">
								<canvas id="budgetsAndScheduleChart" height="200" style="width:100%; height:200px;"></canvas>
							</div>
						</div>

						<div class="row justify-content-center">
							<div class="col-12 mb-3">
								<h4>Project Schedule History</h4>
								<div class="table-responsive mb-3">
									<table width="100%" class="db-table mb-2 mt-0" id="scheduleHistoryDataTable">
										<thead>
											<tr>
												<th scope="col">Period</th>
												<th scope="col">Current Phase</th>
												<th scope="col">Completion Date Forecast</th>
												<th scope="col">Variance (day)</th>
												<th scope="col">Reason for Forecast Completion Change</th>
												<th scope="col">Managing Agency Name</th>
												<th scope="col">Data as of</th>
											</tr>
										</thead>
										<tbody>
										</tbody>
									</table>
								</div>
							</div>
						</div>
					</div>


					<div class="project-bckgnd mb-4">

						<div class="row justify-content-center">
							<div class="col-12 mb-4">
								<h4 class="my-2">Budget & Spending</h4>
								<div id="budgets" class="row mx-0 my-2">
									<div class="col-2">
										<small class="text-muted">Planned</small><br />
										<h6 class="planned"></h6>
									</div>
									<div class="col-2">
										<small class="text-muted">Adopted</small><br />
										<h6 class="adopted"></h6>
									</div>
									<div class="col-2">
										<small class="text-muted">Allocated</small><br />
										<h6 class="allocated"></h6>
									</div>
									<div class="col-2">
										<small class="text-muted">Commited</small><br />
										<h6 class="commited"></h6>
									</div>
									<div class="col-2">
										<small class="text-muted">Spent</small><br />
										<h6 class="spent"></h6>
									</div>
									<div class="col-2">
										<small class="text-muted">Checkbook</small><br />
										<h6 class="checkbook"></h6>
									</div>
								</div>
							</div>
						</div>

						<div class="row justify-content-center">
							<div class="col-12 my-5" id="budgChartOuter">
							{{-- <h4 class="mb-2">Budget Over Time</h4> --}}
								<canvas id="budgPlanChart" height="200" style="width:100%; height:200px;"></canvas>
							</div>
						</div>

						<div class="row justify-content-center">
							<div class="col-12 mb-3">
								<h4 class="mb-2 mt-3">History</h4>
								<div class="table-responsive mb-3">
									<table width="100%" class="db-table mb-2 mt-0" id="budgetSpendHistoryDataTable">
										<thead>
											<tr>
												<th scope="col">Year-Month Reported</th>
												<th scope="col">Total Budget</th>
												<th scope="col">Budget Variance</th>
												<th scope="col">Budget Variance %</th>
												<th scope="col">Spend to Date</th>
												<th scope="col">Spend to Date %</th>
											</tr>
										</thead>
										<tbody>
										</tbody>
									</table>
								</div>
							</div>
						</div>

						<div class="row justify-content-center">
							<div class="col-12 mb-4">
								<h4 class="mb-2 mt-3">Funding Source</h4>
								<div class="table-responsive mb-4">
									<table width="100%" class="db-table mb-2 mt-0" id="priorCostDataTable">
										<thead>
											<tr>
												<th scope="col">Fiscal Year</th>
												<th scope="col">Total Budget (City + Non City)</th>
												<th scope="col">City</th>
												<th scope="col">Non City</th>
												<th scope="col">Spend</th>
											</tr>
										</thead>
										<tbody>
										</tbody>
									</table>
								</div>
							</div>
						</div>
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
											<la	bel class="custom-control-label" for="sa-switch">State Assembly Dist...<hr class="border-sample"></label>
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
										<b>{{ $d }}</b>
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

			
			<div class="row justify-content-center">
				<div id="capproject_profile" class="col-md-12 col-sm-12 pr-0">
					<div class="project-bckgnd mb-5">

						<h4>Commitments</h4>
						<div class="table-responsive mb-4">
							<table width="100%" class="db-table mb-2 mt-0" id="commitments">
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
					</div>


					<div class="my-3">
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
	
	{{-- <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script> --}}
	<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>

	
	<script>
		var chartData = null

		function showPrj() {
			var dd={!! json_encode($data['profile']) !!}
			for (k in dd) {
				if (dd.hasOwnProperty(k) && (k[0] == '#'))
					$(k).html(dd[k])
			}
			var timeline = $('#project_timeline tbody')
			timeline.html('')
			initPopovers();
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

			showPrj();
			
			// *** 327 **
			fapireq("{!! $urls['schedulehistory'] !!}", function (resp) {
				
				if (!resp.data.length) {
					$('#scheduleHistoryDataTable').replaceWith('<div height="100" style="width:100%; height:100px; text-align: center; padding-top: 40px;">No data available</div>');
					return;
				}
				
				data = resp.data
				
				datatable = $('#scheduleHistoryDataTable').DataTable({
					data: data,
					sort: false,
					deferRender: true,
					dom: 'rt',
					columns: [
						{data: function (r) { return String(r['Reporting Period']).substr(4,2) + '/' + String(r['Reporting Period']).substr(0,4); }},	
						{data: 'Current Phase'},
						{data: function (r) { return r['Completion Date'] + ((r['Completion Date']) ? (' (' + r['Completion Date Type'] + ')') : ''); }},
						{data: 'Variance (day)'},
						{data: 'Reason for Forecast Completion Change'},
						{data: 'Managing Agency'},
						{data: 'Data Date'},
					],
				});
			});
				
				
			// *** 244 ** Agency Project Schedule   diagram
			fapireq("{!! $urls['budgetsandschedule'] !!}", function (resp) {
				if (!resp.data.length) {
					$('#budgetsAndScheduleChart').replaceWith('<div height="100" style="width:100%; height:100px; text-align: center; padding-top: 40px;">No data available</div>');
					return;
				}
				
				const cc = ['25, 100, 126', '40, 175, 176', '244, 211, 94', '238, 150, 75', '19, 111, 99', '224, 202, 60', '243, 66, 19', '62, 47, 91', '0, 15, 8'];
				
				// Find max reporting period
				var maxRepDate = resp.data.reduce(function(a, b) {
					return (a['Reporting Period'] > b['Reporting Period']) ? a : b;
				})['Reporting Period'];

				// Filter data by max reporting period
				var filteredData = resp.data.filter(function(d) {
					return d['Reporting Period'] == maxRepDate;
				});

				dd = filteredData.reduce(
						function(acc, v) {
							acc.phases.push({
								'Phase': 		v['Current Phase'],
								'Start': 		usToDashDateNowrap(v['Current Phase Start']),
								'End': 			usToDashDateNowrap(v['Forecast Current Phase End']),
								//'Completion': 	(v['Forecast Completion']) ? usToDashDateNowrap(v['Forecast Completion']) : '',
								//'Design Start':   (v['Actual Design Start']) ? (v['Actual Design Start']) : ''
							});
							acc.min = (usToDashDateNowrap(v['Current Phase Start']) < acc.min) ? usToDashDateNowrap(v['Current Phase Start']) : acc.min;
							if (v['Actual Design Start']) {
								acc.overall[0] = ((acc.overall[0] ?? '2125-01-01') < usToDashDateNowrap(v['Actual Design Start'])) ? (acc.overall[0] ?? '2125-01-01') : usToDashDateNowrap(v['Actual Design Start']);
								acc.min = (acc.overall[0] < acc.min) ? acc.overall[0] : acc.min;
							}
							acc.repdate = (v['Reporting Period'] > acc.repdate) ? v['Reporting Period'] : acc.repdate;
							console.log(v, acc.repdate)
							if (v['Forecast Completion'])
								acc.overall[1] = ((acc.overall[1] ?? '1970-01-01') > usToDashDateNowrap(v['Forecast Completion'])) ? (acc.overall[1] ?? '1970-01-01')  : usToDashDateNowrap(v['Forecast Completion']);
							return acc;
						},
						{phases: [], overall: [null, null], min: '2125-01-01', repdate: '197001'}
					);
				if (dd.overall[0] && dd.overall[1])
					dd.phases.unshift({
						'Phase': 'Overall',
						'Start': dd.overall[0],
						'End': 	 dd.overall[1],
					});
				//console.log('budgetsandschedule', dd);
				const mindate = (dd.min == '2125-01-01') ? (new Date()).toISOString().split('T')[0] : dd.min;
				mm = {'01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec', }
				
				//console.log(dd.repdate);
				const repdate = mm[String(dd.repdate).substr(4, 2)] +' '+ String(dd.repdate).substr(0, 4)
				$('#repdate').text('Reporting Period: '+repdate)
				var data = dd.phases.reduce(
						function(acc, v) {
							i = acc.labels.length
							acc.labels.push(v['Phase']);
							acc.datasets[0].data.push([v['Start'], v['End']]);
							acc.datasets[0].backgroundColor.push((v['Phase'] == 'Overall') ? 'rgba(31, 39, 27, 0.2)' : 'rgba(' + cc[i] + ', 0.2)');
							acc.datasets[0].borderColor.push((v['Phase'] == 'Overall') ? 'rgba(31, 39, 27, 1)' : 'rgba(' + cc[i] + ', 1)');
							acc.datasets[0].dataCustomLabels.push([v['Phase'], dashToUsDate(v['Start']), dashToUsDate(v['End'])]);
							return acc;
						},
						{
						  labels: [],
						  datasets: [{
							label: null,
							data: [],
							dataLabels: [],
							backgroundColor: [],
							borderColor: [],
							barPercentage: 0.8,
							borderWidth: 1,
							borderRadius: 2,
							borderSkipped: false,
							dataCustomLabels: [],
						  }]
						}
					);
				//console.log('budgetsandschedule data', data);

				var canvas = document.getElementById("budgetsAndScheduleChart");
				var config = {
					type: 'bar',
					data: data,
					options: {
						plugins: {
						  tooltip: {
							displayColors: false,
							padding:12,
							bodyColor: '#222',
							cornerRadius: 3,
							//position: 'average',
							backgroundColor: 'rgba(254, 254, 254, 0.7)',
							borderColor: 'rgba(0, 0, 0, 0.4)',
							borderWidth: 1,
							callbacks: {
							  title: (context) => {
								  return '';
							  },
							  label: function (context) {
								  //console.log(context);
								  return [	'Task: ' + context.dataset.dataCustomLabels[context.dataIndex][0],
											'Start Date: ' + context.dataset.dataCustomLabels[context.dataIndex][1], 
											'End Date: ' + context.dataset.dataCustomLabels[context.dataIndex][2],
										]
							  },
							},
						  },
						  datalabels: {
							display: false,
						  },
						  legend: {
							display: false
						  },
						},
						indexAxis: 'y',
						scales: {
						  x: {
							offset: false,
							min: mindate,
							type: 'time',
							time: {
							  unit: 'year',	/* year, month, day, quarter*/
							},
							ticks: {
							  align: 'start',
							},
							grid: {
							  borderDash: [3, 3]
							},
						  },
						  y: {
							beginAtZero: true
						  }
						},
					  },
					plugins: [ChartDataLabels]
				};
				window.chart1 = new Chart(canvas, config);
				

			});
				
				
			// *** 325 **
			fapireq("{!! $urls['budgetandspend'] !!}", function (resp) {
				if (!resp.data.length) {
					$('#priorCostDataTable').replaceWith('<div height="100" style="width:100%; height:100px; text-align: center; padding-top: 40px;">No data available</div>');
					return;
				}

				// Find max reporting period
				var maxRepDate = resp.data.reduce(function(a, b) {
					return (a['Reporting Period'] > b['Reporting Period']) ? a : b;
				})['Reporting Period'];

				// Filter data by max reporting period
				var data = resp.data.filter(function(d) {
					return d['Reporting Period'] == maxRepDate;
				});
			
				
				datatable = $('#priorCostDataTable').DataTable({			
					data: data,
					deferRender: true,
					dom: 'rt',
					columns: [
						{data: 'Fiscal Year'},
						{data: function (r) { return toFin(r['Total Budget City Non City']); }},
						{data: function (r) { return toFin(r['City']); }},
						{data: function (r) { return toFin(r['Non City']); }},
						{data: function (r) { return toFin(r['Spend']); }},
					],
				});
			});


			// *** 326 **
			fapireq("{!! $urls['budgetspendhistory'] !!}", function (resp) {
				if (!resp.data.length) {
					$('#budgPlanChart').replaceWith('<div height="100" style="width:100%; height:100px; text-align: center; padding-top: 40px;">No data available</div>');
					$('#budgetSpendHistoryDataTable').replaceWith('<div height="100" style="width:100%; height:100px; text-align: center; padding-top: 40px;">No data available</div>');
					return;
				}
				
				data = resp.data
				
				var canvas = document.getElementById("budgPlanChart");
				
				var config = {
					type: 'line',
					data: {
						labels: 
							data.reduce(
							  function(acc, v) {acc.push(String(v['Year-Month Reported']).substr(4,2) + '/' + String(v['Year-Month Reported']).substr(0,4)); return acc;},
							  []
							),
						datasets: [
						  {
							  label: 'Total Budget',
							  data: 
								data.reduce(
								  function(acc, v) {acc.push(Number(v['Total Budget'])); return acc;},
								  []
								),
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
							  label: 'Spend to Date',
							  data: 
								data.reduce(
								  function(acc, v) {acc.push(Number(v['Spend to Date'])); return acc;},
								  []
								),
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
				window.chart3 = new Chart(canvas, config);
				
				datatable = $('#budgetSpendHistoryDataTable').DataTable({
					data: data,
					deferRender: true,
					sort: false,
					dom: 'rt',
					columns: [
						{data: function (r) { return String(r['Year-Month Reported']).substr(4,2) + '/' + String(r['Year-Month Reported']).substr(0,4); }},	
						{data: function (r) { return (r['Total Budget']) ? toFin(r['Total Budget']) : ''; }},
						{data: function (r) { return toFin((r['Budget Variance']) ? r['Budget Variance'] : 0); }},
						{data: function (r) { return (parseFloat(r['Budget Variance %']) * 100).toFixed(1) + ((r['Budget Variance %']) ? '%' : ''); }},
						{data: function (r) { return toFin((r['Spend to Date']) ? r['Spend to Date'] : 0); }},
						{data: function (r) { return (parseFloat(r['Spend to Date %']) * 100).toFixed(1) + ((r['Spend to Date %']) ? '%' : ''); }},
					],
				});
			});


			@if ($data['geo_feature'])
				
				const feature = {!! $data['geo_feature'] !!}
				//console.log(feature)
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
							//'line-color': '#53777a',
							'line-color': ['get', 'custom_color'],
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
							//'circle-color': '#53777a'
							'circle-color': ['get', 'custom_color']
						},
						'filter': ['==', '$type', 'Point']
					});

					map.addLayer({
						'id': 'areas',
						'type': 'fill',
						'source': 'route',
						'paint': {
							//'fill-color': '#53777a',
							'fill-color': ['get', 'custom_color'],
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
	


			// *** 240 **
			
			commTable = $('#commitments').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $urls['commitments'] !!}", cb);
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
					{data: function (r) { return toFin(r['plannedcommit_total']); }},
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


