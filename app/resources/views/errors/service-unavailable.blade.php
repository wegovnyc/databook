@extends('layout')

@section('head')
	<meta name="description" content="Temporarily unavailable — Databook.NYC" />
	{{-- Auto-retry: the API is briefly unreachable (e.g. a routine deploy restart),
	     so reload this same URL shortly instead of stranding the visitor on an error. --}}
	<meta http-equiv="refresh" content="5">
@endsection

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-5);">

		<div class="db-empty" style="max-width: 640px; margin: 0 auto;">
			<div class="db-empty-icon"><i class="bi bi-arrow-clockwise"></i></div>
			<div class="db-empty-title" style="font-size: var(--db-text-xl);">Just a moment…</div>
			<p class="db-empty-text" style="max-width: 48ch; margin: 0 auto var(--db-space-3);">
				Databook is briefly unavailable — usually a routine update that clears in a few seconds.
				This page will retry automatically; you don't need to do anything.
			</p>
			<div class="mb-3">
				<a href="" class="db-btn db-btn-primary"><i class="bi bi-arrow-clockwise me-1"></i>Retry now</a>
			</div>
		</div>

	</div>
</div>
@endsection
