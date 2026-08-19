@extends('layout')

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

@php
    // ⚠⚠ COMMITTED MONEY ONLY. This used to sum every contract's award_amount,
    // which folded MASTER-AGREEMENT CEILINGS into a tile captioned "Total
    // Awarded" — ACCENTURE's book alone carried $52.5M of headroom the City has
    // never paid, and two vendors on the renewal queue carry a ceiling with
    // ZERO committed money behind it. A master's purchases are filed under the
    // order ids agencies raise against it, never under its own.
    //
    // The API now serves the split (see modules/contractkind); this reads it
    // rather than re-deriving the MA/MMA rule in Blade, where no Python guard
    // could see it. Falls back to summing rows only if the key is absent.
    $ceiling   = (float) ($spend['ceiling'] ?? 0);
    $ceilingN  = (int) ($spend['ceiling_count'] ?? 0);
    $total = $spend['awarded'] ?? array_reduce($contracts, function($carry, $item) {
        return ($item['amount_kind'] ?? 'committed') === 'ceiling'
            ? $carry : $carry + ($item['award_amount'] ?? 0);
    }, 0);
    // Checkbook actuals across this vendor's contracts. `available` is false while
    // the API's contract-spend map is still populating — show nothing rather than a
    // misleading $0 for a vendor that has real payments.
    $sp        = $spend ?? [];
    $spendOk   = ($sp['available'] ?? false) && ($sp['paid'] ?? 0) > 0;
    $paid      = (float) ($sp['paid'] ?? 0);
    $paidPct   = $sp['pct_used'] ?? null;
    $payments  = (int) ($sp['payments'] ?? 0);
    $compact = function ($n) {
        $n = (float) $n;
        if (abs($n) >= 1e9) return '$' . number_format($n / 1e9, 1) . 'B';
        if (abs($n) >= 1e6) return '$' . number_format($n / 1e6, 1) . 'M';
        if (abs($n) >= 1e3) return '$' . number_format($n / 1e3, 0) . 'K';
        return '$' . number_format($n);
    };

    // PASSPort companion exports (principals, MOCS evaluations, entity record,
    // corporate family, DBA history). Any of these can be absent for a vendor.
    $pp          = $passport ?? [];
    $ppEntity    = $pp['entity'] ?? null;
    $principals  = $pp['principals'] ?? [];
    $ratings     = $pp['evaluations'] ?? null;
    $relatedEnt  = $pp['related'] ?? null;
    $otherNames  = $pp['other_names'] ?? [];
    $adverse     = (int) ($ratings['adverse'] ?? 0);
    // One section covers all three "who is this company" blocks.
    $hasOwnership = count($principals) || count($otherNames)
                    || !empty($relatedEnt) || !empty($ppEntity);
    $ppAsOf      = $pp['as_of'] ?? '';
    // ⚠ Blade will not compile an @if glued to a word character, so any
    // conditional suffix has to be precomputed (see agency enrichment, #126).
    $ppAsOfLabel = $ppAsOf ? 'PASSPort · as of ' . $ppAsOf : 'PASSPort';
    // MOCS Doing Business Database (Local Law 34) — a second custodian's view of
    // who runs the company, and the only source here for registered lobbyists.
    $db          = $doingBusiness ?? [];
    $dbPeople    = $db['people'] ?? [];
    $dbOrgs      = $db['organizations'] ?? [];
    $dbEntity    = $db['entity'] ?? null;
    $dbLobbyists = (int) ($db['lobbyists'] ?? 0);
    $hasDb       = count($dbPeople) || count($dbOrgs);
    $dbAsOf      = $db['as_of'] ?? '';
    $dbAsOfLabel = $dbAsOf ? 'MOCS · Local Law 34 · as of ' . $dbAsOf
                           : 'MOCS · Local Law 34';
    // NY Department of State corporate registry — legal form and, uniquely
    // here, how old the business actually is. Matched by normalized name.
    $dosRec   = $dos ?? null;
    $dosAge   = $dosRec['age_years'] ?? null;
    $hasDos   = !empty($dosRec) && !empty($dosRec['entity_name']);
    $ratingClass = [
        'Excellent'      => 'db-badge-success',
        'Good'           => 'db-badge-success',
        'Satisfactory'   => 'db-badge-neutral',
        'Poor'           => 'db-badge-warning',
        'Unsatisfactory' => 'db-badge-danger',
    ];
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
                <div class="db-stat-sub">Committed contract value</div>
            </div>
            @if($ceiling > 0)
            @php $ceilingSub = $ceilingN . ' master ' . ($ceilingN == 1 ? 'agreement' : 'agreements'); @endphp
            <div class="db-stat">
                <div class="db-stat-label">Ceilings, not spend</div>
                <div class="db-stat-value">{{ $compact($ceiling) }}</div>
                <div class="db-stat-sub">{{ $ceilingSub }} &mdash; headroom to buy against</div>
            </div>
            @endif
            @if($spendOk)
            <div class="db-stat">
                <div class="db-stat-label">Paid to Date @include('procurement.partials.source_badge', ['source' => 'checkbook'])</div>
                <div class="db-stat-value">{{ $compact($paid) }}</div>
                <div class="db-stat-sub">{{ $paidPct !== null ? number_format($paidPct, 1) . '% of awarded' : '' }}{{ $payments ? ' · ' . number_format($payments) . ' payments' : '' }}</div>
            </div>
            @endif
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
                    @if(!empty($sbs))<a href="#section-certified">Certified Business</a>@endif
                    @if($hasOwnership)<a href="#section-ownership">Ownership &amp; Leadership</a>@endif
                    @if($hasDos)<a href="#section-legal-entity">Legal Entity</a>@endif
                    @if($hasDb)<a href="#section-doing-business">Doing Business (LL34)@if($dbLobbyists) <span class="db-badge db-badge-info">{{ $dbLobbyists }} lobbyist{{ $dbLobbyists == 1 ? '' : 's' }}</span>@endif</a>@endif
                    @if($ratings)<a href="#section-ratings">Performance Ratings <span class="db-badge {{ $adverse ? 'db-badge-danger' : 'db-badge-neutral' }}">{{ number_format($ratings['total']) }}</span></a>@endif
                    <a href="#section-contracts">Contracts <span class="db-badge db-badge-neutral">{{ count($contracts) }}</span></a>
                    <a href="#section-transactions">Transactions</a>
                    @if(!empty($nycha))<a href="#section-nycha">NYCHA Activity</a>@endif
                    @if(!empty($software))<a href="#section-software">Software</a>@endif
                    @if(!empty($civicOrgs))<a href="#section-civic">Civic Record</a>@endif
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
                            {{-- Registered-entity facts from the PASSPort entity-summary
                                 export. DUNS in particular exists nowhere else: the
                                 vendors table's own "DUNS Number" column is 0% populated. --}}
                            @if($ppEntity)
                                @if($ppEntity['address'] ?? false)
                                <dt>Business Address</dt>
                                <dd>{{ $ppEntity['address'] }}</dd>
                                @endif
                                @if($ppEntity['telephone'] ?? false)
                                <dt>Phone</dt>
                                <dd class="is-mono">{{ $ppEntity['telephone'] }}</dd>
                                @endif
                                @if($ppEntity['revenue'] ?? false)
                                <dt>Gross Revenue</dt>
                                <dd>{{ $ppEntity['revenue'] }} <span class="text-muted">(self-reported band)</span></dd>
                                @endif
                                @if($ppEntity['for_profit'] ?? false)
                                <dt>For Profit</dt>
                                <dd>{{ $ppEntity['for_profit'] }}</dd>
                                @endif
                                @if($ppEntity['duns'] ?? false)
                                <dt>DUNS</dt>
                                <dd class="is-mono">{{ $ppEntity['duns'] }}</dd>
                                @endif
                                @if($ppEntity['symbol'] ?? false)
                                <dt>Stock Symbol</dt>
                                <dd class="is-mono">{{ $ppEntity['symbol'] }}</dd>
                                @endif
                            @endif
                        </dl>
                    </div></div>
                </div>

                {{-- Ownership & Leadership — the officers and principal owners MOCS
                     collects at registration, plus the corporate family and any
                     other names the firm trades under. PASSPort displays all of
                     this; Databook has never published it. Matched to the vendor
                     by normalized name within the same MOCS export set (~99.5%
                     of rows join), so it is labelled with its own source + date. --}}
                @if($hasOwnership)
                <div id="section-ownership" class="db-anchor mb-5">
                    <div class="d-flex align-items-center flex-wrap mb-3" style="gap: var(--db-space-15);">
                        <h4 class="mb-0">Ownership &amp; Leadership</h4>
                        <span class="db-badge db-badge-neutral">{{ $ppAsOfLabel }}</span>
                    </div>

                    @if(count($principals))
                    <div class="db-table-wrap mb-3">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead><tr><th>Name</th><th>Title</th><th>Role</th></tr></thead>
                                <tbody>
                                    @foreach($principals as $p)
                                    <tr>
                                        <td class="fw-semibold">{{ $p['name'] }}</td>
                                        <td>{{ $p['title'] ?: '—' }}</td>
                                        <td>
                                            @if($p['ownership_type'])
                                            <span class="db-badge {{ $p['ownership_type'] === 'Principal Owner' ? 'db-badge-navy' : 'db-badge-neutral' }}">{{ $p['ownership_type'] }}</span>
                                            @else — @endif
                                        </td>
                                    </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                    @endif

                    @if(count($otherNames))
                    <h5 class="mb-2" style="font-size: var(--db-text-base);">Also known as</h5>
                    <div class="db-table-wrap mb-3">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead><tr><th>Name</th><th>Type</th><th>From</th><th>To</th></tr></thead>
                                <tbody>
                                    @foreach($otherNames as $n)
                                    <tr>
                                        <td class="fw-semibold">{{ $n['name'] }}</td>
                                        <td>{{ $n['type'] ?: '—' }}</td>
                                        <td class="text-muted">{{ $n['from'] ?: '—' }}</td>
                                        <td class="text-muted">{{ $n['to'] ?: '—' }}</td>
                                    </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                    @endif

                    @if($relatedEnt && count($relatedEnt['rows'] ?? []))
                    <div class="d-flex align-items-center mb-2" style="gap: var(--db-space-15);">
                        <h5 class="mb-0" style="font-size: var(--db-text-base);">Related entities</h5>
                        <span class="db-badge db-badge-neutral">{{ number_format($relatedEnt['total']) }}</span>
                    </div>
                    <div class="db-table-wrap">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead><tr><th>Entity</th><th>Relationship</th><th>Location</th></tr></thead>
                                <tbody>
                                    @foreach($relatedEnt['rows'] as $r)
                                    <tr>
                                        <td class="fw-semibold">{{ $r['name'] }}</td>
                                        <td>{{ $r['relationship'] ?: '—' }}</td>
                                        <td class="text-muted">{{ $r['location'] ?: '—' }}</td>
                                    </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                    @if($relatedEnt['total'] > $relatedEnt['showing'])
                    <p class="text-muted mt-2" style="font-size: var(--db-text-sm);">Showing {{ number_format($relatedEnt['showing']) }} of {{ number_format($relatedEnt['total']) }} related entities.</p>
                    @endif
                    @endif

                    <p class="text-muted mt-2" style="font-size: var(--db-text-sm);">Officers, owners and affiliates as disclosed by the vendor to the Mayor's Office of Contract Services during PASSPort registration.</p>
                </div>
                @endif

                {{-- NY Department of State corporate registry. The only source on this
                     page describing the vendor's LEGAL form rather than its procurement
                     behaviour, and the only one that gives a business age. Matched by
                     normalized name against the registry (no shared identifier), so the
                     caveats below are stated rather than implied. --}}
                @if($hasDos)
                <div id="section-legal-entity" class="db-anchor mb-5">
                    <div class="d-flex align-items-center flex-wrap mb-3" style="gap: var(--db-space-15);">
                        <h4 class="mb-0">Legal Entity</h4>
                        <span class="db-badge db-badge-neutral">NY Dept of State</span>
                        @if($dosAge !== null)
                        <span class="db-badge db-badge-info">{{ $dosAge }} year{{ $dosAge == 1 ? '' : 's' }} old</span>
                        @endif
                    </div>
                    <div class="db-card"><div class="db-card-body">
                        <dl class="db-meta-list">
                            <dt>Registered Name</dt>
                            <dd class="fw-semibold">{{ $dosRec['entity_name'] }}</dd>
                            @if($dosRec['entity_type'] ?? false)
                            <dt>Entity Type</dt><dd>{{ $dosRec['entity_type'] }}</dd>
                            @endif
                            @if($dosRec['registered'] ?? false)
                            <dt>Registered</dt>
                            <dd>{{ $dosRec['registered'] }}@if($dosAge !== null)<span class="text-muted"> · {{ $dosAge }} years ago</span>@endif</dd>
                            @endif
                            @if($dosRec['county'] ?? false)
                            <dt>County</dt><dd>{{ $dosRec['county'] }}</dd>
                            @endif
                            @if($dosRec['jurisdiction'] ?? false)
                            <dt>Jurisdiction</dt><dd>{{ $dosRec['jurisdiction'] }}</dd>
                            @endif
                            {{-- 19.6% / 98.3% populated respectively — shown only when present. --}}
                            @if($dosRec['registered_agent'] ?? false)
                            <dt>Registered Agent</dt><dd>{{ $dosRec['registered_agent'] }}</dd>
                            @endif
                            @if($dosRec['process_address'] ?? false)
                            <dt>Service of Process</dt>
                            <dd>@if($dosRec['process_name'] ?? false){{ $dosRec['process_name'] }}<br>@endif{{ $dosRec['process_address'] }}</dd>
                            @endif
                            @if($dosRec['dos_id'] ?? false)
                            <dt>DOS ID</dt><dd class="is-mono">{{ $dosRec['dos_id'] }}</dd>
                            @endif
                        </dl>
                        <a href="{{ $dosRec['lookup_url'] }}" target="_blank" rel="noopener" class="db-btn db-btn-outline db-btn-sm mt-2">Look up on NYS DOS <i class="bi bi-box-arrow-up-right"></i></a>
                    </div></div>
                    <p class="text-muted mt-2" style="font-size: var(--db-text-sm);">
                        Matched to the New York State corporate registry by name. The copy held here covers <span class="fw-semibold">active</span> entities registered in the five NYC counties, so a vendor incorporated elsewhere, or since dissolved, will not appear.
                    </p>
                </div>
                @endif

                {{-- MOCS Doing Business Database (Local Law 34). Collected to enforce
                     campaign-contribution limits, so it is maintained independently of
                     the vendor's own PASSPort registration — it corroborates the panel
                     above and is the only source here for registered lobbyists.
                     Linked to this vendor by exact name (or an exact PASSPort DBA);
                     near-misses are held for human review and never shown. --}}
                @if($hasDb)
                <div id="section-doing-business" class="db-anchor mb-5">
                    <div class="d-flex align-items-center flex-wrap mb-3" style="gap: var(--db-space-15);">
                        <h4 class="mb-0">Doing Business Database</h4>
                        <span class="db-badge db-badge-neutral">{{ $dbAsOfLabel }}</span>
                        @if($dbLobbyists)
                        <span class="db-badge db-badge-info">{{ number_format($dbLobbyists) }} registered lobbyist{{ $dbLobbyists == 1 ? '' : 's' }}</span>
                        @endif
                    </div>

                    @if($dbEntity)
                    <div class="db-card mb-3"><div class="db-card-body">
                        <dl class="db-meta-list">
                            @if($dbEntity['ownership_structure'] ?? false)
                            <dt>Ownership Structure</dt><dd>{{ $dbEntity['ownership_structure'] }}</dd>
                            @endif
                            @if($dbEntity['doing_business_since'] ?? false)
                            <dt>Doing Business Since</dt><dd>{{ $dbEntity['doing_business_since'] }}</dd>
                            @endif
                            @if($dbEntity['phone'] ?? false)
                            <dt>Phone</dt><dd class="is-mono">{{ $dbEntity['phone'] }}</dd>
                            @endif
                        </dl>
                    </div></div>
                    @endif

                    @if(count($dbPeople))
                    <div class="db-table-wrap mb-3">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead><tr><th>Name</th><th>Role</th><th>Since</th></tr></thead>
                                <tbody>
                                    @foreach($dbPeople as $p)
                                    <tr>
                                        <td class="fw-semibold">{{ $p['name'] }}</td>
                                        <td>
                                            @if($p['role'])
                                                {{ $p['role'] }}
                                            @else
                                                {{-- MOCS publishes no public definition for this code, so
                                                     show the group it belongs to plus the raw code rather
                                                     than inventing a title for a named individual. --}}
                                                {{ $p['group'] ?: 'Other' }}
                                                @if($p['role_code'])<span class="text-muted is-mono" style="font-size: var(--db-text-sm);"> ({{ $p['role_code'] }})</span>@endif
                                            @endif
                                        </td>
                                        <td class="text-muted">{{ $p['since'] ?: '—' }}</td>
                                    </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                    @endif

                    @if(count($dbOrgs))
                    {{-- Organizations that own 10%+ of the vendor. Reported separately
                         since 2018 and kept out of the people table — these are
                         companies and trusts, not individuals. --}}
                    <h5 class="mb-2" style="font-size: var(--db-text-base);">Organizations with a 10%+ stake</h5>
                    <div class="db-table-wrap mb-3">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead><tr><th>Organization</th><th>Relationship</th><th>Since</th></tr></thead>
                                <tbody>
                                    @foreach($dbOrgs as $o)
                                    <tr>
                                        <td class="fw-semibold">{{ $o['name'] }}</td>
                                        <td>{{ $o['role'] ?: $o['role_code'] }}</td>
                                        <td class="text-muted">{{ $o['since'] ?: '—' }}</td>
                                    </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                    @endif

                    @if(($db['total'] ?? 0) > ($db['showing'] ?? 0))
                    <p class="text-muted" style="font-size: var(--db-text-sm);">Showing {{ number_format($db['showing']) }} of {{ number_format($db['total']) }} recorded relationships.</p>
                    @endif
                    <p class="text-muted mt-2" style="font-size: var(--db-text-sm);">
                        Filed with the Mayor's Office of Contract Services under Local Law 34 of 2007, which limits campaign contributions from the principal officers, owners and senior managers of firms doing business with the City. Filed as <span class="fw-semibold">{{ $db['organization_name'] ?? '' }}</span>.
                        MOCS publishes some role codes without a public definition; those are shown as the code itself rather than interpreted.
                    </p>
                </div>
                @endif

                {{-- MOCS performance ratings. Agencies formally evaluate vendors at
                     the end of a contract period; the rating is the City's own
                     assessment, not a Databook judgement. Adverse ratings (Poor /
                     Unsatisfactory) are counted out separately because they are the
                     most consequential fact on this page. --}}
                @if($ratings)
                <div id="section-ratings" class="db-anchor mb-5">
                    <div class="d-flex align-items-center flex-wrap mb-3" style="gap: var(--db-space-15);">
                        <h4 class="mb-0">Performance Ratings</h4>
                        <span class="db-badge db-badge-neutral">{{ $ppAsOfLabel }}</span>
                        @if($adverse)
                        <span class="db-badge db-badge-danger">{{ number_format($adverse) }} adverse</span>
                        @endif
                    </div>

                    <div class="db-card mb-3"><div class="db-card-body">
                        <div class="d-flex flex-wrap" style="gap: var(--db-space-15);">
                            @foreach($ratings['ratings'] as $r)
                            <span class="db-badge {{ $ratingClass[$r['rating']] ?? 'db-badge-neutral' }}">{{ $r['rating'] }}: {{ number_format($r['count']) }}</span>
                            @endforeach
                        </div>
                        <p class="text-muted mb-0 mt-3" style="font-size: var(--db-text-sm);">
                            {{ number_format($ratings['total']) }} evaluation{{ $ratings['total'] == 1 ? '' : 's' }}
                            @if($ratings['agencies']) across {{ number_format($ratings['agencies']) }} agenc{{ $ratings['agencies'] == 1 ? 'y' : 'ies' }}@endif
                            @if($ratings['latest']) · most recent {{ $ratings['latest'] }}@endif
                        </p>
                    </div></div>

                    @if(count($ratings['recent'] ?? []))
                    <div class="db-table-wrap">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead><tr><th>Evaluated</th><th>Agency</th><th>Contract</th><th>Period</th><th>Rating</th></tr></thead>
                                <tbody>
                                    @foreach($ratings['recent'] as $e)
                                    @php
                                        $period = trim(($e['period_start'] ?: '') . (($e['period_start'] && $e['period_end']) ? ' – ' : '') . ($e['period_end'] ?: ''));
                                    @endphp
                                    <tr>
                                        <td class="text-muted">{{ $e['date'] ?: '—' }}</td>
                                        <td>{{ $e['agency'] ?: '—' }}</td>
                                        <td>
                                            @if($e['contract_id'])
                                            <span class="is-mono" style="font-size: var(--db-text-sm);">{{ $e['contract_id'] }}</span>
                                            @if($e['purpose'])<div class="text-muted" style="font-size: var(--db-text-sm); max-width: 320px;">{{ $e['purpose'] }}</div>@endif
                                            @else — @endif
                                        </td>
                                        <td class="text-muted" style="font-size: var(--db-text-sm);">{{ $period ?: '—' }}</td>
                                        <td><span class="db-badge {{ $ratingClass[$e['rating']] ?? 'db-badge-neutral' }}">{{ $e['rating'] ?: '—' }}</span></td>
                                    </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                    @if($ratings['total'] > $ratings['showing'])
                    <p class="text-muted mt-2" style="font-size: var(--db-text-sm);">Showing the {{ number_format($ratings['showing']) }} most recent of {{ number_format($ratings['total']) }} evaluations.</p>
                    @endif
                    @endif

                    <p class="text-muted mt-2" style="font-size: var(--db-text-sm);">Ratings are assigned by the contracting agency at the close of an evaluation period and published by the Mayor's Office of Contract Services.</p>
                </div>
                @endif

                {{-- Certified-business profile (NYC Dept of Small Business Services).
                     What the firm actually DOES, plus capacity and past performance —
                     none of which the PASSPort vendor record carries. Matched on
                     normalized name, so it is labelled as a separate source. --}}
                @if(!empty($sbs))
                @php
                    $naics = trim(($sbs['naics_title'] ?? '') . (($sbs['naics_code'] ?? '') ? ' (' . $sbs['naics_code'] . ')' : ''));
                    $sbsSite = $sbs['website'] ?? '';
                    $sbsHref = $sbsSite && !preg_match('~^https?://~i', $sbsSite) ? 'https://' . $sbsSite : $sbsSite;
                    $bond = $sbs['bonding_limit'] ?? '';
                    $bondFmt = is_numeric(str_replace([',','$'], '', $bond)) ? $compact(str_replace([',','$'], '', $bond)) : $bond;
                @endphp
                <div id="section-certified" class="db-anchor mb-5">
                    <div class="d-flex align-items-center flex-wrap mb-3" style="gap: var(--db-space-15);">
                        <h4 class="mb-0">Certified Business Profile</h4>
                        @if($sbs['certification'] ?? false)<span class="db-badge db-badge-warning">{{ $sbs['certification'] }}</span>@endif
                        <span class="db-badge db-badge-neutral">NYC SBS</span>
                    </div>
                    <div class="db-card mb-3"><div class="db-card-body">
                        @if($sbs['description'] ?? false)
                        <p style="margin: 0 0 var(--db-space-3);">{{ $sbs['description'] }}</p>
                        @endif
                        <dl class="db-meta-list">
                            @if($naics)<dt>Industry (NAICS)</dt><dd>{{ $naics }}@if($sbs['naics_sector'] ?? false)<span class="text-muted"> · {{ $sbs['naics_sector'] }}</span>@endif</dd>@endif
                            @if($sbs['dba'] ?? false)<dt>Doing business as</dt><dd>{{ $sbs['dba'] }}</dd>@endif
                            @if($sbs['established'] ?? false)<dt>Established</dt><dd>{{ $sbs['established'] }}</dd>@endif
                            @if($bondFmt)<dt>Bonding limit</dt><dd>{{ $bondFmt }}</dd>@endif
                            @if($sbs['union_signatory'] ?? false)<dt>Union signatory</dt><dd>{{ $sbs['union_signatory'] }}</dd>@endif
                            @if($sbs['construction_types'] ?? false)<dt>Project types</dt><dd>{{ $sbs['construction_types'] }}</dd>@endif
                            @if($sbs['certification_renewal'] ?? false)<dt>Certification renews</dt><dd>{{ $sbs['certification_renewal'] }}</dd>@endif
                            @if($sbs['borough'] ?? false)<dt>Location</dt><dd>{{ trim(($sbs['city'] ?? '') . (($sbs['state'] ?? '') ? ', ' . $sbs['state'] : '')) ?: $sbs['borough'] }}</dd>@endif
                            @if($sbs['telephone'] ?? false)<dt>Phone</dt><dd class="is-mono">{{ $sbs['telephone'] }}</dd>@endif
                            @if($sbsSite)<dt>Website</dt><dd><a href="{{ $sbsHref }}" target="_blank" rel="noopener nofollow">{{ $sbsSite }}</a></dd>@endif
                            @if($sbs['enrolled_in_passport'] ?? false)<dt>Enrolled in PASSPort</dt><dd>{{ $sbs['enrolled_in_passport'] }}</dd>@endif
                        </dl>
                    </div></div>

                    @if(count($sbs['jobs'] ?? []))
                    <div class="d-flex align-items-center mb-2" style="gap: var(--db-space-15);">
                        <h5 class="mb-0" style="font-size: var(--db-text-base);">Self-reported past performance</h5>
                        <span class="db-badge db-badge-neutral">{{ count($sbs['jobs']) }}</span>
                    </div>
                    <div class="db-table-wrap">
                        <div class="table-responsive">
                            <table class="db-table">
                                <thead><tr><th>Client</th><th>Work</th><th class="db-num">Value</th><th class="db-num">When</th></tr></thead>
                                <tbody>
                                    @foreach($sbs['jobs'] as $j)
                                    <tr>
                                        <td class="fw-semibold">{{ $j['client'] }}</td>
                                        <td class="text-muted" style="max-width: 340px;">{{ $j['description'] ?: '—' }}</td>
                                        <td class="db-num">@php $v = str_replace([',','$'], '', $j['value'] ?? ''); @endphp{{ is_numeric($v) && $v !== '' ? $compact($v) : ($j['value'] ?: '—') }}</td>
                                        <td class="db-num text-muted">{{ $j['date'] ?: '—' }}</td>
                                    </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <p class="text-muted mt-2" style="font-size: var(--db-text-sm);">Reported by the firm to NYC Small Business Services as part of certification — not verified against City payment records.</p>
                    @endif
                </div>
                @endif

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
                                        @if($spendOk)<th class="db-num">Paid @include('procurement.partials.source_badge', ['source' => 'checkbook'])</th>
                                        <th style="width: 130px;">Used</th>@endif
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
                                        <td class="db-num">${{ number_format($c['award_amount'] ?? 0) }}@if(($c['amount_kind'] ?? 'committed') === 'ceiling')<div class="db-text-muted" style="font-size: .75rem;" title="Master agreement: a ceiling agencies may buy against. Purchases are filed under their own order ids, so this figure is not spend.">ceiling</div>@endif</td>
                                        @if($spendOk)
                                        @php $u = $c['pct_used']; $ur = $u === null ? 0 : min($u / 100, 1.5); @endphp
                                        <td class="db-num">{{ ($c['spent_to_date'] ?? 0) > 0 ? $compact($c['spent_to_date']) : '—' }}</td>
                                        <td>
                                            @if($u !== null)
                                            <div style="display: flex; align-items: center; gap: var(--db-space-1);">
                                                <div style="flex: 1; background: var(--db-gray-100); border-radius: 999px; height: 6px; overflow: hidden;">
                                                    <div style="width: {{ min($ur * 100, 100) }}%; height: 100%; background: {{ $ur > 1 ? 'var(--db-danger)' : 'var(--db-accent)' }};"></div>
                                                </div>
                                                <span style="font-size: var(--db-text-2xs); color: var(--db-text-muted); font-variant-numeric: tabular-nums; min-width: 38px; text-align: right;">{{ number_format($u, 0) }}%</span>
                                            </div>
                                            @else<span class="text-muted">—</span>@endif
                                        </td>
                                        @endif
                                        <td class="db-num text-muted">{{ $c['start_date'] ?? '' }}</td>
                                        <td class="db-num text-muted">{{ $c['end_date'] ?? '' }}</td>
                                        <td>
                                            @php $reg = ($c['status'] ?? '') == 'Registered'; @endphp
                                            <span class="db-badge {{ $reg ? 'db-badge-success' : 'db-badge-neutral' }}"><span class="db-dot"></span>{{ $c['status'] ?? 'Unknown' }}</span>
                                        </td>
                                    </tr>
                                    @empty
                                    <tr><td colspan="{{ $spendOk ? 9 : 7 }}"><div class="db-empty"><div class="db-empty-title">No contracts found</div></div></td></tr>
                                    @endforelse
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                @include('procurement.partials.transactions_table', ['txFilterParam' => 'vendor', 'txFilterValue' => $vendor['name'] ?? ''])

                {{-- NYCHA activity (crosswalked vendors only — API returns nycha:null otherwise).
                     NYCHA is a separate authority: its contracts/payments live in the Checkbook
                     _NYCHA feeds, not the City tables above, so they're rolled up here and
                     linked into the NYCHA explorers on the org profile. --}}
                {{-- Software products this vendor supplies, from the licence analysis.
                     ⚠ Links into the UNLISTED Licenses section. That section is unlisted
                     because its classifications are AI-derived and uncurated; linking to it
                     from this PUBLIC page makes it reachable by anyone browsing vendors.
                     The target pages keep noindex, so they stay out of search results, but
                     this is the one place the two audiences meet. Remove this block to put
                     it back behind obscurity. --}}
                @if (!empty($software))
                    @php
                        // Precomputed: a Blade directive glued to a word character is not
                        // compiled, and the page 500s with "unexpected endif".
                        $swCount = count($software);
                        $swHeading = $swCount === 1 ? 'Software Product' : 'Software Products';
                        $swNote = $swCount === 1
                            ? 'One product family this vendor licenses to the City.'
                            : $swCount . ' product families this vendor licenses to the City.';
                    @endphp
                    <div class="db-card mb-4" id="section-software">
                        <div class="db-card-head">
                            <span class="db-card-title"><i class="bi bi-window-stack"></i> {{ $swHeading }}</span>
                            <span class="db-analysis-badge"><i class="bi bi-stars"></i> Analysis</span>
                        </div>
                        <div class="db-card-body">
                            <p style="font-size: var(--db-text-sm); color: var(--db-text-secondary); margin-bottom: var(--db-space-3);">
                                {{ $swNote }}
                                Identified by AI from contract text and <strong>not yet reviewed by a
                                person</strong>, so treat it as a lead rather than a record.
                            </p>
                            <table class="db-table">
                                <thead><tr><th>Product</th><th>What it does</th><th style="text-align:right;">Contracts</th></tr></thead>
                                <tbody>
                                @foreach ($software as $sw)
                                    <tr>
                                        <td>
                                            <a href="{{ route('research.digital-reform.license-family', ['slug' => $sw['slug']]) }}">{{ $sw['family'] }}</a>
                                        </td>
                                        <td style="font-size: var(--db-text-sm); color: var(--db-text-secondary);">
                                            @if(!empty($sw['summary']))
                                                {{ $sw['summary'] }}
                                            @else
                                                <span style="color: var(--db-text-muted); font-style: italic;">Not described &mdash; the contract text was too vague to summarise</span>
                                            @endif
                                        </td>
                                        <td style="text-align:right;">{{ number_format($sw['contracts']) }}</td>
                                    </tr>
                                @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                @endif

                @if (!empty($civicOrgs))
                    @php
                        // Track B. Precomputed: a Blade directive glued to a word
                        // character is not compiled and 500s the page while
                        // `php -l` passes clean.
                        $civicOne = count($civicOrgs) === 1;
                        $civicHeading = $civicOne ? 'Civic Record' : 'Civic Records';
                    @endphp
                    <div id="section-civic" class="db-anchor mb-5">
                        <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
                            <h4 class="mb-0">{{ $civicHeading }}</h4>
                            <span class="db-badge db-badge-neutral">Databook org register</span>
                        </div>
                        <div class="db-card"><div class="db-card-body">
                            <p class="text-muted" style="font-size: var(--db-text-sm);">
                                This vendor is also tracked as a civic actor in NYC governance —
                                {{ $civicOne ? 'an organization' : 'organizations' }} with
                                {{ $civicOne ? 'its' : 'their' }} own profile covering leadership,
                                notices and city relationships beyond procurement.
                                Matched by name, so the link is a judgement rather than an identifier.
                            </p>
                            <ul class="list-unstyled mb-0">
                                @foreach ($civicOrgs as $co)
                                    @php
                                        $coName = ($co['display_name'] ?? null) ?: ($co['org_name'] ?? '');
                                        $coTier = $co['match_tier'] ?? '';
                                        $coHow = $coTier === 'curated'
                                            ? 'human-confirmed'
                                            : 'matched on name (' . $coTier . ')';
                                    @endphp
                                    <li class="mb-2">
                                        <a href="{{ route('orgProfile', ['id' => $co['org_id'], 'orgslug' => Str::slug($co['org_name'] ?? '', '-')]) }}">{{ $coName }}</a>
                                        @if (!empty($co['org_type']))
                                            <span class="db-badge db-badge-neutral">{{ $co['org_type'] }}</span>
                                        @endif
                                        <span class="db-meta">{{ $coHow }}</span>
                                    </li>
                                @endforeach
                            </ul>
                        </div></div>
                    </div>
                @endif

                @if(!empty($nycha))
                @php
                    $nychaNames = $nycha['names'] ?? [];
                    $nychaQ = $nychaNames[0] ?? ($vendor['name'] ?? '');
                    $nychaOrg = ['id' => 170020034, 'orgslug' => 'nyc-housing-authority'];
                    $nychaContractsUrl = route('orgSection', $nychaOrg + ['section' => 'procurement-nycha-contracts']) . '?q=' . urlencode($nychaQ);
                    $nychaSpendingUrl  = route('orgSection', $nychaOrg + ['section' => 'procurement-nycha-spending']) . '?q=' . urlencode($nychaQ);
                    $nychaC = $nycha['contracts'] ?? null;
                    $nychaS = $nycha['spending'] ?? null;
                    $nychaFyRange = ($nychaS && $nychaS['min_year'])
                        ? ($nychaS['min_year'] == $nychaS['max_year'] ? 'FY' . $nychaS['min_year'] : 'FY' . $nychaS['min_year'] . '-FY' . $nychaS['max_year'])
                        : '';
                @endphp
                <div id="section-nycha" class="db-anchor mb-5">
                    <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
                        <h4 class="mb-0">NYCHA Activity</h4>
                        <span class="db-badge db-badge-neutral">Housing Authority</span>
                    </div>
                    <div class="db-card"><div class="db-card-body">
                        <p class="text-muted" style="font-size: var(--db-text-sm);">
                            This vendor also does business with the <a href="/o/170020034-nyc-housing-authority/procurement-highlights">NYC Housing Authority</a> —
                            a separate authority whose contracts and payments aren't in the City records above.
                            Matched by vendor name{{ count($nychaNames) > 1 ? 's: ' . implode('; ', $nychaNames) : '' }}.
                            @php
                                // Provenance for a name-based join: say HOW it was matched
                                // rather than presenting the link as certain.
                                $mConf  = $nycha['match']['confidence'] ?? '';
                                $mScore = $nycha['match']['score'] ?? null;
                                $mLabel = ['curated' => 'human-confirmed', 'exact' => 'exact name match',
                                           'fuzzy' => 'fuzzy name match'][$mConf] ?? $mConf;
                            @endphp
                            @if($mLabel)<span class="db-badge db-badge-neutral" title="How this NYCHA vendor was linked to this City vendor record">{{ $mLabel }}@if($mConf === 'fuzzy' && $mScore) · {{ number_format($mScore, 2) }}@endif</span>@endif
                        </p>
                        <div class="db-stat-grid">
                            @if($nychaC)
                            <div class="db-stat">
                                <div class="db-stat-label">NYCHA Contracts</div>
                                <div class="db-stat-value">{{ number_format($nychaC['count']) }}</div>
                            </div>
                            <div class="db-stat">
                                <div class="db-stat-label">Current Contract Value</div>
                                <div class="db-stat-value">${{ number_format($nychaC['current']) }}</div>
                            </div>
                            <div class="db-stat">
                                <div class="db-stat-label">Invoiced</div>
                                <div class="db-stat-value">${{ number_format($nychaC['invoiced']) }}</div>
                            </div>
                            @endif
                            @if($nychaS)
                            <div class="db-stat">
                                <div class="db-stat-label">NYCHA Spending{{ $nychaFyRange ? " ($nychaFyRange)" : '' }}</div>
                                <div class="db-stat-value">${{ number_format($nychaS['total']) }}</div>
                                @if($nychaS['payments'] ?? 0)
                                <div class="db-stat-sub">{{ number_format($nychaS['payments']) }} payments</div>
                                @endif
                            </div>
                            @endif
                        </div>
                        <div class="mt-3 d-flex flex-wrap" style="gap: var(--db-space-1);">
                            @if($nychaC && $nychaC['count'])
                            <a href="{{ $nychaContractsUrl }}" class="db-btn db-btn-outline db-btn-sm">View NYCHA contracts</a>
                            @endif
                            @if($nychaS && $nychaS['payments'])
                            <a href="{{ $nychaSpendingUrl }}" class="db-btn db-btn-outline db-btn-sm">View NYCHA payments</a>
                            @endif
                        </div>
                    </div></div>
                </div>
                @endif

                @include('procurement.partials.related_notices')

            </div>
        </div>

    </div>
</div>
@endsection
