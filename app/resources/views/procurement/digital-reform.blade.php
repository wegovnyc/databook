@extends('layout')

@section('head')
<style>
    /* Digital Services - page-specific glue over the db-* design system. */
    .db-page-lead { max-width: none; }   /* full-width subheading */
    .ds-tabs .nav-link { color: var(--db-text-muted); font-weight: var(--db-weight-semibold); }
    .ds-tabs .nav-link.active { color: var(--db-primary); }
    .ds-cta { display: flex; align-items: center; justify-content: space-between; gap: var(--db-space-3); flex-wrap: wrap; }
    .ds-cta-num { font-size: var(--db-text-xl); font-weight: var(--db-weight-bold); color: var(--db-primary); }
</style>
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <div class="db-eyebrow">Procurement &middot; Digital Services <span class="db-analysis-badge"><i class="bi bi-stars"></i> Analysis</span></div>
        <h1>Digital Service Reform</h1>
        <p class="db-page-lead" style="max-width: none;">Who is selling NYC digital services, what do those services entail, when do the contracts end and which shouldn't be renewed?</p>
        @include('sub.analysis-banner')

        {{-- Summary --}}
        <div class="db-stat-grid mt-3 mb-5">
            <div class="db-stat">
                <div class="db-stat-label">Digital Service Contracts</div>
                <div class="db-stat-value">{{ number_format($stats['count'] ?? 0) }}</div>
                <div class="db-stat-sub">Since 2022</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Total Awarded Value</div>
                <div class="db-stat-value">${{ number_format(($stats['total'] ?? 0) / 1000000, 0) }}M</div>
                <div class="db-stat-sub">Since 2022</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Digital Vendors</div>
                <div class="db-stat-value">{{ $stats['vendor_count'] ?? 0 }}</div>
                <div class="db-stat-sub">Tagged in Database</div>
            </div>
        </div>

        {{-- Charts --}}
        <div class="db-chart-card mb-4">
            <div class="db-chart-head"><span class="db-chart-title">Digital Services Spending Analysis</span></div>
            <div class="row">
                <div class="col-md-7">
                    <h6 class="text-center mb-3">Contract Value by Start Year</h6>
                    <div class="db-chart-body" style="height: 300px;"><canvas id="digitalTrendChart"></canvas></div>
                </div>
                <div class="col-md-5">
                    <h6 class="text-center mb-3">Spending by Agency</h6>
                    <div class="db-chart-body" style="height: 300px;"><canvas id="digitalAgencyChart"></canvas></div>
                </div>
            </div>
        </div>

        {{-- Call-to-action: the Renewal Review Queue lives on its own page --}}
        <div class="db-alert db-alert-info mb-5" role="region" aria-label="Expiring contracts">
            <i class="bi bi-hourglass-split"></i>
            <div class="db-alert-body ds-cta">
                <div>
                    <strong>Renewal Review Queue</strong>
                    <div class="text-muted" style="font-size: var(--db-text-sm);">
                        <span class="ds-cta-num">{{ number_format($expiring['summary']['count'] ?? 0) }}</span>
                        digital contracts (${{ number_format(($expiring['summary']['total_value'] ?? 0) / 1000000, 0) }}M) expire before 2030 &mdash; triage which ones the city shouldn't renew.
                    </div>
                </div>
                <a href="{{ route('research.digital-reform.expiring') }}" class="db-btn db-btn-primary">
                    Review expiring contracts <i class="bi bi-arrow-right"></i>
                </a>
            </div>
        </div>

        {{-- Vendors + Contracts as tabs --}}
        <ul class="nav nav-tabs ds-tabs mb-0" id="dsTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="tab-vendors-btn" data-bs-toggle="tab" data-bs-target="#tab-vendors" type="button" role="tab">
                    <i class="bi bi-building"></i> Vendors ({{ number_format($vendors['total'] ?? 0) }})
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-contracts-btn" data-bs-toggle="tab" data-bs-target="#tab-contracts" type="button" role="tab">
                    <i class="bi bi-file-earmark-text"></i> Contracts ({{ number_format($contracts['total'] ?? 0) }})
                </button>
            </li>
        </ul>
        <div class="tab-content">

        {{-- ---- Vendors tab ---- --}}
        <div class="tab-pane fade show active" id="tab-vendors" role="tabpanel">
        <div class="db-table-wrap mb-5" id="digital-vendors">
            <div class="px-3 pt-3">
                <form method="GET" action="{{ url()->current() }}#digital-vendors" class="db-filter-bar dr-filter-form">
                    @foreach(request()->except(['vendor_q','vendor_page']) as $k => $v)
                        <input type="hidden" name="{{ $k }}" value="{{ $v }}">
                    @endforeach
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input type="search" name="vendor_q" value="{{ $vendorQ }}" placeholder="Search vendors&hellip;" aria-label="Search vendors">
                    </div>
                    <button type="submit" class="db-btn db-btn-primary db-btn-sm"><i class="bi bi-search"></i> Search</button>
                    @if($vendorQ)
                        <a href="{{ url()->current() }}?{{ http_build_query(request()->except(['vendor_q','vendor_page'])) }}#digital-vendors" class="db-btn db-btn-ghost db-btn-sm">Clear</a>
                    @endif
                </form>
            </div>
            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead>
                        <tr>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['vendor_sort' => 'name', 'vendor_order' => ($vendorSort == 'name' && $vendorOrder == 'asc') ? 'desc' : 'asc']) }}#digital-vendors" class="text-decoration-none text-dark">
                                    Vendor @if($vendorSort == 'name'){!! $vendorOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['vendor_sort' => 'contracts', 'vendor_order' => ($vendorSort == 'contracts' && $vendorOrder == 'asc') ? 'desc' : 'asc']) }}#digital-vendors" class="text-decoration-none text-dark">
                                    Digital Contracts @if($vendorSort == 'contracts'){!! $vendorOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['vendor_sort' => 'amount', 'vendor_order' => ($vendorSort == 'amount' && $vendorOrder == 'asc') ? 'desc' : 'asc']) }}#digital-vendors" class="text-decoration-none text-dark">
                                    Digital Spend @if($vendorSort == 'amount'){!! $vendorOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>Digital Share</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse(($vendors['vendors'] ?? []) as $vendor)
                        @php
                            $digCnt = $vendor['contract_count'] ?? 0;
                            $totCnt = $vendor['total_contract_count'] ?? $digCnt;
                            $digSpend = $vendor['total_awarded'] ?? 0;
                            $totSpend = $vendor['total_award_all'] ?? $digSpend;
                            $share = $vendor['digital_share'] ?? null;
                        @endphp
                        <tr>
                            <td>
                                @if($vendor['vendor_id'] ?? null)
                                    <a href="/procurement/vendor/{{ $vendor['vendor_id'] }}">{{ $vendor['vendor_name'] }}</a>
                                @else
                                    <a href="/procurement/vendors?q={{ urlencode($vendor['vendor_name']) }}">{{ $vendor['vendor_name'] }}</a>
                                @endif
                            </td>
                            <td>
                                {{ number_format($digCnt) }}
                                @if($totCnt > $digCnt)<span class="text-muted small">of {{ number_format($totCnt) }}</span>@endif
                            </td>
                            <td>
                                ${{ number_format($digSpend, 0) }}
                                @if($totSpend > $digSpend)<div class="text-muted small">of ${{ number_format($totSpend, 0) }} total</div>@endif
                            </td>
                            <td>
                                @if($share !== null)
                                    @if($share < 0.10)
                                        <span class="db-badge db-badge-warning" title="Digital work is a small fraction of this vendor's NYC contracts">{{ number_format($share * 100, 0) }}% &middot; mostly non-digital</span>
                                    @else
                                        <span class="text-muted">{{ number_format($share * 100, 0) }}%</span>
                                    @endif
                                @else
                                    <span class="text-muted">&mdash;</span>
                                @endif
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="4" class="text-center text-muted py-4">No vendors match &ldquo;{{ $vendorQ }}&rdquo;.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
            @if(($vendors['total_pages'] ?? 0) > 1)
            <div class="db-table-footer">
                <nav aria-label="Vendors pagination">
                    <ul class="pagination pagination-sm justify-content-center mb-0">
                        <li class="page-item {{ $vendorPage == 1 ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['vendor_page' => $vendorPage - 1]) }}#digital-vendors">Previous</a>
                        </li>
                        <li class="page-item disabled"><span class="page-link">Page {{ $vendorPage }} of {{ $vendors['total_pages'] }}</span></li>
                        <li class="page-item {{ $vendorPage >= ($vendors['total_pages'] ?? 1) ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['vendor_page' => $vendorPage + 1]) }}#digital-vendors">Next</a>
                        </li>
                    </ul>
                </nav>
            </div>
            @endif
        </div>
        </div>

        {{-- ---- Contracts tab ---- --}}
        <div class="tab-pane fade" id="tab-contracts" role="tabpanel">
        <div class="db-table-wrap mb-5" id="all-digital-contracts">
            <div class="px-3 pt-3">
                <form method="GET" action="{{ url()->current() }}#all-digital-contracts" class="db-filter-bar dr-filter-form">
                    @foreach(request()->except(['contract_q','contract_method','contract_page']) as $k => $v)
                        <input type="hidden" name="{{ $k }}" value="{{ $v }}">
                    @endforeach
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input type="search" name="contract_q" value="{{ $contractQ }}" placeholder="Search vendor, title, agency, ID&hellip;" aria-label="Search contracts">
                    </div>
                    <div class="db-field">
                        <label for="contract_method">Procurement method</label>
                        <select name="contract_method" id="contract_method">
                            <option value="">All methods</option>
                            @foreach(($contractOptions['methods'] ?? []) as $m)
                                <option value="{{ $m }}" {{ $contractMethod === $m ? 'selected' : '' }}>{{ $m }}</option>
                            @endforeach
                        </select>
                    </div>
                    <button type="submit" class="db-btn db-btn-primary db-btn-sm"><i class="bi bi-funnel"></i> Apply</button>
                    @if($contractQ || $contractMethod)
                        <a href="{{ url()->current() }}?{{ http_build_query(request()->except(['contract_q','contract_method','contract_page'])) }}#all-digital-contracts" class="db-btn db-btn-ghost db-btn-sm">Clear</a>
                    @endif
                </form>
            </div>
            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead>
                        <tr>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'vendor', 'contract_order' => ($contractSort == 'vendor' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    Vendor @if($contractSort == 'vendor'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>Agency</th>
                            <th>Contract ID</th>
                            <th>Title</th>
                            <th>Method</th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'date', 'contract_order' => ($contractSort == 'date' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    Start Date @if($contractSort == 'date'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'end_date', 'contract_order' => ($contractSort == 'end_date' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    End Date @if($contractSort == 'end_date'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'amount', 'contract_order' => ($contractSort == 'amount' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    Amount @if($contractSort == 'amount'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>Classification</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse(($contracts['contracts'] ?? []) as $c)
                        <tr>
                            <td>
                                @if($c['vendor_id'] ?? null)
                                    <a href="/procurement/vendor/{{ $c['vendor_id'] }}">{{ $c['vendor_name'] }}</a>
                                @else
                                    <a href="/procurement/vendors?q={{ urlencode($c['vendor_name']) }}">{{ $c['vendor_name'] }}</a>
                                @endif
                            </td>
                            <td>{{ $c['agency'] }}</td>
                            <td><a href="/procurement/contract/{{ $c['ctr_id'] ?? $c['contract_id'] }}">{{ $c['contract_id'] }}</a></td>
                            <td class="text-muted small">{{ $c['contract_title'] ?? '' }}</td>
                            <td class="text-muted small">{{ $c['procurement_method'] ?? '' }}</td>
                            <td>{{ $c['start_date'] }}</td>
                            <td>{{ $c['end_date'] }}</td>
                            <td>${{ number_format($c['award_amount'] ?? 0, 0) }}</td>
                            <td><span class="db-badge db-badge-navy">{{ $c['classification'] ?? 'Digital' }}</span></td>
                        </tr>
                        @empty
                        <tr><td colspan="9" class="text-center text-muted py-4">No contracts match your filters.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
            @if(($contracts['total_pages'] ?? 0) > 1)
            <div class="db-table-footer">
                <nav aria-label="Contracts pagination">
                    <ul class="pagination pagination-sm justify-content-center mb-0">
                        <li class="page-item {{ $contractPage == 1 ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['contract_page' => $contractPage - 1]) }}#all-digital-contracts">Previous</a>
                        </li>
                        <li class="page-item disabled"><span class="page-link">Page {{ $contractPage }} of {{ $contracts['total_pages'] }}</span></li>
                        <li class="page-item {{ $contractPage >= ($contracts['total_pages'] ?? 1) ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['contract_page' => $contractPage + 1]) }}#all-digital-contracts">Next</a>
                        </li>
                    </ul>
                </nav>
            </div>
            @endif
        </div>
        </div>

        </div> {{-- /.tab-content --}}

        {{-- Research Notes --}}
        <div class="db-alert db-alert-info mt-2" role="alert">
            <i class="bi bi-info-circle"></i>
            <div class="db-alert-body">
                <strong>Research and Methodology Notes</strong>
                <p class="mb-0">
                    This analysis involves custom categorization of vendors and contracts. Build-vs-buy,
                    license detection and function categories are produced by an AI pass (Gemini) over each
                    contract &mdash; a prompt to investigate, not a determination. Special thanks to the
                    <a href="https://github.com/htownley/nyc-tech-spending" target="_blank" rel="noopener" class="fw-semibold">nyc-tech-spending</a>
                    project for the vendor tags and contract-analysis methodologies that supported this dashboard.
                </p>
            </div>
        </div>

    </div> <!-- /.container -->
</div> <!-- /.inner_container -->

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {
    DBChart.apply(Chart);
    const currencyFmt = (val) => '$' + val.toLocaleString(undefined, { maximumFractionDigits: 0 });
    const millionsFmt = DBChart.money;
    const chartData = @json($charts ?? []);

    if (chartData.trend && document.getElementById('digitalTrendChart')) {
        new Chart(document.getElementById('digitalTrendChart'), {
            type: 'bar',
            data: { labels: chartData.trend.labels || [], datasets: [{ label: 'Awarded Amount', data: chartData.trend.values || [], backgroundColor: DBChart.navy, borderRadius: 4 }] },
            options: { responsive: true, maintainAspectRatio: false,
                scales: { y: { ticks: { callback: millionsFmt }, grid: { borderDash: [2, 4] } }, x: { grid: { display: false } } },
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => currencyFmt(c.parsed.y) } } } }
        });
    }
    if (chartData.agencies && document.getElementById('digitalAgencyChart')) {
        new Chart(document.getElementById('digitalAgencyChart'), {
            type: 'doughnut',
            data: { labels: chartData.agencies.labels || [], datasets: [{ data: chartData.agencies.values || [], backgroundColor: DBChart.palette, borderWidth: 1 }] },
            options: { responsive: true, maintainAspectRatio: false, cutout: '60%',
                plugins: { legend: { position: 'right', labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
                    tooltip: { callbacks: { label: (c) => c.label + ': ' + currencyFmt(c.parsed) } } } }
        });
    }

    // Keep the right tab open after a server-side reload (sort/filter/paginate
    // links carry #digital-vendors / #all-digital-contracts).
    var tabFor = { '#all-digital-contracts': 'tab-contracts-btn', '#digital-vendors': 'tab-vendors-btn' };
    var btnId = tabFor[window.location.hash];
    if (btnId && window.bootstrap) { new bootstrap.Tab(document.getElementById(btnId)).show(); }
    document.querySelectorAll('#dsTabs button').forEach(function (b) {
        b.addEventListener('shown.bs.tab', function (e) {
            var anchor = e.target.getAttribute('data-bs-target') === '#tab-contracts' ? 'all-digital-contracts' : 'digital-vendors';
            history.replaceState(null, '', '#' + anchor);
        });
    });
});
</script>
@endsection
