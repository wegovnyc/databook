@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        {{-- Header --}}
        <div class="d-flex flex-wrap justify-content-between align-items-end mb-4" style="gap: var(--db-space-2);">
            <div>
                <div class="db-eyebrow">Procurement</div>
                <h1>Contract Explorer</h1>
                <p class="db-page-lead">Explore government contracts, solicitations and vendors using data from the Mayor's Office of Contract Services, Open Data, and Checkbook NYC.</p>
            </div>
            <a href="{{ route('procurement.datasources') }}" class="db-btn db-btn-outline">Learn More About the Data</a>
        </div>

        {{-- Summary stats --}}
        <div class="db-stat-grid mb-5">
            <a href="{{ route('procurement.contracts') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">Contracts</div>
                <div class="db-stat-value">{{ number_format($stats['contracts']) }}</div>
            </a>
            <a href="{{ route('procurement.vendors') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">Vendors</div>
                <div class="db-stat-value">{{ number_format($stats['vendors']) }}</div>
            </a>
            <a href="{{ route('procurement.solicitations') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">Solicitations</div>
                <div class="db-stat-value">{{ number_format($stats['solicitations']) }}</div>
            </a>
            <a href="{{ route('orgs') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">Agencies</div>
                <div class="db-stat-value">{{ number_format($stats['agencies']) }}</div>
            </a>
            <a href="{{ route('procurement.transactions') }}" class="db-stat is-accent" style="text-decoration:none;">
                <div class="db-stat-label">Total Spending @include('procurement.partials.source_badge', ['source' => 'checkbook'])</div>
                <div class="db-stat-value">${{ number_format(($stats['spending'] ?? 0) / 1e9, 1) }}B</div>
            </a>
        </div>

        {{-- Featured Research --}}
        <h3 class="mb-3">Featured Research</h3>
        <div class="db-card mb-5" style="overflow:hidden;">
            <div class="row g-0">
                <div class="col-md-8 d-flex align-items-center" style="background:var(--db-primary); color:#fff; padding:var(--db-space-5);">
                    <div>
                        <h2 style="color:#fff;" class="mb-3">Digital Service Reform</h2>
                        <p class="mb-4" style="color:var(--db-text-on-navy-muted); font-size:var(--db-text-md);">An in-depth analysis of who is selling digital services to NYC, what those services entail, when contracts expire, and identifying renewal risks.</p>
                        <a href="/research/digital-reform" class="db-btn db-btn-lg" style="background:var(--db-brand); color:var(--db-primary);">Explore Project</a>
                    </div>
                </div>
                <div class="col-md-4 d-flex align-items-center justify-content-center" style="background:var(--db-navy-050); padding:var(--db-space-4); color:var(--db-gray-400);">
                    <i class="bi bi-laptop" style="font-size: 5rem;"></i>
                </div>
            </div>
        </div>

        {{-- Insights Dashboard --}}
        <h3 class="mb-3">Insights</h3>

        <div class="db-chart-card mb-4">
            <div class="db-chart-head"><span class="db-chart-title">Spending Trends @include('procurement.partials.source_badge', ['source' => 'checkbook'])</span></div>
            <div class="db-chart-body" style="height: 300px;"><canvas id="timeChart"></canvas></div>
        </div>

        <div class="row">
            <div class="col-md-6 mb-4">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Top Agencies (Spending) @include('procurement.partials.source_badge', ['source' => 'mocs'])</span></div>
                    <div class="db-chart-body" style="height: 250px;"><canvas id="agencyChart"></canvas></div>
                </div>
            </div>
            <div class="col-md-6 mb-4">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Top Vendors (Spending) @include('procurement.partials.source_badge', ['source' => 'mocs'])</span></div>
                    <div class="db-chart-body" style="height: 250px;"><canvas id="vendorChart"></canvas></div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6 mb-4">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Top Industries @include('procurement.partials.source_badge', ['source' => 'mocs'])</span></div>
                    <div class="db-chart-body" style="height: 280px;"><canvas id="industryChart"></canvas></div>
                </div>
            </div>
            <div class="col-md-6 mb-4">
                <div class="db-chart-card h-100">
                    <div class="db-chart-head"><span class="db-chart-title">Procurement Methods @include('procurement.partials.source_badge', ['source' => 'mocs'])</span></div>
                    <div class="db-chart-body" style="height: 280px;"><canvas id="methodChart"></canvas></div>
                </div>
            </div>
        </div>

        {{-- Capital Projects — mini dashboard (CPDB cost data + Checkbook capital spending) --}}
        <div class="d-flex flex-wrap justify-content-between align-items-end mb-3 mt-4" style="gap:var(--db-space-2);">
            <div>
                <div class="db-eyebrow">Capital Program</div>
                <h3 class="mb-1">Capital Projects</h3>
                <p class="db-page-lead mb-0">The City's managed capital program &mdash; project cost and budget variance, plus actual capital spending. Source: NYC Capital Projects Database &amp; Checkbook NYC.</p>
            </div>
            <a href="{{ route('capital') }}" class="db-btn db-btn-primary"><i class="bi bi-buildings"></i> Explore Capital Projects</a>
        </div>
        {{-- Same globStats fields, labels + ×1000 scaling as /projects/capital so figures match exactly --}}
        <div class="db-stat-grid mb-4">
            <a href="{{ route('capital') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">Number of Projects</div>
                <div class="db-stat-value prj_stat gs_thousandscomma" id="projects_no">&nbsp;</div>
            </a>
            <a href="{{ route('capital') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">Original Cost</div>
                <div class="db-stat-value prj_stat gs_finshort" data-multiplier="1000" id="orig_cost">&nbsp;</div>
            </a>
            <a href="{{ route('capital') }}" class="db-stat is-accent" style="text-decoration:none;">
                <div class="db-stat-label">Current Cost</div>
                <div class="db-stat-value prj_stat gs_finshort" data-multiplier="1000" id="curr_cost">&nbsp;</div>
            </a>
            <a href="{{ route('capital') }}" class="db-stat" style="text-decoration:none;">
                <div class="db-stat-label">Amount Over Budget</div>
                <div class="db-stat-value prj_stat gs_finshort" data-multiplier="1000" id="over_budg_am">&nbsp;</div>
            </a>
        </div>
        {{-- Actual capital spending by fiscal year — Checkbook 'Capital Contracts' payments (cash paid out; distinct from the CPDB budget/cost figures above) --}}
        @if(!empty($capitalSpend['values']))
        <div class="db-card mb-5" style="overflow:hidden; padding:var(--db-space-4);">
            <div class="db-chart-head"><span class="db-chart-title">Actual Capital Spending by Fiscal Year @include('procurement.partials.source_badge', ['source' => 'checkbook'])</span></div>
            <div class="db-chart-body" style="height: 280px;"><canvas id="capitalSpendChart"></canvas></div>
        </div>
        @endif

        {{-- Quick Actions --}}
        <h3 class="mb-3 mt-4">Explore Data</h3>
        <div class="row">
            <div class="col-md-4 mb-3">
                <a href="{{ route('procurement.vendors') }}" class="db-btn db-btn-outline db-btn-lg w-100"><i class="bi bi-building"></i> Search Vendors</a>
            </div>
            <div class="col-md-4 mb-3">
                <a href="{{ route('procurement.contracts') }}" class="db-btn db-btn-outline db-btn-lg w-100"><i class="bi bi-file-earmark-text"></i> Search Contracts</a>
            </div>
            <div class="col-md-4 mb-3">
                <a href="{{ route('procurement.solicitations') }}" class="db-btn db-btn-outline db-btn-lg w-100"><i class="bi bi-megaphone"></i> Browse Solicitations</a>
            </div>
        </div>

    </div>
