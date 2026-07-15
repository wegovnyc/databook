@extends('layout')


@section('head')
	<meta name="description" content="The roles, positions and pay of NYC's civil servants" />
	<meta rel="canonical" href="{!! route('peoplePerson', ['id' => $id, 'slug' => $slug]) !!}" />
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
					dom: '<"toolbar"<"row">>frtip',
					ajax: function (url, cb) {
						fapireq("{!! $url !!}", function (dd) {
							var rr = []
							console.log(dd)
							dd.data.reduce(
								(a, b) => {
									if (b['perm-id'] != '{{ $id }}') {
										a.push(b)
									}
									return a
								},
								rr
							)
							cb({'data': rr})
						});
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

						setTimeout(function(){
							initPopovers();
						}, 1000);
					}

				});
			});
		@endif

	</script>
@php
	// --- Derive display name, role/agency, salary + meta per dataset (presentation only) ---
	$personName  = '';
	$personRole  = '';
	$agencyName  = $person['wegov-org-name'] ?? '';
	$datasetLabel = ['civillist' => 'Civil List', 'civillistactive' => 'Civil List (Active)', 'nycgreenbook' => 'Greenbook', 'payrolldata' => 'Payroll Data'][$tbl] ?? 'City Employee';

	if ($tbl == 'civillist') {
		$personName = $person['EMPLOYEE NAME'] ?? '';
		$personRole = $person['wegov-service-title-desc'] ?? '';
	} elseif ($tbl == 'civillistactive') {
		$personName = preg_replace('~\s+~si', ' ', trim(implode(' ', [$person['First Name'] ?? '', $person['MI'] ?? '', $person['Last Name'] ?? ''])));
		$personRole = $person['wegov-service-title-desc'] ?? '';
	} elseif ($tbl == 'nycgreenbook') {
		$personName = preg_replace('~\s+~si', ' ', trim(implode(' ', [$person['First Name'] ?? '', $person['Middle Initial'] ?? '', $person['Last Name'] ?? ''])));
		$personRole = $person['Office Title'] ?? '';
	} elseif ($tbl == 'payrolldata') {
		$personName = preg_replace('~\s+~si', ' ', trim(implode(' ', [$person['First Name'] ?? '', $person['Mid Init'] ?? '', $person['Last Name'] ?? ''])));
		$personRole = $person['Title Description'] ?? '';
	}

	// Initials fallback for the avatar (no photo available for civil servants).
	$nameParts = preg_split('~\s+~', trim($personName));
	$nameParts = array_values(array_filter($nameParts, fn($p) => $p !== ''));
	$initials = '';
	if (count($nameParts) >= 2) {
		$initials = mb_strtoupper(mb_substr($nameParts[0], 0, 1) . mb_substr(end($nameParts), 0, 1));
	} elseif (count($nameParts) == 1) {
		$initials = mb_strtoupper(mb_substr($nameParts[0], 0, 2));
	}
	if ($initials === '') { $initials = '—'; }
@endphp

