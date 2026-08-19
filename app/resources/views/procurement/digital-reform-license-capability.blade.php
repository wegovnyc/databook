@extends('layout')

@section('head')
{{-- Published with the rest of the license analysis 2026-08-11. ⚠ This page was
     nearly LEFT BEHIND on noindex while its parents were published — and family
     pages link straight into it via the Function link, so it would have been
     reachable-but-unindexed: exactly the incoherent middle state that publishing
     was meant to end. If the analysis is ever unpublished, unpublish this too. --}}
<style>
    .db-page-lead { max-width: none; }
    .lic-note { background: var(--db-gray-050, #f8f9fb); border-left: 3px solid var(--db-brand, #d9730d);
                padding: var(--db-space-3); margin-bottom: var(--db-space-4); font-size: var(--db-text-sm); }
    .lic-h2 { font-size: var(--db-text-lg); margin: 0; }
    .lic-num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
    .lic-sub { font-size: var(--db-text-2xs); color: var(--db-text-muted); }
    .lic-prod { font-size: var(--db-text-2xs); color: var(--db-text-muted); display: block; white-space: normal; }
</style>
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    // ⚠ Plain text only — echoed through Blade escaping.
    $sum = $cap['summary'] ?? [];
    $products = $cap['products'] ?? [];
    $agencies = $cap['agencies'] ?? [];
    $rows = $cap['contracts'] ?? [];
    $capKey = $cap['capability'] ?? '';

    $fmtM = function ($v) {
        $v = (float) $v;
        if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
        if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
        if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
        return '$' . number_format($v, 0);
    };
    // ⚠ NO LABEL MAP HERE. The label is served by the API, which reads it from
    // api/seed/license_capability_vocab.csv. This file and the index page each
    // carried their own partial copy of that mapping and BOTH had fallen behind
    // the seed -- 18 of the 46 tags in use rendered as raw kebab-case keys on a
    // published page, because labelling a new tag meant editing two views nobody
    // thought to open. Falls back to the raw key if the API is older.
    $label = $cap['label'] ?? ($capKey !== '' ? $capKey : 'Software function');
    // Both factors matter: many products across many agencies is fragmentation;
    // many agencies on two products is a citywide agreement working correctly.
    $fragmented = ($sum['products'] ?? 0) >= 5 && ($sum['agencies'] ?? 0) >= 3;
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ route('research.digital-reform.licenses') }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Software Licenses</a>
        <div class="db-eyebrow">Procurement &middot; Digital Services <span class="db-analysis-badge"><i class="bi bi-stars"></i> Analysis</span></div>
        <h1>{{ $label }}</h1>

        @if($capKey === 'other')
            <div class="lic-note">
                <strong><i class="bi bi-question-circle"></i> Not a function.</strong>
                These contracts describe themselves too vaguely to place in any function. They are
                grouped so the volume is visible, not because they are related to each other.
            </div>
        @else
            <p class="db-page-lead">
                <strong>{{ number_format($sum['products'] ?? 0) }} different products</strong> bought by
                {{ number_format($sum['agencies'] ?? 0) }} agencies to do this one job, across
                {{ number_format($sum['contracts'] ?? 0) }} contracts.
            </p>
        @endif

        <div class="db-stat-grid mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Distinct products</div>
                <div class="db-stat-value">{{ number_format($sum['products'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Agencies</div>
                <div class="db-stat-value">{{ number_format($sum['agencies'] ?? 0) }}</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Total value</div>
                <div class="db-stat-value">{{ $fmtM($sum['value'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Vendors</div>
                <div class="db-stat-value">{{ number_format($sum['vendors'] ?? 0) }}</div>
            </div>
        </div>

        @if($fragmented && $capKey !== 'other')
        <div class="lic-note">
            <strong><i class="bi bi-question-circle"></i> Worth asking:</strong>
            is there already a citywide agreement these should ride, or should there be?
            <i class="bi bi-exclamation-triangle"></i> Many products across many agencies is a consolidation question, not an answer &mdash;
            some of these will be genuinely different tools that happen to share a function label,
            and the label itself is AI-assigned from contract text.
        </div>
        @endif

        <div class="db-table-wrap mb-5">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-box-seam"></i> The products</h2>
            </div>
            <table class="db-table">
                <thead>
                    <tr><th>Product</th><th class="lic-num">Contracts</th><th class="lic-num">Agencies</th><th class="lic-num">Value</th><th>Purchase type</th></tr>
                </thead>
                <tbody>
                @foreach($products as $p)
                    <tr>
                        <td>
                            @if(!empty($p['slug']))
                                <a href="{{ route('research.digital-reform.license-family', ['slug' => $p['slug']]) }}"><strong>{{ $p['key'] }}</strong></a>
                            @else
                                <strong>{{ $p['key'] }}</strong>
                            @endif
                            @if(!empty($p['summary']))
                                <span class="lic-prod">{{ $p['summary'] }}</span>
                            @endif
                        </td>
                        <td class="lic-num">{{ number_format($p['contracts']) }}</td>
                        <td class="lic-num">{{ number_format($p['agencies']) }}</td>
                        <td class="lic-num">{{ $fmtM($p['value']) }}</td>
                        <td class="lic-sub">{{ $p['purchase_class'] ?? '' }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>

        <div class="db-table-wrap mb-5">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-building"></i> Agencies buying it</h2>
            </div>
            <table class="db-table">
                <thead><tr><th>Agency</th><th class="lic-num">Contracts</th><th class="lic-num">Products</th><th class="lic-num">Value</th></tr></thead>
                <tbody>
                @foreach($agencies as $a)
                    <tr>
                        <td><a href="{{ route('agency.procurement', ['name' => $a['key']]) }}">{{ $a['key'] }}</a></td>
                        <td class="lic-num">{{ number_format($a['contracts']) }}</td>
                        <td class="lic-num">{{ number_format($a['product_count'] ?? count($a['products'] ?? [])) }}</td>
                        <td class="lic-num">{{ $fmtM($a['value']) }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>

        <div class="lic-note">
            <strong><i class="bi bi-info-circle"></i> How this grouping is made</strong>
            Function tags are assigned by AI from the descriptions the City recorded on each
            contract, against a fixed vocabulary, and are <strong>not human-reviewed</strong>. A
            wrong tag puts a product in the wrong comparison.
            <i class="bi bi-exclamation-triangle"></i> NYC already maintains a commodity taxonomy and applies it to about a quarter of all
            contracts &mdash; but <strong>none</strong> of the software licenses, because those codes
            live on solicitations and license purchases rarely produce one. This page reconstructs
            what the City already knows.
        </div>
    </div>
</div>
@endsection
