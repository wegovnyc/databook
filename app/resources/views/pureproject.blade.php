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

	@php
		$p = $prj[0];
		// Money: list values are plain numeric strings; blank/non-numeric → em-dash.
		$money = function ($v) {
			return ($v === null || $v === '' || !is_numeric($v)) ? '—' : '$' . number_format((float) $v);
		};
		$budget = [
			['Planned Commitment', $p['plannedcommit_total'] ?? null],
			['Adopted',            $p['adopt_total'] ?? null],
			['Allocated',          $p['allocate_total'] ?? null],
			['Committed',          $p['commit_total'] ?? null],
			['Spent',              $p['spent_total'] ?? null],
			['Spent (Checkbook NYC)', $p['spent_total_checkbooknyc'] ?? null],
		];
		$dateRange = trim(($p['mindate'] ?? '') . (($p['mindate'] ?? '') && ($p['maxdate'] ?? '') ? ' – ' : '') . ($p['maxdate'] ?? ''));
	@endphp

	<div class="inner_container">
		<div class="container">
			<div class="db-profile-kicker mt-4">
				<span class="db-type-label">Capital Project</span>
			</div>
			<h1 class="mb-1">{{ $p['description'] }}</h1>
			<p class="db-page-lead mb-4">{{ $p['maprojid'] }}@if (!empty($p['magencyname'])) · {{ $p['magencyname'] }}@endif</p>

			<div class="row">
				<div class="col-lg-8 col-md-7">
					<div class="db-card mb-4">
						<div class="db-card-body">
							<h2 class="db-card-title">Capital Commitment Plan</h2>
							<dl class="db-meta-list">
								@foreach ($budget as [$label, $val])
									<dt>{{ $label }}</dt>
									<dd style="color:var(--db-primary); font-weight:var(--db-weight-semibold);">{{ $money($val) }}</dd>
								@endforeach
							</dl>
						</div>
					</div>

					<h2 class="mb-2" style="font-size:var(--db-text-lg);">Commitments</h2>
					<div class="table-responsive">
						<table class="db-table" id="commitments" width="100%">
							<thead>
								<tr>
									<th scope="col">Budget Line</th>
									<th scope="col">Type</th>
									<th scope="col">Plan Date</th>
									<th scope="col">Description</th>
									<th scope="col">Commitment Type</th>
									<th scope="col" style="text-align:right;">Planned</th>
								</tr>
							</thead>
							<tbody></tbody>
						</table>
					</div>
				</div>

				<aside class="col-lg-4 col-md-5">
					<div class="db-card">
						<div class="db-card-body">
							<h2 class="db-card-title">Project details</h2>
							<dl class="db-meta-list">
								<dt>Project ID</dt><dd class="is-mono">{{ $p['projectid'] ?? $p['maprojid'] }}</dd>
								<dt>Full ID</dt><dd class="is-mono">{{ $p['maprojid'] }}</dd>
								@if (!empty($p['typecategory']))<dt>Category</dt><dd>{{ $p['typecategory'] }}</dd>@endif
								@if (!empty($p['magencyname']))
									<dt>Managing Agency</dt>
									<dd><a href="/o/{{ $p['wegov-org-id'] }}-{{ Str::slug($p['wegov-org-name'] ?? $p['magencyname']) }}">{{ $p['magencyname'] }}</a></dd>
								@endif
								@if ($dateRange)<dt>Timeline</dt><dd>{{ $dateRange }}</dd>@endif
							</dl>
							<p class="mt-3 mb-0"><a href="https://airtable.com/shrWWa3rNJFGSFObd?prefill_project_id={{ $prjId }}" class="db-btn db-btn-sm db-btn-outline" target="_blank" rel="nofollow">Suggest a change</a></p>
						</div>
					</div>
					@if ($dataset)
						<p class="mt-3" style="font-size:var(--db-text-xs); color:var(--db-text-muted);">Source: <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a>@if(!empty($dataset['Last Updated'])) · updated {{ explode(' ', $dataset['Last Updated'])[0] }}@endif</p>
					@endif
				</aside>
			</div>
		</div>
	</div>

	<script>
		$(document).ready(function () {
			function money(v) {
				if (v === null || v === '' || isNaN(v)) return '—';
				return '$' + Number(v).toLocaleString('en-US', {maximumFractionDigits: 0});
			}
			$('#commitments').DataTable({
				ajax: function (url, cb) { fapireq("{!! $commUrl !!}", cb); },
				deferRender: true,
				dom: 'rt',
				order: [],
				columns: [
					{data: 'budgetline', defaultContent: ''},
					{data: 'projecttype', defaultContent: ''},
					{data: 'plancommdate', defaultContent: ''},
					{data: 'commitmentdescription', defaultContent: ''},
					{data: 'typcname', defaultContent: ''},
					{data: 'plannedcommit_total', defaultContent: '', className: 'text-end',
					 render: function (d) { return '<span style="color:var(--db-primary);">' + money(d) + '</span>'; }},
				],
				language: {emptyTable: 'No commitment records for this project.'},
			});
		});
	</script>
	<script type="application/ld+json">{!! json_encode($schema ?? []) !!}</script>
@endsection
