{{-- AJAX-loaded Related Transactions Table Partial
     Expects: $txFilterParam (e.g. 'vendor' or 'agency') and $txFilterValue to be set.
     Optional: $txHeading / $txNote — the filter is NOT always "this record". On a
     contract profile this table is filtered by VENDOR, so it shows that vendor's
     citywide payments; callers should say so rather than implying otherwise. --}}
<div id="section-transactions" class="db-anchor mb-5">
    <div class="d-flex justify-content-between align-items-center mb-2" style="gap: var(--db-space-2);">
        <div class="d-flex align-items-center" style="gap: var(--db-space-15);">
            <h4 class="mb-0">{{ $txHeading ?? 'Recent Transactions' }}</h4>
            <span id="txCount" class="db-badge db-badge-neutral">—</span>
        </div>
        @include('procurement.partials.source_badge', ['source' => 'checkbook'])
    </div>
    @if($txNote ?? false)
    <p class="text-muted mb-2" style="font-size: var(--db-text-sm);">{{ $txNote }}</p>
    @endif

    <div class="db-table-wrap">
        <div class="table-responsive">
            <table class="db-table">
                <thead>
                    <tr>
                        <th>Payee</th>
                        <th>Agency</th>
                        <th>Contract ID</th>
                        <th class="db-num">Amount</th>
                        <th>Date</th>
                        <th>Category</th>
                    </tr>
                </thead>
                <tbody id="txTableBody">
                    <tr>
                        <td colspan="6" class="text-center" style="padding: var(--db-space-4);">
                            <div class="db-spinner" style="margin: 0 auto;" role="status"></div>
                            <span class="text-muted">Loading transactions…</span>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
(function() {
    const filterParam = @json($txFilterParam ?? '');
    const filterValue = @json($txFilterValue ?? '');
    if (!filterParam || !filterValue) return;

    const apiBase = @json(config('apis.fapi_public_entry', 'https://api.databook.nyc'));
    const url = `${apiBase}/oce/transactions?${filterParam}=${encodeURIComponent(filterValue)}&limit=10&sort=date&order=desc`;

    fetch(url)
        .then(r => r.json())
        .then(data => {
            const rows = data.data || [];
            const tbody = document.getElementById('txTableBody');
            const countBadge = document.getElementById('txCount');

            countBadge.textContent = data.total ? data.total.toLocaleString() + ' total' : '0';

            if (rows.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No transactions found.</td></tr>';
                return;
            }

            tbody.innerHTML = rows.map(tx => {
                const amt = parseFloat(tx.check_amount || 0);
                // #20: tx.ctr_id resolves the Checkbook contract_id to a PASSPort contract profile.
                // Link to the profile when resolved; else fall back to a contract search.
                let contractLink = '—';
                if (tx.ctr_id) {
                    contractLink = `<a href="/procurement/contract/${encodeURIComponent(tx.ctr_id)}" class="text-primary">${tx.passport_contract_id || tx.contract_id}</a>`;
                } else if (tx.contract_id) {
                    contractLink = `<a href="/procurement/contracts?q=${encodeURIComponent(tx.contract_id)}" class="text-primary">${tx.contract_id}</a>`;
                }
                // The API already resolves each payee to a PASSPort id (tx.vendor_id) —
                // it was fetched on every request and rendered as dead text. Link it.
                const payee = tx.payee_name || '—';
                const payeeCell = tx.vendor_id
                    ? `<a href="/procurement/vendor/${encodeURIComponent(tx.vendor_id)}">${payee}</a>`
                    : payee;
                return `<tr>
                    <td class="fw-semibold">${payeeCell}</td>
                    <td>${tx.agency || '—'}</td>
                    <td><small>${contractLink}</small></td>
                    <td class="db-num fw-semibold">$${amt.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                    <td><small>${tx.issue_date || '—'}</small></td>
                    <td><small class="text-muted">${tx.spending_category || '—'}</small></td>
                </tr>`;
            }).join('');
        })
        .catch(err => {
            console.error('Transactions load failed:', err);
            document.getElementById('txTableBody').innerHTML =
                '<tr><td colspan="6" class="text-center text-muted py-4">Could not load transactions.</td></tr>';
        });
})();
</script>
