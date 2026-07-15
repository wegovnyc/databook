{{--
    Shared agency-procurement body (design-system `.db-*`).

    Single source of truth for the agency procurement overview — rendered by BOTH
    the standalone procurement page (procurement/org_procurement.blade.php) and the
    org-profile procurement section (org_procurement_section.blade.php), so the two
    surfaces can never drift again. Each parent supplies its own page chrome
    (procurement breadcrumb vs. org header) and then @includes this.

    Expects in scope (both controllers provide all of these):
      $agency            array   — ['name' => ...]
      $stats             array   — contracts / total_value / solicitations / vendors
      $monthly_activity  array   — [{month, contract_count}]
      $yearly_spending   array   — [{year, total_value}]
      $contracts         array   — contract rows
      $solicitations     array   — solicitation rows
      $vendors           array   — vendor rows
--}}
@php
    $agencyName = $agency['name'] ?? 'Agency';

    // Derived highlights from the contracts/vendors already in scope (no extra query).
    // Largest contract + count of contracts expiring within 12 months (renewal signal).
    $largest = null; $expiringSoon = 0;
    $nowTs = time(); $in12 = strtotime('+12 months');
    foreach ($contracts as $c) {
        $amt = (float) ($c['award_amount'] ?? 0);
        if (!$largest || $amt > (float) ($largest['award_amount'] ?? 0)) $largest = $c;
        $ts = !empty($c['end_date']) ? strtotime($c['end_date']) : 0;
        if ($ts && $ts >= $nowTs && $ts <= $in12) $expiringSoon++;
    }
    // /oce/agency/procurement returns vendors ordered by total_value desc.
    $topVendor = $vendors[0] ?? null;
@endphp

{{-- Contents navigation --}}
<div class="db-tabs mt-3 mb-4">
    <a class="db-tab" href="#highlights">Highlights</a>
    <a class="db-tab" href="#spending">Spending</a>
    <a class="db-tab" href="#contracts">Contracts ({{ count($contracts) }})</a>
    <a class="db-tab" href="#solicitations">Solicitations ({{ count($solicitations) }})</a>
    <a class="db-tab" href="#vendors">Vendors ({{ count($vendors) }})</a>
    <a class="db-tab" href="#transactions">Transactions</a>
</div>

