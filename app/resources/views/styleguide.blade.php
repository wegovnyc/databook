@extends('layout')

@section('menubar')
	@include('sub.menubar', ['active' => null])
@endsection

@section('head')
<style>
	/* Styleguide-specific layout (one-off doc page). Components shown use the live .db-* classes. */
	.sg-wrap { display: flex; gap: var(--db-space-5); align-items: flex-start; }
	.sg-side { flex: 0 0 220px; position: sticky; top: calc(var(--db-header-h) + var(--db-space-2)); align-self: flex-start; max-height: calc(100vh - var(--db-header-h) - var(--db-space-3)); overflow-y: auto; padding-bottom: var(--db-space-4); }
	.sg-side .sg-group { font-size: var(--db-text-3xs); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted); font-weight: var(--db-weight-bold); margin: var(--db-space-2) 0 var(--db-space-05); }
	.sg-side a { display: block; padding: 5px var(--db-space-1); font-size: var(--db-text-sm); color: var(--db-text-muted); border-left: 2px solid transparent; border-radius: 0 var(--db-radius-sm) var(--db-radius-sm) 0; }
	.sg-side a:hover { color: var(--db-primary); background: var(--db-navy-050); text-decoration: none; }
	.sg-main { flex: 1 1 auto; min-width: 0; }
	.sg-section { padding-top: var(--db-space-2); margin-bottom: var(--db-space-6); scroll-margin-top: calc(var(--db-header-h) + var(--db-space-2)); }
	.sg-section > h2 { font-size: var(--db-text-2xl); border-bottom: 2px solid var(--db-border); padding-bottom: var(--db-space-1); margin-bottom: var(--db-space-1); }
	.sg-note { color: var(--db-text-muted); font-size: var(--db-text-sm); max-width: 72ch; margin-bottom: var(--db-space-3); }
	.sg-sub { font-size: var(--db-text-3xs); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted); font-weight: var(--db-weight-bold); margin: var(--db-space-3) 0 var(--db-space-1); }
	.sg-swatches { display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--db-space-2); }
	@media (max-width: 900px) { .sg-swatches { grid-template-columns: repeat(2, 1fr); } .sg-side { display: none; } .sg-wrap { display: block; } }
	.sg-swatch { border: 1px solid var(--db-border); border-radius: var(--db-radius); overflow: hidden; }
	.sg-swatch .sg-chip { height: 64px; }
	.sg-swatch .sg-meta { padding: var(--db-space-1); }
	.sg-swatch .sg-name { font-weight: var(--db-weight-semibold); font-size: var(--db-text-2xs); }
	.sg-swatch .sg-val { font-family: var(--db-font-mono); font-size: var(--db-text-3xs); color: var(--db-text-muted); }
	.sg-demo { border: 1px solid var(--db-border); border-radius: var(--db-radius); padding: var(--db-space-3); background: var(--db-white); display: flex; flex-wrap: wrap; gap: var(--db-space-2); align-items: center; }
	.sg-demo.col { flex-direction: column; align-items: stretch; }
	.sg-type-row { display: flex; align-items: baseline; gap: var(--db-space-2); padding: var(--db-space-1) 0; border-bottom: 1px solid var(--db-gray-200); }
	.sg-type-row .sg-tok { flex: 0 0 150px; font-family: var(--db-font-mono); font-size: var(--db-text-3xs); color: var(--db-text-muted); }
	.sg-space-row { display: flex; align-items: center; gap: var(--db-space-2); margin-bottom: var(--db-space-05); }
	.sg-space-row .sg-tok { flex: 0 0 150px; font-family: var(--db-font-mono); font-size: var(--db-text-3xs); color: var(--db-text-muted); }
	.sg-space-bar { background: var(--db-accent); height: 14px; border-radius: 2px; }
	code.sg-code { font-family: var(--db-font-mono); font-size: var(--db-text-2xs); background: var(--db-navy-050); color: var(--db-primary); padding: 1px 6px; border-radius: var(--db-radius-sm); }
</style>
@endsection

