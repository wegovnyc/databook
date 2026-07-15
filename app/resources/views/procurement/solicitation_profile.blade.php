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
                <div class="db-profile-logo"><i class="bi bi-megaphone" style="font-size: 2rem; color: var(--db-gray-500);"></i></div>
                <div class="db-profile-main">
                    <div class="db-profile-kicker">
                        <span class="db-type-label">Solicitation</span>
                        @if($solicitation['rfx_status'] ?? false)
                        <span class="db-badge {{ $solicitation['rfx_status'] == 'Released' ? 'db-badge-success' : 'db-badge-neutral' }}"><span class="db-dot"></span>{{ $solicitation['rfx_status'] }}</span>
                        @endif
                    </div>
                    <h1 class="db-profile-title">{{ $solicitation['epin'] ?? 'Solicitation' }}</h1>
                    <p class="db-profile-subtitle">{{ $solicitation['procurement_name'] ?? '' }}</p>
                </div>
            </div>
        </div>

        {{-- Key highlights --}}
        <div class="db-stat-grid mt-3 mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Resulting Contracts</div>
                <div class="db-stat-value">{{ $stats['contract_count'] ?? 0 }}</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Total Awarded @include('procurement.partials.source_badge', ['source' => 'mocs'])</div>
                <div class="db-stat-value">${{ number_format($stats['total_awarded'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Due Date</div>
                <div class="db-stat-value" style="font-size: var(--db-text-lg);">{{ $solicitation['due_date'] ?? 'TBD' }}</div>
            </div>
        </div>

        <div class="row">
            {{-- Contents sidebar --}}
            <div class="col-md-3 d-none d-md-block">
                <nav class="db-toc">
                    <div class="db-toc-title">Contents</div>
                    <a class="is-active" href="#details">Details</a>
                    <a href="#contracts">Resulting Contracts <span class="db-badge db-badge-neutral">{{ count($contracts) }}</span></a>
                    @if(count($relatedNotices ?? []) > 0)
                    <a href="#notices">City Record Notices <span class="db-badge db-badge-neutral">{{ count($relatedNotices) }}</span></a>
                    @endif
                </nav>
            </div>

            {{-- Main content --}}
            <div class="col-md-9">
                <div id="details" class="db-anchor mb-5">
                    <h4 class="mb-3">Solicitation Details</h4>
                    <div class="db-card"><div class="db-card-body">
                        <dl class="db-meta-list">
                            <dt>Agency</dt>
                            <dd>{{ $solicitation['agency'] ?? 'N/A' }}</dd>
                            <dt>Status</dt>
                            <dd>{{ $solicitation['rfx_status'] ?? 'N/A' }}</dd>
                            <dt>Release Date</dt>
                            <dd>{{ $solicitation['release_date'] ?? 'N/A' }}</dd>
                            <dt>Due Date</dt>
                            <dd>{{ $solicitation['due_date'] ?? 'TBD' }}</dd>
                            <dt>Industry</dt>
                            <dd>{{ $solicitation['industry'] ?? 'N/A' }}</dd>
                            <dt>Procurement Method</dt>
                            <dd>{{ $solicitation['procurement_method'] ?? 'N/A' }}</dd>
                            <dt>Main Commodity</dt>
                            <dd>{{ $solicitation['main_commodity'] ?? 'N/A' }}</dd>
                        </dl>
                    </div></div>
                </div>

                <div id="contracts" class="db-anchor mb-5">
                    <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
                        <h4 class="mb-0">Resulting Contracts</h4>
                        <span class="db-badge db-badge-neutral">{{ count($contracts) }}</span>
                    </div>
                    @if(count($contracts) > 0)
                    <div class="db-table-wrap">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead>
                                    <tr>
                                        <th>Contract ID</th>
                                        <th>Title</th>
                                        <th>Vendor</th>
                                        <th class="db-num">Award Amount @include('procurement.partials.source_badge', ['source' => 'mocs'])</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    @foreach($contracts as $c)
                                    <tr>
                                        <td><a href="{{ route('procurement.contract', ['id' => $c['ctr_id']]) }}" class="fw-semibold">{{ $c['contract_id'] ?? 'N/A' }}</a></td>
                                        <td class="text-muted">{{ $c['contract_title'] ?? '' }}</td>
                                        <td>{{ $c['vendor_name'] ?? 'N/A' }}</td>
                                        <td class="db-num fw-semibold">${{ number_format($c['award_amount'] ?? 0) }}</td>
                                    </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                    @else
                    <div class="db-empty"><div class="db-empty-title">No linked contracts</div><div class="db-empty-text">No contracts found linked to this EPIN.</div></div>
                    @endif
                </div>

                @include('procurement.partials.related_notices')
            </div>
        </div>

    </div>
</div>
@endsection
