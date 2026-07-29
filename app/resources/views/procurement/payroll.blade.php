@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@php
    $compact = function ($n) {
        $n = (float) $n;
        if (abs($n) >= 1e9) return '$' . number_format($n / 1e9, 1) . 'B';
        if (abs($n) >= 1e6) return '$' . number_format($n / 1e6, 1) . 'M';
        if (abs($n) >= 1e3) return '$' . number_format($n / 1e3, 0) . 'K';
        return '$' . number_format($n);
    };
    $available = $summary['available'] ?? false;
    $t = $summary['totals'] ?? [];
    $rows = $agencies['data'] ?? [];
    // record explorer
    $rf = $recFilters ?? [];
    $rq = $rf['q'] ?? ''; $ragency = $rf['agency'] ?? '';
    $rsort = $rf['sort'] ?? 'gross'; $rorder = ($rf['order'] ?? 'desc') === 'asc' ? 'asc' : 'desc';
    $recRows = $records['data'] ?? [];
    $rpage = (int) ($records['page'] ?? 1); $rpages = (int) ($records['pages'] ?? 1);
    $rtotal = (int) ($records['total'] ?? count($recRows));
    $base = route('procurement.payroll');
    $active = array_filter(['q' => $rq, 'agency' => $ragency, 'fiscal_year' => $rf['fiscal_year'] ?? '', 'sort' => $rsort, 'order' => $rorder], fn($v) => $v !== '' && $v !== null);
    $pageUrl = fn($p) => $base . '?' . http_build_query(array_merge($active, ['page' => $p]));
    $exportUrl = \App\Custom\DatabookAPI::url('/oce/payroll/records/export?' . http_build_query($active));
    $sorts = ['gross' => 'Gross pay', 'overtime' => 'Overtime', 'base' => 'Base pay', 'records' => 'Pay records', 'avg_salary' => 'Avg salary', 'title' => 'Title (A–Z)'];
@endphp

