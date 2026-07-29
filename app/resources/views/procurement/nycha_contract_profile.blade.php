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
    $ct = $cp['contract'] ?? [];
    $pay = $cp['payments'] ?? null;
    $vendorId = $cp['vendor_id'] ?? null;
    $vname = trim($ct['vendor'] ?? '');
    $cur = (float) ($ct['current_amt'] ?? 0);
    $inv = (float) ($ct['invoiced'] ?? 0);
    $orig = (float) ($ct['original'] ?? 0);
    $util = $cur > 0 ? min($inv / $cur, 1.5) : 0;
    $paid = (float) ($pay['total'] ?? 0);
    $paidPct = $cur > 0 ? min($paid / $cur, 1.5) : 0;
    $contractsUrl = route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-contracts']);
    $spendingUrl  = route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-spending']) . '?q=' . urlencode($cid);
    // Vendor cell: City profile if crosswalked, else NYCHA-native vendor profile.
    if ($vendorId) {
        $vendorHref = route('procurement.vendor', ['id' => $vendorId]);
    } else {
        $vendorHref = route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-vendor']) . '?name=' . urlencode($vname);
    }
@endphp

@section('content')
@include('sub.orgheader', ['active' => 'procurement-nycha-contracts'])
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-8);">

        <div class="db-eyebrow"><a href="{{ $contractsUrl }}">Contracts</a> · NYCHA</div>

        {{-- Header --}}
        <div class="db-profile-header mt-2">
            <div class="db-profile-header-top">
                <div class="db-profile-main">
                    <div class="db-profile-kicker">
                        <span class="db-type-label">NYCHA Contract</span>
                        @if(($ct['contract_type'] ?? '') !== '')<span class="db-badge db-badge-neutral">{{ $ct['contract_type'] }}</span>@endif
                    </div>
                    <h1 class="db-profile-title is-mono">{{ $cid }}</h1>
                    @if($vname !== '')
                    <p class="db-profile-subtitle"><i class="bi bi-building"></i> <a href="{{ $vendorHref }}">{{ $vname }}</a> @include('procurement.partials.source_badge', ['source' => 'checkbook'])</p>
                    @endif
                </div>
            </div>
        </div>

        {{-- Key stats --}}
        <div class="db-stat-grid mt-3 mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Original</div>
                <div class="db-stat-value">{{ $compact($orig) }}</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Current value</div>
                <div class="db-stat-value">{{ $compact($cur) }}</div>
                <div class="db-stat-sub">registered amount</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Invoiced</div>
                <div class="db-stat-value">{{ $compact($inv) }}</div>
                <div class="db-stat-sub">{{ number_format($util * 100, 1) }}% of current</div>
            </div>
            @if($pay)
            <div class="db-stat">
                <div class="db-stat-label">Paid (Checkbook)</div>
                <div class="db-stat-value">{{ $compact($paid) }}</div>
                <div class="db-stat-sub">{{ number_format($paidPct * 100, 1) }}% of current · {{ number_format($pay['count'] ?? 0) }} payment{{ ($pay['count'] ?? 0) == 1 ? '' : 's' }}</div>
            </div>
            @endif
        </div>

        <div class="row">
            {{-- Details --}}
            <div class="col-md-6 mb-4">
                <div class="db-card h-100"><div class="db-card-body">
                    <h4 class="mb-3">Contract details</h4>
                    <dl class="db-meta-list">
                        <dt>Contract ID</dt><dd class="is-mono">{{ $cid }}</dd>
                        <dt>Vendor</dt><dd>@if($vname !== '')<a href="{{ $vendorHref }}">{{ $vname }}</a>@else — @endif</dd>
                        <dt>PIN</dt><dd class="is-mono">{{ $ct['pin'] ?: '—' }}</dd>
                        <dt>Responsibility center</dt><dd>{{ $ct['responsibility_center'] ?: '—' }}</dd>
                        <dt>Funding source</dt><dd>{{ $ct['funding_source'] ?: '—' }}</dd>
                        <dt>Industry</dt><dd>{{ $ct['industry'] ?: '—' }}</dd>
                        <dt>Award method</dt><dd>{{ $ct['award_method'] ?: '—' }}</dd>
                        <dt>Contract type</dt><dd>{{ $ct['contract_type'] ?: '—' }}</dd>
                        <dt>Start date</dt><dd>{{ $ct['start_date'] ?: '—' }}</dd>
                        <dt>End date</dt><dd>{{ $ct['end_date'] ?: '—' }}</dd>
                        <dt>Releases</dt><dd>{{ number_format($ct['releases'] ?? 0) }}</dd>
                        <dt>Latest fiscal year</dt><dd>{{ $ct['fiscal_year'] ?? '—' }}</dd>
                    </dl>
                </div></div>
            </div>

            {{-- Purpose + payments-by-year --}}
            <div class="col-md-6 mb-4">
                @if(($ct['purpose'] ?? '') !== '')
                <div class="db-card mb-4"><div class="db-card-body">
                    <h4 class="mb-2">Purpose</h4>
                    <p class="mb-0" style="color: var(--db-text-muted);">{{ $ct['purpose'] }}</p>
                </div></div>
                @endif
                @if($pay && count($pay['by_year'] ?? []))
                <div class="db-card h-100"><div class="db-card-body">
                    <h4 class="mb-3">Payments by fiscal year @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h4>
                    @php $maxY = max(array_map(fn($r) => $r['spending'], $pay['by_year'])); @endphp
                    @foreach($pay['by_year'] as $y)
                    <div class="d-flex align-items-center mb-2" style="gap: var(--db-space-1);">
                        <span style="min-width: 56px; color: var(--db-text-muted); font-size: var(--db-text-sm);">FY{{ $y['year'] }}</span>
                        <div style="flex: 1; background: var(--db-gray-100); border-radius: 999px; height: 8px; overflow: hidden;">
                            <div style="width: {{ $maxY > 0 ? ($y['spending'] / $maxY * 100) : 0 }}%; height: 100%; background: var(--db-accent);"></div>
                        </div>
                        <span style="min-width: 72px; text-align: right; font-variant-numeric: tabular-nums; font-size: var(--db-text-sm);">{{ $compact($y['spending']) }}</span>
                    </div>
                    @endforeach
                </div></div>
                @endif
            </div>
        </div>

        {{-- Payments list --}}
        @if($pay && count($pay['list'] ?? []))
        <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
            <h4 class="mb-0">Payments</h4>
            <span class="db-badge db-badge-neutral">{{ number_format($pay['count'] ?? 0) }}</span>
            <a href="{{ $spendingUrl }}" class="db-btn db-btn-outline db-btn-sm ms-auto">View in spending explorer</a>
        </div>
        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Document ID</th>
                            <th class="db-num">Issued</th>
                            <th>Status</th>
                            <th>Category</th>
                            <th>Funding source</th>
                            <th class="db-num">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach($pay['list'] as $p)
                        <tr>
                            <td class="is-mono">{{ $p['document_id'] ?? '—' }}</td>
                            <td class="db-num text-muted">{{ isset($p['issue_date']) ? \Illuminate\Support\Str::limit($p['issue_date'], 10, '') : '' }}</td>
                            <td class="text-muted">{{ $p['check_status'] ?? '—' }}</td>
                            <td class="text-muted">{{ $p['spending_category'] ?? '—' }}</td>
                            <td class="text-muted">{{ $p['funding_source'] ?? '—' }}</td>
                            <td class="db-num">{{ $compact($p['amount'] ?? 0) }}</td>
                        </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
        @if(($pay['count'] ?? 0) > count($pay['list'] ?? []))
        <p class="text-muted mt-2" style="font-size: var(--db-text-sm);">Showing the {{ number_format(count($pay['list'])) }} largest payments of {{ number_format($pay['count']) }}. <a href="{{ $spendingUrl }}">See all in the spending explorer</a>.</p>
        @endif
        @elseif($pay)
        <div class="db-empty"><div class="db-empty-title">No individual payments recorded</div><div class="db-empty-text">No check-level payments are linked to this contract in the spending data.</div></div>
        @endif

    </div>
</div>
@endsection