@section('content')
<div class="inner_container">
	<div class="container" style="padding-block: var(--db-space-3) var(--db-space-6);">
		<div class="db-eyebrow">Databook Design System · v1.0</div>
		<h1>Tokens &amp; components</h1>
		<p class="db-page-lead">A lightweight token + component layer over Bootstrap 5. Everything here extends the live <code class="sg-code">--db-*</code> custom properties (navy <code class="sg-code">#162e51</code>) and <code class="sg-code">.db-*</code> classes — no new framework. This page <em>is</em> the styleguide; it supersedes the old Bootstrap-blue version.</p>

		<div class="sg-wrap mt-4">
			{{-- Sidebar --}}
			<nav class="sg-side">
				<div class="sg-group">Foundations</div>
				<a href="#color">Color</a>
				<a href="#type">Typography</a>
				<a href="#spacing">Spacing</a>
				<a href="#radius">Radius &amp; elevation</a>
				<div class="sg-group">Components</div>
				<a href="#buttons">Buttons</a>
				<a href="#badges">Badges &amp; tags</a>
				<a href="#stats">Stat cards</a>
				<a href="#tables">Data tables</a>
				<a href="#search">Search &amp; filters</a>
				<a href="#tabs">Tabs &amp; pagination</a>
				<a href="#meta">Metadata &amp; cards</a>
				<a href="#alerts">Alerts &amp; forms</a>
				<a href="#charts">Charts</a>
				<a href="#avatars">Avatars</a>
				<a href="#search-results">Search results</a>
				<a href="#org-chart">Org chart</a>
			</nav>

			{{-- Main --}}
			<div class="sg-main">

				{{-- COLOR --}}
				<section id="color" class="sg-section">
					<h2>Color</h2>
					<p class="sg-note">One navy ramp + one gray ramp + four semantic colors. The drifted one-off hexes from old inline styles all map back into these tokens.</p>

					<div class="sg-sub">Brand &amp; navy</div>
					<div class="sg-swatches">
						@foreach ([['navy-900','#0b1f3a'],['primary','#162e51'],['navy-600','#1f3a63'],['navy-100','#e7ecf3'],['navy-050','#f3f6fa']] as $c)
						<div class="sg-swatch"><div class="sg-chip" style="background: {{ $c[1] }};"></div><div class="sg-meta"><div class="sg-name">{{ $c[0] }}</div><div class="sg-val">{{ $c[1] }}</div></div></div>
						@endforeach
					</div>

					<div class="sg-sub">Links &amp; accent</div>
					<div class="sg-swatches">
						@foreach ([['link','#005ea2'],['link-hover','#004080'],['accent','#2491ff'],['accent-soft','#d3e6fb'],['brand (wordmark)','#ff941f']] as $c)
						<div class="sg-swatch"><div class="sg-chip" style="background: {{ $c[1] }};"></div><div class="sg-meta"><div class="sg-name">{{ $c[0] }}</div><div class="sg-val">{{ $c[1] }}</div></div></div>
						@endforeach
					</div>

					<div class="sg-sub">Neutrals</div>
					<div class="sg-swatches">
						@foreach ([['gray-050','#f9fafb'],['gray-100','#f0f2f4'],['gray-300','#dfe1e2'],['gray-600','#757575'],['gray-900','#171717']] as $c)
						<div class="sg-swatch"><div class="sg-chip" style="background: {{ $c[1] }};"></div><div class="sg-meta"><div class="sg-name">{{ $c[0] }}</div><div class="sg-val">{{ $c[1] }}</div></div></div>
						@endforeach
					</div>

					<div class="sg-sub">Semantic state</div>
					<div class="sg-swatches">
						@foreach ([['success','#2e8540'],['danger','#b50909'],['warning','#c2850c'],['info','#005ea2']] as $c)
						<div class="sg-swatch"><div class="sg-chip" style="background: {{ $c[1] }};"></div><div class="sg-meta"><div class="sg-name">{{ $c[0] }}</div><div class="sg-val">{{ $c[1] }}</div></div></div>
						@endforeach
					</div>
				</section>

				{{-- TYPOGRAPHY --}}
				<section id="type" class="sg-section">
					<h2>Typography</h2>
					<p class="sg-note">Public Sans (Inter fallback). USWDS-adjacent, rem-based scale (1rem = 16px). Mono is Roboto Mono for IDs/codes.</p>
					@foreach ([['--db-text-3xl','2.25rem','36 · H1'],['--db-text-2xl','1.875rem','30 · H2'],['--db-text-xl','1.5rem','24 · H3'],['--db-text-lg','1.25rem','20 · H4 / card title'],['--db-text-md','1.0625rem','17 · lead body'],['--db-text-base','1rem','16 · body'],['--db-text-sm','0.9375rem','15 · table body / controls'],['--db-text-xs','0.875rem','14 · metadata'],['--db-text-2xs','0.8125rem','13 · captions']] as $t)
					<div class="sg-type-row">
						<span class="sg-tok">{{ $t[0] }}</span>
						<span style="font-size: {{ $t[1] }}; font-weight: var(--db-weight-bold); color: var(--db-primary); line-height: 1.2;">The five boroughs</span>
						<span class="text-muted" style="font-size: var(--db-text-xs); margin-left:auto;">{{ $t[2] }}</span>
					</div>
					@endforeach
					<div class="mt-3" style="display:flex; gap: var(--db-space-3); flex-wrap:wrap;">
						<span style="font-weight:var(--db-weight-normal)">Regular 400</span>
						<span style="font-weight:var(--db-weight-medium)">Medium 500</span>
						<span style="font-weight:var(--db-weight-semibold)">Semibold 600</span>
						<span style="font-weight:var(--db-weight-bold)">Bold 700</span>
						<span style="font-family:var(--db-font-mono)">Roboto Mono 012345</span>
					</div>
				</section>

				{{-- SPACING --}}
				<section id="spacing" class="sg-section">
					<h2>Spacing</h2>
					<p class="sg-note">8px base, USWDS units. Use the <code class="sg-code">--db-space-*</code> tokens for padding, gaps, and margins instead of ad-hoc pixel values.</p>
					@foreach ([['--db-space-05','4px'],['--db-space-1','8px'],['--db-space-15','12px'],['--db-space-2','16px'],['--db-space-3','24px'],['--db-space-4','32px'],['--db-space-5','40px'],['--db-space-6','48px']] as $s)
					<div class="sg-space-row"><span class="sg-tok">{{ $s[0] }}</span><span class="sg-space-bar" style="width: {{ $s[1] }};"></span><span class="text-muted" style="font-size:var(--db-text-3xs)">{{ $s[1] }}</span></div>
					@endforeach
				</section>

				{{-- RADIUS & ELEVATION --}}
				<section id="radius" class="sg-section">
					<h2>Radius &amp; elevation</h2>
					<div class="sg-demo">
						<div style="text-align:center;"><div style="width:80px;height:56px;background:var(--db-navy-100);border-radius:var(--db-radius-sm);"></div><div class="sg-val mt-1">radius-sm · 4</div></div>
						<div style="text-align:center;"><div style="width:80px;height:56px;background:var(--db-navy-100);border-radius:var(--db-radius);"></div><div class="sg-val mt-1">radius · 8</div></div>
						<div style="text-align:center;"><div style="width:80px;height:56px;background:var(--db-navy-100);border-radius:var(--db-radius-lg);"></div><div class="sg-val mt-1">radius-lg · 12</div></div>
						<div style="text-align:center;"><div style="width:80px;height:56px;background:var(--db-white);box-shadow:var(--db-shadow-sm);border-radius:var(--db-radius);"></div><div class="sg-val mt-1">shadow-sm</div></div>
						<div style="text-align:center;"><div style="width:80px;height:56px;background:var(--db-white);box-shadow:var(--db-shadow-md);border-radius:var(--db-radius);"></div><div class="sg-val mt-1">shadow-md</div></div>
						<div style="text-align:center;"><div style="width:80px;height:56px;background:var(--db-white);box-shadow:var(--db-shadow-lg);border-radius:var(--db-radius);"></div><div class="sg-val mt-1">shadow-lg</div></div>
					</div>
				</section>

				{{-- BUTTONS --}}
				<section id="buttons" class="sg-section">
					<h2>Buttons</h2>
					<p class="sg-note"><code class="sg-code">.db-btn</code> + role + optional size. Focus ring = 3px accent-soft.</p>
					<div class="sg-demo">
						<button class="db-btn db-btn-primary">Primary</button>
						<button class="db-btn db-btn-outline">Outline</button>
						<button class="db-btn db-btn-ghost">Ghost</button>
						<button class="db-btn db-btn-primary db-btn-sm">Small</button>
						<button class="db-btn db-btn-primary db-btn-lg">Large</button>
						<button class="db-btn db-btn-primary" disabled>Disabled</button>
						<a class="db-icon-btn" title="icon button"><i class="bi bi-share"></i></a>
					</div>
				</section>

				{{-- BADGES & TAGS --}}
				<section id="badges" class="sg-section">
					<h2>Badges &amp; tags</h2>
					<p class="sg-note">Three distinct roles: <strong>status</strong> (<code class="sg-code">.db-badge</code>), <strong>category</strong> (<code class="sg-code">.db-type-label</code>), <strong>keyword</strong> (<code class="sg-code">.db-tag</code>).</p>
					<div class="sg-demo">
						<span class="db-badge db-badge-success">Active</span>
						<span class="db-badge db-badge-danger">Closed</span>
						<span class="db-badge db-badge-warning">Pending</span>
						<span class="db-badge db-badge-info">Info</span>
						<span class="db-badge db-badge-neutral">Neutral</span>
						<span class="db-badge db-badge-navy">Navy</span>
						<span class="db-type-label">Mayoral Agency</span>
						<span class="db-tag">budget line</span>
					</div>
				</section>

				{{-- STAT CARDS --}}
				<section id="stats" class="sg-section">
					<h2>Stat cards</h2>
					<p class="sg-note"><code class="sg-code">.db-stat-grid</code> auto-fits <code class="sg-code">.db-stat</code> cards. <code class="sg-code">.is-accent</code> adds a left rail; keep <code class="sg-code">.prj_stat</code>/<code class="sg-code">.gs_*</code> hooks on the value.</p>
					<div class="db-stat-grid">
						<div class="db-stat"><div class="db-stat-label">Employees</div><div class="db-stat-value">5,512</div><div class="db-stat-sub">FY25</div></div>
						<div class="db-stat is-accent"><div class="db-stat-label">Budget</div><div class="db-stat-value">$1.3B</div><div class="db-stat-sub">adopted</div></div>
						<div class="db-stat"><div class="db-stat-label">Contracts</div><div class="db-stat-value">1,284</div></div>
						<div class="db-stat"><div class="db-stat-label">Loading</div><div class="db-stat-value is-loading">&nbsp;</div></div>
					</div>
				</section>

				{{-- DATA TABLES --}}
				<section id="tables" class="sg-section">
					<h2>Data tables</h2>
					<p class="sg-note">Add <code class="sg-code">.db-table</code> to the <code class="sg-code">&lt;table&gt;</code>; for DataTables, keep the element id + <code class="sg-code">dom</code>/colVis and the bridge CSS skins it.</p>
					<div class="db-table-wrap">
						<div class="db-table-toolbar"><span class="db-table-count">Showing <strong>3</strong> rows</span></div>
						<div class="table-responsive">
							<table class="db-table">
								<thead><tr><th>Vendor</th><th>Agency</th><th class="db-num">Amount</th><th>Status</th></tr></thead>
								<tbody>
									<tr><td class="fw-semibold"><a href="#tables">Acme Builders</a></td><td>DOT</td><td class="db-num">$1,240,000</td><td><span class="db-badge db-badge-success">Active</span></td></tr>
									<tr><td class="fw-semibold"><a href="#tables">Skanska USA</a></td><td>DDC</td><td class="db-num">$980,500</td><td><span class="db-badge db-badge-warning">Pending</span></td></tr>
									<tr><td class="fw-semibold"><a href="#tables">Tutor Perini</a></td><td>SCA</td><td class="db-num">$640,000</td><td><span class="db-badge db-badge-neutral">Closed</span></td></tr>
								</tbody>
							</table>
						</div>
					</div>
				</section>

				{{-- SEARCH & FILTERS --}}
				<section id="search" class="sg-section">
					<h2>Search &amp; filters</h2>
					<p class="sg-note"><code class="sg-code">.db-filter-bar</code> with <code class="sg-code">.db-search</code> + <code class="sg-code">.db-field</code> controls.</p>
					<div class="db-filter-bar">
						<div class="db-search"><i class="bi bi-search"></i><input type="search" placeholder="Search…" aria-label="Search"></div>
						<div class="db-field"><label>Fiscal Year</label><select><option>FY25</option><option>FY24</option></select></div>
						<button class="db-btn db-btn-primary db-btn-sm"><i class="bi bi-search"></i> Search</button>
					</div>
				</section>

				{{-- TABS & PAGINATION --}}
				<section id="tabs" class="sg-section">
					<h2>Tabs &amp; pagination</h2>
					<p class="sg-note">Flat <code class="sg-code">.db-tab</code> for sections; <code class="sg-code">.db-tab-dd</code> for dropdown categories (org profiles). Click the dropdown to test.</p>
					<div class="db-tabs-wrap">
						<nav class="db-tabs">
							<a class="db-tab is-active" href="#tabs">Overview</a>
							<a class="db-tab" href="#tabs">Headcount</a>
							<div class="db-tab-dd">
								<button type="button" class="db-tab" data-dd aria-haspopup="true" aria-expanded="false" aria-controls="sg-dd">Procurement <i class="bi bi-chevron-down db-caret"></i></button>
								<div class="db-tab-menu" id="sg-dd" role="menu">
									<a role="menuitem" href="#tabs">Contracts</a>
									<a role="menuitem" href="#tabs">Vendors</a>
									<a role="menuitem" href="#tabs">Solicitations</a>
								</div>
							</div>
						</nav>
					</div>
					<div class="mt-3 db-pagination">
						<span class="db-page is-disabled">Previous</span>
						<a class="db-page is-active" href="#tabs">1</a>
						<a class="db-page" href="#tabs">2</a>
						<a class="db-page" href="#tabs">3</a>
						<a class="db-page" href="#tabs">Next</a>
					</div>
				</section>

				{{-- METADATA & CARDS --}}
				<section id="meta" class="sg-section">
					<h2>Metadata &amp; cards</h2>
					<div class="row">
						<div class="col-md-6 mb-3">
							<div class="db-card is-hoverable"><div class="db-card-body">
								<div class="db-card-title">Card title</div>
								<p class="text-muted" style="margin:0;">A <code class="sg-code">.db-card</code> with <code class="sg-code">.is-hoverable</code> for clickable cards.</p>
							</div></div>
						</div>
						<div class="col-md-6 mb-3">
							<div class="db-card"><div class="db-card-body">
								<dl class="db-meta-list">
									<dt>Agency code</dt><dd>841</dd>
									<dt>Established</dt><dd>1977</dd>
									<dt>Contract ID</dt><dd class="is-mono">CT1-826-20258801735</dd>
								</dl>
							</div></div>
						</div>
					</div>
				</section>

				{{-- ALERTS & FORMS --}}
				<section id="alerts" class="sg-section">
					<h2>Alerts &amp; forms</h2>
					<div class="db-alert db-alert-success mb-2"><i class="bi bi-check-circle"></i><div class="db-alert-body">Saved successfully.</div></div>
					<div class="db-alert db-alert-warning mb-2"><i class="bi bi-exclamation-triangle"></i><div class="db-alert-body">Some data may be incomplete.</div></div>
					<div class="db-alert db-alert-danger mb-3"><i class="bi bi-exclamation-circle"></i><div class="db-alert-body">Something went wrong.</div></div>
					<div class="sg-demo col" style="max-width:420px;">
						<div class="db-field">
							<label>Email <span class="db-required">*</span></label>
							<input class="db-input" type="email" placeholder="you@example.com">
							<div class="db-field-help">We'll never share it.</div>
						</div>
						<div class="db-field is-invalid">
							<label>Invalid field</label>
							<input class="db-input is-invalid" type="text" value="bad value">
							<div class="db-field-error"><i class="bi bi-exclamation-circle"></i> This field has an error.</div>
						</div>
					</div>
				</section>

				{{-- CHARTS --}}
				<section id="charts" class="sg-section">
					<h2>Charts</h2>
					<p class="sg-note">Chart.js is themed by the <code class="sg-code">DBChart</code> factory (<code class="sg-code">js/db-charts.js</code>): call <code class="sg-code">DBChart.apply(Chart)</code> once, then use <code class="sg-code">DBChart.navy</code> / <code class="sg-code">DBChart.accent</code> / <code class="sg-code">DBChart.palette</code> + <code class="sg-code">DBChart.money()</code>. Series 1 = navy, series 2 = accent.</p>
					<div class="sg-demo">
						<span class="db-chart-legend"><span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:var(--db-primary);"></span> Series 1 · navy</span>
						<span class="db-chart-legend"><span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:var(--db-accent);"></span> Series 2 · accent</span>
					</div>
				</section>

				<section id="avatars" class="sg-section">
					<h2>Avatars</h2>
					<p class="sg-note">Circular, initials fallback. <code class="sg-code">.db-avatar</code> + <code class="sg-code">.db-avatar-lg</code> / <code class="sg-code">.db-avatar-sm</code>. Used on People.</p>
					<div class="sg-demo" style="align-items:center; gap:var(--db-space-2);">
						<span class="db-avatar db-avatar-lg">JD</span>
						<span class="db-avatar" style="width:52px;height:52px;">MR</span>
						<span class="db-avatar db-avatar-sm">AB</span>
					</div>
				</section>

				<section id="search-results" class="sg-section">
					<h2>Search results</h2>
					<p class="sg-note">Mixed-type global search: a type-filter rail (<code class="sg-code">.db-result-rail</code>) + result rows (<code class="sg-code">.db-result</code>).</p>
					<div class="sg-demo" style="display:grid; grid-template-columns:200px 1fr; gap:var(--db-space-3); align-items:start;">
						<div class="db-result-rail">
							<button class="db-result-type is-active">All <span class="count">128</span></button>
							<button class="db-result-type">Organizations <span class="count">42</span></button>
							<button class="db-result-type">People <span class="count">61</span></button>
							<button class="db-result-type">Contracts <span class="count">25</span></button>
						</div>
						<div style="border:1px solid var(--db-border); border-radius:var(--db-radius); overflow:hidden;">
							<div class="db-result">
								<div class="db-result-ico"><i class="bi bi-building"></i></div>
								<div class="db-result-main">
									<div class="db-result-title"><a href="#search-results">Fire Department</a></div>
									<div class="db-result-meta">Organization · City Agency</div>
									<div class="db-result-snippet">891 contracts · <mark>FDNY</mark> · budget $5.2B</div>
								</div>
								<div class="db-result-aside"><span class="db-badge db-badge-navy">Org</span></div>
							</div>
							<div class="db-result">
								<div class="db-result-ico"><i class="bi bi-person"></i></div>
								<div class="db-result-main">
									<div class="db-result-title"><a href="#search-results">Jane Doe</a></div>
									<div class="db-result-meta">Person · Commissioner</div>
								</div>
								<div class="db-result-aside"><span class="db-badge db-badge-neutral">Person</span></div>
							</div>
						</div>
					</div>
				</section>

				<section id="org-chart" class="sg-section">
					<h2>Org chart</h2>
					<p class="sg-note">Two views. Indented tree (<code class="sg-code">.db-tree</code> / <code class="sg-code">.db-node</code>) is the mobile-friendly default; connected view (<code class="sg-code">.db-orgtree</code>) scrolls horizontally. Used on Organizations.</p>
					<div class="sg-demo" style="display:block;">
						<div class="db-orgchart">
							<ul class="db-tree">
								<li>
									<div class="db-node is-root">
										<button class="db-node-toggle"><i class="bi bi-chevron-down"></i></button>
										<span class="db-node-ico"><i class="bi bi-building"></i></span>
										<div class="db-node-main"><div class="db-node-name"><a href="#org-chart">Office of the Mayor</a></div><div class="db-node-meta">Executive</div></div>
										<div class="db-node-stat">42 sub-agencies</div>
									</div>
									<ul>
										<li><div class="db-node"><span class="db-node-ico"><i class="bi bi-bank"></i></span><div class="db-node-main"><div class="db-node-name"><a href="#org-chart">Fire Department</a></div><div class="db-node-meta">City Agency</div></div><div class="db-node-stat">11,200 staff</div></div></li>
										<li><div class="db-node"><span class="db-node-ico"><i class="bi bi-bank"></i></span><div class="db-node-main"><div class="db-node-name"><a href="#org-chart">Dept. of Transportation</a></div><div class="db-node-meta">City Agency</div></div><div class="db-node-stat">5,500 staff</div></div></li>
									</ul>
								</li>
							</ul>
						</div>
					</div>
				</section>

			</div>
		</div>
	</div>
</div>
@endsection
