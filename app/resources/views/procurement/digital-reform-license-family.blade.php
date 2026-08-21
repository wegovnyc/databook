@extends('layout')

@section('head')
{{-- Published with its parent page 2026-08-11. ⚠ A family page is only as reviewed
     as the family it describes: the curated families were reviewed, the tail was
     not. What carries that caveat today is the Analysis badge, the
     "AI-derived and unreviewed / two models agreed 92%" note, the `class_tier`
     marker on the purchase class, and the `summary_curated` marker on the
     summary. Do not remove them.
     ⚠ This comment used to name "the top 20 (88.0% of value)". That figure was
     stale where it was rendered on the index page and is stale here too --
     reviewed coverage is now COMPUTED from the class seed and served as
     `summary.reviewed`. Do not reintroduce a typed percentage, in copy or in a
     comment; the next reader believes both. --}}
<style>
    .db-page-lead { max-width: none; }
    .lic-note { background: var(--db-gray-050, #f8f9fb); border-left: 3px solid var(--db-brand, #d9730d);
                padding: var(--db-space-3); margin-bottom: var(--db-space-4); font-size: var(--db-text-sm); }
    .lic-h2 { font-size: var(--db-text-lg); margin: 0; }
    .lic-num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
    .lic-sub { font-size: var(--db-text-2xs); color: var(--db-text-muted); }
    .lic-prod { font-size: var(--db-text-2xs); color: var(--db-text-muted); display: block; }
    .lic-summary { border-left: 3px solid var(--db-navy-500, #162E51); padding: var(--db-space-3);
                   background: var(--db-gray-050, #f8f9fb); }
    .lic-tag { font-size: var(--db-text-2xs); text-transform: uppercase;
               letter-spacing: var(--db-tracking-wide); color: var(--db-text-muted); }
    .lic-chip { display: inline-block; background: var(--db-gray-100, #eef1f5); border-radius: 12px;
                padding: 2px 10px; margin: 2px 4px 2px 0; font-size: var(--db-text-2xs); }
</style>
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    // ⚠ Plain text only — these are echoed through Blade escaping.
    $sum = $fam['summary'] ?? [];
    $products = $fam['products'] ?? [];
    $agencies = $fam['agencies'] ?? [];
    $vendors  = $fam['vendors'] ?? [];
    $rows     = $fam['contracts'] ?? [];
    $years    = $fam['by_year']['years'] ?? [];
    $methods  = $fam['by_method'] ?? [];
    $notices      = $fam['notices'] ?? [];
    $noticesTotal = (int) ($fam['notices_total'] ?? 0);
    // Precomputed: a Blade directive glued to a word character is not compiled,
    // and "top N of M" must only appear when the list is actually capped.
    $noticesCapped = $noticesTotal > count($notices);
    $isGeneric = (bool) ($fam['is_generic'] ?? false);
    $curated   = (bool) ($fam['curated'] ?? false);

    $fmtM = function ($v) {
        $v = (float) $v;
        if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
        if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
        if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
        return '$' . number_format($v, 0);
    };
    $licRoute = route('research.digital-reform.licenses');
    $expLink = route('research.digital-reform.expiring')
        . '?expiring_license=1&expiring_product=' . urlencode($fam['family'] ?? '')
        . '#expiring-contracts';
    // Precomputed: a Blade directive glued to a word character is not compiled.
    $rep = $fam['replaceability'] ?? [];
    // Plain-English label, precomputed: a Blade directive glued to a word
    // character is not compiled, and these strings are echoed escaped.
    $repWords = [
        'high'   => 'Plausibly, with open-source and modern tooling',
        'medium' => 'Feasible, but real effort and integration',
        'low'    => 'Unlikely - specialised, regulated or deeply integrated',
    ];
    $repLabel = $repWords[$rep['top'] ?? ''] ?? 'Not rated';
    $repSpread = '';
    if (!empty($rep['ranked'])) {
        $parts = [];
        foreach ($rep['ranked'] as $r0) {
            $parts[] = $r0['rating'] . ' on ' . $r0['contracts'] . ' contract'
                     . ($r0['contracts'] == 1 ? '' : 's');
        }
        $repSpread = '(' . implode(', ', $parts) . ')';
    }
    $purposes = $fam['recorded_purposes'] ?? [];
    $pClass = $fam['purchase_class'] ?? '';
    $pLever = $fam['lever'] ?? '';
    $cands  = $fam['candidates'] ?? [];
    $catMeta = $fam['catalogue'] ?? [];
    // ⚠ Build-vs-buy is only a meaningful question for a software license.
    // For hosting, cloud, content or services it is the WRONG question, and
    // showing it there is how $6.80M of AWS ended up invisible on `low`.
    // ⚠ $pClass is now the class that DOMINATES this family by value, resolved at
    // product grain. When the family holds more than one kind of purchase the mix
    // is rendered below, so a minority lever is stated rather than absorbed.
    $showRating = ($pClass === '' || $pClass === 'software-licence');
    $classMix   = $fam['class_mix'] ?? [];
    $classMixed = (bool) ($fam['class_mixed'] ?? false);
    $famValue   = 0.0;
    foreach ($classMix as $cm) { $famValue += (float) ($cm['value'] ?? 0); }
    // ⚠ Whether this classification was REVIEWED. The summary below already shows
    // its provenance; the class did not, so on a published page a reader could not
    // tell a hand-held judgement from an automatic one. Precomputed here because a
    // Blade directive glued to a word character is not compiled.
    $classTier  = $fam['class_tier'] ?? '';
    $tierWords  = [
        'curated' => 'Reviewed: held in a version-controlled file and never reclassified automatically.',
        'auto'    => 'Classified by AI and not yet reviewed by a person.',
        'mixed'   => 'Partly reviewed: some products here were classified by hand, others automatically.',
    ];
    $tierLabel  = $tierWords[$classTier] ?? '';
    $tierIcon   = ['curated' => 'bi-clipboard-check', 'auto' => 'bi-stars',
                   'mixed' => 'bi-clipboard-minus'][$classTier] ?? '';
    $classWords = [
        'software-licence'      => 'Software license',
        'managed-hosting'       => 'Managed hosting',
        'cloud-infrastructure'  => 'Cloud infrastructure',
        'oss-support-tier'      => 'Paid tier of open-source software',
        'content-subscription'  => 'Content subscription',
        'professional-services' => 'Professional services',
        'support-maintenance'   => 'Support and maintenance',
    ];
    $leverWords = [
        'open-source-substitute'   => 'Ask: is there an open-source substitute?',
        'benchmark-then-self-host' => 'Ask: is the price right for the volume? Rate cards are public.',
        'price-and-rightsizing'    => 'Ask: is consumption right-sized, and is committed-use pricing in place?',
        'is-the-paid-tier-needed'  => 'Ask: does the commercial tier earn its price? The software itself is free.',
        'is-the-content-needed'    => 'Ask: is this content needed, and is there a cheaper source?',
        'scope-and-rate-review'    => 'Ask: is the scope and day rate right? This is people, not software.',
    ];
    $capability = $fam['capability'] ?? '';
    $rateCard = $fam['rate_card'] ?? null;
    // Unregistered purchasing vehicles naming this product. Never added to any
    // total here -- see the block that renders them.
    $pipeVehicles = $fam['pipeline_vehicles'] ?? [];
    // ⚠ NO LABEL MAP HERE. Served by the API from the capability vocabulary seed
    // -- this was the third partial copy of that mapping across three views, all
    // of them stale. See _capability_labels() in api/routers/licenses.py.
    $capLabel = $fam['capability_label'] ?? $capability;
    $classLabel = $classWords[$pClass] ?? '';
    $leverLabel = $leverWords[$pLever] ?? '';

    $mergedNote = count($products) > 1
        ? 'Merged from ' . count($products) . ' spellings in the source data'
        : '';
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ $licRoute }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Software Licenses</a>
        <div class="db-eyebrow">Procurement &middot; Digital Services <span class="db-analysis-badge"><i class="bi bi-stars"></i> Analysis</span></div>
        <h1>{{ $fam['family'] }}</h1>

        @if($isGeneric)
            <div class="lic-note">
                <strong><i class="bi bi-question-circle"></i> Not a product.</strong>
                These are contracts the classifier flagged as licenses but could not name a product for.
                They are grouped here so the volume is visible, not because they are related to each other.
            </div>
        @else
            <p class="db-page-lead">
                City license contracts for <strong>{{ $fam['family'] }}</strong>, across
                {{ number_format($sum['agencies'] ?? 0) }} agencies and
                {{ number_format($sum['vendors'] ?? 0) }} vendors.
            </p>
        @endif

        {{-- ---------- Product summary ---------- --}}
        @if(empty($fam['summary_text']) && !$isGeneric)
        <div class="lic-summary mb-4">
            <div class="lic-tag">What this software does</div>
            <p style="margin: 4px 0 0; color: var(--db-text-muted); font-style: italic;">
                Not described. The descriptions New York City recorded on these contracts were too
                vague to summarise honestly, so nothing is claimed here rather than something invented.
            </p>
        </div>
        @endif
        @if(!empty($fam['summary_text']))
        <div class="lic-summary mb-4">
            <div class="lic-tag">What this software does</div>
            <p style="font-size: var(--db-text-lg); margin: 4px 0 6px; line-height: 1.4;">{{ $fam['summary_text'] }}</p>
            <div class="lic-sub">
                @if($fam['summary_curated'] ?? false)
                    {{-- ⚠ Deliberately does NOT say "written by a person". Curated means
                         held fixed and reviewable, not necessarily human-authored -- and a
                         page whose point is checkable claims must not make an unverifiable
                         one about its own provenance. --}}
                    Curated: written by hand into a version-controlled file and never
                    regenerated. Still checkable against the recorded purposes below.
                @else
                    Summarised by AI <strong>from the descriptions New York City recorded on these
                    contracts</strong> &mdash; listed below &mdash; not from outside knowledge of the
                    product. Check it against them.
                @endif
            </div>
        </div>
        @endif

        {{-- ---------- What kind of purchase ---------- --}}
        @if($classLabel)
        <div class="lic-summary mb-4">
            <div class="lic-tag">What kind of purchase is this</div>
            <p style="margin: 4px 0 6px; font-size: var(--db-text-lg);"><strong>{{ $classLabel }}</strong></p>
            @if($leverLabel)
                <p style="margin: 0 0 6px;">{{ $leverLabel }}</p>
            @endif
            @if($capability)
                <div class="lic-sub" style="margin-bottom: 6px;">
                    Function:
                    <a href="{{ route('research.digital-reform.license-capability', ['cap' => $capability]) }}">{{ $capLabel }}</a>
                    &mdash; see every product the City buys to do this job.
                </div>
            @endif
            @if($rateCard)
                <div class="lic-sub" style="margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--db-border);">
                    <strong>Published list price:</strong>
                    ${{ $rateCard['list_price_usd'] }} {{ $rateCard['unit'] }}
                    (<a href="{{ $rateCard['source_url'] }}" rel="noopener nofollow">source</a>, as of {{ $rateCard['as_of'] }}).
                    <br>
                    <i class="bi bi-exclamation-triangle"></i>
                    Shown beside the spend, deliberately <strong>not divided into it</strong>: no seat
                    or site count exists in the contract data, so a per-unit figure would require
                    inventing the denominator.
                    @if(!empty($rateCard['note']))
                        <span>{{ $rateCard['note'] }}</span>
                    @endif
                </div>
            @endif
            @if(count($pipeVehicles))
                {{-- ⚠⚠ THE CASE THIS EXISTS FOR: Salesforce reads $3.1M in licences
                     on this page while a $75M CITYWIDE SALESFORCE PURCHASING
                     CONTRACT sits unregistered and invisible to the whole
                     analysis. Matched on the agreement TITLE and the title is
                     shown, so the reader can judge the link rather than trust it. --}}
                <div class="lic-sub" style="margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--db-border);">
                    <strong><i class="bi bi-hourglass"></i> Not yet registered, and not counted above:</strong>
                    @foreach($pipeVehicles as $pv)
                        <div style="margin-top: 4px;">
                            {{ $pv['contract_title'] }} &mdash;
                            <strong>{{ $fmtM($pv['value']) }}</strong> ceiling,
                            {{ $pv['vendor_name'] }}, {{ $pv['agency'] }} ({{ $pv['status'] }}).
                        </div>
                    @endforeach
                    <div style="margin-top: 4px;">
                        <i class="bi bi-exclamation-triangle"></i>
                        Matched because the agreement's title names this product. It carries no contract
                        number yet, so it was never classified and is absent from every figure on this
                        page &mdash; and a ceiling is a spending limit, not a purchase.
                        <a href="{{ $licRoute }}#pipeline">More on pipeline agreements.</a>
                    </div>
                </div>
            @endif
            @if($tierLabel)
                {{-- ⚠ Deliberately does NOT say "written by a person". Curated means
                     held fixed and reviewable, not necessarily human-authored -- the
                     same wording discipline the summary block uses, for the same
                     reason: a page whose point is checkable claims must not make an
                     unverifiable one about its own provenance. --}}
                <div class="lic-sub" style="margin-top: 6px;">
                    <i class="bi {{ $tierIcon }}"></i> {{ $tierLabel }}
                    @if($classTier !== 'curated')
                        Only the largest 20 product families &mdash; 88.0% of the value in this
                        analysis &mdash; have been reviewed by hand so far.
                    @endif
                </div>
            @endif
            @if(!empty($fam['class_why']))
                <div class="lic-sub">{{ $fam['class_why'] }}</div>
            @endif
            @if($classMixed)
                {{-- ⚠ THE POINT OF THE PRODUCT GRAIN. This family holds more than one
                     kind of purchase, so more than one lever applies. Before this
                     block existed the family's dominant class spoke for all of it,
                     and $68.9M of Microsoft support was being asked whether an
                     open-source substitute existed. --}}
                <div class="lic-sub" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--db-border);">
                    <strong><i class="bi bi-diagram-2"></i>
                    This family is not all one kind of purchase.</strong>
                    Each part carries its own question:
                    <table class="db-table" style="margin-top: 6px;">
                        <thead>
                            <tr><th>Part of this family</th><th class="lic-num">Value</th>
                                <th class="lic-num">Share</th><th>The question to ask</th></tr>
                        </thead>
                        <tbody>
                        @foreach($classMix as $cm)
                            @php
                                $cmKey   = $cm['key'] ?? '';
                                $cmLabel = $classWords[$cmKey] ?? ($cmKey === '(unclassified)' ? 'Not yet classified' : $cmKey);
                                $cmLever = $leverWords[$cm['lever'] ?? ''] ?? '';
                                $cmShare = $famValue > 0 ? round(((float) $cm['value']) / $famValue * 100, 1) : 0;
                                $cmProds = $cm['products'] ?? [];
                                // Per-part provenance: within one family a curated product
                                // override can sit beside an auto family answer, so the
                                // header's tier does not speak for every row here.
                                $cmTier = $cm['tier'] ?? '';
                                $cmTierWord = ['curated' => 'reviewed', 'auto' => 'not reviewed',
                                               'mixed' => 'partly reviewed'][$cmTier] ?? '';
                            @endphp
                            <tr>
                                <td>
                                    <strong>{{ $cmLabel }}</strong>
                                    @if($cmTierWord)
                                        <span class="lic-sub">&middot; {{ $cmTierWord }}</span>
                                    @endif
                                    @if(!empty($cmProds))
                                        <div class="lic-sub">{{ implode(', ', $cmProds) }}</div>
                                    @endif
                                </td>
                                <td class="lic-num">{{ $fmtM($cm['value'] ?? 0) }}</td>
                                <td class="lic-num">{{ $cmShare }}%</td>
                                <td class="lic-sub">{{ $cmLever }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                    <div style="margin-top: 6px;">
                        The rating below, where shown, applies to the
                        <strong>{{ $classLabel }}</strong> part only.
                    </div>
                </div>
            @endif
            @if(!$showRating)
                <div class="lic-sub" style="margin-top: 6px;">
                    <i class="bi bi-info-circle"></i>
                    No build-vs-buy rating is shown for this class, because "could the City build
                    this itself?" is the wrong question here &mdash; and answering it anyway is how
                    infrastructure spend became invisible in this analysis.
                </div>
            @endif
        </div>
        @endif

        {{-- ---------- Replaceability (software licenses only) ---------- --}}
        @if(($rep['rated'] ?? 0) && $showRating)
        <div class="lic-note mb-4">
            <div class="lic-tag">Could the City build this itself?</div>
            <p style="margin: 4px 0 6px;">
                <strong style="font-size: var(--db-text-lg);">{{ $repLabel }}</strong>
                <span class="lic-sub">{{ $repSpread }}</span>
            </p>
            @if($rep['mixed'] ?? false)
                <p class="lic-sub mb-0">
                    <i class="bi bi-exclamation-triangle"></i>
                    <strong>The classifier rated this product inconsistently across its own
                    contracts.</strong> That is a reason to distrust the rating for this product
                    specifically, not just in general &mdash; 64 of 435 families show the same
                    disagreement.
                </p>
            @endif
            <p class="lic-sub mb-0" style="margin-top: 6px;">
                <i class="bi bi-exclamation-triangle"></i> This is the least reliable judgement on the site: two models agreed on it only
                <strong>75%</strong> of the time, against 98% for "is this a tech contract".
                Read it as a prompt to look, never as a conclusion.
            </p>
        </div>
        @endif

        @if(count($products))
        <div class="mb-4">
            <div class="lic-sub" style="text-transform: uppercase; letter-spacing: var(--db-tracking-wide);">
                Bought under these names
                @if($curated)
                    <span title="Merged by the curated mapping"><i class="bi bi-link-45deg"></i> curated merge</span>
                @endif
            </div>
            @foreach($products as $p)
                <span class="lic-chip">{{ $p }}</span>
            @endforeach
            @if($mergedNote)
                <div class="lic-sub" style="margin-top: 4px;">
                    {{ $mergedNote }}. If any of these is not the same product, the grouping is wrong
                    and belongs in the curated mapping file, not here.
                </div>
            @endif
        </div>
        @endif

        {{-- ---------- Replacement candidates ---------- --}}
        @if(count($cands))
        <div class="db-table-wrap mb-5">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-arrow-left-right"></i> Possible open-source replacements</h2>
                <p class="lic-sub mb-0">
                    From European public-sector open-source catalogues.
                    <strong>Suggestions, not recommendations</strong> &mdash; nothing here has been
                    checked against this agency's requirements, integrations or support needs.
                    @if(!empty($catMeta['generated_at']))
                        Catalogue data as of {{ $catMeta['generated_at'] }}.
                    @endif
                </p>
            </div>
            <table class="db-table">
                <thead><tr><th>Candidate</th><th>Confidence</th><th>Kind</th><th class="lic-num">Gov adopters</th><th>License</th></tr></thead>
                <tbody>
                @foreach($cands as $cd)
                    @php
                        $isNone = ($cd['candidate_kind'] ?? '') === 'none-found' || empty($cd['candidate']);
                        $confBadge = ['strong' => 'db-badge-success', 'partial' => 'db-badge-warning',
                                      'adjacent' => 'db-badge-neutral'][$cd['confidence'] ?? ''] ?? 'db-badge-neutral';
                    @endphp
                    <tr>
                        <td>
                            @if($isNone)
                                <span class="lic-sub"><em>No known open-source alternative</em></span>
                            @elseif(!empty($cd['url']))
                                <a href="{{ $cd['url'] }}" rel="noopener nofollow"><strong>{{ $cd['candidate'] }}</strong></a>
                            @else
                                <strong>{{ $cd['candidate'] }}</strong>
                            @endif
                            @if(!empty($cd['why']))
                                <span class="lic-prod" style="white-space: normal;">{{ $cd['why'] }}</span>
                            @endif
                        </td>
                        <td>
                            @if(!$isNone)
                                <span class="db-badge {{ $confBadge }}">{{ $cd['confidence'] }}</span>
                            @endif
                        </td>
                        <td class="lic-sub">{{ $isNone ? 'searched, not found' : ($cd['candidate_kind'] ?? '') }}</td>
                        <td class="lic-num">{{ $cd['gov_adopters'] ?? '' }}</td>
                        {{-- ⚠ 'licence' IS A DATA KEY (the DB column on
                             license_replacement_candidate), NOT PROSE. The US-spelling
                             pass blind-renamed it and this cell silently rendered
                             empty for every candidate — `?? ''` made the breakage
                             invisible. Test-pinned now. --}}
                        <td class="lic-sub">{{ $cd['licence'] ?? '' }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>
        @endif

        @if(count($purposes))
        <div class="mb-4">
            <div class="lic-tag">What the contracts themselves say it is for</div>
            <ul class="lic-sub" style="margin: 4px 0 0; padding-left: 1.1rem; columns: 2;">
                @foreach($purposes as $p)
                    <li>{{ $p }}</li>
                @endforeach
            </ul>
        </div>
        @endif

        <div class="db-stat-grid mb-4">
            <div class="db-stat">
                <div class="db-stat-label">Contracts</div>
                <div class="db-stat-value">{{ number_format($sum['contracts'] ?? 0) }}</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Current value</div>
                <div class="db-stat-value">{{ $fmtM($sum['value'] ?? 0) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Expiring before 2030</div>
                <div class="db-stat-value">{{ number_format($sum['expiring'] ?? 0) }}</div>
                <div class="db-stat-sub">
                    @if(($sum['expiring'] ?? 0) > 0)
                        <a href="{{ $expLink }}">{{ $fmtM($sum['expiring_value'] ?? 0) }} up for renewal</a>
                    @else
                        None in the review window
                    @endif
                </div>
            </div>
            @if(!empty($sum['per_year']))
            <div class="db-stat">
                <div class="db-stat-label">Cost per year</div>
                <div class="db-stat-value">{{ $fmtM($sum['per_year']) }}</div>
                <div class="db-stat-sub">
                    Annualised over {{ $sum['per_year_basis'] }} of {{ $sum['contracts'] }}
                    contracts with a usable term
                </div>
            </div>
            @endif
            <div class="db-stat">
                <div class="db-stat-label">Agencies</div>
                <div class="db-stat-value">{{ number_format($sum['agencies'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ number_format($sum['vendors'] ?? 0) }} vendors</div>
            </div>
        </div>

        {{-- Agencies --}}
        <div class="row mb-5">
            <div class="col-lg-6">
                <div class="db-table-wrap">
                    <div class="px-3 pt-3">
                        <h2 class="lic-h2"><i class="bi bi-building"></i> Agencies buying it</h2>
                    </div>
                    <table class="db-table">
                        <thead><tr><th>Agency</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                        <tbody>
                        @foreach($agencies as $a)
                            <tr>
                                <td><a href="{{ route('agency.procurement', ['name' => $a['key']]) }}">{{ $a['key'] }}</a></td>
                                <td class="lic-num">{{ number_format($a['contracts']) }}</td>
                                <td class="lic-num">{{ $fmtM($a['value']) }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="col-lg-6">
                <div class="db-table-wrap">
                    <div class="px-3 pt-3">
                        <h2 class="lic-h2"><i class="bi bi-briefcase"></i> Vendors selling it</h2>
                        <p class="lic-sub mb-0">A reseller often appears here rather than the software maker.</p>
                    </div>
                    <table class="db-table">
                        <thead><tr><th>Vendor</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                        <tbody>
                        @foreach($vendors as $v)
                            <tr>
                                <td>
                                    @if(!empty($v['vendor_id']))
                                        <a href="{{ route('procurement.vendor', $v['vendor_id']) }}">{{ $v['key'] }}</a>
                                    @else
                                        {{ $v['key'] }}
                                        <span class="lic-sub" title="This name does not resolve to exactly one PASSPort supplier id, so it is not linked rather than linked to a guess">(no unique profile)</span>
                                    @endif
                                </td>
                                <td class="lic-num">{{ number_format($v['contracts']) }}</td>
                                <td class="lic-num">{{ $fmtM($v['value']) }}</td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        {{-- Renewal timeline --}}
        @if(count($years))
        <div class="db-table-wrap mb-5">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-calendar-event"></i> When these end</h2>
            </div>
            <table class="db-table">
                <thead><tr><th>Ends</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                <tbody>
                @foreach($years as $y)
                    <tr>
                        <td>{{ $y['year'] }}</td>
                        <td class="lic-num">{{ number_format($y['contracts']) }}</td>
                        <td class="lic-num">{{ $fmtM($y['value']) }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>
        @endif

        {{-- How they are bought --}}
        @if(count($methods))
        <div class="db-table-wrap mb-5">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-signpost-split"></i> Procurement routes</h2>
                <p class="lic-sub mb-0">Reported, not judged. Intergovernmental GSA/OGS means riding an
                    already-competed schedule; a large Sole Source is the line worth asking about.</p>
            </div>
            <table class="db-table">
                <thead><tr><th>Route</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                <tbody>
                @foreach($methods as $m)
                    <tr>
                        <td>{{ $m['key'] }}</td>
                        <td class="lic-num">{{ number_format($m['contracts']) }}</td>
                        <td class="lic-num">{{ $fmtM($m['value']) }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>
        @endif

        {{-- City Record notices naming this product --}}
        @if(count($notices))
        <div class="db-table-wrap mb-5">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-newspaper"></i> City Record notices mentioning it</h2>
                <p class="lic-sub mb-0">Notices whose text names this product.
                    <strong>A mention is not a purchase</strong> - a notice may
                    name a product in a hearing agenda, a background section or a
                    list of requirements, so treat these as leads to read rather
                    than as procurement activity. Contracts linked to a notice by
                    its PIN are shown on the contract pages themselves, which is
                    the accurate identifier-based link.
                    @if($noticesCapped)
                        Showing the {{ number_format(count($notices)) }} most
                        recent of {{ number_format($noticesTotal) }}.
                    @endif
                </p>
            </div>
            <table class="db-table">
                <thead><tr><th>Notice</th><th>Type</th><th>Agency</th><th>Date</th></tr></thead>
                <tbody>
                @foreach($notices as $n)
                    <tr>
                        <td><a href="{{ $n['url'] }}" target="_blank" rel="noopener noreferrer">{{ $n['title'] }}</a></td>
                        <td>{{ $n['type'] }}</td>
                        <td>{{ $n['agency'] }}</td>
                        <td>{{ $n['date'] }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>
        @endif

        {{-- Every contract --}}
        <div class="db-table-wrap mb-5">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-list-ul"></i> All {{ number_format(count($rows)) }} contracts</h2>
            </div>
            <table class="db-table">
                <thead>
                    <tr>
                        <th>Contract</th><th>Product</th><th>Agency</th><th>Vendor</th>
                        <th class="lic-num">Value</th><th>Term</th><th>Route</th>
                    </tr>
                </thead>
                <tbody>
                @foreach($rows as $r)
                    <tr>
                        <td>
                            <a href="{{ route('procurement.contract', $r['contract_id']) }}">{{ $r['contract_id'] }}</a>
                            @if(!empty($r['contract_title']))
                                <span class="lic-prod">{{ $r['contract_title'] }}</span>
                            @endif
                        </td>
                        <td>
                            {{ $r['product'] ?? '' }}
                            @if(!empty($r['purpose']))
                                <span class="lic-prod">{{ $r['purpose'] }}</span>
                            @endif
                        </td>
                        <td>
                            @if(!empty($r['agency']))
                                <a href="{{ route('agency.procurement', ['name' => $r['agency']]) }}">{{ $r['agency'] }}</a>
                            @endif
                        </td>
                        <td>
                            @if(!empty($r['vendor_id']))
                                <a href="{{ route('procurement.vendor', $r['vendor_id']) }}">{{ $r['vendor_name'] }}</a>
                            @else
                                {{ $r['vendor_name'] ?? '' }}
                            @endif
                        </td>
                        <td class="lic-num">{{ $fmtM($r['current_amount'] ?: $r['award_amount']) }}</td>
                        <td class="lic-sub">
                            {{ $r['start_date'] ?? '' }} to {{ $r['end_date'] ?? '' }}
                            @if($r['expiring'] ?? false)
                                <span class="db-badge db-badge-warning">expiring</span>
                            @endif
                        </td>
                        <td class="lic-sub">{{ $r['procurement_method'] ?? '' }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
        </div>

        <div class="lic-note">
            <strong><i class="bi bi-info-circle"></i> About this page</strong>
            License detection is AI-derived and unreviewed &mdash; two models agreed 92% on a sample, so
            roughly 1 contract in 12 may not belong here. The product grouping merges spellings
            automatically for case and punctuation, and by a version-controlled mapping file for genuine
            aliases. One row per contract, valued at current value where set. Vendors are linked only
            where the name resolves to exactly one PASSPort supplier record.
        </div>
    </div>
</div>
@endsection