{{-- Highlights --}}
<section id="highlights" class="db-anchor mb-5">
    <h3 class="mb-3">Highlights</h3>

    <div class="db-stat-grid mb-4">
        <div class="db-stat">
            <div class="db-stat-label">Contracts</div>
            <div class="db-stat-value">{{ number_format($stats['contracts'] ?? 0) }}</div>
        </div>
        <div class="db-stat is-accent">
            <div class="db-stat-label">Total Value @include('procurement.partials.source_badge', ['source' => 'mocs'])</div>
            <div class="db-stat-value">${{ number_format($stats['total_value'] ?? 0, 0) }}</div>
        </div>
        <div class="db-stat">
            <div class="db-stat-label">Solicitations</div>
            <div class="db-stat-value">{{ number_format($stats['solicitations'] ?? 0) }}</div>
        </div>
        <div class="db-stat">
            <div class="db-stat-label">Vendors</div>
            <div class="db-stat-value">{{ number_format($stats['vendors'] ?? 0) }}</div>
        </div>
    </div>

    {{-- Renewal signal — contracts expiring within 12 months. --}}
    @if($expiringSoon > 0)
    <div class="db-alert db-alert-warning" role="alert" style="margin-bottom: var(--db-space-4);">
        <i class="bi bi-exclamation-triangle"></i>
        <div class="db-alert-body"><strong>{{ number_format($expiringSoon) }} {{ $expiringSoon == 1 ? 'contract expires' : 'contracts expire' }} within 12 months.</strong> Review upcoming renewals in the Contracts tab.</div>
    </div>
    @endif

    {{-- Top vendor + largest contract summary cards. --}}
    @if($topVendor || $largest)
    <div class="row mb-4">
        @if($topVendor)
        <div class="col-md-6 mb-3">
            <div class="db-card h-100"><div class="db-card-body">
                <div style="font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted); margin-bottom: var(--db-space-1);">Top vendor</div>
                <div style="font-size: var(--db-text-lg); font-weight: var(--db-weight-semibold); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{{ $topVendor['name'] ?? '' }}">
                    @if(!empty($topVendor['vendor_id']))<a href="{{ route('procurement.vendor', ['id' => $topVendor['vendor_id']]) }}">{{ $topVendor['name'] ?? '—' }}</a>@else{{ $topVendor['name'] ?? '—' }}@endif
                </div>
                <div style="color: var(--db-primary); font-weight: var(--db-weight-semibold); font-variant-numeric: tabular-nums;">${{ number_format($topVendor['total_value'] ?? 0, 0) }}<span style="color: var(--db-text-muted); font-weight: var(--db-weight-regular);"> · {{ number_format($topVendor['contract_count'] ?? 0) }} contracts</span></div>
            </div></div>
        </div>
        @endif
        @if($largest)
        <div class="col-md-6 mb-3">
            <div class="db-card h-100"><div class="db-card-body">
                <div style="font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted); margin-bottom: var(--db-space-1);">Largest contract</div>
                <div style="font-size: var(--db-text-lg); font-weight: var(--db-weight-semibold); color: var(--db-primary); font-variant-numeric: tabular-nums;">${{ number_format($largest['award_amount'] ?? 0, 0) }}</div>
                <div style="color: var(--db-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{{ $largest['vendor'] ?? '' }}">
                    <span style="font-family: var(--db-font-mono); font-size: var(--db-text-xs);">@if(!empty($largest['ctr_id']))<a href="{{ route('procurement.contract', ['id' => $largest['ctr_id']]) }}">{{ $largest['contract_id'] ?? $largest['ctr_id'] }}</a>@else{{ $largest['contract_id'] ?? '—' }}@endif</span>@if(!empty($largest['vendor'])) · {{ $largest['vendor'] }}@endif
                </div>
            </div></div>
        </div>
        @endif
    </div>
    @endif

    <div class="row">
        <div class="col-lg-6 mb-4">
            <div class="db-chart-card h-100">
                <div class="db-chart-head"><span class="db-chart-title">Monthly Contract Activity</span></div>
                <div class="db-chart-body" style="height: 250px;"><canvas id="monthlyActivityChart"></canvas></div>
            </div>
        </div>
        <div class="col-lg-6 mb-4">
            <div class="db-chart-card h-100">
                <div class="db-chart-head"><span class="db-chart-title">Spending By Year</span></div>
                <div class="db-chart-body" style="height: 250px;"><canvas id="yearlySpendingChart"></canvas></div>
            </div>
        </div>
    </div>

    <div class="row">
        <div class="col-lg-6 mb-4">
            <div class="db-chart-card h-100">
                <div class="db-chart-head"><span class="db-chart-title">Top Vendors (By Spending)</span></div>
                <div class="db-chart-body" style="height: 300px;"><canvas id="vendorPieChart"></canvas></div>
            </div>
        </div>
        <div class="col-lg-6 mb-4">
            <div class="db-chart-card h-100">
                <div class="db-chart-head"><span class="db-chart-title">Top 10 Vendors</span></div>
                <div class="table-responsive" style="max-height: 300px;">
                    <table class="db-table">
                        <thead><tr><th>Vendor</th><th class="db-num">Value</th></tr></thead>
                        <tbody>
                            @foreach(array_slice($vendors, 0, 10) as $vendor)
                            <tr>
                                <td>{{ Str::limit($vendor['name'], 35) }}</td>
                                <td class="db-num">${{ number_format($vendor['total_value'] ?? 0, 0) }}</td>
                            </tr>
                            @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</section>

{{-- Checkbook Spending (agency-scoped, lazy-loaded) — actual payments + M/WBE +
     sub-vendor cuts. Distinct from "Contracts" (registered award value): this is
     money actually paid out, sourced from Checkbook NYC. --}}
