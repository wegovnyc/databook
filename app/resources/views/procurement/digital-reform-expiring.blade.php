@extends('layout')

@section('head')
<style>
    /* Expiring Digital Service Contracts (Renewal Review Queue) - page glue. */
    .db-page-lead { max-width: none; }   /* full-width subheading */
    .dr-filter-form { margin-bottom: var(--db-space-3); }
    .dr-filter-form .db-btn { white-space: nowrap; }
    .rr-flag { display: inline-flex; align-items: center; gap: 4px; margin: 1px 2px 1px 0; }
    .rr-flags-cell { min-width: 180px; }
    .rr-exp-date { font-weight: var(--db-weight-bold); white-space: nowrap; }
    .rr-exp-days { font-size: var(--db-text-2xs); color: var(--db-text-muted); }
    .rr-method { font-size: var(--db-text-2xs); }
    .rr-grown { font-size: var(--db-text-2xs); color: var(--db-danger-fg, #b42318); white-space: nowrap; }
    .rr-toggle { line-height: 1; }
    .rr-toggle .bi { transition: transform var(--db-transition); }
    .rr-toggle[aria-expanded="true"] .bi { transform: rotate(180deg); }
    .rr-dossier-row > td { background: var(--db-gray-050, #f8f9fb); padding: 0 !important; border-top: 0; }
    .rr-dossier { padding: var(--db-space-3); }
    .rr-dossier h6 { font-size: var(--db-text-xs); text-transform: uppercase; letter-spacing: var(--db-tracking-wide); color: var(--db-text-muted); margin: 0 0 var(--db-space-1); }
    .rr-dossier-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--db-space-3); }
    @media (max-width: 768px) { .rr-dossier-grid { grid-template-columns: 1fr; } }
    .rr-meta { list-style: none; padding: 0; margin: 0; font-size: var(--db-text-sm); }
    .rr-meta li { padding: 2px 0; }
    .rr-meta .k { color: var(--db-text-muted); margin-right: 6px; }
    .rr-why { list-style: none; padding: 0; margin: 0; }
    .rr-why li { font-size: var(--db-text-sm); padding: 3px 0; display: flex; gap: 6px; }
    .rr-notice { display: block; padding: 4px 0; font-size: var(--db-text-sm); border-bottom: 1px solid var(--db-border); }
    .rr-notice:last-child { border-bottom: 0; }
    .rr-notice .meta { color: var(--db-text-muted); font-size: var(--db-text-2xs); }
</style>
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    $flagMeta = [
        'build_your_own'       => ['cls' => 'db-badge-info',     'icon' => 'bi-robot'],
        'non_competitive'      => ['cls' => 'db-badge-warning',  'icon' => 'bi-shield-exclamation'],
        'no_rebid'             => ['cls' => 'db-badge-neutral',  'icon' => 'bi-megaphone'],
        'scope_growth'         => ['cls' => 'db-badge-neutral',  'icon' => 'bi-graph-up-arrow'],
        'high_value_near_term' => ['cls' => 'db-badge-danger',   'icon' => 'bi-cash-stack'],
        'vendor_lock_in'       => ['cls' => 'db-badge-neutral',  'icon' => 'bi-link-45deg'],
        'underused'            => ['cls' => 'db-badge-danger',   'icon' => 'bi-box-seam'],
        'renewal_chain'        => ['cls' => 'db-badge-warning',  'icon' => 'bi-arrow-repeat'],
    ];
    $flagOptions = [
        'build_your_own'       => 'Build-your-own candidate',
        'underused'            => 'Underused (shelfware)',
        'non_competitive'      => 'Non-competitive award',
        'renewal_chain'        => 'Renewal chain',
        'no_rebid'             => 'No open solicitation posted',
        'scope_growth'         => 'Scope grew over award',
        'high_value_near_term' => 'High value, near-term',
        'vendor_lock_in'       => 'Vendor lock-in',
    ];
    $buildbuyOptions = ['high' => 'High &mdash; easily replaceable', 'medium' => 'Medium &mdash; feasible', 'low' => 'Low &mdash; specialized'];
    $expSummary = $expiring['summary'] ?? [];
    $expOptions = $expiring['options'] ?? ['years' => [], 'agencies' => [], 'methods' => [], 'categories' => []];
    $expFiltered = ($expiringYear || $expiringAgency || $expiringMethod || $expiringMin || $expiringFlag
                    || $expiringCategory || $expiringLicense || $expiringBuildbuy || $expiringShowNonTech);
    $expCtl = ['expiring_flag','expiring_year','expiring_agency','expiring_method','expiring_min','expiring_sort',
               'expiring_page','expiring_category','expiring_license','expiring_buildbuy','expiring_shownontech'];
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ route('research.digital-reform') }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Digital Services</a>
        <div class="db-eyebrow">Procurement &middot; Digital Services <span class="db-analysis-badge"><i class="bi bi-stars"></i> Analysis</span></div>
        <h1>Renewal Review Queue</h1>
        <p class="db-page-lead" style="max-width: none;">
            Every digital contract expiring before January 2030, with signals to help decide which ones
            <strong>shouldn't be renewed as-is</strong> &mdash; services the city could plausibly build itself with
            open-source / AI tooling, non-competitive awards, no replacement bid yet posted, runaway scope,
            shelfware, and vendor lock-in. Each flag is explained; expand a row for the full dossier and any
            linked City Record notices.
        </p>
        @include('sub.analysis-banner')

        {{-- Summary strip (reflects the current filters) --}}
        <div class="db-stat-grid mt-3 mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Expiring before 2030</div>
                <div class="db-stat-value">{{ number_format($expSummary['count'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ $expFiltered ? 'Matching filters' : 'Digital contracts' }}</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Value Up for Renewal</div>
                <div class="db-stat-value">${{ number_format(($expSummary['total_value'] ?? 0) / 1000000, 1) }}M</div>
                <div class="db-stat-sub">Total awarded</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-robot"></i> Build-your-own</div>
                <div class="db-stat-value">{{ number_format($expSummary['build_your_own'] ?? 0) }}</div>
                <div class="db-stat-sub">Possibly replaceable</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-shield-exclamation"></i> Non-competitive</div>
                <div class="db-stat-value">{{ number_format($expSummary['non_competitive'] ?? 0) }}</div>
                <div class="db-stat-sub">Not competitively bid</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-megaphone"></i> No re-bid posted</div>
                <div class="db-stat-value">{{ number_format($expSummary['no_rebid'] ?? 0) }}</div>
                <div class="db-stat-sub">No open solicitation</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-key"></i> Software licenses</div>
                <div class="db-stat-value">{{ number_format($expSummary['licenses'] ?? 0) }}</div>
                <div class="db-stat-sub">Of the above</div>
            </div>
        </div>

        @if(($expSummary['nontech_excluded'] ?? 0) > 0)
        <p class="text-muted mb-3" style="font-size: var(--db-text-sm);">
            <i class="bi bi-funnel"></i> {{ number_format($expSummary['nontech_excluded']) }} likely non-tech
            contracts (mis-tagged as digital &mdash; pest control, ship repair, etc.) are hidden.
            <a href="{{ url()->current() }}?{{ http_build_query(array_merge(request()->except(['expiring_page']), ['expiring_shownontech' => 1])) }}#expiring-contracts">Show them</a>.
        </p>
        @endif

        {{-- Charts --}}
        <div class="db-chart-card mb-4">
            <div class="db-chart-head"><span class="db-chart-title">Expiring Contract Value</span></div>
            <div class="row">
                <div class="col-md-7">
                    <h6 class="text-center mb-3">By Expiration Year</h6>
                    <div class="db-chart-body" style="height: 280px;"><canvas id="expiringTrendChart"></canvas></div>
                </div>
                <div class="col-md-5">
                    <h6 class="text-center mb-3">By Agency</h6>
                    <div class="db-chart-body" style="height: 280px;"><canvas id="expiringAgencyChart"></canvas></div>
                </div>
            </div>
        </div>

        <div class="db-table-wrap mb-5" id="expiring-contracts">
            {{-- Triage filters --}}
            <div class="px-3 pt-3">
                <form method="GET" action="{{ url()->current() }}#expiring-contracts" class="db-filter-bar dr-filter-form">
                    @foreach(request()->except($expCtl) as $k => $v)
                        <input type="hidden" name="{{ $k }}" value="{{ $v }}">
                    @endforeach
                    <div class="db-field">
                        <label for="expiring_flag">Review flag</label>
                        <select name="expiring_flag" id="expiring_flag">
                            <option value="">All contracts</option>
                            @foreach($flagOptions as $fk => $fl)
                                <option value="{{ $fk }}" {{ $expiringFlag === $fk ? 'selected' : '' }}>{{ $fl }}</option>
                            @endforeach
                        </select>
                    </div>
                    <div class="db-field">
                        <label for="expiring_category">Category</label>
                        <select name="expiring_category" id="expiring_category">
                            <option value="">All categories</option>
                            @foreach(($expOptions['categories'] ?? []) as $cat)
                                <option value="{{ $cat }}" {{ $expiringCategory === $cat ? 'selected' : '' }}>{{ $cat }}</option>
                            @endforeach
                        </select>
                    </div>
                    <div class="db-field">
                        <label for="expiring_buildbuy">Build-vs-buy</label>
                        <select name="expiring_buildbuy" id="expiring_buildbuy">
                            <option value="">Any</option>
                            @foreach($buildbuyOptions as $bk => $bl)
                                <option value="{{ $bk }}" {{ $expiringBuildbuy === $bk ? 'selected' : '' }}>{{ $bl }}</option>
                            @endforeach
                        </select>
                    </div>
                    <div class="db-field">
                        <label for="expiring_year">Expires in</label>
                        <select name="expiring_year" id="expiring_year">
                            <option value="">Any year</option>
                            @foreach(($expOptions['years'] ?? []) as $y)
                                <option value="{{ $y }}" {{ $expiringYear === $y ? 'selected' : '' }}>{{ $y }}</option>
                            @endforeach
                        </select>
                    </div>
                    <div class="db-field">
                        <label for="expiring_agency">Agency</label>
                        <select name="expiring_agency" id="expiring_agency">
                            <option value="">All agencies</option>
                            @foreach(($expOptions['agencies'] ?? []) as $a)
                                <option value="{{ $a }}" {{ $expiringAgency === $a ? 'selected' : '' }}>{{ $a }}</option>
                            @endforeach
                        </select>
                    </div>
                    <div class="db-field">
                        <label for="expiring_method">Method</label>
                        <select name="expiring_method" id="expiring_method">
                            <option value="">All methods</option>
                            @foreach(($expOptions['methods'] ?? []) as $m)
                                <option value="{{ $m }}" {{ $expiringMethod === $m ? 'selected' : '' }}>{{ $m }}</option>
                            @endforeach
                        </select>
                    </div>
                    <div class="db-field">
                        <label for="expiring_min">Min amount ($)</label>
                        <input type="number" name="expiring_min" id="expiring_min" min="0" step="100000" value="{{ $expiringMin ? (int)$expiringMin : '' }}" placeholder="0">
                    </div>
                    <div class="db-field">
                        <label for="expiring_sort">Sort by</label>
                        <select name="expiring_sort" id="expiring_sort">
                            <option value="date" {{ $expiringSort === 'date' ? 'selected' : '' }}>Soonest expiry</option>
                            <option value="amount" {{ $expiringSort === 'amount' ? 'selected' : '' }}>Largest amount</option>
                            <option value="priority" {{ $expiringSort === 'priority' ? 'selected' : '' }}>Review priority</option>
                        </select>
                    </div>
                    <div class="db-field">
                        <label>&nbsp;</label>
                        <label class="d-inline-flex align-items-center gap-1" style="font-size: var(--db-text-sm); text-transform: none; letter-spacing: normal;">
                            <input type="checkbox" name="expiring_license" value="1" {{ $expiringLicense ? 'checked' : '' }}> Licenses only
                        </label>
                    </div>
                    <div class="db-field">
                        <label>&nbsp;</label>
                        <label class="d-inline-flex align-items-center gap-1" style="font-size: var(--db-text-sm); text-transform: none; letter-spacing: normal;">
                            <input type="checkbox" name="expiring_shownontech" value="1" {{ $expiringShowNonTech ? 'checked' : '' }}> Include non-tech
                        </label>
                    </div>
                    <button type="submit" class="db-btn db-btn-primary db-btn-sm"><i class="bi bi-funnel"></i> Apply</button>
                    @if($expFiltered || $expiringSort !== 'date')
                        <a href="{{ url()->current() }}?{{ http_build_query(request()->except($expCtl)) }}#expiring-contracts" class="db-btn db-btn-ghost db-btn-sm">Reset</a>
                    @endif
                </form>
            </div>

            <div class="table-responsive">
                <table class="db-table db-table-striped">
                    <thead>
                        <tr>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['expiring_sort' => 'date', 'expiring_order' => ($expiringSort == 'date' && $expiringOrder == 'asc') ? 'desc' : 'asc']) }}#expiring-contracts" class="text-dark text-decoration-none">
                                    Expires @if($expiringSort == 'date'){!! $expiringOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>Vendor</th>
                            <th>Agency</th>
                            <th>
                                <a href="{{ request()->fullUrlWithQuery(['expiring_sort' => 'amount', 'expiring_order' => ($expiringSort == 'amount' && $expiringOrder == 'asc') ? 'desc' : 'asc']) }}#expiring-contracts" class="text-dark text-decoration-none">
                                    Amount @if($expiringSort == 'amount'){!! $expiringOrder == 'asc' ? '&uarr;' : '&darr;' !!}@endif
                                </a>
                            </th>
                            <th>Method</th>
                            <th class="rr-flags-cell">Review flags</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse(($expiring['contracts'] ?? []) as $i => $c)
                        @php $d = $c['days_to_expiry'] ?? null; @endphp
                        <tr>
                            <td>
                                <span class="rr-exp-date">{{ $c['end_date'] }}</span>
                                @if($d !== null && $d <= 180)
                                    <div><span class="db-badge db-badge-danger">&le; 6 months</span></div>
                                @elseif($d !== null && $d <= 365)
                                    <div><span class="db-badge db-badge-warning">&le; 1 year</span></div>
                                @endif
                                @if($d !== null)<div class="rr-exp-days">in {{ number_format($d) }} days</div>@endif
                            </td>
                            <td>
                                @if($c['vendor_id'] ?? null)
                                    <a href="/procurement/vendor/{{ $c['vendor_id'] }}">{{ $c['vendor_name'] }}</a>
                                @else
                                    <a href="/procurement/vendors?q={{ urlencode($c['vendor_name']) }}">{{ $c['vendor_name'] }}</a>
                                @endif
                                @if(($c['function_category'] ?? '') || ($c['is_license'] ?? false))
                                <div class="mt-1">
                                    @if($c['function_category'] ?? '')<span class="db-badge db-badge-neutral rr-method">{{ $c['function_category'] }}</span>@endif
                                    @if($c['is_license'] ?? false)<span class="db-badge db-badge-info rr-method"><i class="bi bi-key"></i> License</span>@endif
                                </div>
                                @endif
                            </td>
                            <td class="small">{{ $c['agency'] }}</td>
                            <td>
                                ${{ number_format($c['award_amount'] ?? 0, 0) }}
                                @if(($c['current_amount'] ?? 0) > ($c['award_amount'] ?? 0) * 1.05)
                                    <div class="rr-grown">now ${{ number_format($c['current_amount'], 0) }}</div>
                                @endif
                            </td>
                            <td><span class="db-badge db-badge-neutral rr-method">@if($c['procurement_method'] ?? ''){{ $c['procurement_method'] }}@else&mdash;@endif</span></td>
                            <td class="rr-flags-cell">
                                @forelse(($c['flags'] ?? []) as $f)
                                    @php $fm = $flagMeta[$f['key']] ?? ['cls' => 'db-badge-neutral', 'icon' => 'bi-flag']; @endphp
                                    <span class="db-badge {{ $fm['cls'] }} rr-flag" title="{{ $f['reason'] }}"><i class="bi {{ $fm['icon'] }}"></i> {{ $f['label'] }}</span>
                                @empty
                                    <span class="text-muted small">&mdash;</span>
                                @endforelse
                            </td>
                            <td class="text-end">
                                <button class="db-btn db-btn-ghost db-btn-sm rr-toggle" type="button" data-bs-toggle="collapse" data-bs-target="#rr-{{ $i }}" aria-expanded="false" aria-controls="rr-{{ $i }}" aria-label="Toggle details">
                                    <i class="bi bi-chevron-down"></i>
                                </button>
                            </td>
                        </tr>
                        <tr class="rr-dossier-row">
                            <td colspan="7">
                                <div class="collapse" id="rr-{{ $i }}">
                                    <div class="rr-dossier">
                                        @if($c['contract_title'] ?? '')
                                            <p class="mb-3"><strong>{{ $c['contract_title'] }}</strong></p>
                                        @endif
                                        <div class="rr-dossier-grid">
                                            <div>
                                                <h6>Why it's in the review queue</h6>
                                                <ul class="rr-why">
                                                    @forelse(($c['flags'] ?? []) as $f)
                                                        @php $fm = $flagMeta[$f['key']] ?? ['cls' => 'db-badge-neutral', 'icon' => 'bi-flag']; @endphp
                                                        <li><span class="db-badge {{ $fm['cls'] }}"><i class="bi {{ $fm['icon'] }}"></i> {{ $f['label'] }}</span> <span class="text-muted">{{ $f['reason'] }}</span></li>
                                                    @empty
                                                        <li class="text-muted">No review flags &mdash; appears in the queue only because it expires before 2030.</li>
                                                    @endforelse
                                                </ul>

                                                <h6 class="mt-3">Contract details</h6>
                                                <ul class="rr-meta">
                                                    <li><span class="k">Contract ID</span><a href="/procurement/contract/{{ $c['ctr_id'] ?? $c['contract_id'] }}">{{ $c['contract_id'] }}</a></li>
                                                    @if($c['epin'] ?? '')<li><span class="k">PIN / EPIN</span><span class="db-mono">{{ $c['epin'] }}</span></li>@endif
                                                    <li><span class="k">Term</span>{{ $c['start_date'] }} &rarr; {{ $c['end_date'] }}</li>
                                                    <li><span class="k">Award</span>${{ number_format($c['award_amount'] ?? 0, 0) }}@if(($c['current_amount'] ?? 0) > 0) &middot; <span class="k">Current</span>${{ number_format($c['current_amount'], 0) }}@endif</li>
                                                    @if(($c['spent'] ?? null) !== null)
                                                    <li><span class="k">Checkbook spend</span>${{ number_format($c['spent'], 0) }}@if(($c['utilization'] ?? null) !== null) <span class="text-muted">({{ number_format($c['utilization'] * 100, 0) }}% of award, recent FYs)</span>@endif</li>
                                                    @endif
                                                    @if($c['program'] ?? '')<li><span class="k">Program</span>{{ $c['program'] }}</li>@endif
                                                    @if($c['industry'] ?? '')<li><span class="k">Industry</span>{{ $c['industry'] }}</li>@endif
                                                    <li><span class="k">Procurement</span>@if($c['procurement_method'] ?? ''){{ $c['procurement_method'] }}@else&mdash;@endif</li>
                                                    @if($c['function_category'] ?? '')<li><span class="k">Category</span>{{ $c['function_category'] }}</li>@endif
                                                    @if($c['is_license'] ?? false)<li><span class="k">License</span>{{ $c['license_product'] ?: 'Software license' }}@if($c['license_purpose'] ?? '') &mdash; {{ $c['license_purpose'] }}@endif</li>@endif
                                                </ul>

                                                @if($c['build_vs_buy'] ?? '')
                                                <h6 class="mt-3">Build-vs-buy assessment <span class="text-muted" style="text-transform:none;font-weight:normal;">(AI &mdash; verify)</span></h6>
                                                <p style="font-size: var(--db-text-sm); margin:0;">
                                                    <span class="db-badge {{ $c['build_vs_buy'] === 'high' ? 'db-badge-info' : ($c['build_vs_buy'] === 'medium' ? 'db-badge-warning' : 'db-badge-neutral') }}">{{ ucfirst($c['build_vs_buy']) }} replaceability</span>
                                                    @if($c['ai_rationale'] ?? '') <span class="text-muted">{{ $c['ai_rationale'] }}</span>@endif
                                                </p>
                                                @endif
                                            </div>
                                            <div>
                                                <h6>City Record notices for this PIN</h6>
                                                @if(!empty($c['notices']))
                                                    @foreach($c['notices'] as $n)
                                                        <a class="rr-notice" href="{{ $n['url'] }}" target="_blank" rel="noopener">
                                                            {{ $n['title'] }}
                                                            <span class="meta">{{ $n['type'] }}@if($n['date']) &middot; {{ $n['date'] }}@endif</span>
                                                        </a>
                                                    @endforeach
                                                @else
                                                    <p class="text-muted small mb-0"><i class="bi bi-megaphone"></i> No City Record notice found for this PIN. (The &ldquo;No open solicitation&rdquo; flag tracks whether a replacement competition &mdash; a Solicitation or Intent-to-Award &mdash; has been posted; an original Award notice alone does not clear it.)</p>
                                                @endif
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="7" class="text-center text-muted py-4">No expiring contracts match your filters.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
            @if(($expiring['total_pages'] ?? 0) > 1)
            <div class="db-table-footer">
                <nav aria-label="Expiring pagination">
                    <ul class="pagination pagination-sm justify-content-center mb-0">
                        <li class="page-item {{ $expiringPage == 1 ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['expiring_page' => $expiringPage - 1]) }}#expiring-contracts">Previous</a>
                        </li>
                        <li class="page-item disabled"><span class="page-link">Page {{ $expiringPage }} of {{ $expiring['total_pages'] }}</span></li>
                        <li class="page-item {{ $expiringPage >= ($expiring['total_pages'] ?? 1) ? 'disabled' : '' }}">
                            <a class="page-link" href="{{ request()->fullUrlWithQuery(['expiring_page' => $expiringPage + 1]) }}#expiring-contracts">Next</a>
                        </li>
                    </ul>
                </nav>
            </div>
            @endif
        </div>

        <div class="db-alert db-alert-info" role="alert">
            <i class="bi bi-info-circle"></i>
            <div class="db-alert-body">
                <strong>Methodology</strong>
                <p class="mb-0">
                    Review flags are transparent signals, not determinations. Build-vs-buy, license detection
                    and function categories come from an AI pass (Gemini) over each contract's title and program;
                    &ldquo;no open solicitation&rdquo; is a live City Record join on the contract PIN; utilization is actual
                    Checkbook spend over recent fiscal years. Verify before acting.
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

    if (chartData.expiring && document.getElementById('expiringTrendChart')) {
        new Chart(document.getElementById('expiringTrendChart'), {
            type: 'bar',
            data: { labels: chartData.expiring.labels || [], datasets: [{ label: 'Total Value ($)', data: chartData.expiring.values || [], backgroundColor: DBChart.accent, borderRadius: 4 }] },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { ticks: { callback: (val) => '$' + (val / 1000000).toFixed(0) + 'M' } } }, plugins: { legend: { display: false } } }
        });
    }
    if (chartData.expiring_agencies && document.getElementById('expiringAgencyChart')) {
        new Chart(document.getElementById('expiringAgencyChart'), {
            type: 'doughnut',
            data: { labels: chartData.expiring_agencies.labels || [], datasets: [{ data: chartData.expiring_agencies.values || [], backgroundColor: DBChart.palette, borderWidth: 1 }] },
            options: { responsive: true, maintainAspectRatio: false, cutout: '60%',
                plugins: { legend: { position: 'right', labels: { boxWidth: 12, padding: 8, font: { size: 10 } } },
                    tooltip: { callbacks: { label: (c) => c.label + ': ' + currencyFmt(c.parsed) } } } }
        });
    }
});
</script>
@endsection
