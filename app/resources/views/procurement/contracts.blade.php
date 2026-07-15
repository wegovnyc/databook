@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@php
    $rows   = $data['data'] ?? [];
    $total  = $data['total'] ?? 0;
    $page   = $data['page'] ?? 1;
    $pages  = $data['pages'] ?? 1;

    $compact = function ($n) {
        $n = (float) $n;
        if ($n >= 1e9) return '$' . number_format($n / 1e9, 1) . 'B';
        if ($n >= 1e6) return '$' . number_format($n / 1e6, 1) . 'M';
        if ($n >= 1e3) return '$' . number_format($n / 1e3, 0) . 'K';
        return '$' . number_format($n);
    };

    $chipLabels = ['agency' => 'Agency', 'status' => 'Status', 'method' => 'Method', 'industry' => 'Industry', 'expense_category' => 'Expense category', 'q' => 'Keyword'];
    $baseQuery = request()->query();
    unset($baseQuery['page']);
    $chips = [];
    foreach ($chipLabels as $key => $label) {
        $val = $filters[$key] ?? '';
        if ($val !== '' && $val !== null) {
            $remove = $baseQuery; unset($remove[$key]);
            $chips[] = ['text' => "{$label}: {$val}", 'url' => route('procurement.contracts', $remove)];
        }
    }
    $minA = $filters['min_amount'] ?? ''; $maxA = $filters['max_amount'] ?? '';
    if ($minA !== '' || $maxA !== '') {
        $remove = $baseQuery; unset($remove['min_amount'], $remove['max_amount']);
        $chips[] = ['text' => 'Amount: ' . ($minA !== '' ? $compact($minA) : '$0') . ' – ' . ($maxA !== '' ? $compact($maxA) : 'any'),
                    'url' => route('procurement.contracts', $remove)];
    }
    $sortOptions = ['amount-desc' => 'Award (high → low)', 'amount-asc' => 'Award (low → high)', 'date-desc' => 'Newest', 'vendor-asc' => 'Vendor (A–Z)'];
