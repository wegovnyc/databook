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
    $available = $vendors['available'] ?? false;
    $rows   = $vendors['data'] ?? [];
    $total  = (int) ($vendors['total'] ?? count($rows));
    $page   = (int) ($vendors['page'] ?? 1);
    $pages  = (int) ($vendors['pages'] ?? 1);
    $q      = $filters['q'] ?? '';
    $sort   = $filters['sort'] ?? 'spending';
    $order  = ($filters['order'] ?? 'desc') === 'asc' ? 'asc' : 'desc';
    $sorts  = ['spending' => 'Spending', 'current' => 'Contract value', 'contracts' => 'Contract count', 'invoiced' => 'Invoiced', 'payments' => 'Payments', 'vendor' => 'Vendor name'];
    $base   = route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => $section]);
    $active = array_filter(['q' => $q, 'sort' => $sort, 'order' => $order], fn($v) => $v !== '' && $v !== null);
    $pageUrl = fn($p) => $base . '?' . http_build_query(array_merge($active, ['page' => $p]));
    $exportUrl = \App\Custom\DatabookAPI::url('/oce/nycha/vendors/export?' . http_build_query($active));
@endphp

@section('content')
@include('sub.orgheader', ['active' => $section])
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-4); padding-bottom: 0;">
        <div class="db-eyebrow">Procurement · NYCHA</div>
        <h1 style="margin: 0 0 var(--db-space-2);">Vendors @include('procurement.partials.source_badge', ['source' => 'checkbook'])</h1>
        <p class="db-page-lead" style="max-width: 72ch;">Every vendor doing business with the New York City Housing Authority, by contract and payment activity. NYCHA is a separate authority — where a vendor also holds a City (PASSPort) record, its name links to the full City vendor profile; otherwise it opens a NYCHA vendor profile here. Sourced from <a href="https://www.checkbooknyc.com" target="_blank" rel="noopener">Checkbook NYC</a>.</p>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-5); padding-bottom: var(--db-space-8);">
        @if(!$available)
        <div class="db-empty" style="margin-top: var(--db-space-4);">
            <div class="db-empty-icon"><i class="bi bi-people"></i></div>
            <div class="db-empty-title">NYCHA vendor data not yet available</div>
            <div class="db-empty-text">The NYCHA vendor directory is being prepared. Check back soon.</div>
        </div>
        @else

        <div class="d-flex align-items-center flex-wrap mb-1" style="gap: var(--db-space-2);">
            <h3 class="mb-0" style="font-size: var(--db-text-lg);">All NYCHA vendors</h3>
            <span class="db-badge db-badge-neutral">{{ number_format($total) }} vendor{{ $total == 1 ? '' : 's' }}</span>
            <a href="{{ $exportUrl }}" class="db-btn db-btn-outline db-btn-sm ms-auto"><i class="bi bi-download"></i> Export CSV</a>
        </div>

        <form method="GET" action="{{ $base }}" class="db-filter-bar mb-3">
            <input class="db-input" type="search" name="q" value="{{ $q }}" placeholder="Search vendor name…" style="min-width: 260px;" autocomplete="off">
            <select class="db-select" name="sort" aria-label="Sort by">
                @foreach($sorts as $k => $lbl)<option value="{{ $k }}" {{ $sort === $k ? 'selected' : '' }}>{{ $lbl }}</option>@endforeach
            </select>
            <select class="db-select" name="order" aria-label="Order">
                <option value="desc" {{ $order === 'desc' ? 'selected' : '' }}>High → low</option>
                <option value="asc" {{ $order === 'asc' ? 'selected' : '' }}>Low → high</option>
            </select>
            <button type="submit" class="db-btn db-btn-primary">Apply</button>
            @if(count($active))<a href="{{ $base }}" class="db-btn db-btn-outline">Clear</a>@endif
        </form>

        <div class="db-table-wrap">
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Vendor</th>
                            <th>Profile</th>
                            <th class="db-num">Contracts</th>
                            <th class="db-num">Contract Value</th>
                            <th class="db-num">Spending</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($rows as $row)
                        <tr>
                            <td class="fw-semibold" style="max-width: 360px; overflow: hidden; text-overflow: ellipsis;">@include('procurement.partials.nycha_vendor_link', ['r' => $row])</td>
                            <td>
                                @if(!empty($row['vendor_id']))
                                <span class="db-badge db-badge-success"><span class="db-dot"></span>City profile</span>
                                @else
                                <span class="db-badge db-badge-neutral">NYCHA only</span>
                                @endif
                            </td>
                            <td class="db-num">{{ number_format($row['contracts'] ?? 0) }}</td>
                            <td class="db-num">{{ $compact($row['current'] ?? 0) }}</td>
                            <td class="db-num">{{ $compact($row['spending'] ?? 0) }}</td>
                        </tr>
                        @empty
                        <tr><td colspan="5" class="text-muted text-center py-4">No vendors match your search.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @if($pages > 1)
        <div class="d-flex align-items-center justify-content-center mt-3" style="gap: var(--db-space-1);">
            <a class="db-page {{ $page <= 1 ? 'is-disabled' : '' }}" href="{{ $page <= 1 ? '#' : $pageUrl(max($page - 1, 1)) }}">Previous</a>
            <span class="db-page is-disabled">Page {{ number_format($page) }} of {{ number_format($pages) }}</span>
            <a class="db-page {{ $page >= $pages ? 'is-disabled' : '' }}" href="{{ $page >= $pages ? '#' : $pageUrl(min($page + 1, $pages)) }}">Next</a>
        </div>
        @endif

        @endif
    </div>
</div>
@endsection
