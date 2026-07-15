@extends('layout')


@section('head')
	<meta name="description" content="NYC Capital Projects categories." />
	<meta rel="canonical" href="{!! route('prjCategories') !!}" />
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
		
		var data = {!! json_encode($data) !!}


		$(document).ready(function() {
			table = $('#prjsCats').DataTable( {
				pageLength: 20,
				deferRender: true,
				order: [[1, 'asc']],
				//dom: '<"toolbar"<"row">>frtip',
				dom: '<"toolbar"<"row">>frtip',
				data: data,
				
				columns: [
					{data: 'pubdate', visible: false},
					{data: function (r) {
							return '<a href="/capital/categories/' + r['category-slug'] + '">' + r['category'] + '</a>'
						},
						type: 'html'
					},
					{data: 'fundingsource'},
					{data: function (r) { return toFin(r['year1amount'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin(r['year10total'] * 1000) }, type: 'html'},
					{data: 'prjnum'},
					{data: function (r) { return toFin(r['plannedcost'] * 1000) }, type: 'html'},
					{data: function (r) { return toFin(r['currcost'] * 1000) }, type: 'html', visible: false},
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

					this.api().columns([2]).every(function () {
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- ' + $(column.header()).text() + ' -</option></select>')
							.appendTo($('div.toolbar'))
							//.appendTo($('#pub_date_filter'))
							.on('change', function () {
								var val = $(this).val()
								column
									.search(val ? val : '', false, false)
									.draw();
							});
						var tt = []

						rg = />([^<]+)</g;
						column.data().each(function (d, j) {
							d.split(', ').forEach(function (v, k) {
								tt.push(v)
							})
							//tt.push(d)
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
						select.append( '<option value="'+d+'">'+d+'</option>' )
					});

					setTimeout(function(){
						select.val('City').trigger('change')
					}, 800);
					});
				}
			});
		});
	</script>
<div class="inner_container">
	<div class="container organization_data pb-0">
		<div class="row justify-content-center">
			<div class="col-md-12">
				<div class="db-eyebrow">Projects</div>
				<h2>Categories</h2>
				<p class="lead">The <a target="_blank" href="https://data.cityofnewyork.us/dataset/Ten-Year-Capital-Strategy/b37a-3faw">Ten-Year Capital Strategy</a> explains the Mayor's long-term vision for the city's capital program. It's updated every two years and is organized into <a href="{!! route('prjTypes') !!}">project types</a>, which are often agency specific, and thematic <a href="{!! route('prjCategories') !!}">categories</a>. Both project type and categories are used to classify each capital project.</p>
			</div>
		</div>
		<div class="row justify-content-center">
			<div class="col-md-7">
			</div>
			<div class="col-md-5 mt-2" id="org_summary">
				<table class="table-sm stats-table" width="100%">
				<thead>
					<tr>
						<th scope="col" width="50%" class="text-center px-0" data-content="See the project info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
						<th scope="col" width="50%" id="pub_date_filter"></th>
					</tr>
					<tr>
						<td></td><td style="min-width: 350px;">* <i>If calculations don’t appear change the publication date.</i></td>
					</tr>
				</thead>
				</table>
			</div>
		</div>
	</div>

	<div class="container">
		<div class="row justify-content-center">
			<div class="col-md-12 organization_data">
                <div class="table-responsive">
                    <table id="prjsCats" class="db-table display table" style="width:100%;padding-top: 30px;">
                        <thead>
                            <tr>
								<th scope="col">Published Date</th>
								<th scope="col">Category</th>
								<th scope="col">Funding Sources</th>
								<th scope="col">Fiscal Year 1 Amount</th>
								<th scope="col">Ten Year Total</th>
								<th scope="col">Amount of Projects</th>
								<th scope="col">Planned Project Cost</th>
								<th scope="col">Current Project Cost</th>
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
