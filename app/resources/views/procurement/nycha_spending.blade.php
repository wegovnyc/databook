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
@include('sub.orgheader', ['active' => $section])
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-4); padding-bottom: 0;">
        <div class="db-eyebrow">Procurement · NYCHA</div>
        <h1 style="margin: 0 0 var(--db-space-2);">Spending @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h1>
        <p class="db-page-lead" style="max-width: 68ch;">Every payment the New York City Housing Authority makes — by spending category, funding source, and responsibility center (developments &amp; functional units). Federal Section&nbsp;8 subsidies are flagged. Sourced from <a href="https://www.checkbooknyc.com" target="_blank" rel="noopener">Checkbook NYC</a>.</p>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">


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

        {{-- ============ Payment (record) explorer — check-level, FY-scoped ============ --}}
        @php
            $rf       = $recFilters ?? [];
            $prows    = $records['data'] ?? [];
            $pq       = $rf['q'] ?? '';
            $pfy      = (string) ($rf['fiscal_year'] ?? '');
            $pcat     = (string) ($rf['spending_category'] ?? '');
            $ps8      = (string) ($rf['section_8'] ?? '');
            $psort    = $rf['sort'] ?? 'amount';
            $porder   = ($rf['order'] ?? 'desc') === 'asc' ? 'asc' : 'desc';
            $ppage    = (int) ($records['page'] ?? 1);
            $ppages   = (int) ($records['pages'] ?? 1);
            $ptotal   = (int) ($records['total'] ?? count($prows));
            $pbase    = route('orgSection', ['id' => $id, 'orgslug' => $orgslug ?? \Illuminate\Support\Str::slug($org['name'], '-'), 'section' => $section]);
            $pfyOpts  = array_values(array_filter(array_map(fn($y) => $y['year'] ?? null, $summary['by_year'] ?? [])));
            rsort($pfyOpts);
            $pactive  = array_filter(['q' => $pq, 'fiscal_year' => $pfy, 'spending_category' => $pcat, 'section_8' => $ps8, 'sort' => $psort, 'order' => $porder], fn($v) => $v !== '' && $v !== null);
            $pPageUrl = fn($p) => $pbase . '?' . http_build_query(array_merge($pactive, ['page' => $p]));
            $pExport  = \App\Custom\DatabookAPI::url('/oce/nycha/spending/records/export?' . http_build_query($pactive));
            $pSortLbl = ['amount' => 'Amount', 'date' => 'Date', 'vendor' => 'Vendor (A–Z)'];
        @endphp

        <div class="d-flex align-items-center flex-wrap mt-5 mb-1" style="gap: var(--db-space-2);">
            <h3 class="mb-0" style="font-size: var(--db-text-lg);">Payments</h3>
            <span class="db-badge db-badge-neutral">{{ number_format($ptotal) }} payment{{ $ptotal == 1 ? '' : 's' }}{{ $pfy !== '' ? ' · FY' . $pfy : '' }}</span>
            <a href="{{ $pExport }}" class="db-btn db-btn-outline db-btn-sm ms-auto"><i class="bi bi-download"></i> Export CSV</a>
        </div>
        <p style="color: var(--db-text-muted); font-size: var(--db-text-sm); margin: 0 0 var(--db-space-2);">Individual check-level payments (one row per payment). Payroll is aggregate-only in the feed and isn't itemized here.</p>

        <form method="GET" action="{{ $pbase }}" class="db-filter-bar mb-3">
            <input class="db-input" type="search" name="q" value="{{ $pq }}" placeholder="Vendor, purpose, document or contract ID…" style="min-width: 240px;" autocomplete="off">
            <select class="db-select" name="fiscal_year" aria-label="Fiscal year">
                @foreach($pfyOpts as $y)
                <option value="{{ $y }}" {{ $pfy === (string) $y ? 'selected' : '' }}>FY{{ $y }}</option>
                @endforeach
            </select>
            <select class="db-select" name="spending_category" aria-label="Category">
                <option value="">All categories</option>
                @foreach(['Contracts', 'Other', 'Section 8'] as $c)
                <option value="{{ $c }}" {{ $pcat === $c ? 'selected' : '' }}>{{ $c }}</option>
                @endforeach
            </select>
            <select class="db-select" name="section_8" aria-label="Section 8">
                <option value="">Section 8: any</option>
                <option value="Y" {{ $ps8 === 'Y' ? 'selected' : '' }}>Section 8 only</option>
                <option value="N" {{ $ps8 === 'N' ? 'selected' : '' }}>Non-Section 8</option>
            </select>
            <select class="db-select" name="sort" aria-label="Sort by">
                @foreach($pSortLbl as $k => $lbl)<option value="{{ $k }}" {{ $psort === $k ? 'selected' : '' }}>{{ $lbl }}</option>@endforeach
            </select>
            <select class="db-select" name="order" aria-label="Order">
                <option value="desc" {{ $porder === 'desc' ? 'selected' : '' }}>High → low</option>
                <option value="asc" {{ $porder === 'asc' ? 'selected' : '' }}>Low → high</option>
            </select>
            <button type="submit" class="db-btn db-btn-primary">Apply</button>
            @if(count(array_diff_key($pactive, ['fiscal_year' => 1, 'sort' => 1, 'order' => 1])))<a href="{{ $pbase }}?fiscal_year={{ $pfy }}" class="db-btn db-btn-outline">Clear</a>@endif
        </form>

        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th style="width: 28px;"></th>
                            <th>Vendor</th>
                            <th style="width: 110px;">Date</th>
                            <th>Category</th>
                            <th>Funding source</th>
                            <th class="db-num">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($prows as $i => $r)
                        <tr class="nycha-pay-row" data-det="paydet-{{ $i }}" style="cursor: pointer;">
                            <td class="text-center"><i class="bi bi-chevron-right nycha-pay-caret" style="color: var(--db-text-muted); transition: transform .15s;"></i></td>
                            <td class="fw-semibold">@include('procurement.partials.nycha_vendor_link')</td>
                            <td style="color: var(--db-text-muted); font-size: var(--db-text-sm);">{{ $r['issue_date'] ?: '—' }}</td>
                            <td>{{ $r['spending_category'] ?: '—' }}@if(($r['section_8'] ?? '') === 'Y')<span class="db-badge db-badge-neutral" style="font-size: .6em; vertical-align: middle;">§8</span>@endif</td>
                            <td style="max-width: 240px; color: var(--db-text-muted); font-size: var(--db-text-sm);" title="{{ $r['funding_source'] }}">{{ \Illuminate\Support\Str::limit($r['funding_source'] ?? '', 34) }}</td>
                            <td class="db-num">{{ $compact((float)($r['amount'] ?? 0)) }}</td>
                        </tr>
                        <tr class="db-row-detail" id="paydet-{{ $i }}" style="display: none;">
                            <td colspan="6" style="background: var(--db-gray-50);">
                                <div class="row" style="font-size: var(--db-text-sm);">
                                    @php
                                        $pd = [
                                            'Document ID' => $r['document_id'] ?? '', 'Contract ID' => $r['contract_id'] ?? '',
                                            'Status' => $r['check_status'] ?? '', 'PO type' => $r['po_type'] ?? '',
                                            'Responsibility center' => $r['responsibility_center'] ?? '',
                                            'Expense category' => $r['expense_category'] ?? '', 'Industry' => $r['industry'] ?? '',
                                            'Section 8' => ($r['section_8'] ?? '') === 'Y' ? 'Yes' : 'No',
                                        ];
                                    @endphp
                                    @foreach($pd as $k => $v)
                                    <div class="col-md-4 mb-1"><span style="color: var(--db-text-muted);">{{ $k }}:</span> {{ $v !== '' && $v !== null ? $v : '—' }}</div>
                                    @endforeach
                                    @if(($r['purpose'] ?? '') !== '')
                                    <div class="col-12 mt-1"><span style="color: var(--db-text-muted);">Purpose:</span> {{ $r['purpose'] }}</div>
                                    @endif
                                </div>
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="6" class="text-muted text-center py-4">No payments match your filters.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @if($ppages > 1)
        <div class="d-flex align-items-center justify-content-center mt-3" style="gap: var(--db-space-1);">
            <a class="db-page {{ $ppage <= 1 ? 'is-disabled' : '' }}" href="{{ $ppage <= 1 ? '#' : $pPageUrl(max($ppage - 1, 1)) }}">Previous</a>
            <span class="db-page is-disabled">Page {{ number_format($ppage) }} of {{ number_format($ppages) }}</span>
            <a class="db-page {{ $ppage >= $ppages ? 'is-disabled' : '' }}" href="{{ $ppage >= $ppages ? '#' : $pPageUrl(min($ppage + 1, $ppages)) }}">Next</a>
        </div>
        @endif

        @endif
    </div>
</div>

@if($available)
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function () {
    // Expandable payment detail rows.
    document.querySelectorAll('.nycha-pay-row').forEach(function (row) {
        row.addEventListener('click', function () {
            var det = document.getElementById(row.getAttribute('data-det'));
            if (!det) return;
            var open = det.style.display !== 'none';
            det.style.display = open ? 'none' : 'table-row';
            var caret = row.querySelector('.nycha-pay-caret');
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
