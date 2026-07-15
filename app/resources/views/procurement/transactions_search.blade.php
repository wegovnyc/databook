@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@php
    $rows      = $data['data'] ?? [];
    $total     = $data['total'] ?? 0;
    $totalAmt  = $data['total_amount'] ?? 0;
    $page      = $data['page'] ?? 1;
    $pages     = $data['pages'] ?? 1;
    $fy        = (int) ($filters['fiscal_year'] ?? 2026);

    $compact = function ($n) {
        $n = (float) $n;
        if ($n >= 1e9) return '$' . number_format($n / 1e9, 1) . 'B';
        if ($n >= 1e6) return '$' . number_format($n / 1e6, 1) . 'M';
        if ($n >= 1e3) return '$' . number_format($n / 1e3, 0) . 'K';
        return '$' . number_format($n);
    };

    // Active-filter chips (optional filters only; fiscal year lives in its select).
    $chipLabels = [
        'agency' => 'Agency', 'expense_category' => 'Expense category',
        'spending_category' => 'Spending category', 'industry' => 'Industry',
        'mwbe_category' => 'M/WBE category', 'q' => 'Keyword',
    ];
    $baseQuery = request()->query();
    unset($baseQuery['page']);
    $chips = [];
    foreach ($chipLabels as $key => $label) {
        $val = $filters[$key] ?? '';
        if ($val !== '' && $val !== null) {
            $remove = $baseQuery; unset($remove[$key]);
            $chips[] = ['text' => "{$label}: {$val}", 'url' => route('procurement.transactions.search', $remove)];
        }
    }
    $minA = $filters['min_amount'] ?? ''; $maxA = $filters['max_amount'] ?? '';
    if ($minA !== '' || $maxA !== '') {
        $remove = $baseQuery; unset($remove['min_amount'], $remove['max_amount']);
        $label = 'Amount: ' . ($minA !== '' ? $compact($minA) : '$0') . ' – ' . ($maxA !== '' ? $compact($maxA) : 'any');
        $chips[] = ['text' => $label, 'url' => route('procurement.transactions.search', $remove)];
    }
    $dFrom = $filters['date_from'] ?? ''; $dTo = $filters['date_to'] ?? '';
    if ($dFrom !== '' || $dTo !== '') {
        $remove = $baseQuery; unset($remove['date_from'], $remove['date_to']);
        $label = 'Date: ' . ($dFrom !== '' ? $dFrom : 'any') . ' – ' . ($dTo !== '' ? $dTo : 'any');
        $chips[] = ['text' => $label, 'url' => route('procurement.transactions.search', $remove)];
    }
    if (($filters['sub_vendor'] ?? '') !== '') {
        $remove = $baseQuery; unset($remove['sub_vendor']);
        $label = 'Payment type: ' . ($filters['sub_vendor'] === 'Yes' ? 'Sub-vendor' : 'Direct');
        $chips[] = ['text' => $label, 'url' => route('procurement.transactions.search', $remove)];
    }
    foreach (['woman_owned' => 'Woman-owned', 'emerging' => 'Emerging (EBE)'] as $key => $label) {
        if (($filters[$key] ?? '') !== '') {
            $remove = $baseQuery; unset($remove[$key]);
            $chips[] = ['text' => "{$label}: {$filters[$key]}", 'url' => route('procurement.transactions.search', $remove)];
        }
    }
    // M/WBE controls only exist once the v2 re-ingest lands the columns; the API
    // signals that by returning an mwbe_category facet list.
    $mwbeReady = !empty($facets['mwbe_category']);
    $sortOptions = ['amount-desc' => 'Amount (high → low)', 'amount-asc' => 'Amount (low → high)', 'date-desc' => 'Date (newest)', 'vendor-asc' => 'Payee (A–Z)'];
