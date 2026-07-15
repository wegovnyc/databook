@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
{{--
    Standalone agency procurement page (/procurement/agency/{name}).
    Body is the shared design-system partial so this can never drift from the
    org-profile procurement section. After the agency-profile merge this route
    redirects into the org profile when the agency resolves to a wegov_orgs id;
    this view remains the fallback for agencies with no org record — so it carries
    its own navy hero (the org-profile path uses sub.orgheader instead).
--}}
<div class="db-hero">
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                <div class="db-eyebrow" style="color: var(--db-accent);">Agency</div>
                <h1>{{ $agency['name'] ?? 'Agency' }}</h1>
                <p style="max-width: 62ch; font-size: var(--db-text-lg); line-height: 1.5; color: var(--db-text-on-navy-muted); margin: var(--db-space-2) 0 0;">Procurement overview — contracts, solicitations, vendors, and actual Checkbook spending for {{ $agency['name'] ?? 'this agency' }}.</p>
                <form action="{{ route('procurement.transactions.search') }}" method="GET" style="margin-top: var(--db-space-4); max-width: 620px;">
                    <input type="hidden" name="agency" value="{{ $agency['name'] ?? '' }}">
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input type="search" name="q" placeholder="Search this agency's payments…" aria-label="Search this agency's spending" autocomplete="off">
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">

        @include('procurement.partials.agency_body')

    </div>
</div>
@endsection
