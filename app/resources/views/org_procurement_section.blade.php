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

        <div class="db-eyebrow">Procurement</div>
        <h1>{{ $org['name'] }}</h1>
        <p class="db-page-lead">Procurement overview — contracts, solicitations, vendors, and spending.</p>

        @include('procurement.partials.agency_body')

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
