@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@php
    $compact = function ($n) {
        $n = (float) $n;
        if ($n >= 1e9) return '$' . number_format($n / 1e9, 1) . 'B';
        if ($n >= 1e6) return '$' . number_format($n / 1e6, 1) . 'M';
        if ($n >= 1e3) return '$' . number_format($n / 1e3, 0) . 'K';
        return '$' . number_format($n);
    };
    $pct = fn ($x) => number_format(((float) $x) * 100, 1) . '%';

    // One config row per domain drives the four hub cards. `stat`/`sub` are
    // rendered from each domain's own summary, so a card degrades to a
    // "not yet available" state on its own when its Parquet is absent.
    $bt = $budget['totals'] ?? [];
    $rt = $revenue['totals'] ?? [];
    $ct = $contracts['totals'] ?? [];
    $st = $spending['totals'] ?? [];

    $cards = [
        [
            'label' => 'Expense Budget',
            'icon'  => 'bi-wallet2',
            'href'  => route('procurement.nycha.budget'),
            'avail' => $budget['available'] ?? false,
            'stat'  => $compact($bt['committed'] ?? 0),
            'sub'   => 'committed · FY' . ($budget['latest_year'] ?? '—') . ' · ' . $pct($bt['utilization'] ?? 0) . ' spent',
            'desc'  => 'Adopted vs modified vs committed vs actual spending, by responsibility center (developments &amp; functional units) and expense category.',
        ],
        [
            'label' => 'Revenue',
            'icon'  => 'bi-cash-coin',
            'href'  => route('procurement.nycha.revenue'),
            'avail' => $revenue['available'] ?? false,
            'stat'  => $compact($rt['recognized'] ?? 0),
            'sub'   => 'recognized · FY' . ($revenue['latest_year'] ?? '—') . ' · ' . $pct($rt['realization'] ?? 0) . ' of budget',
            'desc'  => 'Where NYCHA money comes from — recognized vs budgeted revenue by funding source and revenue category (largely federal subsidies and tenant rent).',
        ],
        [
            'label' => 'Contracts',
            'icon'  => 'bi-file-earmark-text',
            'href'  => route('procurement.nycha.contracts'),
            'avail' => $contracts['available'] ?? false,
            'stat'  => $compact($ct['current'] ?? 0),
            'sub'   => number_format($ct['contracts'] ?? 0) . ' contracts · ' . $pct($ct['utilization'] ?? 0) . ' invoiced',
            'desc'  => 'Registered NYCHA contracts and their current value, top vendors, and how much has been invoiced against them to date.',
        ],
        [
            'label' => 'Spending',
            'icon'  => 'bi-receipt',
            'href'  => route('procurement.nycha.spending'),
            'avail' => $spending['available'] ?? false,
            'stat'  => $compact($st['spending'] ?? 0),
            'sub'   => 'spent · FY' . ($spending['latest_year'] ?? '—'),
            'desc'  => 'Actual check-level payments by expense category, funding source and development — including a spend-by-development view unique to Databook.',
        ],
    ];
@endphp

@section('content')
<div class="db-hero">
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                <div class="db-eyebrow" style="color: var(--db-accent);">Procurement · NYCHA</div>
                <h1>NYC Housing Authority @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h1>
                <p style="max-width: 68ch; font-size: var(--db-text-lg); line-height: 1.5; color: var(--db-text-on-navy-muted); margin: var(--db-space-2) 0 0;">The New York City Housing Authority (NYCHA) is the largest public-housing landlord in North America and a separate, largely federally-funded authority — so its finances sit outside the City's operating budget. These four domains cover NYCHA's money end to end. Sourced from <a href="https://www.checkbooknyc.com" target="_blank" rel="noopener" style="color: var(--db-on-dark-accent);">Checkbook NYC</a> (Office of the Comptroller).</p>
            </div>
        </div>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">

        @include('procurement.partials.nycha_tabs')

        <div class="row">
            @foreach($cards as $c)
            <div class="col-md-6 mb-4">
                @if($c['avail'])
                <x-db.card :href="$c['href']" hoverable class="h-100">
                    <div class="db-eyebrow" style="color: var(--db-text-muted); display: flex; align-items: center; gap: var(--db-space-1);">
                        <i class="bi {{ $c['icon'] }}"></i> {{ $c['label'] }}
                    </div>
                    <div class="db-stat-value" style="margin: var(--db-space-2) 0 var(--db-space-05);">{{ $c['stat'] }}</div>
                    <div class="db-stat-sub" style="color: var(--db-text-muted);">{{ $c['sub'] }}</div>
                    <p style="margin: var(--db-space-3) 0 var(--db-space-3); color: var(--db-text-secondary); font-size: var(--db-text-sm); line-height: 1.5;">{!! $c['desc'] !!}</p>
                    <span style="color: var(--db-accent); font-weight: var(--db-weight-semibold); font-size: var(--db-text-sm);">View {{ strtolower($c['label']) }} <i class="bi bi-arrow-right"></i></span>
                </x-db.card>
                @else
                <div class="db-card h-100"><div class="db-card-body">
                    <div class="db-eyebrow" style="color: var(--db-text-muted); display: flex; align-items: center; gap: var(--db-space-1);">
                        <i class="bi {{ $c['icon'] }}"></i> {{ $c['label'] }}
                    </div>
                    <div class="db-stat-value" style="margin: var(--db-space-2) 0 var(--db-space-05); color: var(--db-text-muted);">—</div>
                    <div class="db-stat-sub" style="color: var(--db-text-muted);">not yet available</div>
                    <p style="margin: var(--db-space-3) 0 0; color: var(--db-text-secondary); font-size: var(--db-text-sm); line-height: 1.5;">{!! $c['desc'] !!}</p>
                </div></div>
                @endif
            </div>
            @endforeach
        </div>

    </div>
</div>
@endsection