@endphp

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-8);">

        <div style="display: flex; align-items: baseline; gap: var(--db-space-2); margin-bottom: var(--db-space-2);">
            <h1 style="margin: 0;">Contracts</h1>
            <span style="color: var(--db-text-muted); font-size: var(--db-text-sm);">registered awards + spending</span>
        </div>

        <form method="GET" action="{{ route('procurement.contracts') }}">
            <div class="db-filter-bar">
                <div class="db-field" style="flex: 1 1 220px;">
                    <label for="f-q">Keyword</label>
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input id="f-q" type="search" name="q" value="{{ $filters['q'] ?? '' }}" placeholder="Contract ID, title, vendor…" autocomplete="off">
                    </div>
                </div>
                <div class="db-field" style="flex: 1 1 170px;">
                    <label for="f-agency">Agency</label>
                    <input id="f-agency" class="db-input" type="text" name="agency" value="{{ $filters['agency'] ?? '' }}" placeholder="All agencies" autocomplete="off">
                </div>
                @php
                    $facetFields = [
                        ['status', 'Status', 'All statuses', $filterOptions['statuses'] ?? []],
                        ['method', 'Method', 'All methods', $filterOptions['methods'] ?? []],
                        ['industry', 'Industry', 'All industries', $filterOptions['industries'] ?? []],
                        ['expense_category', 'Expense category', 'All categories', $filterOptions['expense_categories'] ?? []],
                    ];
                @endphp
                @foreach($facetFields as [$name, $label, $allLabel, $opts])
                <div class="db-field" style="flex: 1 1 160px;">
                    <label for="f-{{ $name }}">{{ $label }}</label>
                    <select id="f-{{ $name }}" name="{{ $name }}" class="db-select">
                        <option value="">{{ $allLabel }}</option>
                        @foreach($opts as $o)
                        <option value="{{ $o }}" {{ ($filters[$name] ?? '') === $o ? 'selected' : '' }}>{{ $o }}</option>
                        @endforeach
                    </select>
                </div>
                @endforeach
                <div class="db-field" style="flex: 0 0 auto;">
                    <label>Award amount</label>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <input class="db-input" type="number" name="min_amount" value="{{ $filters['min_amount'] ?? '' }}" placeholder="Min $" style="width: 100px;" aria-label="Minimum award">
                        <span style="color: var(--db-text-muted);">–</span>
                        <input class="db-input" type="number" name="max_amount" value="{{ $filters['max_amount'] ?? '' }}" placeholder="Max $" style="width: 100px;" aria-label="Maximum award">
                    </div>
                </div>
                <button type="submit" class="db-btn db-btn-primary">Apply filters</button>
            </div>

            @if(count($chips))
            <div class="db-chips" style="margin-top: var(--db-space-2);">
                @foreach($chips as $chip)
                <span class="db-chip">{{ $chip['text'] }}<a href="{{ $chip['url'] }}" class="db-chip-remove" aria-label="Remove filter"><i class="bi bi-x-lg"></i></a></span>
                @endforeach
                <a href="{{ route('procurement.contracts') }}" class="db-chip-clear">Clear all</a>
            </div>
            @endif

            <div class="db-toolbar" style="border-bottom: 1px solid var(--db-border);">
                <div class="db-toolbar-info"><strong>{{ number_format($total) }}</strong> contracts</div>
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

        @if(count($rows))
        <div class="db-table-wrap" style="margin-top: var(--db-space-2);">
            <table class="db-table" id="ctrTable">
                <thead>
                    <tr>
                        <th style="width: 28px;"></th>
                        <th>Contract</th>
                        <th>Agency</th>
                        <th>Vendor</th>
                        <th style="text-align: right;">Award</th>
                        <th style="text-align: right;">Spent</th>
                        <th style="width: 130px;">Utilization</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($rows as $i => $c)
                    @php
                        $pct = $c['pct_used'] ?? null;
                        $registered = ($c['status'] ?? '') === 'Registered';
                    @endphp
                    <tr class="se-row" data-target="cdet-{{ $i }}" style="cursor: pointer;">
                        <td style="color: var(--db-gray-500);"><button type="button" class="db-row-toggle" aria-expanded="false" aria-label="Expand row"><i class="bi bi-chevron-right"></i></button></td>
                        <td>
                            <a href="{{ route('procurement.contract', ['id' => $c['ctr_id'] ?? $c['contract_id']]) }}" style="font-weight: var(--db-weight-semibold); font-family: var(--db-font-mono); font-size: var(--db-text-xs);">{{ $c['contract_id'] ?? 'N/A' }}</a>
                            <div style="color: var(--db-text-muted); font-size: var(--db-text-2xs); max-width: 40ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ ($c['purpose'] ?? '') ?: ($c['contract_title'] ?? '') }}</div>
                        </td>
                        <td style="color: var(--db-text-muted);">{{ $c['agency'] ?? '—' }}</td>
                        <td><a href="{{ route('procurement.vendors', ['q' => $c['vendor_name'] ?? '']) }}">{{ $c['vendor_name'] ?? 'Unknown' }}</a></td>
                        <td style="text-align: right; color: var(--db-primary); font-weight: var(--db-weight-semibold); font-variant-numeric: tabular-nums;">{{ $compact($c['award_amount'] ?? 0) }}</td>
                        <td style="text-align: right; color: var(--db-primary); font-variant-numeric: tabular-nums;">{{ $compact($c['spent_to_date'] ?? 0) }}</td>
                        <td>
                            @if($pct !== null)
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <div style="flex: 1; min-width: 46px; height: 6px; background: var(--db-gray-200); border-radius: var(--db-radius-pill); overflow: hidden;">
                                    <div style="height: 100%; width: {{ min($pct, 100) }}%; background: {{ $pct > 100 ? 'var(--db-warning)' : 'var(--db-primary)' }};"></div>
                                </div>
                                <span style="font-size: var(--db-text-2xs); color: var(--db-text-muted); font-variant-numeric: tabular-nums;">{{ $pct }}%</span>
                            </div>
                            @else
                            <span style="color: var(--db-gray-400);">—</span>
                            @endif
                        </td>
                        <td><span class="db-badge {{ $registered ? 'db-badge-success' : 'db-badge-neutral' }}">@if($registered)<span class="db-dot"></span>@endif{{ $c['status'] ?? 'Unknown' }}</span></td>
                    </tr>
                    <tr class="db-row-detail se-detail" id="cdet-{{ $i }}" style="display: none;">
                        <td colspan="8">
                            <dl class="db-detail-grid">
                                <div><dt>Award amount</dt><dd style="font-variant-numeric: tabular-nums;">${{ number_format((float) ($c['award_amount'] ?? 0)) }}</dd></div>
                                <div><dt>Spent to date</dt><dd style="font-variant-numeric: tabular-nums;">${{ number_format((float) ($c['spent_to_date'] ?? 0)) }}</dd></div>
                                <div><dt>Payments</dt><dd>{{ number_format($c['payment_count'] ?? 0) }}</dd></div>
                                <div><dt>Expense category</dt><dd>{{ ($c['expense_category'] ?? '') ?: '—' }}</dd></div>
                                <div><dt>Method</dt><dd>{{ ($c['award_method'] ?? '') ?: ($c['procurement_method'] ?? '—') }}</dd></div>
                                <div><dt>Industry</dt><dd>{{ $c['industry'] ?? '—' }}</dd></div>
                                <div><dt>Start</dt><dd>{{ $c['start_date'] ?? '—' }}</dd></div>
                                <div><dt>End</dt><dd>{{ $c['end_date'] ?? '—' }}</dd></div>
                                @if(!empty($c['purpose']))
                                <div style="grid-column: 1 / -1;"><dt>Purpose</dt><dd>{{ $c['purpose'] }}</dd></div>
                                @endif
                                <div style="grid-column: 1 / -1;"><a href="{{ route('procurement.contract', ['id' => $c['ctr_id'] ?? $c['contract_id']]) }}" style="font-weight: var(--db-weight-semibold);">Open contract {{ $c['contract_id'] ?? '' }} <i class="bi bi-arrow-right"></i></a></div>
                            </dl>
                        </td>
                    </tr>
                    @endforeach
                </tbody>
            </table>
        </div>

        @if($pages > 1)
        @php $qp = request()->query(); @endphp
        <nav class="db-pagination" aria-label="Pagination" style="justify-content: center; margin-top: var(--db-space-3);">
            <a class="db-page {{ $page <= 1 ? 'is-disabled' : '' }}" href="{{ route('procurement.contracts', array_merge($qp, ['page' => max($page - 1, 1)])) }}">Previous</a>
            <span class="db-page is-disabled">Page {{ number_format($page) }} of {{ number_format($pages) }}</span>
            <a class="db-page {{ $page >= $pages ? 'is-disabled' : '' }}" href="{{ route('procurement.contracts', array_merge($qp, ['page' => min($page + 1, $pages)])) }}">Next</a>
        </nav>
        @endif

        @else
        <div class="db-empty" style="margin-top: var(--db-space-3);">
            <div class="db-empty-icon"><i class="bi bi-search"></i></div>
            <div class="db-empty-title">No contracts found</div>
            <div class="db-empty-text">Try widening your filters. <a href="{{ route('procurement.contracts') }}">Reset all filters</a>.</div>
        </div>
        @endif

    </div>
</div>

<script>
document.querySelectorAll('#ctrTable .se-row').forEach(function (row) {
    row.addEventListener('click', function (e) {
        if (e.target.closest('a')) return;
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