<section id="spending" class="db-anchor mb-5">
    <div class="d-flex justify-content-between align-items-center mb-3" style="gap: var(--db-space-2);">
        <div class="d-flex align-items-center" style="gap: var(--db-space-15);">
            <h3 class="mb-0">Checkbook Spending @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h3>
        </div>
        <a href="{{ route('procurement.transactions.search', ['agency' => $agencyName]) }}" class="db-btn db-btn-outline db-btn-sm">Explore spending →</a>
    </div>

    <div class="db-stat-grid mb-4" id="agSpendStats">
        <div class="db-stat"><div class="db-stat-label">Actual spending</div><div class="db-stat-value">
            <span class="db-spinner" role="status" style="width:1rem;height:1rem;"></span></div></div>
    </div>

    <div class="row">
        <div class="col-lg-6 mb-4" id="agMwbeCard" style="display:none;">
            <div class="db-card h-100"><div class="db-card-body">
                <h3 style="margin: 0 0 var(--db-space-1); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">Spending by M/WBE category</h3>
                <div class="db-ranked-list" id="agMwbeList"></div>
            </div></div>
        </div>
        <div class="col-lg-6 mb-4" id="agSubCard" style="display:none;">
            <div class="db-card h-100"><div class="db-card-body">
                <h3 style="margin: 0 0 var(--db-space-1); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted);">Top sub-vendors</h3>
                <div class="db-ranked-list" id="agSubList"></div>
            </div></div>
        </div>
    </div>
</section>

{{-- Contracts --}}
<section id="contracts" class="db-anchor mb-5">
    <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
        <h3 class="mb-0">Contracts</h3><span class="db-badge db-badge-neutral">{{ count($contracts) }}</span>
    </div>
    <div class="db-table-wrap">
        <div class="db-table-toolbar">
            <span class="db-table-count">Show
                <select id="contractsPerPage" class="db-input" style="width:auto; display:inline-block; padding:2px 8px;">
                    <option value="10" selected>10</option><option value="25">25</option><option value="50">50</option><option value="100">100</option>
                </select> entries</span>
            <div class="db-spacer"></div>
            <div id="contractsPagination" class="d-flex align-items-center" style="gap: var(--db-space-1);"></div>
        </div>
        <div class="table-responsive">
            <table class="db-table" id="contractsTable">
                <thead>
                    <tr>
                        <th>Contract ID</th>
                        <th>Title</th>
                        <th class="sortable" data-table="contracts" data-key="vendor" data-type="string">Vendor <span class="sort-icon"></span></th>
                        <th class="db-num sortable" data-table="contracts" data-key="award_amount" data-type="number">Amount <span class="sort-icon"></span></th>
                        <th class="sortable" data-table="contracts" data-key="start_date" data-type="string">Start <span class="sort-icon"></span></th>
                        <th class="sortable" data-table="contracts" data-key="end_date" data-type="string">End <span class="sort-icon"></span></th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="contractsTableBody"></tbody>
            </table>
        </div>
    </div>
</section>

{{-- Solicitations --}}
<section id="solicitations" class="db-anchor mb-5">
    <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
        <h3 class="mb-0">Solicitations</h3><span class="db-badge db-badge-neutral">{{ count($solicitations) }}</span>
    </div>
    <div class="db-table-wrap">
        <div class="db-table-toolbar">
            <span class="db-table-count">Show
                <select id="solicitationsPerPage" class="db-input" style="width:auto; display:inline-block; padding:2px 8px;">
                    <option value="10" selected>10</option><option value="25">25</option><option value="50">50</option><option value="100">100</option>
                </select> entries</span>
            <div class="db-spacer"></div>
            <div id="solicitationsPagination" class="d-flex align-items-center" style="gap: var(--db-space-1);"></div>
        </div>
        <div class="table-responsive">
            <table class="db-table" id="solicitationsTable">
                <thead>
                    <tr>
                        <th>EPIN</th>
                        <th>Title</th>
                        <th>Method</th>
                        <th class="sortable" data-table="solicitations" data-key="release_date" data-type="string">Release Date <span class="sort-icon"></span></th>
                        <th class="sortable" data-table="solicitations" data-key="due_date" data-type="string">Due Date <span class="sort-icon"></span></th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="solicitationsTableBody"></tbody>
            </table>
        </div>
    </div>
</section>

