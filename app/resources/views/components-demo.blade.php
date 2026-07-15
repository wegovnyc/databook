@extends('layout')

@section('menubar')
	@include('sub.menubar', ['active' => null])
@endsection

@section('content')
<x-db.hero eyebrow="Design system" title="Blade components">
	<p>The <code>&lt;x-db.*&gt;</code> layer — thin wrappers that emit the canonical <code>.db-*</code> markup. Same CSS, less copy-paste. See <a href="/styleguide">/styleguide</a> for the full visual reference.</p>
</x-db.hero>

<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-6); max-width: 960px;">

		<x-db.eyebrow>Buttons</x-db.eyebrow>
		<div style="display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin:12px 0 32px;">
			<x-db.button variant="primary"><x-db.icon name="arrow-right"/> Primary</x-db.button>
			<x-db.button variant="outline">Outline</x-db.button>
			<x-db.button variant="ghost">Ghost</x-db.button>
			<x-db.button variant="primary" size="sm">Small</x-db.button>
			<x-db.button variant="primary" size="lg">Large</x-db.button>
			<x-db.button variant="primary" href="/styleguide">As link</x-db.button>
		</div>

		<x-db.eyebrow>Badges</x-db.eyebrow>
		<div style="display:flex; gap:8px; flex-wrap:wrap; margin:12px 0 32px;">
			<x-db.badge tone="success" dot>Active</x-db.badge>
			<x-db.badge tone="warning">Pending</x-db.badge>
			<x-db.badge tone="danger">Closed</x-db.badge>
			<x-db.badge tone="info">Info</x-db.badge>
			<x-db.badge tone="neutral">Neutral</x-db.badge>
			<x-db.badge tone="navy">Navy</x-db.badge>
		</div>

		<x-db.eyebrow>Card + stat grid</x-db.eyebrow>
		<div style="margin:12px 0 32px;">
			<x-db.card title="Agency snapshot">
				<x-db.stat-grid>
					{{-- Value slot keeps the live hooks (id + prj_stat) --}}
					<x-db.stat label="Agencies" accent><span id="agencies_no" class="prj_stat">167</span></x-db.stat>
					<x-db.stat label="Modified budget" sub="FY27">$13.4B</x-db.stat>
					<x-db.stat label="Contracts">55,806</x-db.stat>
				</x-db.stat-grid>
			</x-db.card>
		</div>

		<x-db.eyebrow>Tabs</x-db.eyebrow>
		<div style="margin:12px 0 32px;">
			<x-db.tabs>
				<x-db.tab href="#" active>Overview</x-db.tab>
				<x-db.tab href="#">Headcount</x-db.tab>
				<x-db.tab href="#">Procurement</x-db.tab>
			</x-db.tabs>
		</div>

		<x-db.eyebrow>Table</x-db.eyebrow>
		<div style="margin:12px 0 32px;">
			<x-db.table-wrap>
				<x-db.table id="demoTable">
					<thead><tr><th>Vendor</th><th>Agency</th><th class="db-num">Award</th><th>Status</th></tr></thead>
					<tbody>
						<tr><td class="fw-semibold">Acme Builders</td><td>DOT</td><td class="db-num">$1,240,000</td><td><x-db.badge tone="success">Active</x-db.badge></td></tr>
						<tr><td class="fw-semibold">Skanska USA</td><td>DDC</td><td class="db-num">$980,500</td><td><x-db.badge tone="warning">Pending</x-db.badge></td></tr>
					</tbody>
				</x-db.table>
			</x-db.table-wrap>
		</div>

		<x-db.eyebrow>Search + alerts</x-db.eyebrow>
		<div style="margin:12px 0 16px; max-width:320px;">
			<x-db.search name="q" placeholder="Search agencies…" />
		</div>
		<x-db.alert tone="success" class="mb-2">Saved successfully.</x-db.alert>
		<x-db.alert tone="warning" class="mb-2">Some data may be incomplete.</x-db.alert>
		<x-db.alert tone="info" dismissible>Dismissible info alert.</x-db.alert>

		<x-db.eyebrow>Empty state</x-db.eyebrow>
		<div style="margin:12px 0 32px;">
			<x-db.empty icon="inbox" title="No results">Try a different filter or search term.</x-db.empty>
		</div>

	</div>
</div>
@endsection
