@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects - Open Data Driven Profiles by NYC Databook." />
	<meta rel="canonical" href="{!! route('capital') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')


<div class="inner_container">

	<div class="container">
		<div class="row my-4">
			<div class="col-md-12">
				<h1>New York City’s Capital Program</h1>
				<p class="lead">Our city’s infrastructure – its roads, sewers, parks and schools – is funded and managed through the city’s capital program. This website uses NYC Open Data to explore the capital program’s four phases: Strategy, Budget, Commitments and Projects.</p>

			</div>
		</div>	
		
		<div class="row mb-4">
			<div class="col-4">
				<h2>Strategy</h2>
				<p class="lead">The Mayor’s Office of Management & Budget (OMB) updates a <a href="https://data.cityofnewyork.us/dataset/Ten-Year-Capital-Strategy/b37a-3faw" target="_blank">10-Year Strategy</a> document every 2 years, organizing the plan by project types and categories.</p>
				<div class="float-left mr-4 my-4">
					<a href="{!! route('prjTypes') !!}" class="float-left no-underline">
						<span class="type-label">View Project Types</span>
					</a>
				</div>					
				<div class="float-left mr-4 my-4">
					<a href="{!! route('prjCategories') !!}" class="float-left no-underline">
						<span class="type-label">View Categories</span>
					</a>
				</div>					
			</div>

			<div class="col-4">
				<h2>Budget</h2>
				<p class="lead">The Mayor submits an <a href="https://data.cityofnewyork.us/City-Government/Capital-Budget/46m8-77gv/" target="_blank">Executive Capital Budget</a> for approval by the City Council every year. This breaks the strategy into budget lines that will fund specific projects.</p>
				<div class="float-left mr-4 my-4">
					<a href="{!! route('budgetLines') !!}" class="float-left no-underline">
						<span class="type-label">View Budget Lines</span>
					</a>
				</div>					
			</div>
			
			<div class="col-4">
				<h2>Commitments</h2>
				<p class="lead">OMB publishes a <a href="https://data.cityofnewyork.us/City-Government/Capital-Commitment-Plan/2cmn-uidm" target="_blank">Capital Commitment Plan</a> three times a year that schedules agency capital spending. These commitments make it possible for agencies to fund projects.</p>
				<div class="float-left mr-4 my-4">
					<a href="{!! route('prjCommitments') !!}" class="float-left no-underline">
						<span class="type-label">View Commitments</span>
					</a>
				</div>					
			</div>

		</div>	

		<div class="row mb-4">

			<div class="col-12">
				<h2>Capital Projects</h2>
				<p class="lead">We combined over a dozen datasets from four different city agencies to create the most comprehensive publicly available capital project profiles.</p>

				<div id="stats_collapse" class="collapse show mt-0 mb-3">
					<div class="row justify-content-center my-1">
						<div class="col-md-3">
							<div class="card">
								<div class="card-body">
									<div class="card-text text-center">
										Number of Projects
										<h2 id="projects_no" class="prj_stat gs_thousandscomma">&nbsp;</h2>
									</div>
								</div>
							</div>
						</div>
					
						<div class="col-md-3">
							<div class="card">
								<div class="card-body">
									<div class="card-text text-center">
										Original Cost
										<h2 id="orig_cost" class="prj_stat gs_finshort" data-multiplier="1000">&nbsp;</h2>
									</div>
								</div>
							</div>
						</div>
					
						<div class="col-md-3">
							<div class="card">
								<div class="card-body">
									<div class="card-text text-center">
										Current Cost
										<h2 id="curr_cost" class="prj_stat gs_finshort" data-multiplier="1000">&nbsp;</h2>
									</div>
								</div>
							</div>
						</div>
					
						<div class="col-md-3">
							<div class="card">
								<div class="card-body">
									<div class="card-text text-center">
										Amount Over Budget
										<h2 id="over_budg_am" class="prj_stat gs_finshort" data-multiplier="1000">&nbsp;</h2>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>

				<div class="float-left mr-4 my-4">
					<a href="{!! route('projects') !!}" class="float-left no-underline">
						<span class="type-label">View Capital Projects</span>
					</a>
				</div>
			</div>
		</div>	
		
	</div>	
	
	<div class="container">
		<div class="row mb-1">
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
								<table id="dsStatsTable" class="display table-hover table-borderless" style="width:100%;">
								</table>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
		
		<p class="mt-2 mb-4 mx-4" style="font-size: 1.2rem;">
			<i class="bi-geo-alt" style="font-weight: 600;"></i>&nbsp;&nbsp;Our map uses data from <a href="https://data.cityofnewyork.us/City-Government/Capital-Projects-Database-CPDB-Projects-Polygons-/9jkp-n57r/" target="_blank">Capital&nbsp;Projects Database (CPDB) - Projects (Polygons)</a>, <a href="https://data.cityofnewyork.us/City-Government/Capital-Projects-Database-CPDB-Projects-Points-/h2ic-zdws/" target="_blank">Capital&nbsp;Projects Database (CPDB) - Projects (Points)</a> datasets.
		</p>

		
    </div>
</div>


<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/rowgroup/1.1.4/js/dataTables.rowGroup.min.js"></script>
<script>
	var datasets = {!! json_encode(array_values($datasets)) !!}
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
{{--
	function loadFinStat() {
		var uu = {!! json_encode($finStatUrls) !!}
		for (let sel in uu) {
			fapireq(uu[sel], function (resp) {
				var v = resp['data'][0]['res'] ?? '-'
				//console.log(['#orig_cost', '#curr_cost', '#over_budg_am'].includes(sel))
				if ((['#orig_cost', '#curr_cost', '#over_budg_am'].includes(sel)) && (v != '-')) {
					$(sel).text(toFinShortK(v, 1000))
					$(sel).attr('data-content', toFin(v, 1000))
				}						
				else 
					$(sel).text(v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","))
			})
		}
		setTimeout(function(){
			initPopovers();
		}, 700);
	}
--}}
	$(document).ready(function () {

		const globStats = {!! json_encode($globStats) !!};
		globStatView(globStats);
		
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
		
		//loadFinStat()
	});

</script>

@endsection