<div class="db-profile-header">
	<div class="inner_container">
		<div class="container">
			<nav class="db-breadcrumb" aria-label="breadcrumb">
				<a href="{{ route('root') }}">Home</a>
				<span class="db-breadcrumb-sep">/</span>
				<a href="{{ route('people') }}">People</a>
				<span class="db-breadcrumb-sep">/</span>
				<span class="is-current">{{ $personName }}</span>
			</nav>

			<div class="db-profile-header-top">
				<div class="db-avatar db-avatar-lg" aria-hidden="true">{{ $initials }}</div>

				<div class="db-profile-main">
					<div class="db-profile-kicker">
						<span class="db-type-label">{{ $datasetLabel }}</span>
					</div>

					<h1 class="db-profile-title">{{ $personName }}</h1>

					@if ($personRole || $agencyName)
						<p class="db-profile-subtitle">
							@if ($personRole){{ $personRole }}@endif
							@if ($personRole && $agencyName) · @endif
							@if ($agencyName){{ $agencyName }}@endif
						</p>
					@endif

					@php
						// Lightweight at-a-glance meta row, mirroring the visible facts per dataset.
						$metaItems = [];
						if ($tbl == 'civillist') {
							if ($person['wegov-service-title-desc'] ?? null) $metaItems[] = ['bi-card-text', 'Title', $person['wegov-service-title-desc']];
							if (($person['SALARY RATE'] ?? null) !== null && $person['SALARY RATE'] !== '') $metaItems[] = ['bi-cash', 'Salary rate', '$' . number_format((float) preg_replace('~[^0-9.]~', '', (string) $person['SALARY RATE']), 0, '.', ',')];
							if ($person['CALENDAR YEAR'] ?? null) $metaItems[] = ['bi-calendar3', 'Year', $person['CALENDAR YEAR']];
						} elseif ($tbl == 'civillistactive') {
							if ($person['wegov-service-title-desc'] ?? null) $metaItems[] = ['bi-card-text', 'Title', $person['wegov-service-title-desc']];
							if ($person['Published Date'] ?? null) $metaItems[] = ['bi-calendar3', 'Published', $person['Published Date']];
						} elseif ($tbl == 'nycgreenbook') {
							if ($person['Office Title'] ?? null) $metaItems[] = ['bi-card-text', 'Title', $person['Office Title']];
							if ($person['Work Location Borough'] ?? null) $metaItems[] = ['bi-geo-alt', 'Borough', $person['Work Location Borough']];
						} elseif ($tbl == 'payrolldata') {
							if ($person['Title Description'] ?? null) $metaItems[] = ['bi-card-text', 'Title', $person['Title Description']];
							if (($person['Base Salary'] ?? null) !== null) $metaItems[] = ['bi-cash', 'Base', '$' . number_format($person['Base Salary'], 0, '.', ',')];
							if ($person['Fiscal Year'] ?? null) $metaItems[] = ['bi-calendar3', 'FY', $person['Fiscal Year']];
							if ($person['Work Location Borough'] ?? null) $metaItems[] = ['bi-geo-alt', 'Borough', $person['Work Location Borough']];
						}
					@endphp
					@if (count($metaItems))
						<div class="db-profile-meta">
							@foreach ($metaItems as $mi)
								<span class="db-meta-item"><i class="bi {{ $mi[0] }}"></i> {{ $mi[1] }} <strong>{{ $mi[2] }}</strong></span>
							@endforeach
						</div>
					@endif
				</div>

				@if (($person['wegov-org-id'] ?? null))
					<div class="db-profile-actions">
						@php
							$agencySection = ['civillist' => 'civil-list', 'civillistactive' => 'candidates', 'nycgreenbook' => 'public-contacts', 'payrolldata' => 'public-contacts'][$tbl] ?? 'about';
						@endphp
						<a class="db-btn db-btn-outline db-btn-sm" href="{!! route('orgSection', ['id' => $person['wegov-org-id'], 'orgslug' => Str::slug($agencyName), 'section' => $agencySection]) !!}">
							<i class="bi bi-building"></i> View agency
						</a>
					</div>
				@endif
			</div>
		</div>
	</div>
</div>

