@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        {{-- Profile header --}}
        <div class="db-profile-header">
            <div class="db-profile-header-top">
                <div class="db-profile-logo"><i class="bi bi-file-text" style="font-size: 2rem; color: var(--db-gray-500);"></i></div>
                <div class="db-profile-main">
                    <div class="db-profile-kicker">
                        <span class="db-type-label">Contract</span>
                        @if($contract['status'] ?? false)
                        <span class="db-badge db-badge-neutral"><span class="db-dot"></span>{{ $contract['status'] }}</span>
                        @endif
                    </div>
                    <h1 class="db-profile-title">
                        {{ !empty($contract['contract_id']) ? $contract['contract_id'] : ($contract['contract_title'] ?? 'Contract') }}
                        @if(empty($contract['contract_id']))
                        <span class="db-badge db-badge-warning">No Contract ID Yet</span>
                        @endif
                    </h1>
                    @if(!empty($contract['contract_id']) && !empty($contract['contract_title']))
                    <p class="db-profile-subtitle">{{ $contract['contract_title'] }}</p>
                    @endif
                </div>
            </div>
        </div>

        {{-- Key highlights: registered award vs actual spending --}}
        @php
            $pctUsed = $contract['pct_used'] ?? null;
            // MOCS end-of-period performance ratings for this contract (27.7% of
            // contracts have at least one). Adverse ratings are surfaced in the
            // TOC badge so a Poor rating is visible without scrolling.
            $evals = $evaluations ?? [];
            $evalAdverse = count(array_filter($evals, function ($e) {
                return in_array($e['rating'] ?? '', ['Poor', 'Unsatisfactory'], true);
            }));
            $evalRatingClass = [
                'Excellent'      => 'db-badge-success',
                'Good'           => 'db-badge-success',
                'Satisfactory'   => 'db-badge-neutral',
                'Poor'           => 'db-badge-warning',
                'Unsatisfactory' => 'db-badge-danger',
            ];
            // Blade will not compile an @if glued to a word char — precompute.
            $evalAsOfLabel = ($evaluationsAsOf ?? '')
                ? 'MOCS · as of ' . $evaluationsAsOf : 'MOCS';
        @endphp
        <div class="db-stat-grid mt-3 mb-4">
            <div class="db-stat is-accent">
                <div class="db-stat-label">Award amount @include('procurement.partials.source_badge', ['source' => 'mocs'])</div>
                <div class="db-stat-value">${{ number_format($contract['award_amount'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Spent to date @include('procurement.partials.source_badge', ['source' => 'checkbook'])</div>
                <div class="db-stat-value">${{ number_format($contract['spent_to_date'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ number_format($contract['payment_count'] ?? 0) }} payments</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Utilization</div>
                <div class="db-stat-value">{{ $pctUsed !== null ? $pctUsed . '%' : '—' }}</div>
                @if($pctUsed !== null)
                <div class="db-stat-sub" style="margin-top: var(--db-space-1);">
                    <div style="height: 6px; background: var(--db-gray-200); border-radius: var(--db-radius-pill); overflow: hidden;">
                        <div style="height: 100%; width: {{ min($pctUsed, 100) }}%; background: {{ $pctUsed > 100 ? 'var(--db-warning)' : 'var(--db-primary)' }};"></div>
                    </div>
                </div>
                @endif
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Contract term</div>
                <div class="db-stat-value" style="font-size: var(--db-text-md);">{{ $contract['start_date'] ?? 'N/A' }} → {{ $contract['end_date'] ?? 'N/A' }}</div>
                @php
                    // The payment WINDOW vs the contract TERM. Both dates were already
                    // computed by the spend join and thrown away by this template.
                    $pFirst = $contract['first_payment'] ?? null; $pLast = $contract['last_payment'] ?? null;
                @endphp
                @if($pFirst || $pLast)
                <div class="db-stat-sub">paid {{ substr($pFirst ?? '', 0, 10) ?: '?' }} → {{ substr($pLast ?? '', 0, 10) ?: '?' }}</div>
                @endif
            </div>
            @php
                // Award growth: `current_amount` is the registered-to-date value and can
                // exceed the original award (modifications/renewals). It was fetched on
                // every request and never shown.
                // NOTE: show it whenever it differs from the award — INCLUDING when
                // award_amount is 0, which happens in the real data (e.g. ctr 5604825:
                // award $0, current $113k, $651k actually paid). Gating on award > 0
                // would hide the only value the record actually has. The % comparison
                // is what needs a non-zero award, not the tile.
                $awardAmt = (float) ($contract['award_amount'] ?? 0);
                $currAmt  = (float) ($contract['current_amount'] ?? 0);
                $showCurr = $currAmt > 0 && abs($currAmt - $awardAmt) > 0.5;
            @endphp
            @if($showCurr)
            <div class="db-stat">
                <div class="db-stat-label">Current value @include('procurement.partials.source_badge', ['source' => 'mocs'])</div>
                <div class="db-stat-value">${{ number_format($currAmt) }}</div>
                @if($awardAmt > 0)
                <div class="db-stat-sub">{{ $currAmt > $awardAmt ? '+' : '' }}{{ number_format(($currAmt - $awardAmt) / $awardAmt * 100, 1) }}% vs original award</div>
                @else
                <div class="db-stat-sub">registered value (no original award on record)</div>
                @endif
            </div>
            @endif
        </div>

        <div class="row">
            {{-- Contents sidebar --}}
            <div class="col-md-3 d-none d-md-block">
                <nav class="db-toc">
                    <div class="db-toc-title">Contents</div>
                    <a class="is-active" href="#details">Details</a>
                    @if(!empty($spendTimeline['labels']) || count($spendVendors ?? []))<a href="#spending">Spending</a>@endif
                    @if(count($evaluations ?? []))<a href="#section-ratings">Performance Rating <span class="db-badge {{ $evalAdverse ? 'db-badge-danger' : 'db-badge-neutral' }}">{{ count($evaluations) }}</span></a>@endif
                    @if($vendor)<a href="#vendor">Vendor</a>@endif
                    @if($solicitation)<a href="#solicitation">Solicitation</a>@endif
                    <a href="#section-transactions">Transactions</a>
                    @if(count($relatedNotices ?? []) > 0)<a href="#notices">City Record Notices <span class="db-badge db-badge-neutral">{{ count($relatedNotices) }}</span></a>@endif
                </nav>
            </div>

            {{-- Main content --}}
            <div class="col-md-9">
                <div id="details" class="db-anchor mb-5">
                    <h4 class="mb-3">Contract Details</h4>
                    <div class="db-card"><div class="db-card-body">
                        <dl class="db-meta-list">
                            <dt>Agency</dt>
                            @php
                                // The linked solicitation carries wegov-org-id, so the agency
                                // can point at its canonical org profile instead of being
                                // dead text. Falls back to plain text when unmatched.
                                $agencyOrgId = $solicitation['wegov-org-id'] ?? null;
                                $agencyName  = $contract['agency'] ?? 'N/A';
                            @endphp
                            <dd>
                                @if($agencyOrgId)
                                <a href="{{ route('orgProfile', ['id' => $agencyOrgId, 'orgslug' => \Illuminate\Support\Str::slug($agencyName, '-')]) }}">{{ $agencyName }}</a>
                                @else
                                {{ $agencyName }}
                                @endif
                            </dd>

                            <dt>Vendor</dt>
                            <dd>
                                @if($vendor)
                                <a href="{{ route('procurement.vendor', ['id' => $vendor['PASSPort Supplier-ID']]) }}">{{ $contract['vendor_name'] ?? 'N/A' }}</a>
                                @else
                                {{ $contract['vendor_name'] ?? 'N/A' }}
                                @endif
                            </dd>

                            <dt>Award Amount</dt>
                            <dd class="fw-semibold">${{ number_format($contract['award_amount'] ?? 0) }}</dd>

                            <dt>Status</dt>
                            <dd>{{ $contract['status'] ?? 'N/A' }}</dd>

                            <dt>EPIN</dt>
                            <dd class="is-mono">
                                @if($solicitation)
                                <a href="{{ route('procurement.solicitation', ['epin' => $contract['epin']]) }}">{{ $contract['epin'] ?? 'N/A' }}</a>
                                @else
                                {{ $contract['epin'] ?? 'N/A' }}
                                @endif
                            </dd>

                            <dt>Industry</dt>
                            <dd>{{ $contract['industry'] ?? 'N/A' }}</dd>

                            @if(!empty($contract['expense_category']))
                            <dt>Expense Category @include('procurement.partials.source_badge', ['source' => 'checkbook'])</dt>
                            <dd>{{ $contract['expense_category'] }}</dd>
                            @endif

                            <dt>Award Method</dt>
                            <dd>{{ ($contract['award_method'] ?? '') ?: ($contract['procurement_method'] ?? 'N/A') }}</dd>

                            @if(!empty($contract['purpose']))
                            <dt>Purpose / Scope @include('procurement.partials.source_badge', ['source' => 'checkbook'])</dt>
                            <dd>{{ $contract['purpose'] }}</dd>
                            @endif
                        </dl>
                    </div></div>
                </div>

                @if(!empty($spendTimeline['labels']) || count($spendVendors ?? []))
                <div id="spending" class="db-anchor mb-5">
                    <h4 class="mb-3">Spending</h4>
                    @if(!empty($spendTimeline['labels']))
                    <div class="db-chart-card mb-3">
                        <div class="db-chart-head"><span class="db-chart-title">Payments over time</span></div>
                        <div class="db-chart-body" style="height: 240px;"><canvas id="ctrSpendChart" aria-label="Payments over time"></canvas></div>
                    </div>
                    @endif
                    @if(count($spendVendors ?? []))
                    <div class="db-table-wrap">
                        <table class="db-table">
                            <thead><tr><th>Payee</th><th>Role</th><th style="text-align: right;">Spent</th><th style="text-align: right;">Payments</th></tr></thead>
                            <tbody>
                                @foreach($spendVendors as $v)
                                <tr>
                                    <td style="font-weight: var(--db-weight-semibold);">{{ $v['payee'] ?? '—' }}</td>
                                    <td>
                                        @if($v['is_sub_vendor'] ?? false)<span class="db-badge db-badge-info">Sub-vendor</span>@else<span class="db-badge db-badge-neutral">Prime</span>@endif
                                        @if(!empty($v['prime_vendor']))<span style="color: var(--db-text-muted); font-size: var(--db-text-2xs);">via {{ $v['prime_vendor'] }}</span>@endif
                                    </td>
                                    <td style="text-align: right; color: var(--db-primary); font-weight: var(--db-weight-semibold); font-variant-numeric: tabular-nums;">${{ number_format((float) ($v['spent'] ?? 0)) }}</td>
                                    <td style="text-align: right; color: var(--db-text-muted); font-variant-numeric: tabular-nums;">{{ number_format($v['payments'] ?? 0) }}</td>
                                </tr>
                                @endforeach
                            </tbody>
                        </table>
                    </div>
                    @endif
                </div>
                @endif

                {{-- MOCS performance rating for THIS contract — the contracting
                     agency's own assessment at the close of an evaluation period.
                     A contract can have several (one per period). --}}
                @if(count($evals))
                <div id="section-ratings" class="db-anchor mb-5">
                    <div class="d-flex align-items-center flex-wrap mb-3" style="gap: var(--db-space-15);">
                        <h4 class="mb-0">Performance Rating</h4>
                        <span class="db-badge db-badge-neutral">{{ $evalAsOfLabel }}</span>
                        @if($evalAdverse)
                        <span class="db-badge db-badge-danger">{{ $evalAdverse }} adverse</span>
                        @endif
                    </div>
                    <div class="db-table-wrap">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead><tr><th>Evaluated</th><th>Agency</th><th>Period</th><th>Rating</th></tr></thead>
                                <tbody>
                                    @foreach($evals as $e)
                                    @php
                                        $ps = $e['period_start'] ?: '';
                                        $pe = $e['period_end'] ?: '';
                                        $period = trim($ps . (($ps && $pe) ? ' – ' : '') . $pe);
                                    @endphp
                                    <tr>
                                        <td class="text-muted">{{ $e['date'] ?: '—' }}</td>
                                        <td>{{ $e['agency'] ?: '—' }}</td>
                                        <td class="text-muted" style="font-size: var(--db-text-sm);">{{ $period ?: '—' }}</td>
                                        <td><span class="db-badge {{ $evalRatingClass[$e['rating']] ?? 'db-badge-neutral' }}">{{ $e['rating'] ?: '—' }}</span></td>
                                    </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <p class="text-muted mt-2" style="font-size: var(--db-text-sm);">Assigned by the contracting agency and published by the Mayor's Office of Contract Services.</p>
                </div>
                @endif

                @if($vendor)
                <div id="vendor" class="db-anchor mb-5">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h4 class="mb-0">Vendor Profile</h4>
                        <a href="{{ route('procurement.vendor', ['id' => $vendor['PASSPort Supplier-ID']]) }}" class="db-btn db-btn-outline db-btn-sm">View Full Profile</a>
                    </div>
                    <div class="db-card"><div class="db-card-body">
                        <h5 class="mb-3">{{ $vendor['Vendor Name'] ?? 'Unknown Vendor' }}</h5>
                        <dl class="db-meta-list">
                            <dt>PASSPort ID</dt>
                            <dd class="is-mono">{{ $vendor['PASSPort Supplier-ID'] ?? 'N/A' }}</dd>
                            <dt>Category</dt>
                            <dd>{{ $vendor['Business Category'] ?? 'N/A' }}</dd>
                            <dt>Certifications</dt>
                            <dd>{{ $vendor['Certification Type'] ?? 'None Listed' }}</dd>
                        </dl>
                    </div></div>
                </div>
                @endif

                @if($solicitation)
                <div id="solicitation" class="db-anchor mb-5">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h4 class="mb-0">Linked Solicitation</h4>
                        <a href="{{ route('procurement.solicitation', ['epin' => $solicitation['EPIN']]) }}" class="db-btn db-btn-outline db-btn-sm">View Solicitation</a>
                    </div>
                    <div class="db-card"><div class="db-card-body">
                        <div class="d-flex justify-content-between align-items-start" style="gap: var(--db-space-2);">
                            <h5 class="mb-3 text-truncate">{{ $solicitation['Procurement Name'] ?? 'Untitled' }}</h5>
                            <span class="db-badge db-badge-neutral">{{ $solicitation['RFx Status'] ?? '' }}</span>
                        </div>
                        <dl class="db-meta-list">
                            <dt>EPIN</dt>
                            <dd class="is-mono">{{ $solicitation['EPIN'] ?? 'N/A' }}</dd>
                            <dt>Method</dt>
                            <dd>{{ $solicitation['Procurement Method'] ?? 'N/A' }}</dd>
                            <dt>Due Date</dt>
                            <dd>{{ $solicitation['Due Date'] ?? 'N/A' }}</dd>
                        </dl>
                    </div></div>
                </div>
                @endif

                @include('procurement.partials.transactions_table', [
                    'txFilterParam' => 'vendor',
                    'txFilterValue' => $contract['vendor_name'] ?? ($vendor['Vendor Name'] ?? ''),
                    // Filtered by vendor, not by this contract — label it honestly.
                    // This contract's own payments are the timeline + payee table above.
                    'txHeading' => 'Recent payments to this vendor',
                    'txNote' => 'All Checkbook payments to ' . ($contract['vendor_name'] ?? 'this vendor')
                        . ' citywide — not limited to this contract. This contract\'s own payments are charted above.',
                ])

                @include('procurement.partials.related_notices')

            </div>
        </div>

    </div>
</div>

@if(!empty($spendTimeline['labels']))
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
DBChart.apply(Chart);
$(document).ready(function () {
    var tl = @json($spendTimeline);
    var el = document.getElementById('ctrSpendChart');
    if (el && tl.labels && tl.labels.length) {
        new Chart(el.getContext('2d'), {
            type: 'line',
            data: { labels: tl.labels, datasets: [{ data: tl.values, borderColor: DBChart.accent, backgroundColor: DBChart.accentFill, fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, grid: { color: DBChart.grid }, ticks: { callback: DBChart.money } }, x: { grid: { display: false } } } }
        });
    }
});
</script>
@endif
@endsection
