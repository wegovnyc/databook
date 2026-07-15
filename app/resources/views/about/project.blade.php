@extends('layout')

@section('head')
	<meta name="description" content="About the Databook.NYC project - normalizing, joining and serving NYC government data since 2017." />
@endsection

@section('menubar')
	@include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

		{{-- Migrated onto <x-db.*> components (Phase B proof-of-adoption).
		     Also fixes 6 invisible Font Awesome icons -> Bootstrap Icons. --}}
		<x-db.eyebrow>About</x-db.eyebrow>
		<h1>The Project</h1>
		<p class="db-page-lead" style="max-width: none;">
			New York City's government has released over 3,000 datasets in the NYC Open Data portal thanks to the work of the Mayor's Office of Data Analytics (MODA). Many of these datasets are updated at regular intervals ranging from once a day to once a year. The purpose of this project is to integrate these automatically updated datasets to create an understandable view inside city government.
		</p>

		<h4 class="mt-5 mb-3">Explore</h4>
		@php
			$links = [
				['url' => route('about.data'),   'icon' => 'heart-pulse',   'title' => 'Data Health',     'desc' => 'Monitor dataset freshness, detect stale data, and track unmapped entities across all sources.'],
				['url' => route('about.tables'), 'icon' => 'database',      'title' => 'Database Tables', 'desc' => 'Browse all database tables with row counts, column details, and schema information.'],
				['url' => route('about.log'),    'icon' => 'clock-history', 'title' => 'Ingestion Log',   'desc' => 'View the history of data imports, updates, and pipeline activity.'],
				['url' => route('mcp'),          'icon' => 'plug',          'title' => 'MCP',             'desc' => 'Connect to Databook via the Model Context Protocol for AI-powered data access.'],
				['url' => '/styleguide',         'icon' => 'palette',       'title' => 'Styleguide',      'desc' => 'Design system, component library, and visual standards for Databook.'],
				['url' => route('blog'),         'icon' => 'newspaper',     'title' => 'Blog',            'desc' => 'Updates, analyses, and news from the Databook team.'],
			];
		@endphp
		<div class="row">
			@foreach($links as $l)
				<div class="col-md-4 mb-3">
					<x-db.card hoverable :href="$l['url']" class="h-100">
						<div class="db-card-title"><x-db.icon name="{{ $l['icon'] }}" class="me-2" style="color: var(--db-accent);" /> {{ $l['title'] }}</div>
						<p class="mb-0" style="color: var(--db-text-muted); font-size: var(--db-text-sm);">{{ $l['desc'] }}</p>
					</x-db.card>
				</div>
			@endforeach
		</div>

		<p class="db-prose mt-5" style="color: var(--db-text-muted); max-width: none;">
			Databook is a nonprofit project of
			<a href="https://wegov.nyc" target="_blank" rel="noopener">WeGov.NYC</a>, built and maintained by
			<a href="https://sarapis.org" target="_blank" rel="noopener">Sarapis</a>, a 501(c)(3) nonprofit
			organization, and is not affiliated with the City of New York.
		</p>

	</div>
</div>
@endsection
