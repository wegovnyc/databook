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
    $rows = $contracts['data'] ?? [];
@endphp

@section('content')
<div class="db-hero">
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                <div class="db-eyebrow" style="color: var(--db-accent);">Procurement · NYCHA</div>
                <h1>NYCHA Contracts @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h1>
                <p style="max-width: 62ch; font-size: var(--db-text-lg); line-height: 1.5; color: var(--db-text-on-navy-muted); margin: var(--db-space-2) 0 0;">Contracts and agreements of the New York City Housing Authority — original vs current vs invoiced value, by vendor and responsibility center. Sourced from <a href="https://www.checkbooknyc.com" target="_blank" rel="noopener" style="color: var(--db-on-dark-accent);">Checkbook NYC</a>.</p>
            </div>
        </div>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">

        @include('procurement.partials.nycha_tabs')

        @if(!$available)
        <div class="db-empty" style="margin-top: var(--db-space-4);">
            <div class="db-empty-icon"><i class="bi bi-file-earmark-text"></i></div>
            <div class="db-empty-title">NYCHA contract data not yet available</div>
            <div class="db-empty-text">The NYCHA contracts dataset is being prepared. Check back soon.</div>
        </div>
        @else

        {{-- Stat tiles --}}
        <div class="db-stat-grid mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Contracts</div>
                <div class="db-stat-value">{{ number_format($t['contracts'] ?? 0) }}</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Current value</div>
                <div class="db-stat-value">{{ $compact($t['current'] ?? 0) }}</div>
                <div class="db-stat-sub">registered amount</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Invoiced</div>
                <div class="db-stat-value">{{ $compact($t['invoiced'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ number_format(($t['utilization'] ?? 0) * 100, 1) }}% of current</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Utilization</div>
                <div class="db-stat-value">{{ number_format(($t['utilization'] ?? 0) * 100, 1) }}%</div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-7 mb-4">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Contracts by fiscal year</span></div>
                    <div class="db-chart-body" style="height: 300px;"><canvas id="byYearChart"></canvas></div>
                </div>
            </div>
            <div class="col-lg-5 mb-4">
                <div class="db-card h-100"><div class="db-card-body">
                    <h3 style="margin: 0 0 var(--db-space-1); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">Top vendors by current value</h3>
                    <div class="db-ranked-list">
                        @foreach($summary['top_vendors'] ?? [] as $i => $v)
                        <div class="db-ranked-item">
                            <span class="db-ranked-rank">{{ $i + 1 }}</span>
                            <span class="db-ranked-name" title="{{ $v['vendor'] }}">{{ $v['vendor'] }}<span style="color: var(--db-text-muted); font-size: var(--db-text-2xs);"> · {{ number_format($v['contracts'] ?? 0) }} contract{{ ($v['contracts'] ?? 0) == 1 ? '' : 's' }}</span></span>
                            <span class="db-ranked-value">{{ $compact($v['current'] ?? 0) }}</span>
                        </div>
                        @endforeach
                    </div>
                </div></div>
            </div>
        </div>

        {{-- Largest contracts (by current value) --}}
        <div class="d-flex align-items-center mb-2" style="gap: var(--db-space-15);">
            <h3 class="mb-0" style="font-size: var(--db-text-lg);">Largest contracts</h3>
            <span class="db-badge db-badge-neutral">{{ number_format($contracts['total'] ?? count($rows)) }} total</span>
        </div>
        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Vendor</th>
                            <th>Purpose</th>
                            <th class="db-num">Current</th>
                            <th class="db-num">Invoiced</th>
                            <th style="width: 150px;">Utilization</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($rows as $r)
                        @php
                            $cur = (float)($r['current_amt'] ?? 0);
                            $inv = (float)($r['invoiced'] ?? 0);
                            $u = $cur > 0 ? min($inv / $cur, 1.5) : 0;
                            $pct = number_format($u * 100, 1);
                        @endphp
                        <tr>
                            <td class="fw-semibold">{{ $r['vendor'] ?: '—' }}</td>
                            <td style="max-width: 340px; color: var(--db-text-muted); font-size: var(--db-text-sm);" title="{{ $r['purpose'] }}">{{ \Illuminate\Support\Str::limit($r['purpose'] ?? '', 70) }}</td>
                            <td class="db-num">{{ $compact($cur) }}</td>
                            <td class="db-num">{{ $compact($inv) }}</td>
                            <td>
                                <div style="display: flex; align-items: center; gap: var(--db-space-1);">
                                    <div style="flex: 1; background: var(--db-gray-100); border-radius: 999px; height: 6px; overflow: hidden;">
                                        <div style="width: {{ min($u * 100, 100) }}%; height: 100%; background: {{ $u > 1 ? 'var(--db-danger)' : 'var(--db-accent)' }};"></div>
                                    </div>
                                    <span style="font-size: var(--db-text-2xs); color: var(--db-text-muted); font-variant-numeric: tabular-nums; min-width: 42px; text-align: right;">{{ $pct }}%</span>
                                </div>
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="5" class="text-muted text-center py-4">No contract data.</td></tr>
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
                    { label: 'Contracts', data: byYear.map(d => d.contracts), backgroundColor: DBChart.navy, borderRadius: 3 },
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.raw.toLocaleString() + ' contracts' } } },
                scales: { y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { precision: 0 } }, x: { grid: { display: false } } }
            }
        });
    }
});
</script>
@endif
@endsection
