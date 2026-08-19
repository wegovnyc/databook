@extends('layout')

@section('head')
<style>
    /* Digital Services Analysis: Overview - page glue over the db-* design system. */
    .db-page-lead { max-width: none; }   /* full-width subheading */
    .ds-tabs .nav-link { color: var(--db-text-muted); font-weight: var(--db-weight-semibold); }
    .ds-tabs .nav-link.active { color: var(--db-primary); }
    .ds-cta { display: flex; align-items: center; justify-content: space-between; gap: var(--db-space-3); flex-wrap: wrap; }
    .ds-cta-num { font-size: var(--db-text-xl); font-weight: var(--db-weight-bold); color: var(--db-primary); }
    .ds-scope-note summary { cursor: pointer; }

    /* The composition bar. One stacked bar, one row per segment below it. The
       licence segment carries the section's accent because it is the only segment
       with its own analysis page; everything else is a navy ramp, so the colour
       encodes "there is more to read here" rather than decorating. */
    .ds-bar { display: flex; width: 100%; height: 34px; border-radius: var(--db-radius-sm);
              overflow: hidden; border: 1px solid var(--db-border); }
    .ds-bar a, .ds-bar span { display: block; height: 100%; min-width: 3px; text-decoration: none; }
    .ds-bar a:hover { filter: brightness(1.15); }
    .ds-seg-1 { background: #162E51; } .ds-seg-2 { background: #24456F; }
    .ds-seg-3 { background: #35608F; } .ds-seg-4 { background: var(--db-brand, #B24413); }
    .ds-seg-5 { background: #4E7CA8; } .ds-seg-6 { background: #6A96BD; }
    .ds-seg-7 { background: #8AAFCD; } .ds-seg-8 { background: #A7C4DB; }
    .ds-seg-9 { background: #C2D6E7; } .ds-seg-0 { background: #DCE6EF; }
    .ds-legend { display: flex; flex-wrap: wrap; gap: var(--db-space-1) var(--db-space-3);
                 margin-top: var(--db-space-2); font-size: var(--db-text-sm); }
    .ds-legend .k { display: inline-block; width: 10px; height: 10px; border-radius: 2px;
                    margin-right: 5px; vertical-align: baseline; }
    .ds-legend a { color: inherit; text-decoration: none; }
    .ds-legend a:hover { text-decoration: underline; }
    .ds-sib { font-size: var(--db-text-2xs); color: var(--db-text-muted); }
    .ds-chip { display: inline-flex; align-items: center; gap: 6px; }
</style>
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    $comp        = $composition ?? [];
    $segments    = $comp['segments'] ?? [];
    $bar         = $comp['bar'] ?? [];
    $compTotals  = $comp['totals'] ?? [];
    $pipe        = $pipeline ?? [];
    $segSel      = $contracts['segment'] ?? '';
    $segSelSlug  = $contracts['segment_slug'] ?? '';
    // The licence segment's own function mix, carried on its segment row.
    $licSeg      = null;
    foreach ($segments as $s) { if (!empty($s['functions'])) { $licSeg = $s; } }
    // Precomputed so no conditional phrase is glued to a directive: a Blade
    // directive touching a word character is not compiled at all and the page 500s.
    $barFloorPct = ($compTotals['bar_floor_share'] ?? 0.01) * 100;
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <div class="db-eyebrow">Procurement &middot; Digital Services <span class="db-analysis-badge"><i class="bi bi-stars"></i> Analysis</span></div>
        <h1>Digital Services Analysis: Overview</h1>
        <p class="db-page-lead" style="max-width: none;">
            How New York City buys technology &mdash; who it buys from, what kind of thing it is
            buying, and which contracts are coming up for renewal. <strong>Most of this spend is
            not software</strong>, and each kind of purchase raises a different question.
        </p>
        @include('sub.analysis-banner')
        @include('sub.digital-scope-note', ['scope' => $scope ?? []])

        {{-- Headline tiles. ⚠ Each carries its active/ended split, because the totals
             are all-time and a bare figure reads as current exposure: measured, most
             of these contracts have already ended. --}}
        <div class="db-stat-grid mt-3 mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Technology contracts</div>
                <div class="db-stat-value">{{ number_format($stats['count'] ?? 0) }}</div>
                <div class="db-stat-sub">
                    {{ number_format($stats['active_count'] ?? 0) }} not known to have ended &middot;
                    {{ number_format($stats['ended_count'] ?? 0) }} ended
                </div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Total value, all time</div>
                <div class="db-stat-value">${{ number_format(($stats['total'] ?? 0) / 1000000, 0) }}M</div>
                <div class="db-stat-sub">
                    ${{ number_format(($stats['active_total'] ?? 0) / 1000000, 0) }}M still running &middot;
                    ${{ number_format(($stats['ended_total'] ?? 0) / 1000000, 0) }}M ended
                </div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Vendors</div>
                <div class="db-stat-value">{{ number_format($stats['vendor_count'] ?? 0) }}</div>
                <div class="db-stat-sub">Hold at least one confirmed technology contract</div>
            </div>
        </div>

        {{-- ============ THE COMPOSITION: this page's argument ============ --}}
        @if($comp['available'] ?? false)
        <div class="db-chart-card mb-4" id="composition">
            <div class="db-chart-head">
                <span class="db-chart-title">What kind of technology the City is buying</span>
                <span class="text-muted" style="font-size: var(--db-text-sm);">
                    {{ number_format($compTotals['contracts'] ?? 0) }} contracts &middot;
                    {{ number_format($compTotals['segments'] ?? 0) }} kinds
                </span>
            </div>
            <div class="px-3 pb-3">
                <div class="ds-bar" role="img" aria-label="Technology spend by kind of purchase">
                    @foreach($bar as $i => $b)
                        @php
                            $cls = 'ds-seg-' . (($i + 1) % 10);
                            $pct = number_format(($b['share'] ?? 0) * 100, 1);
                            $lbl = $b['segment'] . ' ' . $pct . '% ($' . number_format(($b['value'] ?? 0) / 1000000, 1) . 'M)';
                        @endphp
                        @if(!empty($b['slug']))
                            <a class="{{ $cls }}" style="width: {{ $pct }}%" title="{{ $lbl }}"
                               href="{{ url()->current() }}?contract_segment={{ $b['slug'] }}#all-digital-contracts"></a>
                        @else
                            <span class="{{ $cls }}" style="width: {{ $pct }}%" title="{{ $lbl }}"></span>
                        @endif
                    @endforeach
                </div>
                <div class="ds-legend">
                    @foreach($bar as $i => $b)
                        @php $cls = 'ds-seg-' . (($i + 1) % 10); @endphp
                        <span>
                            <span class="k {{ $cls }}"></span>
                            @if(!empty($b['slug']))
                                <a href="{{ url()->current() }}?contract_segment={{ $b['slug'] }}#all-digital-contracts">{{ $b['segment'] }}</a>
                            @else
                                {{ $b['segment'] }}
                            @endif
                            <span class="text-muted">{{ number_format(($b['share'] ?? 0) * 100, 1) }}%</span>
                        </span>
                    @endforeach
                </div>
                <p class="text-muted mt-3 mb-0" style="font-size: var(--db-text-sm);">
                    A contract bought as a licence is counted as a licence; everything else is
                    named by what it does. That is one bucket per contract, so the bar adds up.
                    Segments below {{ number_format($barFloorPct, 0) }}% of value are folded into
                    &ldquo;Other technology&rdquo; in the bar and listed in full in the table below.
                    Click a segment to see its contracts.
                </p>
            </div>
        </div>

        <div class="db-table-wrap mb-5">
            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead>
                        <tr>
                            <th>Kind of purchase</th>
                            <th class="db-num">Contracts</th>
                            <th class="db-num">Value</th>
                            <th class="db-num">Still running</th>
                            <th>Also bought as licences</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach($segments as $s)
                        <tr>
                            <td>
                                <a href="{{ url()->current() }}?contract_segment={{ $s['slug'] }}#all-digital-contracts">{{ $s['segment'] }}</a>
                                @if(!empty($s['functions']))
                                    <div class="ds-sib">
                                        Across {{ number_format($s['functions_total'] ?? 0) }} different functions &mdash;
                                        <a href="{{ route('research.digital-reform.licenses') }}">analysed family by family</a>
                                    </div>
                                @endif
                            </td>
                            <td class="db-num">{{ number_format($s['contracts'] ?? 0) }}</td>
                            <td class="db-num">${{ number_format(($s['value'] ?? 0) / 1000000, 1) }}M</td>
                            <td class="db-num">
                                {{ number_format($s['active_contracts'] ?? 0) }}
                                <div class="ds-sib">${{ number_format(($s['active_value'] ?? 0) / 1000000, 1) }}M</div>
                            </td>
                            <td>
                                @if(isset($s['licence_siblings']) && $s['licence_siblings'] > 0)
                                    <span class="text-muted">{{ number_format($s['licence_siblings']) }} more contracts
                                    (${{ number_format(($s['licence_siblings_value'] ?? 0) / 1000000, 1) }}M) do this job
                                    but were bought as licences, so they are counted above.</span>
                                @elseif(!empty($s['functions']))
                                    <span class="text-muted">&mdash;</span>
                                @else
                                    <span class="text-muted">None</span>
                                @endif
                            </td>
                        </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
        @elseif(!empty($comp['reason']))
        <div class="db-alert db-alert-warning mb-5" role="alert">
            <i class="bi bi-exclamation-triangle"></i>
            <div class="db-alert-body">
                <strong>The composition view is unavailable</strong>
                <p class="mb-0">{{ $comp['reason'] }}. It is hidden rather than approximated: at
                    amendment-row grain a contract with three amendments would be counted three
                    times and the bar would not add up to anything.</p>
            </div>
        </div>
        @endif

        {{-- Charts --}}
        <div class="db-chart-card mb-4">
            <div class="db-chart-head"><span class="db-chart-title">Technology contract value</span></div>
            <div class="row">
                <div class="col-md-7">
                    <h6 class="text-center mb-3">By Start Year</h6>
                    <div class="db-chart-body" style="height: 300px;"><canvas id="digitalTrendChart"></canvas></div>
                </div>
                <div class="col-md-5">
                    <h6 class="text-center mb-3">By Agency</h6>
                    <div class="db-chart-body" style="height: 300px;"><canvas id="digitalAgencyChart"></canvas></div>
                </div>
            </div>
        </div>

        {{-- ============ CITYWIDE VEHICLES IN THE PIPELINE ============
             ⚠⚠ CEILINGS, NEVER ADDED TO ANY TOTAL ON THIS PAGE. These agreements have
             not reached registration, so no figure above can see them — and the
             consolidation argument this section makes is precisely about them. --}}
        @if(($pipe['count'] ?? 0) > 0)
        <div class="db-table-wrap mb-5" id="pipeline">
            <div class="px-3 pt-3">
                <h2 style="font-size: var(--db-text-lg);">Citywide vehicles waiting in approval</h2>
                <p class="text-muted" style="font-size: var(--db-text-sm);">
                    {{ number_format($pipe['count']) }} purchasing agreements involving these vendors
                    have <strong>not reached registration</strong>, so PASSPort has assigned them no
                    contract id and <strong>nothing above counts them</strong> &mdash; including
                    {{ number_format($pipe['masters'] ?? 0) }} master agreements.
                    Their combined <em>ceiling</em> is
                    ${{ number_format(($pipe['ceiling'] ?? 0) / 1000000, 1) }}M across
                    {{ number_format($pipe['vendors'] ?? 0) }} vendors.
                    A ceiling is the most that may be spent on unsigned paper, usually covering far
                    more than technology &mdash; it is not spend, and adding it to anything above
                    would be wrong.
                    Showing the {{ number_format(count($pipe['rows'] ?? [])) }} above
                    ${{ number_format(($pipe['floor'] ?? 0) / 1000000, 0) }}M.
                </p>
            </div>
            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead>
                        <tr><th>Vendor</th><th>Agency</th><th>Agreement</th><th>Status</th><th class="db-num">Ceiling</th></tr>
                    </thead>
                    <tbody>
                        @foreach(($pipe['rows'] ?? []) as $p)
                        <tr>
                            <td>{{ $p['vendor_name'] }}
                                @if($p['is_master'] ?? false)<span class="db-badge db-badge-warning">Master</span>@endif
                            </td>
                            <td class="small">{{ $p['agency'] }}</td>
                            <td class="text-muted small">{{ $p['contract_title'] }}</td>
                            <td class="small">{{ $p['status'] }}</td>
                            <td class="db-num">${{ number_format($p['ceiling'] ?? 0, 0) }}</td>
                        </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
        @endif

        {{-- Lens cards into the two deeper pages --}}
        <div class="row mb-5">
            <div class="col-md-6 mb-3">
                <div class="db-alert db-alert-info h-100" role="region" aria-label="Expiring contracts">
                    <i class="bi bi-hourglass-split"></i>
                    <div class="db-alert-body">
                        <strong>Renewal Queue</strong>
                        <div class="text-muted" style="font-size: var(--db-text-sm);">
                            <span class="ds-cta-num">{{ number_format($expiring['summary']['count'] ?? 0) }}</span>
                            contracts (${{ number_format(($expiring['summary']['total_value'] ?? 0) / 1000000, 0) }}M)
                            expire before 2030, with transparent flags for the ones worth a second look.
                        </div>
                        <a href="{{ route('research.digital-reform.expiring') }}" class="db-btn db-btn-primary mt-2">
                            Review expiring contracts <i class="bi bi-arrow-right"></i>
                        </a>
                    </div>
                </div>
            </div>
            <div class="col-md-6 mb-3">
                <div class="db-alert db-alert-info h-100" role="region" aria-label="Software licenses">
                    <i class="bi bi-key"></i>
                    <div class="db-alert-body">
                        <strong>Software Licenses</strong>
                        <div class="text-muted" style="font-size: var(--db-text-sm);">
                            <span class="ds-cta-num">{{ number_format($expiring['summary']['licenses'] ?? 0) }}</span>
                            of those expiring contracts are licences. The licence inventory is analysed
                            product family by product family, with the lever each purchase actually has.
                        </div>
                        <a href="{{ route('research.digital-reform.licenses') }}" class="db-btn db-btn-primary mt-2">
                            Open the licence analysis <i class="bi bi-arrow-right"></i>
                        </a>
                    </div>
                </div>
            </div>
        </div>

        {{-- Vendors + Contracts as tabs --}}
        <ul class="nav nav-tabs ds-tabs mb-0" id="dsTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="tab-vendors-btn" data-bs-toggle="tab" data-bs-target="#tab-vendors" type="button" role="tab">
                    <i class="bi bi-building"></i> Vendors ({{ number_format($vendors['total'] ?? 0) }})
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-contracts-btn" data-bs-toggle="tab" data-bs-target="#tab-contracts" type="button" role="tab">
                    <i class="bi bi-file-earmark-text"></i> Contracts ({{ number_format($contracts['total'] ?? 0) }})
                </button>
            </li>
        </ul>
        <div class="tab-content">

        {{-- ---- Vendors tab ---- --}}
        <div class="tab-pane fade show active" id="tab-vendors" role="tabpanel">
        <div class="db-table-wrap mb-5" id="digital-vendors">
            <div class="px-3 pt-3">
                <form method="GET" action="{{ url()->current() }}#digital-vendors" class="db-filter-bar dr-filter-form">
                    @foreach(request()->except(['vendor_q','vendor_page']) as $k => $v)
                        <input type="hidden" name="{{ $k }}" value="{{ $v }}">
                    @endforeach
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input type="search" name="vendor_q" value="{{ $vendorQ }}" placeholder="Search vendors&hellip;" aria-label="Search vendors">
                    </div>
                    <button type="submit" class="db-btn db-btn-primary db-btn-sm"><i class="bi bi-search"></i> Search</button>
                    @if($vendorQ)
                        <a href="{{ url()->current() }}?{{ http_build_query(request()->except(['vendor_q','vendor_page'])) }}#digital-vendors" class="db-btn db-btn-ghost db-btn-sm">Clear</a>
                    @endif
                </form>
                {{-- ⚠ "Digital Share" retired here. It divided a vendor's tagged spend by
                     their TOTAL City spend, which ranked a physical-guard company fifth
                     at "100% digital". The honest columns are the confirmed ones. --}}
                <p class="text-muted mb-3" style="font-size: var(--db-text-sm);">
                    Counts and values cover <strong>only the contracts the classification confirmed
                    are technology</strong> &mdash; not a vendor's whole book of City business.
                    Where a vendor resells other companies' software, the product families it sells
                    are listed, which is what distinguishes a reseller from a maker.
                </p>
            </div>
            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead>
                        <tr>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['vendor_sort' => 'name', 'vendor_order' => ($vendorSort == 'name' && $vendorOrder == 'asc') ? 'desc' : 'asc']) }}#digital-vendors" class="text-decoration-none text-dark">
                                    Vendor @if($vendorSort == 'name'){!! $vendorOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th class="db-num">
                                <a href="{{ request()->fullUrlWithQuery(['vendor_sort' => 'contracts', 'vendor_order' => ($vendorSort == 'contracts' && $vendorOrder == 'asc') ? 'desc' : 'asc']) }}#digital-vendors" class="text-decoration-none text-dark">
                                    Technology contracts @if($vendorSort == 'contracts'){!! $vendorOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th class="db-num">
                                <a href="{{ request()->fullUrlWithQuery(['vendor_sort' => 'amount', 'vendor_order' => ($vendorSort == 'amount' && $vendorOrder == 'asc') ? 'desc' : 'asc']) }}#digital-vendors" class="text-decoration-none text-dark">
                                    Technology value @if($vendorSort == 'amount'){!! $vendorOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th class="db-num">Agencies</th>
                            <th>Sells</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse(($vendors['vendors'] ?? []) as $vendor)
                        @php
                            $sells = $vendor['sells'] ?? [];
                            $sellsTotal = $vendor['sells_total'] ?? 0;
                        @endphp
                        <tr>
                            <td>
                                @if($vendor['vendor_id'] ?? null)
                                    <a href="/procurement/vendor/{{ $vendor['vendor_id'] }}">{{ $vendor['vendor_name'] }}</a>
                                @else
                                    <a href="/procurement/vendors?q={{ urlencode($vendor['vendor_name']) }}">{{ $vendor['vendor_name'] }}</a>
                                @endif
                            </td>
                            <td class="db-num">{{ number_format($vendor['contract_count'] ?? 0) }}</td>
                            <td class="db-num">${{ number_format($vendor['total_awarded'] ?? 0, 0) }}</td>
                            <td class="db-num">{{ number_format($vendor['agencies'] ?? 0) }}</td>
                            <td class="small">
                                @if($sellsTotal > 0)
                                    {{ implode(', ', $sells) }}
                                    @if($sellsTotal > count($sells))
                                        <span class="text-muted">and {{ number_format($sellsTotal - count($sells)) }} more
                                        ({{ number_format($sellsTotal) }} product families in total)</span>
                                    @endif
                                @else
                                    <span class="text-muted">No licensed products &mdash; services, hardware or telecom</span>
                                @endif
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="5" class="text-center text-muted py-4">No vendors match &ldquo;{{ $vendorQ }}&rdquo;.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
            @if(($vendors['total_pages'] ?? 0) > 1)
            <div class="db-table-footer">
                <nav aria-label="Vendors pagination">
                    <ul class="pagination pagination-sm justify-content-center mb-0">
                        <li class="page-item {{ $vendorPage == 1 ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['vendor_page' => $vendorPage - 1]) }}#digital-vendors">Previous</a>
                        </li>
                        <li class="page-item disabled"><span class="page-link">Page {{ $vendorPage }} of {{ $vendors['total_pages'] }}</span></li>
                        <li class="page-item {{ $vendorPage >= ($vendors['total_pages'] ?? 1) ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['vendor_page' => $vendorPage + 1]) }}#digital-vendors">Next</a>
                        </li>
                    </ul>
                </nav>
            </div>
            @endif
        </div>
        </div>

        {{-- ---- Contracts tab ---- --}}
        <div class="tab-pane fade" id="tab-contracts" role="tabpanel">
        <div class="db-table-wrap mb-5" id="all-digital-contracts">
            <div class="px-3 pt-3">
                <form method="GET" action="{{ url()->current() }}#all-digital-contracts" class="db-filter-bar dr-filter-form">
                    @foreach(request()->except(['contract_q','contract_method','contract_page']) as $k => $v)
                        <input type="hidden" name="{{ $k }}" value="{{ $v }}">
                    @endforeach
                    <div class="db-search">
                        <i class="bi bi-search"></i>
                        <input type="search" name="contract_q" value="{{ $contractQ }}" placeholder="Search vendor, title, agency, ID&hellip;" aria-label="Search contracts">
                    </div>
                    <div class="db-field">
                        <label for="contract_method">Procurement method</label>
                        <select name="contract_method" id="contract_method">
                            <option value="">All methods</option>
                            @foreach(($contractOptions['methods'] ?? []) as $m)
                                <option value="{{ $m }}" {{ $contractMethod === $m ? 'selected' : '' }}>{{ $m }}</option>
                            @endforeach
                        </select>
                    </div>
                    <button type="submit" class="db-btn db-btn-primary db-btn-sm"><i class="bi bi-funnel"></i> Apply</button>
                    @if($contractQ || $contractMethod)
                        <a href="{{ url()->current() }}?{{ http_build_query(request()->except(['contract_q','contract_method','contract_page'])) }}#all-digital-contracts" class="db-btn db-btn-ghost db-btn-sm">Clear</a>
                    @endif
                </form>

                {{-- ⚠ The composition drill-down is NOT one of the form controls above, so
                     without this chip the table would silently be showing a subset. --}}
                @if($segSel !== '')
                <div class="mb-3" style="font-size: var(--db-text-sm);">
                    <span class="db-badge db-badge-info ds-chip">
                        <i class="bi bi-diagram-3"></i> {{ $segSel }}
                        <a href="{{ url()->current() }}?{{ http_build_query(request()->except(['contract_segment','contract_page'])) }}#all-digital-contracts"
                           title="Show all technology contracts">&times;</a>
                    </span>
                    <span class="text-muted">{{ number_format($contracts['total'] ?? 0) }} contracts in this segment.</span>
                </div>
                @endif
            </div>
            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead>
                        <tr>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'vendor', 'contract_order' => ($contractSort == 'vendor' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    Vendor @if($contractSort == 'vendor'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>Agency</th>
                            <th>Contract ID</th>
                            <th>Title</th>
                            <th>Method</th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'date', 'contract_order' => ($contractSort == 'date' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    Start Date @if($contractSort == 'date'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'end_date', 'contract_order' => ($contractSort == 'end_date' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    End Date @if($contractSort == 'end_date'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th class="db-num">
                                <a href="{{ request()->fullUrlWithQuery(['contract_sort' => 'amount', 'contract_order' => ($contractSort == 'amount' && $contractOrder == 'asc') ? 'desc' : 'asc']) }}#all-digital-contracts" class="text-dark text-decoration-none">
                                    Amount @if($contractSort == 'amount'){!! $contractOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>Kind</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse(($contracts['contracts'] ?? []) as $c)
                        <tr>
                            <td>
                                @if($c['vendor_id'] ?? null)
                                    <a href="/procurement/vendor/{{ $c['vendor_id'] }}">{{ $c['vendor_name'] }}</a>
                                @else
                                    <a href="/procurement/vendors?q={{ urlencode($c['vendor_name']) }}">{{ $c['vendor_name'] }}</a>
                                @endif
                            </td>
                            <td>{{ $c['agency'] }}</td>
                            <td><a href="/procurement/contract/{{ $c['ctr_id'] ?? $c['contract_id'] }}">{{ $c['contract_id'] }}</a></td>
                            <td class="text-muted small">{{ $c['contract_title'] ?? '' }}</td>
                            <td class="text-muted small">{{ $c['procurement_method'] ?? '' }}</td>
                            <td>{{ $c['start_date'] }}</td>
                            <td>{{ $c['end_date'] }}</td>
                            <td class="db-num">${{ number_format($c['award_amount'] ?? 0, 0) }}</td>
                            {{-- ⚠ The row's composition segment, resolved by the same module as
                                 the bar. It replaced a badge that read the constant "Digital". --}}
                            <td><span class="db-badge {{ ($c['is_license'] ?? false) ? 'db-badge-info' : 'db-badge-neutral' }}">{{ $c['segment'] ?? '' }}</span></td>
                        </tr>
                        @empty
                        <tr><td colspan="9" class="text-center text-muted py-4">No contracts match your filters.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
            @if(($contracts['total_pages'] ?? 0) > 1)
            <div class="db-table-footer">
                <nav aria-label="Contracts pagination">
                    <ul class="pagination pagination-sm justify-content-center mb-0">
                        <li class="page-item {{ $contractPage == 1 ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['contract_page' => $contractPage - 1]) }}#all-digital-contracts">Previous</a>
                        </li>
                        <li class="page-item disabled"><span class="page-link">Page {{ $contractPage }} of {{ $contracts['total_pages'] }}</span></li>
                        <li class="page-item {{ $contractPage >= ($contracts['total_pages'] ?? 1) ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['contract_page' => $contractPage + 1]) }}#all-digital-contracts">Next</a>
                        </li>
                    </ul>
                </nav>
            </div>
            @endif
        </div>
        </div>

        </div> {{-- /.tab-content --}}

        {{-- Research Notes --}}
        <div class="db-alert db-alert-info mt-2" role="alert">
            <i class="bi bi-info-circle"></i>
            <div class="db-alert-body">
                <strong>Research and Methodology Notes</strong>
                <p class="mb-0">
                    Whether a contract is technology, whether it is a licence and what function it
                    serves are produced by an AI pass over each contract's title, purpose and
                    related City Record notices &mdash; a prompt to investigate, not a
                    determination. Where a figure has been reviewed by hand, the section says so.
                    Function categories are the classifier's own free-text buckets and carry no
                    curation layer, which is why corrections are recorded per contract in a
                    version-controlled file rather than edited into a page.
                    Thanks to the
                    <a href="https://github.com/htownley/nyc-tech-spending" target="_blank" rel="noopener" class="fw-semibold">nyc-tech-spending</a>
                    project, whose vendor tags and contract-analysis methodology this section grew
                    out of and has now replaced with a full-population classification.
                </p>
            </div>
        </div>

    </div> <!-- /.container -->
</div> <!-- /.inner_container -->

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {
    DBChart.apply(Chart);
    const currencyFmt = (val) => '$' + val.toLocaleString(undefined, { maximumFractionDigits: 0 });
    const chartData = @json($charts ?? []);

    if (chartData.trend && document.getElementById('digitalTrendChart')) {
        new Chart(document.getElementById('digitalTrendChart'), {
            type: 'bar',
            data: { labels: chartData.trend.labels || [], datasets: [{ label: 'Awarded Amount', data: chartData.trend.values || [], backgroundColor: DBChart.navy, borderRadius: 4 }] },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { ticks: { callback: (val) => '$' + (val / 1000000).toFixed(0) + 'M' } } }, plugins: { legend: { display: false } } }
        });
    }
    if (chartData.agencies && document.getElementById('digitalAgencyChart')) {
        new Chart(document.getElementById('digitalAgencyChart'), {
            type: 'doughnut',
            data: { labels: chartData.agencies.labels || [], datasets: [{ data: chartData.agencies.values || [], backgroundColor: DBChart.palette, borderWidth: 1 }] },
            options: { responsive: true, maintainAspectRatio: false, cutout: '60%',
                plugins: { legend: { position: 'right', labels: { boxWidth: 12, padding: 8, font: { size: 10 } } },
                    tooltip: { callbacks: { label: (c) => c.label + ': ' + currencyFmt(c.parsed) } } } }
        });
    }

    // Deep links into a specific tab (the composition bar targets the contracts table).
    const hash = window.location.hash;
    const btnId = hash === '#all-digital-contracts' ? 'tab-contracts-btn'
                : (hash === '#digital-vendors' ? 'tab-vendors-btn' : null);
    if (btnId && window.bootstrap) { new bootstrap.Tab(document.getElementById(btnId)).show(); }
});
</script>
@endsection
