@extends('layout')


@section('head')
	<meta name="description" content="The roles, positions and pay of NYC's civil servants" />
	<meta rel="canonical" href="{!! route('people') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<script>
		var table = null
		var tblCode = {'civillist': 'cl', 'civillistactive': 'cla', 'nycgreenbook': 'gb', 'payrolldata': 'pr'}
		var tblNames = {'civillist': 'Civil List', 'civillistactive': 'Civil List Active', 'nycgreenbook': 'Greenbook', 'payrolldata': 'Payroll Data'}

		@if ($url ?? null)
			$(document).ready(function() {
				table = $('#peopleTable').DataTable( {
					pageLength: 20,
					deferRender: true,
					order: [],
					dom: '<"toolbar container-flex"<"row">>frtip',
					ajax: function (url, cb) {
						fapireq("{!! $url !!}", cb);
					},
						
					columns: [
						{data: 'fullname'},
						{data: 'date'},
						{data: function (r) { 
								return `<a href="/o/${r['wegov-org-id']}-${slug(r['wegov-org-name'])}">${r['wegov-org-name']}</a>`;
						}},
						{data: function (r) { return tblNames[r['tbl']]; }},
						{data: function (r) { 
								return `<a href="/people/${r['perm-id']}-${slug(r['fullname'].toLowerCase().replace(/\s+/g, ' '))}">More Info</a>`;
						}},
					],
					
					initComplete: function () {
						this.api().columns([1,2,3]).every(function (c,a,i) {
							var delim = {};
							var column = this;
							var select = $('<select class="filter" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="myTable"><option value="" selected>- ' + $(column.header()).text() + ' -</option></select>')
								.appendTo($("div.toolbar .row"))
								.on('change', function () {
									var val = $(this).val()
									column
										.search(val ? '^'+val+'$': '', true, false)
										.draw();
								});
							select.wrap('<div class="drop_dowm_select col"></div>');
							$('div.toolbar').insertAfter('#myTable_filter');

							var tt = []
							dd = column.data()

							column.data().each(function (d, j) {
								d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
								if (c in delim && typeof d == 'string') {
									d.split(delim[c]).forEach(function (v, k) {
										tt.push(v)
									})
								}
								else
									tt.push(d)
							})
							tt = [...new Set(tt)]

							tt.sort().forEach(function (d, j) {
								select.append('<option value="'+d+'">'+d+'</option>')
							});
						});
					
					{{--	@foreach ($details['filters'] as $i=>$v)
							@if ($v)
								setTimeout(function(){
									$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
								}, 500 + 1000 * {{ $i }});
							@endif
						@endforeach
					--}}
						setTimeout(function(){
							initPopovers();
						}, 1000);
					}					

				});
			});
		@endif
		
		function peopleFormSubmit() {
			var url = '{!! route('peopleSearchTbl', ['req'=>'RRRR', 'tbl'=>'TTTT']) !!}'
			var req = $('#peopleSearch').val().toLowerCase()
			var tbl = 'all'
			url = url.replace('RRRR', encodeURIComponent(req).replaceAll('%20', '+')).replace('TTTT', tbl)
			//console.log(url)
			window.location.href = url
		}
	</script>
<div class="inner_container">
	<div class="mt-4 mb-5 mx-3">
		<div class="db-eyebrow">People</div>
		<h1 class="main_hdr">People</h1>
		<p class="db-page-lead">Search for people who work in and around New York City government.</p>
		<div class="db-filter-bar mt-3 mb-2">
			<div class="db-search">
				<i class="bi bi-search"></i>
				<input type="search" id="peopleSearch" placeholder="Search people…" aria-label="Search people" @if($req ?? null ) value="{!! $req !!}" @endif>
			</div>
			<button type="button" class="db-btn db-btn-primary" onclick="peopleFormSubmit();"><i class="bi bi-search"></i> Search</button>
		</div>

		<p class="text-muted"><small>Results come from multiple open and public city data sources.</small></p>
	</div>
	<div class="container">
		@if ($url ?? null)
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data">
					<div class="table-responsive">
						<table id="peopleTable" class="db-table display table" style="width:100%;padding-top: 30px;">
							<thead>
								<tr>
									<th>Name</th>
									<th>Date</th>
									<th>Agency</th>
									<th>Dataset</th>
									<th></th>
								</tr>
							</thead>
						</table>
					</div>
				</div>
			</div>
		@endif
	</div>
</div>
@endsection