<div class="inner_container">
	<div class="container mb-5" style="padding-top: var(--db-space-3);">
		@if ($dataset)
			<p class="db-page-lead bottom_lastupdate">
				<i class="bi bi-info-circle"></i> This data comes from
				<a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a>.
				<span style="font-weight: 300;"><i>Last updated {{ explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span>
			</p>
		@endif

		@if ($tbl == 'civillist')
			<div class="db-card mt-3">
				<div class="db-card-body">
					<h2 class="db-card-title">Record details</h2>
					<dl class="db-meta-list mt-2">
						<dt>Name</dt>
						<dd>{{ $person['EMPLOYEE NAME'] }}</dd>
						<dt>Agency</dt>
						<dd>
							@if($person['wegov-org-id'])
								<a href="{!! route('orgSection', ['id' => $person['wegov-org-id'], 'orgslug' => Str::slug($person['wegov-org-name']), 'section' => 'civil-list']) !!}">{{ $person['wegov-org-name'] }}</a>
							@endif
						</dd>
						<dt>Title</dt>
						<dd>
							@if($person['wegov-service-title-id'])
								<a href="{!! route('title', ['id' => $person['wegov-service-title-id'], 'tslug' => Str::slug($person['wegov-service-title-desc'])]) !!}">{{ $person['wegov-service-title-desc'] }}</a>
							@endif
						</dd>
						<dt>Pay Class</dt>
						<dd>{{ $person['PAY CLASS'] }}</dd>
						<dt>Calendar Year</dt>
						<dd>{{ $person['CALENDAR YEAR'] }}</dd>
						<dt>Salary Rate</dt>
						<dd class="db-num gs_thousandscomma">{{ $person['SALARY RATE'] }}</dd>
					</dl>
				</div>
			</div>
		@elseif ($tbl == 'civillistactive')
			<div class="db-card mt-3">
				<div class="db-card-body">
					<h2 class="db-card-title">Record details</h2>
					<dl class="db-meta-list mt-2">
						<dt>Name</dt>
						<dd>{{ preg_replace('~\s+~si', ' ', implode(' ', [$person['First Name'], $person['MI'], $person['Last Name']]))  }}</dd>
						<dt>Agency</dt>
						<dd>
							@if($person['wegov-org-id'])
								<a href="{!! route('orgSection', ['id' => $person['wegov-org-id'], 'orgslug' => Str::slug($person['wegov-org-name']), 'section' => 'candidates']) !!}">{{ $person['wegov-org-name'] }}</a>
							@endif
						</dd>
						<dt>Published Date</dt>
						<dd>{{ $person['Published Date'] }}</dd>
						<dt>Title</dt>
						<dd>
							@if($person['wegov-service-title-id'])
								<a href="{!! route('title', ['id' => $person['wegov-service-title-id'], 'tslug' => Str::slug($person['wegov-service-title-desc'])]) !!}">{{ $person['wegov-service-title-desc'] }}</a>
							@endif
						</dd>
						<dt>Exam No</dt>
						<dd>{{ $person['Exam No'] }}</dd>
						<dt>List No</dt>
						<dd>{{ $person['List No'] }}</dd>
						<dt>Adj. FA</dt>
						<dd>{{ $person['Adj. FA'] }}</dd>
						<dt>Group No</dt>
						<dd>{{ $person['Group No'] }}</dd>
						<dt>List Div Code</dt>
						<dd>{{ $person['List Div Code'] }}</dd>
						<dt>Established Date</dt>
						<dd>{{ $person['Established Date'] }}</dd>
						<dt>Anniversary Date</dt>
						<dd>{{ $person['Anniversary Date'] }}</dd>
						<dt>Extension Date</dt>
						<dd>{{ $person['Extension Date'] }}</dd>
						<dt>Veteran Credit</dt>
						<dd>{{ $person['Veteran Credit'] }}</dd>
						<dt>Parent Lgy Credit</dt>
						<dd>{{ $person['Parent Lgy Credit'] }}</dd>
						<dt>Sibling Lgy Credit</dt>
						<dd>{{ $person['Sibling Lgy Credit'] }}</dd>
						<dt>Residency Credit</dt>
						<dd>{{ $person['Residency Credit'] }}</dd>
					</dl>
				</div>
			</div>

		@elseif ($tbl == 'nycgreenbook')
			<div class="db-card mt-3">
				<div class="db-card-body">
					<h2 class="db-card-title">Record details</h2>
					<dl class="db-meta-list mt-2">
						<dt>Name</dt>
						<dd>{{ preg_replace('~\s+~si', ' ', implode(' ', [$person['First Name'], $person['Middle Initial'], $person['Last Name']]))  }}</dd>
						<dt>Agency</dt>
						<dd>
							@if($person['wegov-org-id'])
								<a href="{!! route('orgSection', ['id' => $person['wegov-org-id'], 'orgslug' => Str::slug($person['wegov-org-name']), 'section' => 'public-contacts']) !!}">{{ $person['wegov-org-name'] }}</a>
							@endif
						</dd>
						<dt>Title</dt>
						<dd>{{ $person['Office Title'] }}</dd>
						<dt>Division Name</dt>
						<dd>{{ $person['Division Name'] }}</dd>
						<dt>Parent Division</dt>
						<dd>{{ $person['Parent Division'] }}</dd>
						<dt>Grand Parent Division</dt>
						<dd>{{ $person['Grand Parent Division'] }}</dd>
						<dt>Great Grand Parent Division</dt>
						<dd>{{ $person['Great Grand Parent Division'] }}</dd>
						<dt>Address</dt>
						<dd>{{ $person['Address'] }}</dd>
						<dt>City</dt>
						<dd>{{ $person['City'] }}</dd>
						<dt>State</dt>
						<dd>{{ $person['State'] }}</dd>
						<dt>Zip Code</dt>
						<dd>{{ $person['Zip Code'] }}</dd>
						<dt>Phone</dt>
						<dd>{{ $person['Phone 1'] }}</dd>
						<dt>Agency Phone</dt>
						<dd>{{ $person['Agency Primary Phone'] }}</dd>
						<dt>Division Phone</dt>
						<dd>{{ $person['Division Primary Phone'] }}</dd>
						<dt>Section</dt>
						<dd>{{ $person['Section'] }}</dd>
					</dl>
				</div>
			</div>

		@elseif ($tbl == 'payrolldata')
			<div class="db-stat-grid mt-3 mb-3">
				<div class="db-stat is-accent">
					<div class="db-stat-label"><i class="bi bi-cash"></i> Base Salary</div>
					<div class="db-stat-value gs_thousandscomma">${{ number_format($person['Base Salary'], 0, '.', ',') }}</div>
				</div>
				<div class="db-stat">
					<div class="db-stat-label">Regular Gross Paid</div>
					<div class="db-stat-value gs_thousandscomma">${{ number_format($person['Regular Gross Paid'], 0, '.', ',') }}</div>
				</div>
				<div class="db-stat">
					<div class="db-stat-label">Total Other Pay</div>
					<div class="db-stat-value gs_thousandscomma">${{ number_format($person['Total Other Pay'], 0, '.', ',') }}</div>
				</div>
				<div class="db-stat">
					<div class="db-stat-label">Total OT Paid</div>
					<div class="db-stat-value">{{ $person['Total OT Paid'] }}</div>
				</div>
			</div>
			<div class="db-card mt-3">
				<div class="db-card-body">
					<h2 class="db-card-title">Record details</h2>
					<dl class="db-meta-list mt-2">
						<dt>Name</dt>
						<dd>{{ preg_replace('~\s+~si', ' ', implode(' ', [$person['First Name'], $person['Mid Init'], $person['Last Name']]))  }}</dd>
						<dt>Agency</dt>
						<dd>
							@if($person['wegov-org-id'])
								<a href="{!! route('orgSection', ['id' => $person['wegov-org-id'], 'orgslug' => Str::slug($person['wegov-org-name']), 'section' => 'public-contacts']) !!}">{{ $person['wegov-org-name'] }}</a>
							@endif
						</dd>
						<dt>Fiscal Year</dt>
						<dd>{{ $person['Fiscal Year'] }}</dd>
						<dt>Title Description</dt>
						<dd>{{ $person['Title Description'] }}</dd>
						<dt>Agency Start Date</dt>
						<dd>{{ $person['Agency Start Date'] }}</dd>
						<dt>Leave Status as of June 30</dt>
						<dd>{{ $person['Leave Status as of June 30'] }}</dd>
						<dt>Work Location Borough</dt>
						<dd>{{ $person['Work Location Borough'] }}</dd>
						<dt>Payroll Number</dt>
						<dd>{{ $person['Payroll Number'] }}</dd>
						<dt>Pay Basis</dt>
						<dd>{{ $person['Pay Basis'] }}</dd>
						<dt>OT Hours</dt>
						<dd>{{ $person['OT Hours'] }}</dd>
					</dl>
				</div>
			</div>

		@endif

		<h2 class="db-section-title main_hdr mt-5 mb-2">Possible Matches</h2>
		<p class="db-page-lead">Records with similar names are shown below.</p>

		@if ($url ?? null)
			<div class="db-table-wrap mt-3">
				<div class="table-responsive organization_data">
					<table id="peopleTable" class="db-table display table" style="width:100%;">
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
		@endif
	</div>
</div>
@endsection
