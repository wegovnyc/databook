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
    $rows = $sources['data'] ?? [];
@endphp

@section('content')
@include('sub.orgheader', ['active' => $section])
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-4); padding-bottom: 0;">
        <div class="db-eyebrow">Procurement · NYCHA</div>
        <h1 style="margin: 0 0 var(--db-space-2);">Revenue @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h1>
        <p class="db-page-lead" style="max-width: 68ch;">Revenue the New York City Housing Authority recognizes — adopted vs modified vs recognized, by funding source and revenue category. Dominated by federal operating subsidies (Section 8 / vouchers) rather than City tax revenue. Sourced from <a href="https://www.checkbooknyc.com" target="_blank" rel="noopener">Checkbook NYC</a>.</p>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">


        @if(!$available)
        <div class="db-empty" style="margin-top: var(--db-space-4);">
            <div class="db-empty-icon"><i class="bi bi-cash-coin"></i></div>
            <div class="db-empty-title">NYCHA revenue data not yet available</div>
            <div class="db-empty-text">The NYCHA revenue dataset is being prepared. Check back soon.</div>
        </div>
        @else

        <div style="display: flex; align-items: baseline; gap: var(--db-space-2); margin-bottom: var(--db-space-3);">
            <h2 style="margin: 0;">FY{{ $summary['latest_year'] }}</h2>
            <span style="color: var(--db-text-muted); font-size: var(--db-text-sm);">NYCHA revenue</span>
        </div>

        {{-- Stat tiles --}}
        <div class="db-stat-grid mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Adopted</div>
                <div class="db-stat-value">{{ $compact($t['adopted'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Modified</div>
                <div class="db-stat-value">{{ $compact($t['modified'] ?? 0) }}</div>
                <div class="db-stat-sub">current plan</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Recognized</div>
                <div class="db-stat-value">{{ $compact($t['recognized'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ number_format(($t['realization'] ?? 0) * 100, 1) }}% of modified</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Realization</div>
                <div class="db-stat-value">{{ number_format(($t['realization'] ?? 0) * 100, 1) }}%</div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-7 mb-4">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Revenue by fiscal year</span></div>
                    <div class="db-chart-body" style="height: 300px;"><canvas id="byYearChart"></canvas></div>
                </div>
            </div>
            <div class="col-lg-5 mb-4">
                <div class="db-card h-100"><div class="db-card-body">
                    <h3 style="margin: 0 0 var(--db-space-1); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">Top revenue categories</h3>
                    <div class="db-ranked-list">
                        @foreach($summary['by_category'] ?? [] as $i => $c)
                        <div class="db-ranked-item">
                            <span class="db-ranked-rank">{{ $i + 1 }}</span>
                            <span class="db-ranked-name" title="{{ $c['category'] }}">{{ $c['category'] }}</span>
                            <span class="db-ranked-value">{{ $compact($c['recognized'] ?? 0) }}</span>
                        </div>
                        @endforeach
                    </div>
                </div></div>
            </div>
        </div>

        {{-- By funding source (federal Section 8 vs City vs capital, etc.) --}}
        <div class="d-flex align-items-center mb-2" style="gap: var(--db-space-15);">
            <h3 class="mb-0" style="font-size: var(--db-text-lg);">By funding source</h3>
            <span class="db-badge db-badge-neutral">{{ number_format($sources['total'] ?? count($rows)) }}</span>
        </div>
        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Funding source</th>
                            <th class="db-num">Adopted</th>
                            <th class="db-num">Modified</th>
                            <th class="db-num">Recognized</th>
                            <th style="width: 160px;">Realization</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($rows as $r)
                        @php $u = min(($r['realization'] ?? 0), 1.5); $pct = number_format($u * 100, 1); @endphp
                        <tr>
                            <td class="fw-semibold">{{ $r['source'] }}</td>
                            <td class="db-num">{{ $compact($r['adopted'] ?? 0) }}</td>
                            <td class="db-num">{{ $compact($r['modified'] ?? 0) }}</td>
                            <td class="db-num">{{ $compact($r['recognized'] ?? 0) }}</td>
                            <td>
                                <div style="display: flex; align-items: center; gap: var(--db-space-1);">
                                    <div style="flex: 1; background: var(--db-gray-100); border-radius: 999px; height: 6px; overflow: hidden;">
                                        <div style="width: {{ min($u * 100, 100) }}%; height: 100%; background: var(--db-accent);"></div>
                                    </div>
                                    <span style="font-size: var(--db-text-2xs); color: var(--db-text-muted); font-variant-numeric: tabular-nums; min-width: 42px; text-align: right;">{{ $pct }}%</span>
                                </div>
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="5" class="text-muted text-center py-4">No funding-source data.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @php $vFyOpts = array_values(array_filter(array_map(fn($y) => $y['year'] ?? null, $summary['by_year'] ?? []))); rsort($vFyOpts); @endphp
        @include('procurement.partials.nycha_record_table', [
            'recTitle' => 'Revenue lines',
            'recNoun'  => 'line',
            'recExportPath' => '/oce/nycha/revenue/records/export',
            'recSearchPlaceholder' => 'Revenue category, funding source, budget name…',
            'recFyOpts' => $vFyOpts,
            'recSorts' => ['recognized' => 'Recognized', 'modified' => 'Modified', 'adopted' => 'Adopted', 'category' => 'Revenue category'],
            'recCols' => [
                ['label' => 'Revenue category', 'key' => 'revenue_category'],
                ['label' => 'Funding source', 'key' => 'funding_source'],
                ['label' => 'Adopted', 'key' => 'adopted', 'money' => true],
                ['label' => 'Modified', 'key' => 'modified', 'money' => true],
                ['label' => 'Recognized', 'key' => 'recognized', 'money' => true],
            ],
            'recDetail' => [
                ['label' => 'Fiscal year', 'key' => 'year'],
                ['label' => 'Revenue class', 'key' => 'revenue_class'],
                ['label' => 'Revenue/expense category', 'key' => 'revenue_expense_category'],
                ['label' => 'Budget name', 'key' => 'budget_name'],
                ['label' => 'Budget type', 'key' => 'budget_type'],
                ['label' => 'Responsibility center', 'key' => 'responsibility_center'],
                ['label' => 'Remaining', 'key' => 'remaining', 'money' => true],
            ],
        ])

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
                    { label: 'Adopted', data: byYear.map(d => d.adopted), backgroundColor: DBChart.navySoft || 'rgba(22,46,81,0.35)', borderRadius: 3 },
                    { label: 'Modified', data: byYear.map(d => d.modified), backgroundColor: DBChart.navy, borderRadius: 3 },
                    { label: 'Recognized', data: byYear.map(d => d.recognized), backgroundColor: DBChart.accent, borderRadius: 3 },
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: true, position: 'bottom' }, tooltip: { callbacks: { label: c => c.dataset.label + ': $' + c.raw.toLocaleString() } } },
                scales: { y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { callback: DBChart.money } }, x: { grid: { display: false } } }
            }
        });
    }
});
</script>
@endif
@endsection