{{-- Vendors --}}
<section id="vendors" class="db-anchor mb-5">
    <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
        <h3 class="mb-0">Vendors</h3><span class="db-badge db-badge-neutral">{{ count($vendors) }}</span>
    </div>
    <div class="db-table-wrap">
        <div class="db-table-toolbar">
            <span class="db-table-count">Show
                <select id="vendorsPerPage" class="db-input" style="width:auto; display:inline-block; padding:2px 8px;">
                    <option value="10" selected>10</option><option value="25">25</option><option value="50">50</option><option value="100">100</option>
                </select> entries</span>
            <div class="db-spacer"></div>
            <div id="vendorsPagination" class="d-flex align-items-center" style="gap: var(--db-space-1);"></div>
        </div>
        <div class="table-responsive">
            <table class="db-table" id="vendorsTable">
                <thead>
                    <tr>
                        <th class="sortable" data-table="vendors" data-key="name" data-type="string">Vendor <span class="sort-icon"></span></th>
                        <th class="db-num sortable" data-table="vendors" data-key="contract_count" data-type="number">Contracts <span class="sort-icon"></span></th>
                        <th class="db-num sortable" data-table="vendors" data-key="total_value" data-type="number">Total Value @include('procurement.partials.source_badge', ['source' => 'mocs']) <span class="sort-icon"></span></th>
                    </tr>
                </thead>
                <tbody id="vendorsTableBody"></tbody>
            </table>
        </div>
    </div>
</section>

{{-- Transactions (AJAX lazy-loaded) --}}
<section id="transactions" class="db-anchor mb-5">
    <div class="d-flex justify-content-between align-items-center mb-3" style="gap: var(--db-space-2);">
        <div class="d-flex align-items-center" style="gap: var(--db-space-15);">
            <h3 class="mb-0">Recent Transactions @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h3>
            <span id="orgTxCount" class="db-badge db-badge-neutral">—</span>
        </div>
        <a href="{{ route('procurement.transactions.search', ['agency' => $agencyName]) }}" class="db-btn db-btn-outline db-btn-sm">View All Transactions →</a>
    </div>
    <div class="db-table-wrap">
        <div class="table-responsive">
            <table class="db-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Payee</th>
                        <th>Contract ID</th>
                        <th class="db-num">Amount</th>
                        <th>Category</th>
                    </tr>
                </thead>
                <tbody id="orgTxTableBody">
                    <tr>
                        <td colspan="5" class="text-center" style="padding: var(--db-space-4);">
                            <div class="db-spinner" style="margin: 0 auto;" role="status"></div>
                            <span class="text-muted">Loading transactions…</span>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</section>

