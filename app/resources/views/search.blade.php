@extends('layout')

@section('head')
	<meta name="robots" content="noindex,nofollow">
@endsection

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
@php
	$icons = [
		'organizations' => 'bi-building', 'people' => 'bi-person',
		'titles' => 'bi-briefcase', 'contracts' => 'bi-file-earmark-text',
		'solicitations' => 'bi-megaphone', 'projects' => 'bi-cone-striped',
		'schools' => 'bi-mortarboard', 'notices' => 'bi-newspaper',
	];
	$groups = $data['groups'] ?? [];
@endphp

{{-- Navy hero with the search box --}}
<div class="db-hero">
	<div class="inner_container">
		<div class="container db-hero-inner is-centered">
			<div class="db-hero-copy">
				<div class="db-eyebrow" style="color:var(--db-accent);">Search</div>
				<h1>Search Databook</h1>
				<form class="db-hero-search" action="{{ route('search') }}" method="get" role="search" style="margin-top:var(--db-space-2);">
					<i class="bi bi-search"></i>
					<input type="search" name="q" value="{{ $q }}" placeholder="Search organizations, people, contracts, titles…" aria-label="Search Databook" autofocus>
				</form>
			</div>
		</div>
	</div>
</div>

<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-5);">
		@if ($q === '' || mb_strlen($q) < 2)
			<div class="db-empty">
				<div class="db-empty-icon"><i class="bi bi-search"></i></div>
				<div class="db-empty-title">Search across NYC government</div>
				<div class="db-empty-text">Organizations, people, civil-service titles, contracts, solicitations, capital projects, schools, and notices — type at least two characters.</div>
			</div>
		@elseif (empty($groups))
			<div class="db-empty">
				<div class="db-empty-icon"><i class="bi bi-search"></i></div>
				<div class="db-empty-title">No results for “{{ $q }}”</div>
				<div class="db-empty-text">Try a different spelling, an acronym (e.g. FDNY), or a broader term.</div>
			</div>
		@else
			<div class="db-search-layout" style="display:grid; grid-template-columns:220px 1fr; gap:var(--db-space-3); align-items:start;">
				{{-- Type-filter rail --}}
				<div class="db-result-rail" id="search-rail">
					<button class="db-result-type is-active" data-type="all">All <span class="count">{{ $data['total'] ?? 0 }}</span></button>
					@foreach ($groups as $g)
						<button class="db-result-type" data-type="{{ $g['type'] }}">{{ $g['label'] }} <span class="count">{{ $g['count'] }}</span></button>
					@endforeach
				</div>

				{{-- Grouped results --}}
				<div id="search-results">
					@foreach ($groups as $g)
						<section class="search-group" data-type="{{ $g['type'] }}" style="margin-bottom:var(--db-space-4);">
							<div class="db-eyebrow" style="margin-bottom:var(--db-space-1);">{{ $g['label'] }} <span style="color:var(--db-text-muted);">· {{ $g['count'] }}</span></div>
							<div style="border:1px solid var(--db-border); border-radius:var(--db-radius); overflow:hidden; background:#fff;">
								@foreach ($g['results'] as $r)
									<div class="db-result">
										<div class="db-result-ico"><i class="bi {{ $icons[$g['type']] ?? 'bi-dot' }}"></i></div>
										<div class="db-result-main">
											<div class="db-result-title">
												<a href="{{ $r['url'] }}"@if (!empty($r['external'])) target="_blank" rel="nofollow"@endif>{{ $r['title'] }}@if (!empty($r['external'])) <i class="bi bi-box-arrow-up-right" style="font-size:12px;"></i>@endif</a>
											</div>
											@if (!empty($r['meta']))<div class="db-result-meta">{{ $r['meta'] }}</div>@endif
										</div>
									</div>
								@endforeach
							</div>
						</section>
					@endforeach
				</div>
			</div>
		@endif
	</div>
</div>

<script>
(function () {
	// Rail filters which type-groups show; "All" shows everything. No re-query.
	var rail = document.getElementById('search-rail');
	if (!rail) return;
	rail.addEventListener('click', function (e) {
		var btn = e.target.closest('.db-result-type');
		if (!btn) return;
		rail.querySelectorAll('.db-result-type').forEach(function (b) { b.classList.remove('is-active'); });
		btn.classList.add('is-active');
		var t = btn.getAttribute('data-type');
		document.querySelectorAll('#search-results .search-group').forEach(function (sec) {
			sec.style.display = (t === 'all' || sec.getAttribute('data-type') === t) ? '' : 'none';
		});
	});
})();
</script>
@endsection
