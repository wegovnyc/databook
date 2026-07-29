{{-- The four NYCHA domain summary cards. Self-contained: expects $budget,
     $revenue, $contracts, $spending (each an /oce/nycha/*/summary payload).
     Shared by the /procurement/nycha hub and the NYCHA org-profile Procurement
     tab. Each card degrades to "not yet available" on its own. --}}
@php
    $nyOslug = $orgslug ?? \Illuminate\Support\Str::slug($org['name'] ?? '', '-');
    $nyHref = fn ($s) => route('orgSection', ['id' => $id, 'orgslug' => $nyOslug, 'section' => $s]);
    $nyCompact = function ($n) {
        $n = (float) $n;
        if ($n >= 1e9) return '$' . number_format($n / 1e9, 1) . 'B';
        if ($n >= 1e6) return '$' . number_format($n / 1e6, 1) . 'M';
        if ($n >= 1e3) return '$' . number_format($n / 1e3, 0) . 'K';
        return '$' . number_format($n);
    };
    $nyPct = fn ($x) => number_format(((float) $x) * 100, 1) . '%';

    $bt = $budget['totals'] ?? [];
    $rt = $revenue['totals'] ?? [];
    $ct = $contracts['totals'] ?? [];
    $st = $spending['totals'] ?? [];

    $nyCards = [
        [
            'label' => 'Expense Budget',
            'icon'  => 'bi-wallet2',
            'href'  => $nyHref('procurement-nycha-budget'),
            'avail' => $budget['available'] ?? false,
            'stat'  => $nyCompact($bt['committed'] ?? 0),
            'sub'   => 'committed · FY' . ($budget['latest_year'] ?? '—') . ' · ' . $nyPct($bt['utilization'] ?? 0) . ' spent',
            'desc'  => 'Adopted vs modified vs committed vs actual spending, by responsibility center (developments &amp; functional units) and expense category.',
        ],
        [
            'label' => 'Revenue',
            'icon'  => 'bi-cash-coin',
            'href'  => $nyHref('procurement-nycha-revenue'),
            'avail' => $revenue['available'] ?? false,
            'stat'  => $nyCompact($rt['recognized'] ?? 0),
            'sub'   => 'recognized · FY' . ($revenue['latest_year'] ?? '—') . ' · ' . $nyPct($rt['realization'] ?? 0) . ' of budget',
            'desc'  => 'Where NYCHA money comes from — recognized vs budgeted revenue by funding source and revenue category (largely federal subsidies and tenant rent).',
        ],
        [
            'label' => 'Contracts',
            'icon'  => 'bi-file-earmark-text',
            'href'  => $nyHref('procurement-nycha-contracts'),
            'avail' => $contracts['available'] ?? false,
            'stat'  => $nyCompact($ct['current'] ?? 0),
            'sub'   => number_format($ct['contracts'] ?? 0) . ' contracts · ' . $nyPct($ct['utilization'] ?? 0) . ' invoiced',
            'desc'  => 'Registered NYCHA contracts and their current value, top vendors, and how much has been invoiced against them to date.',
        ],
        [
            'label' => 'Spending',
            'icon'  => 'bi-receipt',
            'href'  => $nyHref('procurement-nycha-spending'),
            'avail' => $spending['available'] ?? false,
            'stat'  => $nyCompact($st['spending'] ?? 0),
            'sub'   => 'spent · FY' . ($spending['latest_year'] ?? '—'),
            'desc'  => 'Actual check-level payments by expense category, funding source and development — including a spend-by-development view unique to Databook.',
        ],
        // Council discretionary funding — sourced from the City Council dataset
        // (not Checkbook), so it lives on its own tab; this is the overview stub.
        [
            'label' => 'Council Discretionary Funding',
            'icon'  => 'bi-cash-stack',
            'href'  => $nyHref('city-council-discretionary'),
            'avail' => ($councilCount ?? 0) > 0,
            'stat'  => number_format($councilCount ?? 0),
            'sub'   => 'discretionary funding records',
            'desc'  => 'City Council member items allocated to NYCHA and NYCHA-serving organizations — by fiscal year, council member, and recipient.',
        ],
    ];
@endphp

<div class="row">
    @foreach($nyCards as $c)
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
