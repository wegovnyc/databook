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
    $available = $summary['available'] ?? false;
    $t = $summary['totals'] ?? [];
    $s8 = $summary['section_8'] ?? [];
    $rows = $developments['data'] ?? [];
    $maxSpend = 0;
    foreach ($rows as $r) { $maxSpend = max($maxSpend, (float)($r['spending'] ?? 0)); }
@endphp

@section('content')
<div class="db-hero">
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                <div class="db-eyebrow" style="color: var(--db-accent);">Procurement · NYCHA</div>
                <h1>NYCHA Spending @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h1>
                <p style="max-width: 62ch; font-size: var(--db-text-lg); line-height: 1.5; color: var(--db-text-on-navy-muted); margin: var(--db-space-2) 0 0;">Every payment the New York City Housing Authority makes — by spending category, funding source, and responsibility center (developments &amp; functional units). Federal Section&nbsp;8 subsidies are flagged. Sourced from <a href="https://www.checkbooknyc.com" target="_blank" rel="noopener" style="color: var(--db-on-dark-accent);">Checkbook NYC</a>.</p>
            </div>
        </div>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">

        @include('procurement.partials.nycha_tabs')

        @if(!$available)
        <div class="db-empty" style="margin-top: var(--db-space-4);">
            <div class="db-empty-icon"><i class="bi bi-cash-stack"></i></div>
            <div class="db-empty-title">NYCHA spending data not yet available</div>
            <div class="db-empty-text">The NYCHA spending dataset is being prepared. Check back soon.</div>
        </div>
        @else

        <div style="display: flex; align-items: baseline; gap: var(--db-space-2); margin-bottom: var(--db-space-3);">
            <h2 style="margin: 0;">FY{{ $summary['latest_year'] }}</h2>
            <span style="color: var(--db-text-muted); font-size: var(--db-text-sm);">NYCHA spending</span>
        </div>

        {{-- Stat tiles --}}
        <div class="db-stat-grid mb-4">
            <div class="db-stat is-accent">
                <div class="db-stat-label">Total spending</div>
                <div class="db-stat-value">{{ $compact($t['spending'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Section 8</div>
                <div class="db-stat-value">{{ $compact($s8['Section 8'] ?? 0) }}</div>
                <div class="db-stat-sub">federal voucher subsidy</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Non-Section 8</div>
                <div class="db-stat-value">{{ $compact($s8['Other'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Cost centers</div>
                <div class="db-stat-value">{{ number_format($developments['total'] ?? 0) }}</div>
                <div class="db-stat-sub">developments &amp; units</div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-7 mb-4">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Spending by fiscal year</span></div>
                    <div class="db-chart-body" style="height: 300px;"><canvas id="byYearChart"></canvas></div>
                </div>
            </div>
            <div class="col-lg-5 mb-4">
                <div class="db-card h-100"><div class="db-card-body">
                    <h3 style="margin: 0 0 var(--db-space-1); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">Top spending categories</h3>
                    <div class="db-ranked-list">
                        @foreach($summary['by_category'] ?? [] as $i => $c)
                        <div class="db-ranked-item">
                            <span class="db-ranked-rank">{{ $i + 1 }}</span>
                            <span class="db-ranked-name" title="{{ $c['category'] }}">{{ $c['category'] }}</span>
                            <span class="db-ranked-value">{{ $compact($c['spending'] ?? 0) }}</span>
                        </div>
                        @endforeach
                    </div>
                </div></div>
            </div>
        </div>

        {{-- Spend by development / cost center — the view CheckbookNYC doesn't offer --}}
        <div class="d-flex align-items-center mb-2" style="gap: var(--db-space-15);">
            <h3 class="mb-0" style="font-size: var(--db-text-lg);">Spending by development &amp; cost center</h3>
            <span class="db-badge db-badge-neutral">{{ number_format($developments['total'] ?? count($rows)) }}</span>
        </div>
        <p style="color: var(--db-text-muted); font-size: var(--db-text-sm); margin: 0 0 var(--db-space-2);">NYCHA responsibility centers — named developments (e.g. Queensbridge, Red Hook) alongside central/functional units.</p>
        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Responsibility center</th>
                            <th class="db-num">Payments</th>
                            <th class="db-num">Spending</th>
                            <th style="width: 200px;">Share</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($rows as $r)
                        @php
                            $sp = (float)($r['spending'] ?? 0);
                            $w = $maxSpend > 0 ? ($sp / $maxSpend * 100) : 0;
                        @endphp
                        <tr>
                            <td class="fw-semibold">{{ $r['development'] ?: '—' }}</td>
                            <td class="db-num">{{ number_format($r['payments'] ?? 0) }}</td>
                            <td class="db-num">{{ $compact($sp) }}</td>
                            <td>
                                <div style="background: var(--db-gray-100); border-radius: 999px; height: 6px; overflow: hidden;">
                                    <div style="width: {{ $w }}%; height: 100%; background: var(--db-accent);"></div>
                                </div>
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="4" class="text-muted text-center py-4">No spending data.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @endif
    </div>
</div>

@if($available)
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function () {
    DBChart.apply(Chart);
    const byYear = @json($summary['by_year'] ?? []);
    if (byYear.length) {
        new Chart(document.getElementById('byYearChart'), {
            type: 'bar',
            data: {
                labels: byYear.map(d => 'FY' + d.year),
                datasets: [
                    { label: 'Spending', data: byYear.map(d => d.spending), backgroundColor: DBChart.accent, borderRadius: 3 },
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => '$' + c.raw.toLocaleString() } } },
                scales: { y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { callback: DBChart.money } }, x: { grid: { display: false } } }
            }
        });
    }
});
</script>
@endif
@endsection
