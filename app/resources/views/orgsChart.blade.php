@extends('layout')

@section('head')
	<meta name="description" content="Data-powered profiles of every NYC government agency." />
	<meta rel="canonical" href="{!! route('orgs') !!}" />
	<style>
		.db-node.is-current { background: var(--db-navy-100); border-color: var(--db-accent); }
		.db-orgchart { max-width: 920px; }
	</style>
@endsection

@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')
<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

		<div class="db-eyebrow">Organizations</div>
		<h1>Citywide Organizational Chart</h1>
		<p class="db-page-lead">The relationship between city officials and agencies, top to bottom. Click an entity to open its profile; use the arrows to expand or collapse branches.</p>

		@if (!empty($chart))
			<div class="d-flex" style="gap: var(--db-space-1); margin: var(--db-space-2) 0;">
				<button type="button" class="db-btn db-btn-outline db-btn-sm" id="oc-expand"><i class="bi bi-arrows-expand"></i> Expand all</button>
				<button type="button" class="db-btn db-btn-ghost db-btn-sm" id="oc-collapse"><i class="bi bi-arrows-collapse"></i> Collapse all</button>
			</div>

			<div class="db-orgchart">
				<ul class="db-tree">
					@include('sub.orgnode', ['node' => $chart, 'depth' => 0, 'defId' => $defId ?? null])
				</ul>
			</div>
		@else
			<div class="db-empty">
				<div class="db-empty-icon"><i class="bi bi-diagram-3"></i></div>
				<div class="db-empty-title">Org chart unavailable</div>
				<div class="db-empty-text">The citywide organizational chart could not be loaded.</div>
			</div>
		@endif

		<p class="db-page-lead" style="margin-top: var(--db-space-4); font-size: var(--db-text-sm);">
			<i class="bi bi-info-circle"></i> Generated from the city’s official (but outdated) organizational chart
			<a href="https://www1.nyc.gov/office-of-the-mayor/org-chart.page" rel="nofollow">published here</a>, with edits for legibility and currency.
			Spot an inaccuracy? <a href="https://wegovnyc.notion.site/Contact-Us-54b075fa86ec47ebae48dae1595afc2c" rel="nofollow">Let us know</a>.
		</p>

	</div>
</div>

<script>
(function () {
	var chart = document.querySelector('.db-orgchart');
	if (!chart) return;
	// Toggle a branch
	chart.addEventListener('click', function (e) {
		var btn = e.target.closest('button.db-node-toggle');
		if (!btn) return;
		var li = btn.closest('li');
		if (li) li.classList.toggle('is-collapsed');
	});
	// Expand / collapse all
	var ea = document.getElementById('oc-expand'), ca = document.getElementById('oc-collapse');
	if (ea) ea.addEventListener('click', function () {
		chart.querySelectorAll('li.is-collapsed').forEach(function (li) { li.classList.remove('is-collapsed'); });
	});
	if (ca) ca.addEventListener('click', function () {
		chart.querySelectorAll('.db-tree li').forEach(function (li) {
			if (li.querySelector(':scope > ul')) li.classList.add('is-collapsed');
		});
	});
@if (!empty($defId))
	// Focus the requested org: expand its ancestors, highlight, scroll into view.
	var target = chart.querySelector('a[href*="/organization/{{ $defId }}"]');
	if (target) {
		var node = target.closest('.db-node');
		if (node) node.classList.add('is-current');
		var li = target.closest('li');
		while (li) { li.classList.remove('is-collapsed'); li = li.parentElement ? li.parentElement.closest('li') : null; }
		setTimeout(function () { target.scrollIntoView({ block: 'center', behavior: 'smooth' }); }, 250);
	}
@endif
})();
</script>
@endsection
