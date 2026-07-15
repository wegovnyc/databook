@extends('layout')

@section('head')
	<meta name="description" content="Page not found — Databook.NYC" />
@endsection

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-5);">

		<div class="db-empty" style="max-width: 640px; margin: 0 auto;">
			<div class="db-empty-icon"><i class="bi bi-compass"></i></div>
			<div class="db-empty-title" style="font-size: var(--db-text-xl);">Page not found</div>
			<p class="db-empty-text" style="max-width: 46ch; margin: 0 auto var(--db-space-3);">
				The page may have moved, or the record you're looking for isn't in Databook.
				Try a search, or head back to one of the main sections.
			</p>

			{{-- Search — internal federated search (same as the header) --}}
			<form class="db-search" action="{{ route('search') }}" method="get" role="search" style="margin: 0 auto var(--db-space-3);">
				<i class="bi bi-search"></i>
				<input type="search" name="q" placeholder="Search Databook…" aria-label="Search Databook">
			</form>

			{{-- Recovery links --}}
			<div class="mb-3">
				<a href="{{ route('root') }}" class="db-btn db-btn-primary"><i class="bi bi-house-door me-1"></i>Go home</a>
			</div>

			<div class="d-flex flex-wrap justify-content-center align-items-center gap-2">
				<span class="db-tag">Popular</span>
				<a href="{{ route('orgs') }}">Organizations</a>
				<a href="{{ route('people') }}">People</a>
				<a href="{{ route('procurement.index') }}">Procurement</a>
				<a href="{{ route('notices') }}">Notices</a>
			</div>
		</div>

	</div>
</div>
@endsection