<style>
    /* JS-generated pagination buttons + sort affordances (token-themed) */
    .pagination-btn { min-width: 32px; height: 32px; padding: 0 8px; border: 1px solid var(--db-border); background: #fff; color: var(--db-link); cursor: pointer; border-radius: var(--db-radius-sm); font-size: var(--db-text-xs); }
    .pagination-btn:hover { background: var(--db-navy-050); }
    .pagination-btn.active { background: var(--db-primary); color: #fff; border-color: var(--db-primary); }
    .pagination-btn:disabled { cursor: not-allowed; opacity: 0.5; }
    table.db-table thead th.sortable { cursor: pointer; }
    table.db-table thead th.sortable:hover { color: var(--db-primary); }
    .sort-icon { font-size: 0.7em; color: var(--db-primary); }
</style>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {
    DBChart.apply(Chart);
    // Data from server
    const contractsData = @json($contracts);
    const solicitationsData = @json($solicitations);
    const vendorsData = @json($vendors);

    // Sort + Pagination helper
    const sortState = {}; // { tableName: { key, dir } }

    function createPaginator(tableName, data, tbodyId, paginationId, perPageId, renderRow) {
        let currentPage = 1;
        let perPage = parseInt(document.getElementById(perPageId).value);
        let sortedData = data.slice(); // mutable copy

        function sortBy(key, type) {
            const state = sortState[tableName] || {};
            const newDir = (state.key === key && state.dir === 'asc') ? 'desc' : 'asc';
            sortState[tableName] = { key, dir: newDir };

            sortedData.sort((a, b) => {
                let va = a[key], vb = b[key];
                if (type === 'number') { va = parseFloat(va) || 0; vb = parseFloat(vb) || 0; }
                else { va = (va || '').toString().toLowerCase(); vb = (vb || '').toString().toLowerCase(); }
                if (va < vb) return newDir === 'asc' ? -1 : 1;
                if (va > vb) return newDir === 'asc' ? 1 : -1;
                return 0;
            });
            currentPage = 1;
            updateSortIcons();
            render();
        }

        function updateSortIcons() {
            document.querySelectorAll(`.sortable[data-table="${tableName}"] .sort-icon`).forEach(el => { el.textContent = ''; });
            const state = sortState[tableName];
            if (state) {
                const th = document.querySelector(`.sortable[data-table="${tableName}"][data-key="${state.key}"] .sort-icon`);
                if (th) th.textContent = state.dir === 'asc' ? ' ▲' : ' ▼';
            }
        }

        function render() {
            const tbody = document.getElementById(tbodyId);
            const totalPages = Math.ceil(sortedData.length / perPage);
            const start = (currentPage - 1) * perPage;
            const end = start + perPage;
            const pageData = sortedData.slice(start, end);

            tbody.innerHTML = pageData.length ? pageData.map(renderRow).join('') :
                '<tr><td colspan="7" class="text-muted text-center py-4">No data found</td></tr>';

            const paginationDiv = document.getElementById(paginationId);
            let paginationHtml = `<span class="text-muted small me-2">Page ${currentPage} of ${totalPages || 1}</span>`;
            paginationHtml += `<button class="pagination-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="window['${tbodyId}Paginator'].prev()">‹</button>`;
            paginationHtml += `<button class="pagination-btn" ${currentPage >= totalPages ? 'disabled' : ''} onclick="window['${tbodyId}Paginator'].next()">›</button>`;
            paginationDiv.innerHTML = paginationHtml;
        }

        function next() { if (currentPage < Math.ceil(sortedData.length / perPage)) { currentPage++; render(); } }
        function prev() { if (currentPage > 1) { currentPage--; render(); } }

        document.getElementById(perPageId).addEventListener('change', (e) => { perPage = parseInt(e.target.value); currentPage = 1; render(); });

        return { render, next, prev, sortBy };
    }

    // Contract row renderer
    function renderContractRow(c) {
        const statusClass = (c.status === 'Active') ? 'db-badge-success' : 'db-badge-neutral';
        return `<tr>
            <td><a href="/procurement/contract/${c.ctr_id}" class="fw-semibold">${c.contract_id || c.ctr_id}</a></td>
            <td class="text-muted">${c.contract_title || ''}</td>
            <td>${(c.vendor || '').substring(0, 40)}</td>
            <td class="db-num">$${(c.award_amount || 0).toLocaleString()}</td>
            <td class="text-nowrap">${c.start_date || '-'}</td>
            <td class="text-nowrap">${c.end_date || '-'}</td>
            <td><span class="db-badge ${statusClass}"><span class="db-dot"></span>${c.status || '-'}</span></td>
        </tr>`;
    }

    // Solicitation row renderer
    function renderSolicitationRow(s) {
        const statusClass = (s.status === 'Open') ? 'db-badge-info' : 'db-badge-neutral';
        return `<tr>
            <td><a href="/procurement/solicitation/${s.epin}" class="fw-semibold">${s.epin}</a></td>
            <td>${(s.title || '').substring(0, 50)}</td>
            <td>${s.method || '-'}</td>
            <td class="text-nowrap">${s.release_date || '-'}</td>
            <td class="text-nowrap">${s.due_date || '-'}</td>
            <td><span class="db-badge ${statusClass}"><span class="db-dot"></span>${s.status || '-'}</span></td>
        </tr>`;
    }

    // Vendor row renderer
    function renderVendorRow(v) {
        const vendorLink = v.vendor_id ?
            `<a href="/procurement/vendor/${v.vendor_id}" class="fw-semibold">${v.name}</a>` :
            v.name;
        return `<tr>
            <td>${vendorLink}</td>
            <td class="db-num">${(v.contract_count || 0).toLocaleString()}</td>
            <td class="db-num fw-semibold">$${(v.total_value || 0).toLocaleString()}</td>
        </tr>`;
    }

    // Initialize paginators with sort support
    window.contractsTableBodyPaginator = createPaginator('contracts', contractsData, 'contractsTableBody', 'contractsPagination', 'contractsPerPage', renderContractRow);
    window.solicitationsTableBodyPaginator = createPaginator('solicitations', solicitationsData, 'solicitationsTableBody', 'solicitationsPagination', 'solicitationsPerPage', renderSolicitationRow);
    window.vendorsTableBodyPaginator = createPaginator('vendors', vendorsData, 'vendorsTableBody', 'vendorsPagination', 'vendorsPerPage', renderVendorRow);

    // Bind sort click handlers
    document.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const table = th.dataset.table;
            const key = th.dataset.key;
            const type = th.dataset.type || 'string';
            const paginatorMap = { contracts: window.contractsTableBodyPaginator, solicitations: window.solicitationsTableBodyPaginator, vendors: window.vendorsTableBodyPaginator };
            if (paginatorMap[table]) paginatorMap[table].sortBy(key, type);
        });
    });

    // Initial render
    window.contractsTableBodyPaginator.render();
    window.solicitationsTableBodyPaginator.render();
    window.vendorsTableBodyPaginator.render();

    // Charts
    const monthlyData = @json($monthly_activity ?? []);
    if (monthlyData.length > 0) {
        new Chart(document.getElementById('monthlyActivityChart'), {
            type: 'bar',
            data: {
                labels: monthlyData.map(d => d.month),
                datasets: [{
                    label: 'Contracts',
                    data: monthlyData.map(d => d.contract_count),
                    backgroundColor: DBChart.navy,
                    borderRadius: 4
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: DBChart.grid } }, x: { grid: { display: false } } } }
        });
    }

    const yearlyData = @json($yearly_spending ?? []);
    if (yearlyData.length > 0) {
        new Chart(document.getElementById('yearlySpendingChart'), {
            type: 'bar',
            data: {
                labels: yearlyData.map(d => d.year),
                datasets: [{
                    label: 'Spending ($)',
                    data: yearlyData.map(d => d.total_value),
                    backgroundColor: DBChart.accent,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => '$' + ctx.raw.toLocaleString() } } },
                scales: { y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { callback: DBChart.money } }, x: { grid: { display: false } } }
            }
        });
    }

    const topVendors = @json(array_slice($vendors, 0, 10));
    if (topVendors.length > 0) {
        new Chart(document.getElementById('vendorPieChart'), {
            type: 'doughnut',
            data: {
                labels: topVendors.map(d => d.name.substring(0, 25) + (d.name.length > 25 ? '...' : '')),
                datasets: [{ data: topVendors.map(d => d.total_value), backgroundColor: DBChart.palette, borderWidth: 1 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } }, tooltip: { callbacks: { label: ctx => '$' + ctx.raw.toLocaleString() } } }
            }
        });
    }
});

