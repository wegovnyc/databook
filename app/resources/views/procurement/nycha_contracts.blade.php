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
@include('sub.orgheader', ['active' => $section])
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-4); padding-bottom: 0;">
        <div class="db-eyebrow">Procurement · NYCHA</div>
        <h1 style="margin: 0 0 var(--db-space-2);">Contracts @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h1>
        <p class="db-page-lead" style="max-width: 68ch;">Contracts and agreements of the New York City Housing Authority — original vs current vs invoiced value, by vendor and responsibility center. Sourced from <a href="https://www.checkbooknyc.com" target="_blank" rel="noopener">Checkbook NYC</a>.</p>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">


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

        {{-- ================= Record explorer: search / filter / paginate ================= --}}
        @php
            $f        = $filters ?? [];
            $qval     = $f['q'] ?? '';
            $fyval    = (string) ($f['fiscal_year'] ?? '');
            $sortval  = $f['sort'] ?? 'current';
            $orderval = ($f['order'] ?? 'desc') === 'asc' ? 'asc' : 'desc';
            $page     = (int) ($contracts['page'] ?? 1);
            $pages    = (int) ($contracts['pages'] ?? 1);
            $total    = (int) ($contracts['total'] ?? count($rows));
            $base     = route('orgSection', ['id' => $id, 'orgslug' => $orgslug ?? \Illuminate\Support\Str::slug($org['name'], '-'), 'section' => $section]);
            $fyOpts   = array_values(array_filter(array_map(fn($y) => $y['year'] ?? null, $summary['by_year'] ?? [])));
            rsort($fyOpts);
            $active   = array_filter(['q' => $qval, 'fiscal_year' => $fyval, 'sort' => $sortval, 'order' => $orderval], fn($v) => $v !== '' && $v !== null);
            $pageQuery = fn($p) => $base . '?' . http_build_query(array_merge($active, ['page' => $p]));
            $exportUrl = \App\Custom\DatabookAPI::url('/oce/nycha/contracts/export?' . http_build_query($active));
            $sortLabels = ['current' => 'Current value', 'invoiced' => 'Invoiced', 'original' => 'Original value', 'vendor' => 'Vendor (A–Z)', 'end_date' => 'End date', 'releases' => 'Releases'];
        @endphp

        <div class="d-flex align-items-center flex-wrap mb-3" style="gap: var(--db-space-2);">
            <h3 class="mb-0" style="font-size: var(--db-text-lg);">All contracts</h3>
            <span class="db-badge db-badge-neutral">{{ number_format($total) }} match{{ $total == 1 ? '' : 'es' }}</span>
            <a href="{{ $exportUrl }}" class="db-btn db-btn-outline db-btn-sm ms-auto"><i class="bi bi-download"></i> Export CSV</a>
        </div>

        {{-- Filter bar (GET → reloads this section with query params) --}}
        <form method="GET" action="{{ $base }}" class="db-filter-bar mb-3">
            <input class="db-input" type="search" name="q" value="{{ $qval }}" placeholder="Vendor, purpose, or contract ID…" style="min-width: 240px;" autocomplete="off">
            <select class="db-select" name="fiscal_year" aria-label="Fiscal year">
                <option value="">All fiscal years</option>
                @foreach($fyOpts as $y)
                <option value="{{ $y }}" {{ $fyval === (string) $y ? 'selected' : '' }}>FY{{ $y }}</option>
                @endforeach
            </select>
            <select class="db-select" name="sort" aria-label="Sort by">
                @foreach($sortLabels as $k => $lbl)
                <option value="{{ $k }}" {{ $sortval === $k ? 'selected' : '' }}>{{ $lbl }}</option>
                @endforeach
            </select>
            <select class="db-select" name="order" aria-label="Order">
                <option value="desc" {{ $orderval === 'desc' ? 'selected' : '' }}>High → low</option>
                <option value="asc" {{ $orderval === 'asc' ? 'selected' : '' }}>Low → high</option>
            </select>
            <button type="submit" class="db-btn db-btn-primary">Apply</button>
            @if(count($active))<a href="{{ $base }}" class="db-btn db-btn-outline">Clear</a>@endif
        </form>

        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th style="width: 28px;"></th>
                            <th>Contract ID</th>
                            <th>Vendor</th>
                            <th>Purpose</th>
                            <th class="db-num" style="width: 70px;">FY</th>
                            <th class="db-num">Current</th>
                            <th class="db-num">Invoiced</th>
                            <th style="width: 140px;">Utilization</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($rows as $i => $r)
                        @php
                            $cur = (float)($r['current_amt'] ?? 0);
                            $inv = (float)($r['invoiced'] ?? 0);
                            $u = $cur > 0 ? min($inv / $cur, 1.5) : 0;
                            $pct = number_format($u * 100, 1);
                        @endphp
                        <tr class="nycha-ctr-row" data-det="ctrdet-{{ $i }}" style="cursor: pointer;">
                            <td class="text-center"><i class="bi bi-chevron-right nycha-ctr-caret" style="color: var(--db-text-muted); transition: transform .15s;"></i></td>
                            <td class="fw-semibold is-mono">
                                @if(!empty($r['contract_id']))
                                <a href="{{ route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-contract']) }}?id={{ urlencode($r['contract_id']) }}" onclick="event.stopPropagation()" title="Contract profile">{{ $r['contract_id'] }}</a>
                                @else — @endif
                            </td>
                            <td class="fw-semibold">@include('procurement.partials.nycha_vendor_link')</td>
                            <td style="max-width: 320px; color: var(--db-text-muted); font-size: var(--db-text-sm);" title="{{ $r['purpose'] }}">{{ \Illuminate\Support\Str::limit($r['purpose'] ?? '', 64) }}</td>
                            <td class="db-num">{{ $r['fiscal_year'] ?? '—' }}</td>
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
                        <tr class="db-row-detail" id="ctrdet-{{ $i }}" style="display: none;">
                            <td colspan="8" style="background: var(--db-gray-50);">
                                <div class="row" style="font-size: var(--db-text-sm);">
                                    @php
                                        $det = [
                                            'Contract ID' => $r['contract_id'] ?? '', 'PIN' => $r['pin'] ?? '',
                                            'Responsibility center' => $r['responsibility_center'] ?? '',
                                            'Funding source' => $r['funding_source'] ?? '', 'Industry' => $r['industry'] ?? '',
                                            'Award method' => $r['award_method'] ?? '', 'Contract type' => $r['contract_type'] ?? '',
                                            'Start' => $r['start_date'] ?? '', 'End' => $r['end_date'] ?? '',
                                            'Original' => $compact((float)($r['original'] ?? 0)), 'Releases' => $r['releases'] ?? 0,
                                        ];
                                    @endphp
                                    @foreach($det as $k => $v)
                                    <div class="col-md-4 mb-1"><span style="color: var(--db-text-muted);">{{ $k }}:</span> {{ $v !== '' && $v !== null ? $v : '—' }}</div>
                                    @endforeach
                                    @if(($r['purpose'] ?? '') !== '')
                                    <div class="col-12 mt-1"><span style="color: var(--db-text-muted);">Purpose:</span> {{ $r['purpose'] }}</div>
                                    @endif
                                </div>
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="8" class="text-muted text-center py-4">No contracts match your filters.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        {{-- Pagination --}}
        @if($pages > 1)
        <div class="d-flex align-items-center justify-content-center mt-3" style="gap: var(--db-space-1);">
            <a class="db-page {{ $page <= 1 ? 'is-disabled' : '' }}" href="{{ $page <= 1 ? '#' : $pageQuery(max($page - 1, 1)) }}">Previous</a>
            <span class="db-page is-disabled">Page {{ number_format($page) }} of {{ number_format($pages) }}</span>
            <a class="db-page {{ $page >= $pages ? 'is-disabled' : '' }}" href="{{ $page >= $pages ? '#' : $pageQuery(min($page + 1, $pages)) }}">Next</a>
        </div>
        @endif

        @endif
    </div>
</div>

@if($available)
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function () {
    // Expandable contract detail rows.
    document.querySelectorAll('.nycha-ctr-row').forEach(function (row) {
        row.addEventListener('click', function () {
            var det = document.getElementById(row.getAttribute('data-det'));
            if (!det) return;
            var open = det.style.display !== 'none';
            det.style.display = open ? 'none' : 'table-row';
            var caret = row.querySelector('.nycha-ctr-caret');
            if (caret) caret.style.transform = open ? '' : 'rotate(90deg)';
        });
    });

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
