@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects commitments." />
	<meta rel="canonical" href="{!! route('prjCommitments') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<style>
		.toolbar {float: right; width: 45%;}
		select.filter-top {width: 46%;}
	</style>
	<script>
		var table = null
		
		var data = {!! json_encode($data) !!}


		$(document).ready(function() {
			table = $('#prjsCats').DataTable( {
				pageLength: 20,
				deferRender: true,
				order: [[1, 'asc']],
				//dom: '<"toolbar"<"row">>frtip',
				dom: '<"toolbar container-flex"<"row ml-4">>frtip',
				data: data,
				
				columns: [
					{data: 'Published Date', visible: false},
					{data: function (r) {
							return '<a href="/capital/budget-lines/' + r['Budget Line'] + '">' + r['Budget Line'] + '</a>'
						},
						type: 'html'
					},
					{data: 'Budget Line Description'},
					{data: 'Funding Type'},
					{data: 'First Fiscal Year'},
					{data: function (r) { return toFin(r['Fiscal Year 1 Amount'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin(r['Fiscal Year 2 Amount'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin(r['Fiscal Year 3 Amount'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin(r['Fiscal Year 4 Amount'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin((r['Fiscal Year 1 Amount'] + r['Fiscal Year 2 Amount'] + r['Fiscal Year 3 Amount'] + r['Fiscal Year 4 Amount']) * 1000) }, type: 'html'},
                ],
				@if ($defSearch ?? null)
					search: {
						'search': '{{ $defSearch }}'
				    },
				@endif	

				initComplete: function () {
					this.api().columns([4]).every(function () {						// First Fiscal Year
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- First Fiscal Year -</option></select>')
							.appendTo($('div.toolbar .row'))
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
							select.append( '<option value="'+d+'">'+d+'</option>' )
						});

						setTimeout(function(){
							select.val(tt[tt.length-1]).trigger('change')
							//select.val('20210426').trigger('change')
						}, 700);
					});

					
					this.api().columns([0]).every(function () {						// pubdate
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- Published Date -</option></select>')
							.appendTo($('div.toolbar .row'))
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
							//select.val('20210426').trigger('change')
						}, 700);
					});


				}
			});
		});
	</script>
<div class="inner_container">
	<div class="mt-4 mx-3">
		<div class="db-eyebrow">Projects</div>
		<h2>Commitments</h2>
		<p class="lead">The Mayor's Office of Management and Budget (OMB) publishes a <a target="_blank" href="https://data.cityofnewyork.us/City-Government/Capital-Commitment-Plan/2cmn-uidm/about_data">Capital Commitment Plan</a> scheduling agency capital spending three times a year. These commitments make funding available to projects.</p>
	</div>
	<div class="container">
		<div class="row justify-content-center">
			<div class="col-md-12 organization_data">
                <div class="table-responsive">
                    <table id="prjsCats" class="db-table display table" style="width:100%;padding-top: 30px;">
                        <thead>
                            <tr>
								<th scope="col">Published Date</th>
								<th scope="col">Budget Line</th>
								<th scope="col">Budget Line Description</th>
								<th scope="col">Funding Type</th>
								<th scope="col">First Fiscal Year</th>
								<th scope="col">Fiscal Year 1 Amount</th>
								<th scope="col">Fiscal Year 2 Amount</th>
								<th scope="col">Fiscal Year 3 Amount</th>
								<th scope="col">Fiscal Year 4 Amount</th>
								<th scope="col">Total Commitment Value</th>
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

    </div>
</div>
@endsection