// Lazy-load transactions
(function() {
    const agencyName = @json($agencyName);
    if (!agencyName) return;
    const apiBase = @json(config('apis.fapi_public_entry', 'https://api.databook.nyc'));
    const url = `${apiBase}/oce/transactions?agency=${encodeURIComponent(agencyName)}&limit=10&sort=date&order=desc`;

    fetch(url)
        .then(r => r.json())
        .then(data => {
            const rows = data.data || [];
            const tbody = document.getElementById('orgTxTableBody');
            const countBadge = document.getElementById('orgTxCount');
            countBadge.textContent = data.total ? data.total.toLocaleString() + ' total' : '0';
            if (rows.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No transactions found.</td></tr>';
                return;
            }
            tbody.innerHTML = rows.map(tx => {
                const amt = parseFloat(tx.check_amount || 0);
                const contractLink = tx.contract_id
                    ? `<a href="/procurement/contracts?q=${encodeURIComponent(tx.contract_id)}" class="text-primary">${tx.contract_id}</a>`
                    : '—';
                return `<tr>
                    <td class="text-nowrap"><small>${tx.issue_date || '—'}</small></td>
                    <td class="fw-semibold">${tx.payee_name || '—'}</td>
                    <td><small>${contractLink}</small></td>
                    <td class="db-num fw-semibold">$${amt.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                    <td><small class="text-muted">${tx.spending_category || '—'}</small></td>
                </tr>`;
            }).join('');
        })
        .catch(err => {
            console.error('Transactions load failed:', err);
            document.getElementById('orgTxTableBody').innerHTML =
                '<tr><td colspan="5" class="text-center text-muted py-4">Could not load transactions.</td></tr>';
        });
})();

