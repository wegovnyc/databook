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
    $available = $vp['available'] ?? false;
    $c = $vp['contracts'] ?? null;
    $s = $vp['spending'] ?? null;
    $clist = $vp['contract_list'] ?? [];
    $fyRange = ($s && ($s['min_year'] ?? null))
        ? (($s['min_year'] == $s['max_year']) ? 'FY' . $s['min_year'] : 'FY' . $s['min_year'] . '-FY' . $s['max_year'])
        : '';
    $contractsUrl = route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-contracts']) . '?q=' . urlencode($vname);
    $spendingUrl  = route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-spending']) . '?q=' . urlencode($vname);
    $vendorsUrl   = route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-vendors']);
@endphp

@section('content')
@include('sub.orgheader', ['active' => 'procurement-nycha-vendors'])
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-8);">

        <div class="db-eyebrow"><a href="{{ $vendorsUrl }}">Vendors</a> · NYCHA</div>

        {{-- Profile header --}}
        <div class="db-profile-header mt-2">
            <div class="db-profile-header-top">
                <div class="db-profile-logo" style="font-size: 2rem; font-weight: var(--db-weight-bold); color: var(--db-primary);">{{ strtoupper(substr($vname, 0, 1)) }}</div>
                <div class="db-profile-main">
                    <div class="db-profile-kicker">
                        <span class="db-type-label">NYCHA Vendor</span>
                        <span class="db-badge db-badge-neutral">Not in City PASSPort registry</span>
                    </div>
                    <h1 class="db-profile-title">{{ $vname }}</h1>
                    <p class="db-profile-subtitle"><i class="bi bi-receipt"></i> Housing Authority vendor @include('procurement.partials.source_badge', ['source' => 'checkbook'])</p>
                </div>
            </div>
        </div>

        @if(!$available)
        <div class="db-empty" style="margin-top: var(--db-space-4);">
            <div class="db-empty-icon"><i class="bi bi-person-x"></i></div>
            <div class="db-empty-title">No NYCHA activity found for this vendor</div>
            <div class="db-empty-text">This name has no NYCHA contracts or payments in the current data. <a href="{{ $vendorsUrl }}">Back to all NYCHA vendors</a>.</div>
        </div>
        @else

        <x-db.alert tone="info" class="mt-3 mb-4">
            <strong>Why this vendor is here.</strong>
            {{ $vname }} does business with NYCHA — a separate public authority — but has no matching record in the City's PASSPort vendor registry, so it has no City vendor profile. Its NYCHA contracts and payments (Checkbook NYC) are summarized below.
        </x-db.alert>

        {{-- Key stats --}}
        <div class="db-stat-grid mb-4">
            @if($c)
            <div class="db-stat is-accent">
                <div class="db-stat-label">NYCHA Contracts</div>
                <div class="db-stat-value">{{ number_format($c['count']) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Current Contract Value</div>
                <div class="db-stat-value">{{ $compact($c['current']) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Invoiced</div>
                <div class="db-stat-value">{{ $compact($c['invoiced']) }}</div>
            </div>
            @endif
            @if($s)
            <div class="db-stat">
                <div class="db-stat-label">Spending{{ $fyRange ? " ($fyRange)" : '' }}</div>
                <div class="db-stat-value">{{ $compact($s['total']) }}</div>
            </div>
            @if($s['payments'])
            <div class="db-stat">
                <div class="db-stat-label">Payments</div>
                <div class="db-stat-value">{{ number_format($s['payments']) }}</div>
            </div>
            @endif
            @endif
        </div>

        <div class="mb-4 d-flex flex-wrap" style="gap: var(--db-space-1);">
            @if($c && $c['count'])<a href="{{ $contractsUrl }}" class="db-btn db-btn-outline db-btn-sm">View in NYCHA contracts</a>@endif
            @if($s && $s['payments'])<a href="{{ $spendingUrl }}" class="db-btn db-btn-outline db-btn-sm">View NYCHA payments</a>@endif
        </div>

        {{-- Contracts table --}}
        @if(count($clist))
        <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
            <h4 class="mb-0">Contracts</h4>
            <span class="db-badge db-badge-neutral">{{ number_format(count($clist)) }}{{ count($clist) >= 500 ? '+' : '' }}</span>
        </div>
        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Contract ID</th>
                            <th>Purpose</th>
                            <th>Responsibility Center</th>
                            <th class="db-num">Current</th>
                            <th class="db-num">Invoiced</th>
                            <th class="db-num">End Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach($clist as $ct)
                        <tr>
                            <td class="fw-semibold is-mono">{{ $ct['contract_id'] ?? 'N/A' }}</td>
                            <td class="text-muted" style="max-width: 320px; overflow: hidden; text-overflow: ellipsis;" title="{{ $ct['purpose'] ?? '' }}">{{ $ct['purpose'] ?? '—' }}</td>
                            <td class="text-muted">{{ $ct['responsibility_center'] ?? '—' }}</td>
                            <td class="db-num">{{ $compact($ct['current_amt'] ?? 0) }}</td>
                            <td class="db-num">{{ $compact($ct['invoiced'] ?? 0) }}</td>
                            <td class="db-num text-muted">{{ $ct['end_date'] ?? '' }}</td>
                        </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
        @endif

        @endif
    </div>
</div>
@endsection