@section('content')
<div class="db-hero">
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                <div class="db-eyebrow" style="color: var(--db-accent);">Procurement</div>
                <h1>Payroll @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h1>
                <p style="max-width: 64ch; font-size: var(--db-text-lg); line-height: 1.5; color: var(--db-text-on-navy-muted); margin: var(--db-space-2) 0 0;">What the City of New York pays its workforce — gross pay, base pay, and overtime by agency and civil-service title. Sourced from <a href="https://www.checkbooknyc.com" target="_blank" rel="noopener" style="color: var(--db-on-dark-accent);">Checkbook NYC</a>.</p>
            </div>
        </div>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">

        @if(!$available)
        <div class="db-empty" style="margin-top: var(--db-space-4);">
            <div class="db-empty-icon"><i class="bi bi-people"></i></div>
            <div class="db-empty-title">Payroll data not yet available</div>
            <div class="db-empty-text">The payroll dataset is being prepared. Check back soon.</div>
        </div>
        @else

        <div style="display: flex; align-items: baseline; gap: var(--db-space-2); margin-bottom: var(--db-space-3);">
            <h2 style="margin: 0;">FY{{ $summary['latest_year'] }}</h2>
            <span style="color: var(--db-text-muted); font-size: var(--db-text-sm);">citywide payroll</span>
        </div>

        {{-- Stat tiles --}}
        <div class="db-stat-grid mb-4">
            <div class="db-stat is-accent">
                <div class="db-stat-label">Gross pay</div>
                <div class="db-stat-value">{{ $compact($t['gross'] ?? 0) }}</div>
                <div class="db-stat-sub">total paid</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Base pay</div>
                <div class="db-stat-value">{{ $compact($t['base'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Overtime</div>
                <div class="db-stat-value">{{ $compact($t['overtime'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ number_format(($t['ot_share'] ?? 0) * 100, 1) }}% of gross</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Avg annual salary</div>
                <div class="db-stat-value">{{ $compact($t['avg_salary'] ?? 0) }}</div>
                <div class="db-stat-sub">salaried titles</div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-7 mb-4">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Gross pay &amp; overtime by fiscal year</span></div>
                    <div class="db-chart-body" style="height: 300px;"><canvas id="byYearChart"></canvas></div>
                </div>
            </div>
            <div class="col-lg-5 mb-4">
                <div class="db-card h-100"><div class="db-card-body">
                    <h3 style="margin: 0 0 var(--db-space-1); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">Top titles by gross pay</h3>
                    <div class="db-ranked-list">
                        @foreach($summary['by_title'] ?? [] as $i => $c)
                        <div class="db-ranked-item">
                            <span class="db-ranked-rank">{{ $i + 1 }}</span>
                            <span class="db-ranked-name" title="{{ $c['title'] }}">{{ $c['title'] }}<span style="color: var(--db-text-muted); font-size: var(--db-text-2xs);"> · {{ $compact($c['avg_salary'] ?? 0) }} avg</span></span>
                            <span class="db-ranked-value">{{ $compact($c['gross'] ?? 0) }}</span>
                        </div>
                        @endforeach
                    </div>
                </div></div>
            </div>
        </div>

        {{-- By-agency table with OT-share bars --}}
        <div class="d-flex align-items-center mb-2" style="gap: var(--db-space-15);">
            <h3 class="mb-0" style="font-size: var(--db-text-lg);">By agency</h3>
            <span class="db-badge db-badge-neutral">{{ number_format($agencies['total'] ?? count($rows)) }}</span>
        </div>
        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Agency</th>
                            <th class="db-num">Gross</th>
                            <th class="db-num">Overtime</th>
                            <th class="db-num">Avg salary</th>
                            <th style="width: 160px;">OT share</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($rows as $r)
                        @php $g = (float)($r['gross'] ?? 0); $ot = (float)($r['overtime'] ?? 0); $u = $g > 0 ? $ot / $g : 0; $pct = number_format($u * 100, 1); @endphp
                        <tr>
                            <td class="fw-semibold">{{ $r['agency'] }}</td>
                            <td class="db-num">{{ $compact($g) }}</td>
                            <td class="db-num">{{ $compact($ot) }}</td>
                            <td class="db-num">{{ $compact($r['avg_salary'] ?? 0) }}</td>
                            <td>
                                <div style="display: flex; align-items: center; gap: var(--db-space-1);">
                                    <div style="flex: 1; background: var(--db-gray-100); border-radius: 999px; height: 6px; overflow: hidden;">
                                        <div style="width: {{ min($u * 100 * 4, 100) }}%; height: 100%; background: {{ $u > 0.15 ? 'var(--db-danger)' : 'var(--db-accent)' }};"></div>
                                    </div>
                                    <span style="font-size: var(--db-text-2xs); color: var(--db-text-muted); font-variant-numeric: tabular-nums; min-width: 42px; text-align: right;">{{ $pct }}%</span>
                                </div>
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="5" class="text-muted text-center py-4">No agency data.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        {{-- Title-level record explorer --}}
        <div class="d-flex align-items-center flex-wrap mt-5 mb-1" style="gap: var(--db-space-2);">
            <h3 class="mb-0" style="font-size: var(--db-text-lg);">Pay by title</h3>
            <span class="db-badge db-badge-neutral">{{ number_format($rtotal) }} row{{ $rtotal == 1 ? '' : 's' }}</span>
            <a href="{{ $exportUrl }}" class="db-btn db-btn-outline db-btn-sm ms-auto"><i class="bi bi-download"></i> Export CSV</a>
        </div>
        <form method="GET" action="{{ $base }}" class="db-filter-bar mb-3">
            <input class="db-input" type="search" name="q" value="{{ $rq }}" placeholder="Search title or agency…" style="min-width: 240px;" autocomplete="off">
            <select class="db-select" name="sort" aria-label="Sort by">
                @foreach($sorts as $k => $lbl)<option value="{{ $k }}" {{ $rsort === $k ? 'selected' : '' }}>{{ $lbl }}</option>@endforeach
            </select>
            <select class="db-select" name="order" aria-label="Order">
                <option value="desc" {{ $rorder === 'desc' ? 'selected' : '' }}>High → low</option>
                <option value="asc" {{ $rorder === 'asc' ? 'selected' : '' }}>Low → high</option>
            </select>
            @if($ragency !== '')<input type="hidden" name="agency" value="{{ $ragency }}">@endif
            <button type="submit" class="db-btn db-btn-primary">Apply</button>
            @if(count($active))<a href="{{ $base }}" class="db-btn db-btn-outline">Clear</a>@endif
        </form>
        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Title</th>
                            <th>Agency</th>
                            <th>Type</th>
                            <th class="db-num">Gross</th>
                            <th class="db-num">Overtime</th>
                            <th class="db-num">Avg salary</th>
                            <th class="db-num">Pay records</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($recRows as $r)
                        <tr>
                            <td class="fw-semibold" style="max-width: 280px; overflow: hidden; text-overflow: ellipsis;">{{ $r['title'] ?? '—' }}</td>
                            <td class="text-muted" style="max-width: 220px; overflow: hidden; text-overflow: ellipsis;">{{ $r['agency'] ?? '—' }}</td>
                            <td class="text-muted">{{ $r['payroll_type'] ?? '—' }}</td>
                            <td class="db-num">{{ $compact($r['gross'] ?? 0) }}</td>
                            <td class="db-num">{{ $compact($r['overtime'] ?? 0) }}</td>
                            <td class="db-num">{{ ($r['avg_salary'] ?? 0) > 0 ? $compact($r['avg_salary']) : '—' }}</td>
                            <td class="db-num">{{ number_format($r['records'] ?? 0) }}</td>
                        </tr>
                        @empty
                        <tr><td colspan="7" class="text-muted text-center py-4">No rows match your filters.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>
        @if($rpages > 1)
        <div class="d-flex align-items-center justify-content-center mt-3" style="gap: var(--db-space-1);">
            <a class="db-page {{ $rpage <= 1 ? 'is-disabled' : '' }}" href="{{ $rpage <= 1 ? '#' : $pageUrl(max($rpage - 1, 1)) }}">Previous</a>
            <span class="db-page is-disabled">Page {{ number_format($rpage) }} of {{ number_format($rpages) }}</span>
            <a class="db-page {{ $rpage >= $rpages ? 'is-disabled' : '' }}" href="{{ $rpage >= $rpages ? '#' : $pageUrl(min($rpage + 1, $rpages)) }}">Next</a>
        </div>
        @endif

        <p class="text-muted mt-3" style="font-size: var(--db-text-sm); max-width: 76ch;">
            <i class="bi bi-info-circle"></i> Checkbook's payroll feed carries no employee names or IDs, so figures are aggregated by agency and title with no personal data. <strong>Pay records</strong> counts payment rows, not distinct employees; <strong>average salary</strong> is over positions that report an annual salary (excludes hourly/per-session titles). Amounts are actual disbursements for the fiscal year.
        </p>

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
                    { label: 'Gross pay', data: byYear.map(d => d.gross), backgroundColor: DBChart.navy, borderRadius: 3 },
                    { label: 'Overtime', data: byYear.map(d => d.overtime), backgroundColor: DBChart.accent, borderRadius: 3 },
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