// Agency-scoped Checkbook spending analytics (actual spending + M/WBE + sub-vendor).
// Lazy-loaded like transactions — these Parquet scans are slow for large agencies.
(function() {
    const agencyName = @json($agencyName);
    if (!agencyName) return;
    const apiBase = @json(config('apis.fapi_public_entry', 'https://api.databook.nyc'));
    const q = encodeURIComponent(agencyName);
    const money = n => {
        n = parseFloat(n || 0);
        if (n >= 1e9) return '$' + (n/1e9).toFixed(1) + 'B';
        if (n >= 1e6) return '$' + (n/1e6).toFixed(1) + 'M';
        if (n >= 1e3) return '$' + (n/1e3).toFixed(0) + 'K';
        return '$' + n.toLocaleString();
    };
    const tile = (label, value, sub, accent) =>
        `<div class="db-stat${accent ? ' is-accent' : ''}"><div class="db-stat-label">${label}</div>` +
        `<div class="db-stat-value">${value}</div>${sub ? `<div class="db-stat-sub">${sub}</div>` : ''}</div>`;

    // Three independent fetches; render whatever resolves.
    const jget = u => fetch(u).then(r => r.ok ? r.json() : null).catch(() => null);
    Promise.all([
        jget(`${apiBase}/oce/transactions?agency=${q}&limit=1`),
        jget(`${apiBase}/oce/spending/mwbe?agency=${q}`),
        jget(`${apiBase}/oce/spending/subvendors?agency=${q}&limit=8`),
    ]).then(([tx, mwbe, sub]) => {
        // Stat tiles
        const stats = document.getElementById('agSpendStats');
        let tiles = tile('Actual spending', money(tx && tx.total_amount), 'paid out', true) +
                    tile('Payments', (tx && tx.total ? Number(tx.total).toLocaleString() : '0'), 'transactions');
        if (mwbe && mwbe.available) {
            tiles += tile('Certified M/WBE', money(mwbe.certified_mwbe && mwbe.certified_mwbe.total_amount), 'of spending');
            tiles += tile('Woman-owned', money(mwbe.woman_owned && mwbe.woman_owned.total_amount));
        } else if (sub && sub.payment_count > 0) {
            tiles += tile('Sub-vendor spending', money(sub.total_amount), Number(sub.payment_count).toLocaleString() + ' payments');
        }
        if (stats) stats.innerHTML = tiles;

        // M/WBE by-category card
        if (mwbe && mwbe.available && (mwbe.by_category || []).length) {
            const list = document.getElementById('agMwbeList');
            list.innerHTML = mwbe.by_category.slice(0, 8).map((c, i) =>
                `<div class="db-ranked-item"><span class="db-ranked-rank">${i+1}</span>` +
                `<span class="db-ranked-name" title="${c.category || ''}">${c.category || '—'}` +
                `<span style="color:var(--db-text-muted);font-size:var(--db-text-2xs);"> · ${Number(c.payment_count||0).toLocaleString()} payments</span></span>` +
                `<span class="db-ranked-value">${money(c.total_amount)}</span></div>`).join('');
            document.getElementById('agMwbeCard').style.display = '';
        }

        // Top sub-vendors card
        if (sub && (sub.top_subvendors || []).length) {
            const list = document.getElementById('agSubList');
            list.innerHTML = sub.top_subvendors.map((s, i) =>
                `<div class="db-ranked-item"><span class="db-ranked-rank">${i+1}</span>` +
                `<span class="db-ranked-name" title="${s.payee || ''}">${s.payee || '—'}` +
                (s.prime ? `<span style="color:var(--db-text-muted);font-size:var(--db-text-2xs);"> · via ${s.prime}</span>` : '') +
                `</span><span class="db-ranked-value">${money(s.amount)}</span></div>`).join('');
            document.getElementById('agSubCard').style.display = '';
        }
    });
})();
</script>
