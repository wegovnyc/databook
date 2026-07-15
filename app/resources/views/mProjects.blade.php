@extends('layout')


@section('head')
	<meta name="description" content="NYC Minor Capital Projects." />
	<meta rel="canonical" href="{!! route('mProjects') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'projects'])
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<style>
		.toolbar {float: right; width: 25%;}
		select.filter-top {width: 100%;}
	</style>
<div class="inner_container">
	<div class="container organization_data pb-4">
		<div class="row justify-content-center">
			<div class="col-md-12 md-4">
				<div class="db-eyebrow">Projects</div>
				<h2>Minor Projects</h2>
				<p class="lead">These projects have received financial commitments from the city but aren’t documented in the main city capital project datasets that show details, milestones and locations.
				</p>
			</div>
		</div>
	</div>

	<div class="container" style="margin-top: -10px;">
		<div class="row justify-content-center">
			<div class="col-md-12 organization_data pt-0">
                <div class="table-responsive">
                    <table id="mProjects" class="db-table display table" style="width:100%;padding-top: 30px;">
                        <thead>
                            <tr>
                                <th>Project ID</th>
                                <th>Name</th>
                                <th>Planned Commitment</th>
                                <th>Min Date</th>
                                <th>Max Date</th>
                                <th>Agency</th>
                                <th>CCP Version</th>
                                <th>Commitments</th>
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
		
		{{--
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
		--}}

    </div>
</div>
@endsection


@section('scripts')

	<script>
		var table = null
		var data = {!! json_encode($data) !!}
		
		{{--var datasets = {!! json_encode(array_values($datasets)) !!}
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
		--}}

		$(document).ready(function() {
			table = $('#mProjects').DataTable( {
				pageLength: 20,
				deferRender: true,
				order: [[1, 'asc']],
				dom: '<"toolbar"<"row">>frtip',
				data: data,
				
				columns: [
                    {data: function (r) {
							return `<a href="{{ route('mProjects') }}/${r['maprojid']}">${r['maprojid']}</a>`
						},
						type: 'html'
					},
                    {data: 'description'},
                    {data: function (r) { return toFin(r['totalplannedcommit']) }, type: 'html'},
                    {data: 'mindate'},
                    {data: 'maxdate'},
                    {data: 'wegov-org-name'},
                    {data: 'ccpversion'},
                    {data: 'commitments_no'},
                ],

				initComplete: function () {
					this.api().columns([5]).every(function () {						// pubdate
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- Agency Name -</option></select>')
							.appendTo($('div.toolbar'))
							//.appendTo($('#pub_date_filter'))
							.on('change', function () {
								/*var val = $.fn.dataTable.util.escapeRegex(
									$(this).val()
								);
								*/
								var val = $(this).val();
								column
									.search(val ? val : '', false, false)
									.draw();
							});
						var tt = []

						rg = />([^<]+)</g;
						column.data().each(function (d, j) {
							if (d)
								tt.push(d)
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							//select.append( '<option value="'+d+'">'+toDashDate(d)+'</option>' )
							select.append( '<option value="'+d+'">'+d+'</option>' )
						});

						{{--
							setTimeout(function(){
								//select.val(tt[tt.length-1]).trigger('change')
								select.val('20210114').trigger('change')
							}, 700);
						--}}
					});

					
				}
			});

			{{--
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
			--}}
		});
	</script>

@endsection