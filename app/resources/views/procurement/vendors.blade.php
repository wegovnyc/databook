@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <div class="db-eyebrow">Procurement</div>
        <h1>Vendors</h1>
        <p class="db-page-lead">Search and filter vendors doing business with New York City.</p>

        {{-- Filter bar --}}
        <form action="{{ route('procurement.vendors') }}" method="GET" class="db-filter-bar mt-3 mb-4">
            <div class="db-search">
                <i class="bi bi-search"></i>
                <input type="search" name="q" placeholder="Search by name or ID…" aria-label="Search vendors" value="{{ $q }}">
            </div>
            <div class="db-field">
                <label for="f-category">Business Category</label>
                <select id="f-category" name="category">
                    <option value="">All Categories</option>
                    @foreach($data['categories'] ?? [] as $cat)
                    <option value="{{ $cat }}" {{ $category == $cat ? 'selected' : '' }}>{{ $cat }}</option>
                    @endforeach
                </select>
            </div>
            <div class="db-field">
                <label for="f-mwbe">MWBE Status</label>
                <select id="f-mwbe" name="mwbe">
                    <option value="">All Statuses</option>
                    @foreach($data['mwbe_options'] ?? [] as $opt)
                    <option value="{{ $opt }}" {{ $mwbe == $opt ? 'selected' : '' }}>{{ $opt }}</option>
                    @endforeach
                </select>
            </div>
            <button type="submit" class="db-btn db-btn-primary db-btn-sm">Apply</button>
            @if($q || $category || $mwbe)
            <a href="{{ route('procurement.vendors') }}" class="db-btn db-btn-ghost db-btn-sm">Reset</a>
            @endif

            {{-- Preserve active sort across filtering --}}
            @if($sort)
                <input type="hidden" name="sort" value="{{ $sort }}">
            @endif
            @if($order ?? false)
                <input type="hidden" name="order" value="{{ $order }}">
            @endif
        </form>

        @php
            $currentSort = $sort ?? 'name';
            $currentOrder = $order ?? 'asc';
            // Build sort URL: toggle direction if same column, else default direction
            function sortUrl($col, $currentSort, $currentOrder, $defaultOrder = 'asc') {
                $newOrder = ($currentSort === $col && $currentOrder === $defaultOrder)
                    ? ($defaultOrder === 'asc' ? 'desc' : 'asc')
                    : $defaultOrder;
                $params = request()->query();
                $params['sort'] = $col;
                $params['order'] = $newOrder;
                $params['page'] = 1; // Reset to page 1 on sort change
                return route('procurement.vendors', $params);
            }
            function sortClass($col, $currentSort, $currentOrder) {
                if ($currentSort !== $col) return 'is-sortable';
                return $currentOrder === 'asc' ? 'is-sorted-asc' : 'is-sorted-desc';
            }
        @endphp

        {{-- Results table --}}
        <div class="db-table-wrap">
            <div class="db-table-toolbar">
                <span class="db-table-count">Showing <strong>{{ number_format($data['total']) }}</strong> vendors</span>
            </div>
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>Supplier ID</th>
                            <th class="{{ sortClass('name', $currentSort, $currentOrder) }}">
                                <a href="{{ sortUrl('name', $currentSort, $currentOrder, 'asc') }}">Name</a>
                            </th>
                            <th>Business Category</th>
                            <th class="db-num {{ sortClass('contracts', $currentSort, $currentOrder) }}">
                                <a href="{{ sortUrl('contracts', $currentSort, $currentOrder, 'desc') }}">Contracts</a>
                            </th>
                            <th class="db-num {{ sortClass('amount', $currentSort, $currentOrder) }}">
                                <a href="{{ sortUrl('amount', $currentSort, $currentOrder, 'desc') }}">Total Awarded</a>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($data['data'] as $vendor)
                        <tr>
                            <td class="text-muted">{{ $vendor['PASSPort Supplier-ID'] }}</td>
                            <td>
                                <a href="{{ route('procurement.vendor', $vendor['PASSPort Supplier-ID']) }}" class="fw-semibold">
                                    {{ $vendor['Vendor Name'] }}
                                </a>
                                @if(!empty($vendor['Certification Type']) && $vendor['Certification Type'] != 'Non-MWBE')
                                    <span class="db-badge db-badge-warning ms-1">{{ $vendor['Certification Type'] }}</span>
                                @endif
                            </td>
                            <td>{{ $vendor['Business Category'] ?? '-' }}</td>
                            <td class="db-num">{{ number_format($vendor['contract_count']) }}</td>
                            <td class="db-num fw-semibold">{{ App\Custom\Utils::currency($vendor['total_awarded']) }}</td>
                        </tr>
                        @empty
                        <tr>
                            <td colspan="5">
                                <div class="db-empty">
                                    <div class="db-empty-icon"><i class="bi bi-search"></i></div>
                                    <div class="db-empty-title">No vendors found</div>
                                    <div class="db-empty-text">Try widening your filters or clearing the search.</div>
                                </div>
                            </td>
                        </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @if(($data['pages'] ?? 1) > 1)
        <nav aria-label="Vendors pagination" class="d-flex justify-content-center mt-3">
            <div class="db-pagination">
                @if($data['page'] > 1)
                <a class="db-page" href="{{ route('procurement.vendors', array_merge(request()->query(), ['page' => $data['page'] - 1])) }}">Previous</a>
                @else
                <span class="db-page is-disabled">Previous</span>
                @endif
                <span class="db-page is-disabled">Page {{ $data['page'] }} of {{ $data['pages'] }}</span>
                @if($data['page'] < $data['pages'])
                <a class="db-page" href="{{ route('procurement.vendors', array_merge(request()->query(), ['page' => $data['page'] + 1])) }}">Next</a>
                @else
                <span class="db-page is-disabled">Next</span>
                @endif
            </div>
        </nav>
        @endif

    </div>
</div>
@endsection
