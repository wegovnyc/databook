@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <div class="db-eyebrow">Procurement</div>
        <h1>Agencies</h1>
        <p class="db-page-lead">Search and filter agencies by procurement activity.</p>

        {{-- Filter bar --}}
        <form action="{{ route('procurement.agencies') }}" method="GET" class="db-filter-bar mt-3 mb-4">
            <div class="db-search">
                <i class="bi bi-search"></i>
                <input type="search" name="q" placeholder="Search by agency name…" aria-label="Search agencies" value="{{ $q }}">
            </div>
            <div class="db-field">
                <label for="f-sort">Sort By</label>
                <select id="f-sort" name="sort">
                    <option value="amount" {{ $sort == 'amount' ? 'selected' : '' }}>Total Spending</option>
                    <option value="count" {{ $sort == 'count' ? 'selected' : '' }}>Contract Count</option>
                    <option value="name" {{ $sort == 'name' ? 'selected' : '' }}>Agency Name</option>
                </select>
            </div>
            <div class="db-field">
                <label for="f-order">Order</label>
                <select id="f-order" name="order">
                    <option value="desc" {{ $order == 'desc' ? 'selected' : '' }}>Descending</option>
                    <option value="asc" {{ $order == 'asc' ? 'selected' : '' }}>Ascending</option>
                </select>
            </div>
            <button type="submit" class="db-btn db-btn-primary db-btn-sm">Apply</button>
            @if($q)
            <a href="{{ route('procurement.agencies') }}" class="db-btn db-btn-ghost db-btn-sm">Reset</a>
            @endif
        </form>

        {{-- Results table --}}
        <div class="db-table-wrap">
            <div class="db-table-toolbar">
                <span class="db-table-count">Showing <strong>{{ number_format($data['total'] ?? 0) }}</strong> agencies</span>
            </div>
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Agency Name</th>
                            <th class="db-num">Contracts</th>
                            <th class="db-num">Total Spending</th>
                            <th>Top Vendor</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($data['agencies'] ?? [] as $agency)
                        <tr>
                            <td>
                                @if(!empty($agency['org_id']))
                                <a href="{{ route('orgSection', ['id' => $agency['org_id'], 'orgslug' => Str::slug($agency['name'], '-'), 'section' => 'procurement-highlights']) }}" class="fw-semibold">
                                    {{ $agency['name'] }}
                                </a>
                                @else
                                <a href="{{ route('agency.procurement', ['name' => $agency['name']]) }}" class="fw-semibold">
                                    {{ $agency['name'] }}
                                </a>
                                @endif
                            </td>
                            <td class="db-num">{{ number_format($agency['contract_count'] ?? 0) }}</td>
                            <td class="db-num fw-semibold">${{ number_format($agency['total_value'] ?? 0, 0) }}</td>
                            <td class="text-truncate text-muted" style="max-width: 250px;">{{ $agency['top_vendor'] ?? '—' }}</td>
                        </tr>
                        @empty
                        <tr>
                            <td colspan="4">
                                <div class="db-empty">
                                    <div class="db-empty-icon"><i class="bi bi-search"></i></div>
                                    <div class="db-empty-title">No agencies found</div>
                                    <div class="db-empty-text">Try a different search term.</div>
                                </div>
                            </td>
                        </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @if(($data['pages'] ?? 1) > 1)
        <nav aria-label="Agencies pagination" class="d-flex justify-content-center mt-3">
            <div class="db-pagination">
                @if(($data['page'] ?? 1) > 1)
                <a class="db-page" href="{{ route('procurement.agencies', array_merge(request()->query(), ['page' => $data['page'] - 1])) }}">Previous</a>
                @else
                <span class="db-page is-disabled">Previous</span>
                @endif
                <span class="db-page is-disabled">Page {{ $data['page'] ?? 1 }} of {{ $data['pages'] ?? 1 }}</span>
                @if(($data['page'] ?? 1) < ($data['pages'] ?? 1))
                <a class="db-page" href="{{ route('procurement.agencies', array_merge(request()->query(), ['page' => $data['page'] + 1])) }}">Next</a>
                @else
                <span class="db-page is-disabled">Next</span>
                @endif
            </div>
        </nav>
        @endif

    </div>
</div>
@endsection