</div>

<script>
    // Hydrate the capital mini-dashboard tiles from precomputed homepage stats,
    // using the same globStatView() formatter (gs_finshort/gs_thousandscomma) the
    // /projects/capital page uses, so figures match exactly.
    $(function () {
        try { globStatView(@json($globStats ?? [])); } catch (e) { console.warn('capital stats hydrate failed', e); }
    });
</script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
    DBChart.apply(Chart);

    document.addEventListener('DOMContentLoaded', function() {
        const money = DBChart.money;
        const commonOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) { label += ': '; }
                            const val = context.parsed.y !== undefined && context.parsed.y !== null ? context.parsed.y : context.parsed;
                            label += new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
                            return label;
                        }
                    }
                }
            }
        };

        // Actual Capital Spending by Fiscal Year (Bar) — Checkbook 'Capital Contracts'
        var capEl = document.getElementById('capitalSpendChart');
        if (capEl) {
            new Chart(capEl, {
                type: 'bar',
                data: {
                    labels: {!! json_encode($capitalSpend['labels'] ?? []) !!},
                    datasets: [{
                        label: 'Capital Spending',
                        data: {!! json_encode($capitalSpend['values'] ?? []) !!},
                        backgroundColor: DBChart.navy, borderRadius: 4
                    }]
                },
                options: { ...commonOptions, plugins: { ...commonOptions.plugins, legend: { display: false } },
                    scales: { y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { callback: money } }, x: { grid: { display: false } } }
                }
            });
        }

        // Time Chart (Line with area)
        new Chart(document.getElementById('timeChart'), {
            type: 'line',
            data: {
                labels: {!! json_encode($stats['charts']['time']['labels'] ?? []) !!},
                datasets: [{
                    label: 'Total Spending',
                    data: {!! json_encode($stats['charts']['time']['values'] ?? []) !!},
                    borderColor: DBChart.accent,
                    backgroundColor: DBChart.accentFill,
                    borderWidth: 2, fill: true, tension: 0.3, pointRadius: 3, pointHoverRadius: 6
                }]
            },
            options: { ...commonOptions, plugins: { ...commonOptions.plugins, legend: { display: false } },
                scales: { y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { callback: money } }, x: { grid: { display: false } } }
            }
        });

        // Top Agencies (Horizontal Bar)
        new Chart(document.getElementById('agencyChart'), {
            type: 'bar',
            data: {
                labels: {!! json_encode($stats['charts']['agencies']['labels'] ?? []) !!},
                datasets: [{ label: 'Spending', data: {!! json_encode($stats['charts']['agencies']['values'] ?? []) !!}, backgroundColor: DBChart.navy, borderRadius: 4 }]
            },
            options: { ...commonOptions, indexAxis: 'y',
                scales: { x: { grid: { color: DBChart.grid }, ticks: { callback: money } }, y: { grid: { display: false } } },
                plugins: { ...commonOptions.plugins, legend: { display: false } }
            }
        });

        // Top Vendors (Horizontal Bar)
        new Chart(document.getElementById('vendorChart'), {
            type: 'bar',
            data: {
                labels: {!! json_encode($stats['charts']['vendors']['labels'] ?? []) !!},
                datasets: [{ label: 'Spending', data: {!! json_encode($stats['charts']['vendors']['values'] ?? []) !!}, backgroundColor: DBChart.accent, borderRadius: 4 }]
            },
            options: { ...commonOptions, indexAxis: 'y',
                scales: { x: { grid: { color: DBChart.grid }, ticks: { callback: money } }, y: { grid: { display: false } } },
                plugins: { ...commonOptions.plugins, legend: { display: false } }
            }
        });

        // Industries (Doughnut)
        const industryLabels = {!! json_encode($stats['charts']['industries']['labels'] ?? []) !!};
        const industryValues = {!! json_encode($stats['charts']['industries']['values'] ?? []) !!};
        if (industryLabels.length > 0) {
            new Chart(document.getElementById('industryChart'), {
                type: 'doughnut',
                data: { labels: industryLabels, datasets: [{ data: industryValues, backgroundColor: DBChart.palette, borderWidth: 1 }] },
                options: { responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 }, padding: 8 } },
                        tooltip: { callbacks: { label: ctx => '$' + ctx.raw.toLocaleString() } } } }
            });
        }

        // Procurement Methods (Doughnut)
        const methodLabels = {!! json_encode($stats['charts']['methods']['labels'] ?? []) !!};
        const methodValues = {!! json_encode($stats['charts']['methods']['values'] ?? []) !!};
        if (methodLabels.length > 0) {
            new Chart(document.getElementById('methodChart'), {
                type: 'doughnut',
                data: { labels: methodLabels, datasets: [{ data: methodValues, backgroundColor: DBChart.palette, borderWidth: 1 }] },
                options: { responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 }, padding: 8 } },
                        tooltip: { callbacks: { label: ctx => '$' + ctx.raw.toLocaleString() } } } }
            });
        }
    });
</script>
@endsection