@endphp

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-8);">

        <div style="display: flex; align-items: baseline; gap: var(--db-space-2); margin-bottom: var(--db-space-2);">
            <h1 style="margin: 0;">Transactions</h1>
            <span style="color: var(--db-text-muted); font-size: var(--db-text-sm);">FY{{ $fy }} spending</span>
        </div>

        <form method="GET" action="{{ route('procurement.transactions.search') }}">
            {{-- Facet filter bar --}}
            <div class="db-filter-bar">
                <div class="db-field" style="flex: 1 1 140px;">
                    <label for="f-fy">Fiscal year</label>
                    <select id="f-fy" name="fiscal_year">
                        @for($y = 2026; $y >= 2010; $y--)
                        <option value="{{ $y }}" {{ $fy == $y ? 'selected' : '' }}>FY{{ $y }}</option>
                        @endfor
                    </select>
                </div>
                @php
                    $facetFields = [
                        ['agency', 'Agency', 'All agencies', $facets['agency'] ?? []],
                        ['expense_category', 'Expense category', 'All categories', $facets['expense_category'] ?? []],
                        ['spending_category', 'Spending category', 'All', $facets['spending_category'] ?? []],
                        ['industry', 'Industry', 'All industries', $facets['industry'] ?? []],
                    ];
                @endphp
                @foreach($facetFields as [$name, $label, $allLabel, $opts])
                <div class="db-field" style="flex: 1 1 170px;">
                    <label for="f-{{ $name }}">{{ $label }}</label>
                    <select id="f-{{ $name }}" name="{{ $name }}" class="db-select">
                        <option value="">{{ $allLabel }}</option>
                        @foreach($opts as $o)
                        <option value="{{ $o['value'] }}" {{ ($filters[$name] ?? '') === $o['value'] ? 'selected' : '' }}>{{ $o['value'] }}</option>
                        @endforeach
                    </select>
                </div>
                @endforeach
                <div class="db-field" style="flex: 0 0 auto;">
                    <label>Amount range</label>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <input class="db-input" type="number" name="min_amount" value="{{ $filters['min_amount'] ?? '' }}" placeholder="Min $" style="width: 100px;" aria-label="Minimum amount">
                        <span style="color: var(--db-text-muted);">–</span>
                        <input class="db-input" type="number" name="max_amount" value="{{ $filters['max_amount'] ?? '' }}" placeholder="Max $" style="width: 100px;" aria-label="Maximum amount">
                    </div>
                </div>
                <div class="db-field" style="flex: 0 0 auto;">
                    <label>Date range</label>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <input class="db-input" type="date" name="date_from" value="{{ $filters['date_from'] ?? '' }}" style="width: 145px;" aria-label="From date">
                        <span style="color: var(--db-text-muted);">–</span>
                        <input class="db-input" type="date" name="date_to" value="{{ $filters['date_to'] ?? '' }}" style="width: 145px;" aria-label="To date">
                    </div>
                </div>
                <div class="db-field" style="flex: 1 1 150px;">
                    <label for="f-subvendor">Payment type</label>
                    <select id="f-subvendor" name="sub_vendor" class="db-select">
                        <option value="">All payments</option>
                        <option value="No" {{ ($filters['sub_vendor'] ?? '') === 'No' ? 'selected' : '' }}>Direct only</option>
                        <option value="Yes" {{ ($filters['sub_vendor'] ?? '') === 'Yes' ? 'selected' : '' }}>Sub-vendor only</option>
                    </select>
                </div>
                @if($mwbeReady)
                <div class="db-field" style="flex: 1 1 190px;">
                    <label for="f-mwbe">M/WBE category</label>
                    <select id="f-mwbe" name="mwbe_category" class="db-select">
                        <option value="">All</option>
                        @foreach($facets['mwbe_category'] as $o)
                        <option value="{{ $o['value'] }}" {{ ($filters['mwbe_category'] ?? '') === $o['value'] ? 'selected' : '' }}>{{ $o['value'] }}</option>
                        @endforeach
                    </select>
                </div>
                <div class="db-field" style="flex: 1 1 150px;">
                    <label for="f-woman">Woman-owned</label>
                    <select id="f-woman" name="woman_owned" class="db-select">
                        <option value="">Any</option>
                        <option value="Yes" {{ ($filters['woman_owned'] ?? '') === 'Yes' ? 'selected' : '' }}>Woman-owned only</option>
                    </select>
                </div>
                <div class="db-field" style="flex: 1 1 150px;">
                    <label for="f-emerging">Emerging (EBE)</label>
                    <select id="f-emerging" name="emerging" class="db-select">
                        <option value="">Any</option>
                        <option value="Yes" {{ ($filters['emerging'] ?? '') === 'Yes' ? 'selected' : '' }}>Emerging only</option>
                    </select>
                </div>
                @endif
                <div class="db-field" style="flex: 1 1 220px;">
                    <label for="f-q">Keyword</label>
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input id="f-q" type="search" name="q" value="{{ $filters['q'] ?? '' }}" placeholder="Payee, agency, contract…" autocomplete="off">
                    </div>
                </div>
                <button type="submit" class="db-btn db-btn-primary">Apply filters</button>
            </div>

            {{-- Active filter chips --}}
            @if(count($chips))
            <div class="db-chips" style="margin-top: var(--db-space-2);">
                @foreach($chips as $chip)
                <span class="db-chip">{{ $chip['text'] }}<a href="{{ $chip['url'] }}" class="db-chip-remove" aria-label="Remove filter"><i class="bi bi-x-lg"></i></a></span>
                @endforeach
                <a href="{{ route('procurement.transactions.search', ['fiscal_year' => $fy]) }}" class="db-chip-clear">Clear all</a>
            </div>
            @endif

            {{-- Toolbar --}}
            <div class="db-toolbar" style="border-bottom: 1px solid var(--db-border);">
                <div class="db-toolbar-info"><strong>{{ number_format($total) }}</strong> transactions · <strong>{{ $compact($totalAmt) }}</strong></div>
                <div class="db-toolbar-actions">
                    <select name="sort" class="db-select" aria-label="Sort" onchange="this.form.submit()">
                        @foreach($sortOptions as $val => $lbl)
                        <option value="{{ $val }}" {{ $sortKey === $val ? 'selected' : '' }}>{{ $lbl }}</option>
                        @endforeach
                    </select>
                    <a href="{{ $exportUrl }}" class="db-btn db-btn-outline"><i class="bi bi-download"></i> Export CSV</a>
                </div>
            </div>
        </form>

        {{-- Results --}}
        @if(count($rows))
        <div class="db-table-wrap" style="margin-top: var(--db-space-2);">
            <table class="db-table" id="txnTable">
                <thead>
                    <tr>
                        <th style="width: 28px;"></th>
                        <th>Payee</th>
                        <th>Agency</th>
                        <th>Contract</th>
                        <th style="text-align: right;">Amount</th>
                        <th>Date</th>
                        <th>Category</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($rows as $i => $tx)
                    @php
                        $payee = $tx['payee_name'] ?? '—';
                        $ctrId = $tx['ctr_id'] ?? null;
                        $contractLabel = ($tx['passport_contract_id'] ?? '') ?: ($tx['contract_id'] ?? '—');
                        $primeRaw = $tx['associated_prime_vendor'] ?? '';
                        $prime = ($primeRaw !== '' && $primeRaw !== 'N/A') ? $primeRaw : $payee;
                    @endphp
                    <tr class="se-row" data-target="det-{{ $i }}" style="cursor: pointer;">
                        <td style="color: var(--db-gray-500);"><button type="button" class="db-row-toggle" aria-expanded="false" aria-label="Expand row"><i class="bi bi-chevron-right"></i></button></td>
                        <td style="font-weight: var(--db-weight-semibold);">
                            @if(!empty($tx['vendor_id']))<a href="{{ route('procurement.vendor', ['id' => $tx['vendor_id']]) }}">{{ $payee }}</a>@else{{ $payee }}@endif
                        </td>
                        <td style="color: var(--db-text-muted);">{{ $tx['agency'] ?? '—' }}</td>
                        <td style="font-family: var(--db-font-mono); font-size: var(--db-text-xs);">
                            @if($ctrId)<a href="{{ route('procurement.contract', ['id' => $ctrId]) }}">{{ $contractLabel }}</a>@else{{ $contractLabel }}@endif
                        </td>
                        <td style="text-align: right; color: var(--db-primary); font-weight: var(--db-weight-semibold); font-variant-numeric: tabular-nums;">${{ number_format((float) ($tx['check_amount'] ?? 0)) }}</td>
                        <td style="color: var(--db-text-muted); font-variant-numeric: tabular-nums;">{{ $tx['issue_date'] ?? '—' }}</td>
                        <td style="color: var(--db-text-muted);">{{ $tx['spending_category'] ?? '—' }}</td>
                    </tr>
                    <tr class="db-row-detail se-detail" id="det-{{ $i }}" style="display: none;">
                        <td colspan="7">
                            <dl class="db-detail-grid">
                                <div><dt>Department</dt><dd>{{ ($tx['department'] ?? '') ?: '—' }}</dd></div>
                                <div><dt>Budget code</dt><dd style="font-family: var(--db-font-mono);">{{ ($tx['budget_code'] ?? '') ?: '—' }}</dd></div>
                                <div><dt>Expense category</dt><dd>{{ ($tx['expense_category'] ?? '') ?: '—' }}</dd></div>
                                <div><dt>Prime vendor</dt><dd>{{ $prime }}</dd></div>
                                @if(array_key_exists('mwbe_category', $tx))
                                <div><dt>M/WBE category</dt><dd>{{ ($tx['mwbe_category'] ?? '') ?: '—' }}@if(($tx['woman_owned_business'] ?? '') === 'Yes') · <span style="color: var(--db-accent);">Woman-owned</span>@endif@if(($tx['emerging_business'] ?? '') === 'Yes') · Emerging@endif</dd></div>
                                @endif
                                @if($ctrId)
                                <div style="grid-column: 1 / -1;"><a href="{{ route('procurement.contract', ['id' => $ctrId]) }}" style="font-weight: var(--db-weight-semibold);">View contract {{ $contractLabel }} <i class="bi bi-arrow-right"></i></a></div>
                                @endif
                            </dl>
                        </td>
                    </tr>
                    @endforeach
                </tbody>
            </table>
        </div>

        {{-- Pagination --}}
        @if($pages > 1)
        @php $qp = request()->query(); @endphp
        <nav class="db-pagination" aria-label="Pagination" style="justify-content: center; margin-top: var(--db-space-3);">
            <a class="db-page {{ $page <= 1 ? 'is-disabled' : '' }}" href="{{ route('procurement.transactions.search', array_merge($qp, ['page' => max($page - 1, 1)])) }}">Previous</a>
            <span class="db-page is-disabled">Page {{ number_format($page) }} of {{ number_format($pages) }}</span>
            <a class="db-page {{ $page >= $pages ? 'is-disabled' : '' }}" href="{{ route('procurement.transactions.search', array_merge($qp, ['page' => min($page + 1, $pages)])) }}">Next</a>
        </nav>
        @endif

        @else
        {{-- Empty state --}}
        <div class="db-empty" style="margin-top: var(--db-space-3);">
            <div class="db-empty-icon"><i class="bi bi-search"></i></div>
            <div class="db-empty-title">No transactions matched your filters</div>
            <div class="db-empty-text">Try widening the amount range or clearing a filter. <a href="{{ route('procurement.transactions.search', ['fiscal_year' => $fy]) }}">Reset all filters</a>.</div>
        </div>
        @endif

    </div>
</div>

<script>
// Expandable rows: clicking a summary row toggles its detail row + caret.
document.querySelectorAll('#txnTable .se-row').forEach(function (row) {
    row.addEventListener('click', function (e) {
        if (e.target.closest('a')) return; // let deep links work
        var det = document.getElementById(row.getAttribute('data-target'));
        var toggle = row.querySelector('.db-row-toggle');
        var open = det.style.display === 'none';
        det.style.display = open ? 'table-row' : 'none';
        toggle.classList.toggle('is-open', open);
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
});
</script>
@endsection
