@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects taxonomy." />
	<meta rel="canonical" href="{!! route('prjTypes') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<style>
		.toolbar {float: right; width: 25%;}
		select.filter-top {width: 100%;}
	</style>
	<script>
		var table = null
		var data = {!! json_encode(array_values($data)) !!}
		
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


		$(document).ready(function() {
			table = $('#prjsTypes').DataTable( {
				data: data,
				pageLength: 20,
				deferRender: true,
				order: [[1, 'asc']],
				//dom: '<"toolbar"<"row">>frtip',
				dom: '<"toolbar"<"row">>frtip',
				
				columns: [
                    {data: 'pubdate', visible: false},
                    {data: function (r) {
							return '<a href="' + r['link'] + '">' + r['ptype_name'] + '</a>'
						},
						type: 'html'
					},
                    {data: 'catnum'},
                    {data: function (r) { return toFin(r["yr10_total"] * 1000) }, type: 'html'},
                    {data: 'blnum'},
                    {data: function (r) { return toFin(r["bl_yr4_total"]) }, type: 'html'},
                    {data: 'cnum'},
                    {data: function (r) { return toFin(r["yr1_amt"] * 1000) }, type: 'html'},
                    {data: 'pnum'},
                    {data: function (r) { return toFin(r["budg_cost"] * 1000) }, type: 'html'},
                    {data: function (r) { return toFin(r["curr_cost"] * 1000) }, type: 'html'},
                    {data: function (r) { return toFin(r["budg_cost"]  * 1000 - r["curr_cost"] * 1000) }, type: 'html', visible: false},
                ],
				@if ($defSearch ?? null)
					search: {
						'search': '{{ $defSearch }}'
				    },
				@endif	

				initComplete: function () {
					this.api().columns([0]).every(function () {						// pubdate
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- Published Date -</option></select>')
							//.appendTo($('div.toolbar'))
							.appendTo($('#pub_date_filter'))
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
							//select.val('20230112').trigger('change')
						}, 700);
						
					});

					
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

		});
	</script>
<div class="inner_container">
	<div class="container organization_data pb-0">
		<div class="row justify-content-center">
			<div class="col-md-12">
				<div class="db-eyebrow">Projects</div>
				<h2>Project Types</h2>
				<p class="lead">The <a target="_blank" href="https://data.cityofnewyork.us/dataset/Ten-Year-Capital-Strategy/b37a-3faw">Ten-Year Capital Strategy</a> explains the Mayor's long-term vision for the city's capital program. It's updated every two years and is organized into <a href="{!! route('prjTypes') !!}">project types</a>, which are often agency specific, and thematic <a href="{!! route('prjCategories') !!}">categories</a>. Both project type and categories are used to classify each capital project.</p>
			</div>
		</div>
		<div class="row justify-content-center">
			<div class="col-md-7">
			</div>
			<div class="col-md-5 mt-0" id="org_summary">
				<table class="table-sm stats-table" width="100%">
				<thead>
					<tr>
						<th scope="col" width="50%" class="text-center px-0" data-content="See the project info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
						<th scope="col" width="50%" id="pub_date_filter"></th>
					</tr>
					<tr>
						<td></td><td style="min-width: 350px;">* <i>The most recent publications might not offer project data.</i></td>
					</tr>
				</thead>
				</table>
			</div>
		</div>
	</div>

	<div class="container" style="margin-top: -10px;">
		<div class="row justify-content-center">
			<div class="col-md-12 organization_data pt-0">
                <div class="table-responsive">
                    <table id="prjsTypes" class="db-table display table" style="width:100%;padding-top: 30px;">
                        <thead>
                            <tr>
                                <th>Publication Date</th>
                                <th>Name</th>
                                <th>Categories</th>
                                <th>10-Year Value</th>
                                <th>Budget Lines</th>
                                <th>4-Year Value</th>
                                <th>Commitments</th>
                                <th>1-Year Value</th>
                                <th>Projects</th>
                                <th>Original Budget</th>
                                <th>Current Budget</th>
                                <th>Difference</th>
                            </tr>
                        </thead>
                    </table>
                </div>
			</div>
		</div>
		{{--<div class="row justify-content-center">
			<div class="col-md-12">
				<div class="bottom_lastupdate">
		@if ($dataset)
					<p class="lead"><img src="/img/info.png" alt=""> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span></p>
				</div>
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
</div>
@endsection
