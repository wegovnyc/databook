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

{{--
    Org-profile procurement section. Renders the SAME shared design-system body as
    the standalone /procurement/agency/{name} page (procurement.partials.agency_body)
    so the two agency surfaces can't drift. The org header above provides the org
    identity + section nav; the body is the full procurement overview.
    (Previously each procurement-* subsection rendered its own stale Bootstrap
    markup — now unified onto the `.db-*` design system.)
--}}
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        @if($isNycha ?? false)
            {{-- NYCHA: separate authority — Finances & Procurement unified here.
                 Tabs = sub-nav (Finances Overview + the four NYCHA domains +
                 Council Funding); flag explains the difference; cards deep-link
                 into each domain (all org-profile URLs). --}}
            <div class="db-eyebrow">Finances &amp; Procurement</div>
            <h1>Finances Overview</h1>
            <p class="db-page-lead">Budget, revenue, contracts, spending, and Council discretionary funding for the New York City Housing Authority.</p>
            @include('procurement.partials.nycha_flag')
            @include('procurement.partials.nycha_cards')
        @else
            <div class="db-eyebrow">Procurement</div>
            <h1>{{ $org['name'] }}</h1>
            <p class="db-page-lead">Procurement overview — contracts, solicitations, vendors, and spending.</p>
            @include('procurement.partials.agency_body')
        @endif

    </div>
</div>

{{-- The org nav has one item per procurement subsection; the body shows the full
     overview, so scroll to the section matching the clicked nav item. --}}
@if(($subsection ?? 'highlights') !== 'highlights')
<script>
document.addEventListener('DOMContentLoaded', function () {
    var el = document.getElementById(@json($subsection));
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
});
</script>
@endif
@endsection
