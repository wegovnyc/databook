@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

@php
    $total = array_reduce($contracts, function($carry, $item) {
        return $carry + ($item['award_amount'] ?? 0);
    }, 0);
@endphp

        {{-- Profile header --}}
        <div class="db-profile-header">
            <div class="db-profile-header-top">
                <div class="db-profile-logo" style="font-size: 2rem; font-weight: var(--db-weight-bold); color: var(--db-primary);">{{ strtoupper(substr($vendor['name'] ?? 'V', 0, 1)) }}</div>
                <div class="db-profile-main">
                    <div class="db-profile-kicker">
                        <span class="db-type-label">Vendor</span>
                        @if($vendor['certification_type'])
                        <span class="db-badge db-badge-warning">{{ $vendor['certification_type'] }}</span>
                        @endif
                    </div>
                    <h1 class="db-profile-title">{{ $vendor['name'] }}</h1>
                    <p class="db-profile-subtitle"><i class="bi bi-building"></i> {{ $vendor['business_category'] ?? 'NYC Registered Vendor' }}</p>
                </div>
            </div>
        </div>

        {{-- Key highlights --}}
        <div class="db-stat-grid mt-3 mb-4">
            <div class="db-stat is-accent">
                <div class="db-stat-label">Total Awarded @include('procurement.partials.source_badge', ['source' => 'mocs'])</div>
                <div class="db-stat-value">${{ number_format($total) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Contracts</div>
                <div class="db-stat-value">{{ count($contracts) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Business Type</div>
                <div class="db-stat-value" style="font-size: var(--db-text-lg);">{{ $vendor['corporate_structure'] ?? 'N/A' }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">PASSPort ID</div>
                <div class="db-stat-value" style="font-size: var(--db-text-lg);">{{ $vendor['passport_supplier_id'] }}</div>
            </div>
        </div>

        <div class="row">
            {{-- Contents sidebar --}}
            <div class="col-md-3 d-none d-md-block">
                <nav class="db-toc">
                    <div class="db-toc-title">Contents</div>
                    <a class="is-active" href="#section-overview">Overview</a>
                    <a href="#section-contracts">Contracts <span class="db-badge db-badge-neutral">{{ count($contracts) }}</span></a>
                    <a href="#section-transactions">Transactions</a>
                    @if(count($relatedNotices ?? []) > 0)<a href="#notices">City Record Notices <span class="db-badge db-badge-neutral">{{ count($relatedNotices) }}</span></a>@endif
                </nav>
            </div>

            {{-- Main content --}}
            <div class="col-md-9">

                <div id="section-overview" class="db-anchor mb-5">
                    <h4 class="mb-3">Overview</h4>
                    <div class="db-card"><div class="db-card-body">
                        <dl class="db-meta-list">
                            <dt>Vendor Name</dt>
                            <dd class="fw-semibold">{{ $vendor['name'] }}</dd>
                            <dt>PASSPort ID</dt>
                            <dd class="is-mono">{{ $vendor['passport_supplier_id'] }}</dd>
                            <dt>Business Category</dt>
                            <dd>{{ $vendor['business_category'] ?? 'N/A' }}</dd>
                            <dt>Corporate Structure</dt>
                            <dd>{{ $vendor['corporate_structure'] ?? 'N/A' }}</dd>
                            <dt>Certifications</dt>
                            <dd>{{ $vendor['certification_type'] ?: 'None Listed' }}</dd>
                            @if($vendor['ethnicity'] ?? false)
                            <dt>Ethnicity</dt>
                            <dd>{{ $vendor['ethnicity'] }}</dd>
                            @endif
                        </dl>
                    </div></div>
                </div>

                <div id="section-contracts" class="db-anchor mb-5">
                    <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
                        <h4 class="mb-0">Contracts</h4>
                        <span class="db-badge db-badge-neutral">{{ count($contracts) }}</span>
                    </div>
                    <div class="db-table-wrap">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead>
                                    <tr>
                                        <th>Contract ID</th>
                                        <th>Title</th>
                                        <th>Agency</th>
                                        <th class="db-num">Award @include('procurement.partials.source_badge', ['source' => 'mocs'])</th>
                                        <th class="db-num">Start Date</th>
                                        <th class="db-num">End Date</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    @forelse($contracts as $c)
                                    <tr>
                                        <td><a href="{{ route('procurement.contract', ['id' => $c['ctr_id']]) }}" class="fw-semibold">{{ $c['contract_id'] ?? 'N/A' }}</a></td>
                                        <td class="text-muted">{{ $c['contract_title'] ?? '' }}</td>
                                        <td>{{ $c['agency'] ?? 'N/A' }}</td>
                                        <td class="db-num">${{ number_format($c['award_amount'] ?? 0) }}</td>
                                        <td class="db-num text-muted">{{ $c['start_date'] ?? '' }}</td>
                                        <td class="db-num text-muted">{{ $c['end_date'] ?? '' }}</td>
                                        <td>
                                            @php $reg = ($c['status'] ?? '') == 'Registered'; @endphp
                                            <span class="db-badge {{ $reg ? 'db-badge-success' : 'db-badge-neutral' }}"><span class="db-dot"></span>{{ $c['status'] ?? 'Unknown' }}</span>
                                        </td>
                                    </tr>
                                    @empty
                                    <tr><td colspan="7"><div class="db-empty"><div class="db-empty-title">No contracts found</div></div></td></tr>
                                    @endforelse
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                @include('procurement.partials.transactions_table', ['txFilterParam' => 'vendor', 'txFilterValue' => $vendor['name'] ?? ''])

                @include('procurement.partials.related_notices')

            </div>
        </div>

    </div>
</div>
@endsection
