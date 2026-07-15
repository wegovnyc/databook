@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <div class="db-eyebrow">Procurement</div>
        <h1>Solicitations</h1>
        <p class="db-page-lead">Search and explore active solicitations from New York City agencies.</p>

        {{-- Filter bar --}}
        <form action="{{ route('procurement.solicitations') }}" method="GET" class="db-filter-bar mt-3 mb-4">
            <div class="db-search">
                <i class="bi bi-search"></i>
                <input type="search" name="q" placeholder="Search by EPIN or name…" aria-label="Search solicitations" value="{{ $q }}">
            </div>
            <div class="db-field">
                <label for="f-status">Status</label>
                <select id="f-status" name="status">
                    <option value="">All Statuses</option>
                    @foreach($filterOptions['statuses'] ?? [] as $s)
                    <option value="{{ $s }}" {{ $status == $s ? 'selected' : '' }}>{{ $s }}</option>
                    @endforeach
                </select>
            </div>
            <div class="db-field">
                <label for="f-method">Method</label>
                <select id="f-method" name="method">
                    <option value="">All Methods</option>
                    @foreach($filterOptions['methods'] ?? [] as $m)
                    <option value="{{ $m }}" {{ $method == $m ? 'selected' : '' }}>{{ $m }}</option>
                    @endforeach
                </select>
            </div>
            <div class="db-field">
                <label for="f-industry">Industry</label>
                <select id="f-industry" name="industry">
                    <option value="">All Industries</option>
                    @foreach($filterOptions['industries'] ?? [] as $i)
                    <option value="{{ $i }}" {{ $industry == $i ? 'selected' : '' }}>{{ $i }}</option>
                    @endforeach
                </select>
            </div>
            <button type="submit" class="db-btn db-btn-primary db-btn-sm">Apply</button>
            @if($q || $status || $method || $industry)
            <a href="{{ route('procurement.solicitations') }}" class="db-btn db-btn-ghost db-btn-sm">Reset</a>
            @endif
        </form>

        {{-- Results table --}}
        <div class="db-table-wrap">
            <div class="db-table-toolbar">
                <span class="db-table-count">Showing <strong>{{ number_format($data['total'] ?? 0) }}</strong> solicitations</span>
            </div>
            <div class="table-responsive">
                <table class="db-table">
                    <thead>
                        <tr>
                            <th>EPIN</th>
                            <th>Procurement Name</th>
                            <th>Agency</th>
                            <th>Status</th>
                            <th>Due Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($data['data'] as $sol)
                        <tr>
                            <td><a href="{{ route('procurement.solicitation', ['epin' => $sol['EPIN']]) }}" class="fw-semibold">{{ $sol['EPIN'] ?? 'N/A' }}</a></td>
                            <td>{{ $sol['Procurement Name'] ?? 'Untitled' }}</td>
                            <td>{{ $sol['Agency'] ?? 'N/A' }}</td>
                            <td><span class="db-badge db-badge-info"><span class="db-dot"></span>{{ $sol['RFx Status'] ?? 'Unknown' }}</span></td>
                            <td>{{ $sol['Due Date'] ?? 'N/A' }}</td>
                        </tr>
                        @empty
                        <tr>
                            <td colspan="5">
                                <div class="db-empty">
                                    <div class="db-empty-icon"><i class="bi bi-search"></i></div>
                                    <div class="db-empty-title">No solicitations found</div>
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
        <nav aria-label="Solicitations pagination" class="d-flex justify-content-center mt-3">
            <div class="db-pagination">
                @if($data['page'] > 1)
                <a class="db-page" href="{{ route('procurement.solicitations', ['page' => $data['page'] - 1, 'q' => $q, 'status' => $status, 'method' => $method, 'industry' => $industry]) }}">Previous</a>
                @else
                <span class="db-page is-disabled">Previous</span>
                @endif
                <span class="db-page is-disabled">Page {{ $data['page'] }} of {{ $data['pages'] }}</span>
                @if($data['page'] < $data['pages'])
                <a class="db-page" href="{{ route('procurement.solicitations', ['page' => $data['page'] + 1, 'q' => $q, 'status' => $status, 'method' => $method, 'industry' => $industry]) }}">Next</a>
                @else
                <span class="db-page is-disabled">Next</span>
                @endif
            </div>
        </nav>
        @endif

    </div>
</div>
@endsection
