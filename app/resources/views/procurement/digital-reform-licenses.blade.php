@extends('layout')

@section('head')
{{-- PUBLISHED 2026-08-11, after the top-20 review was completed and accepted by
     the owner. This page was `noindex` + absent from the nav for as long as every
     judgement on it was unreviewed AI output; it is now in the Digital Services
     Analysis submenu and indexable.
     ⚠ The Analysis banner and the stated limits below are what carry the caveats
     now -- they are the reason publishing is defensible, so do not strip them.
     ⚠ THE REVIEWED SHARE IS NOW COMPUTED, NOT TYPED. It used to read "the largest
     20 product families -- 88.0% of the value" as literal text while the page's
     own concentration strip said 87.7% and the seed had grown past 20. Every
     figure on this page must come from the payload. If you are about to type a
     number here, add it to the API instead. --}}
<style>
    /* Software Licenses (Renewal/license analysis) - page glue. */
    .db-page-lead { max-width: none; }
    .lic-note { background: var(--db-gray-050, #f8f9fb); border-left: 3px solid var(--db-brand, #d9730d);
                padding: var(--db-space-3); margin-bottom: var(--db-space-4); font-size: var(--db-text-sm); }
    .lic-bar-wrap { display: flex; align-items: center; gap: 8px; min-width: 120px; }
    .lic-bar { height: 8px; border-radius: 4px; background: var(--db-navy-500, #162E51); flex: 0 0 auto; }
    .lic-bar.is-accent { background: var(--db-brand, #d9730d); }
    .lic-num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
    .lic-sub { font-size: var(--db-text-2xs); color: var(--db-text-muted); }
    .lic-prod { font-size: var(--db-text-2xs); color: var(--db-text-muted); display: block;
                max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .lic-section-head { display: flex; align-items: baseline; justify-content: space-between;
                        gap: var(--db-space-3); flex-wrap: wrap; margin-bottom: var(--db-space-2); }
    .lic-tag { font-size: var(--db-text-2xs); text-transform: uppercase; letter-spacing: var(--db-tracking-wide);
               color: var(--db-text-muted); }
    .lic-generic { color: var(--db-text-muted); font-style: italic; }
    /* One class per heading instead of ten copies of the same inline style. */
    .lic-h2 { font-size: var(--db-text-lg); margin: 0; }
    /* Jump navigation. ~10 sections over 15,000px had no way to move between
       them except scrolling. */
    .lic-jump { display: flex; flex-wrap: wrap; gap: var(--db-space-1);
                margin: var(--db-space-3) 0 var(--db-space-4); }
    .lic-chapter { border-top: 2px solid var(--db-navy-500, #162E51); padding-top: var(--db-space-2);
                   margin-top: var(--db-space-5); margin-bottom: var(--db-space-3); }
    /* The one visual anchor on an all-tables page: the class mix as a single bar. */
    .lic-mix { display: flex; width: 100%; height: 26px; border-radius: 4px; overflow: hidden;
               margin-bottom: var(--db-space-2); }
    .lic-mix-seg { height: 100%; min-width: 2px; }
    .lic-mix-key { display: flex; flex-wrap: wrap; gap: var(--db-space-3); font-size: var(--db-text-2xs); }
    .lic-mix-key span { display: inline-flex; align-items: center; gap: 5px; }
    .lic-swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
    .lic-legacy { font-size: var(--db-text-2xs); }
    /* Awarded beside paid. Two columns on desktop, stacked below 992px — the
       comparison is the point, so they must not end up one above the fold and one
       below it on a normal screen. */
    .lic-two-charts { display: grid; grid-template-columns: 1fr 1fr;
                      gap: var(--db-space-4); padding: var(--db-space-3); }
    @media (max-width: 991px) { .lic-two-charts { grid-template-columns: 1fr; } }
    /* ⚠ The component default is `overflow: hidden`, and it only becomes
       scrollable under the 768px breakpoint -- so a wide table is CLIPPED on a
       desktop, not scrolled. These run to 8 columns, so they opt into scrolling
       at every width; the page itself then never scrolls sideways. */
    .db-table-wrap { overflow-x: auto; }
    @media (max-width: 575px) {
        .lic-prod { max-width: 200px; }
        .lic-jump .db-btn { font-size: var(--db-text-2xs); }
    }
</style>
@endsection

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    // ⚠ PLAIN TEXT ONLY in these strings: they are echoed through Blade escaping,
    // so an HTML entity here would reach the reader literally. (That is exactly
    // how the Build-vs-buy filter came to read "High &mdash; easily replaceable".)
    $available = (bool) ($lic['available'] ?? false);
    $sum   = $lic['summary'] ?? [];
    $conc  = $lic['concentration'] ?? [];
    $fams  = $lic['families'] ?? [];
    $years = $lic['by_year']['years'] ?? [];
    $noEnd = $lic['by_year']['no_end_date'] ?? 0;
    $ended = $lic['by_year']['ended'] ?? ['contracts' => 0, 'value' => 0];
    $byAg  = $lic['by_agency'] ?? [];
    $byVen = $lic['by_vendor'] ?? [];
    $generic = $lic['generic'] ?? null;
    $grouped = (bool) ($lic['grouped'] ?? false);
    // ⚠ Full lengths of every list the API truncates. Rendering a capped table
    // with no denominator is how "By vendor" implied it showed all 88 vendors
    // while showing 25.
    $totals = $lic['totals'] ?? [];
    // ⚠ `fragmented` is still served for API consumers but is NO LONGER RENDERED as
    // its own table — it was a subset of $fams. The count and the per-row flags are
    // what the page shows now, so there is no second list to fall out of step.
    // ⚠ MUST come after $totals is assigned. Written above it first, where
    // $totals was still undefined, so the count silently rendered 0 — a wrong
    // number that looks like a measured one.
    $fragCount = $totals['fragmented'] ?? 0;
    $fragRule  = $lic['consolidation_rule'] ?? ['min_agencies' => 3, 'min_contracts' => 3];

    // ⚠ ACTUALS, and the only figures on this page that are not awarded value.
    // Every number in this block is served, including the coverage caveat and the
    // name of the largest contract with no payments — a "58% of value" with no
    // subject reads as a matching bug rather than as one citywide master.
    // AWARDED by year — a commitment, and the only view in which a citywide master
    // agreement appears at all (it carries no payments under its own id).
    $award      = $lic['award_by_year'] ?? [];
    $awardOK    = (bool) ($award['available'] ?? false);
    $awardYears = $award['years'] ?? [];
    $awardPart  = $award['partial'] ?? [];
    $awardDrop  = $award['dropped'] ?? ['contracts' => 0, 'value' => 0, 'before' => 0];
    // ⚠ SELECTED from the served rows, not recomputed: the biggest award year and
    // what dominates it. A $794.1M bar with no subject reads as a broad-based surge
    // rather than as one Microsoft renewal.
    $awardTop = null;
    foreach ($awardYears as $y) {
        if ($awardTop === null || (float) $y['value'] > (float) $awardTop['value']) {
            $awardTop = $y;
        }
    }

    $spend      = $lic['spend_by_year'] ?? [];
    $spendOK    = (bool) ($spend['available'] ?? false);
    // Scanned off the request path, so "not here yet" is a normal state for a few
    // seconds after an API restart — and a different state from "unavailable".
    $spendPending = !$spendOK && (bool) ($spend['pending'] ?? false);
    $spendYears = $spend['years'] ?? [];
    $spendDrop  = $spend['dropped'] ?? ['paid' => 0, 'before' => 0];
    // Master agreements vs ordinary contracts — the SHAPE of the unpaid gap, which
    // is what answers "is this a matching failure?". Served, because the counts move
    // whenever the inventory does.
    $spendKinds = [];
    foreach (($spend['coverage']['by_kind'] ?? []) as $k) {
        $spendKinds[$k['kind']] = $k;
    }
    $spendMaster = $spendKinds['master'] ?? null;
    $spendPlain  = $spendKinds['contract'] ?? null;
    // The fiscal year in progress, reported rather than drawn: a partial bar looks
    // like a collapse. Normally exactly one; a list because the payload cannot
    // promise that and silently dropping the rest is the defect _by_year had.
    $spendPart  = $spend['partial'] ?? [];
    $spendCov   = $spend['coverage'] ?? [];
    $spendBig   = $spendCov['largest_unmatched'] ?? null;
    $spendFirst = count($spendYears) ? ($spendYears[0]['label'] ?? '') : '';
    $spendLast  = count($spendYears) ? ($spendYears[count($spendYears) - 1]['label'] ?? '') : '';

    $fmtM = function ($v) {
        $v = (float) $v;
        if ($v >= 1000000000) return '$' . number_format($v / 1000000000, 2) . 'B';
        if ($v >= 1000000)    return '$' . number_format($v / 1000000, 1) . 'M';
        if ($v >= 1000)       return '$' . number_format($v / 1000, 0) . 'K';
        return '$' . number_format($v, 0);
    };
    $maxYearVal = count($years) ? max(array_map(function ($y) { return (float) $y['value']; }, $years)) : 0;
    $totalValue = (float) ($sum['total_value'] ?? 0);
    // Share of total value, as a percentage string. ⚠ Replaces a bar whose width
    // was max(2, round(100*v/max)) -- with the largest family at 47%, every other
    // row rendered at the identical 2% floor, so the column looked like a
    // measurement and carried no information.
    $pctOf = function ($v) use ($totalValue) {
        if ($totalValue <= 0) return '-';
        $p = 100 * (float) $v / $totalValue;
        return $p >= 0.1 ? number_format($p, 1) . '%' : '<0.1%';
    };
    // MM/DD/YYYY -> YYYY, for a compact term span. Blank stays blank rather than
    // becoming a wrong year.
    $yr = function ($d) {
        $d = trim((string) $d);
        return strlen($d) === 10 ? substr($d, -4) : '';
    };

    $expRoute = route('research.digital-reform.expiring');
    // Per-family URL, with a fallback to the old query-param view for any family
    // that has no slug yet (which happens only if the mapping table is absent).
    $famUrl = function ($f) {
        return !empty($f['slug'])
            ? route('research.digital-reform.license-family', ['slug' => $f['slug']])
            : route('research.digital-reform.licenses') . '?family=' . urlencode($f['key']) . '#family-detail';
    };
    $methods = $lic['by_method'] ?? [];
    $amb = $sum['ambiguity'] ?? [];
    $byClass = $lic['by_class'] ?? [];
    $byCap = $lic['by_capability'] ?? [];
    // ⚠ NO $capWords MAP HERE. Function labels are served by the API from
    // api/seed/license_capability_vocab.csv, because the two copies that used to
    // live in this file and in the capability view had both fallen behind the
    // seed -- 18 of 46 tags rendered as raw kebab-case keys on a published page.
    $catMeta = $lic['catalogue'] ?? [];
    $gaps = $catMeta['known_gaps']['no_results_observed_for'] ?? [];
    $classWords = [
        'software-licence' => 'Software license', 'managed-hosting' => 'Managed hosting',
        'cloud-infrastructure' => 'Cloud infrastructure',
        'oss-support-tier' => 'Paid tier of open-source software',
        'content-subscription' => 'Content subscription',
        'professional-services' => 'Professional services',
        'support-maintenance' => 'Support and maintenance',
        '(unclassified)' => 'Not yet classified',
    ];
    // ⚠ The KEYS above are data values from license_family_class.class and keep
    // the British spelling they were stored with. Only the labels are American.
    $classColors = [
        'software-licence' => '#162E51', 'managed-hosting' => '#2b5c8a',
        'support-maintenance' => '#d9730d', 'content-subscription' => '#4d8fbe',
        'cloud-infrastructure' => '#7ab3d4', 'oss-support-tier' => '#a3c9e0',
        'professional-services' => '#c9a227', '(unclassified)' => '#b9bfc9',
    ];
    $leverWords = [
        'open-source-substitute' => 'Is there an open-source substitute?',
        'benchmark-then-self-host' => 'Is the price right? Rate cards are public.',
        'price-and-rightsizing' => 'Right-sized? Committed-use pricing in place?',
        'is-the-paid-tier-needed' => 'Does the paid tier earn its price?',
        'is-the-content-needed' => 'Is the content needed? Cheaper source?',
        'scope-and-rate-review' => 'Scope and day rate review.',
    ];

    // ⚠ Deliberately NOT a "not competitively bid" percentage. That figure is a
    // true 100% -- no license used competitive sealed bid or proposal -- and
    // printing it as a headline would insinuate a scandal that the breakdown
    // disproves: most contracts take the small-purchase route and 149 ride an
    // already-competed federal GSA schedule. Show the route, not a verdict.
    $topMethodName = count($methods) ? $methods[0]['key'] : 'Unknown';
    $topMethodPct  = (count($methods) && ($sum['contracts'] ?? 0) > 0)
        ? round(100 * $methods[0]['contracts'] / $sum['contracts'])
        : 0;
    // ⚠ AND ITS VALUE SHARE, because the two disagree violently: the leading
    // route is 61% of contracts and about 6% of the money. The count alone
    // implied the opposite of what the routes section carefully argues.
    $topMethodValPct = (count($methods) && $totalValue > 0)
        ? round(100 * $methods[0]['value'] / $totalValue)
        : 0;
    // Precomputed so no Blade directive ends up glued to a word character
    // (a directive touching one is not compiled and the page 500s).
    $modelNote = implode(' + ', $sum['ai_models'] ?? []);
    $reviewed = $sum['reviewed'] ?? ['families' => 0, 'share' => 0];
    $endedPct = ($sum['contracts'] ?? 0) > 0
        ? round(100 * $ended['contracts'] / $sum['contracts'])
        : 0;
    $largestFamily = count($fams) ? $fams[0]['key'] : '';
    // ISO timestamp -> plain date. The raw string rendered mid-sentence as
    // "2026-08-11T21:43:23Z", which is noise where a date does the same job.
    $catDate = '';
    if (!empty($catMeta['generated_at'])) {
        $catDate = substr(trim((string) $catMeta['generated_at']), 0, 10);
    }
    $concLabels = ['top1' => 'Largest family', 'top3' => 'Top 3', 'top5' => 'Top 5',
                   'top10' => 'Top 10', 'top20' => 'Top 20'];
    // ⚠ Unregistered purchasing vehicles moved to the Overview (#247), which holds
    // the section-level figure; this page points there. The locals that fed the old
    // table are deleted rather than left assigned to nothing — an unused $pipeCount
    // reads as "the block is still here somewhere" to the next person.
    // ⚠ The FAMILY pages still render their own title-matched vehicles from
    // `pipeline_vehicles`, which is a different view and not a second total.
    // Jump navigation, in reading order.
    $jumps = [
        'spending'  => 'Awarded vs paid',
        'classes'   => 'Kind of purchase',
        'functions' => 'By function',
        'calendar'  => 'Renewal calendar',
        'families'  => 'Product families',
        'routes'    => 'How they are bought',
        'pipeline'  => 'In the pipeline',
        'agencies'  => 'Agencies & vendors',
        'method'    => 'Method & limits',
    ];
@endphp
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <a href="{{ route('research.digital-reform') }}" class="db-btn db-btn-ghost db-btn-sm mb-2"><i class="bi bi-arrow-left"></i> Digital Services</a>
        <div class="db-eyebrow">Procurement &middot; Digital Services <span class="db-analysis-badge"><i class="bi bi-stars"></i> Analysis</span></div>
        <h1>Software Licenses</h1>
        <p class="db-page-lead">
            Every City digital contract the classifier identifies as a <strong>software license or
            subscription</strong> &mdash; grouped by product family, so the same product bought by
            eight agencies on eight contracts reads as one line rather than eight.
        </p>

        {{-- ⚠ THIS BLOCK USED TO SAY "Unlisted draft ... not linked from the site
             navigation and marked noindex". Publishing the page made its own
             self-description false, and it was still rendering that sentence after
             the meta tag came out. Whatever this note says must stay true.
             ⚠ It also used to restate the whole 92%/1-in-12 passage that the
             methods note at the foot of the page already carries word for word,
             so the reader met the same caveat three times before any data. One
             sentence here, the detail there, and a link between them. --}}
        <div class="lic-note">
            <strong><i class="bi bi-clipboard-check"></i> How far this has been reviewed.</strong>
            <strong>{{ number_format($reviewed['families'] ?? 0) }} product families,
            {{ $reviewed['share'] ?? 0 }}% of the value on this page</strong>, carry a
            hand-reviewed classification held in version-controlled files where each
            decision is a reviewable change. Everything else &mdash; the long tail, and
            license detection itself &mdash; is <strong>AI-derived and unreviewed</strong>.
            Treat this as an analysis to check, not an inventory.
            <a href="#method">What this is built from, and what it cannot tell you.</a>
            @if($modelNote)
                <span class="lic-sub">Classified by {{ $modelNote }}.</span>
            @endif
        </div>

        @include('sub.analysis-banner')
        {{-- ONE scope note for the whole section — see the partial. A guard asserts
             all three pages include it, because three pages explaining themselves
             three different ways is how the section ended up with two universes. --}}
        @include('sub.digital-scope-note', ['scope' => ['mode' => 'derived', 'positive' => true]])

        @if(!$available)
            <div class="db-alert db-alert-warning mt-3">
                <i class="bi bi-exclamation-triangle"></i>
                License analysis is not available right now.
                @if(!empty($lic['reason']))
                    <span class="lic-sub">Reason: {{ $lic['reason'] }}</span>
                @endif
            </div>
        @else

        <div class="lic-jump">
            @foreach($jumps as $anchor => $label)
                <a class="db-btn db-btn-ghost db-btn-sm" href="#{{ $anchor }}">{{ $label }}</a>
            @endforeach
        </div>

        {{-- ---------- Summary ---------- --}}
        <div class="db-stat-grid mt-3 mb-4">
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-key"></i> License contracts</div>
                <div class="db-stat-value">{{ number_format($sum['contracts'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ number_format($sum['active_contracts'] ?? 0) }} not known to have ended</div>
            </div>
            <div class="db-stat is-accent">
                <div class="db-stat-label">Total current value</div>
                <div class="db-stat-value">{{ $fmtM($sum['total_value'] ?? 0) }}</div>
                {{-- ⚠ Multi-year TERM values spanning 2019-2031, not annual spend,
                     and most of it is already historical. Both facts belong on the
                     tile a reader will quote. --}}
                <div class="db-stat-sub">Multi-year term values; {{ $fmtM($sum['active_value'] ?? 0) }} on contracts still running</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-hourglass-split"></i> Expiring before 2030</div>
                <div class="db-stat-value">{{ number_format($sum['expiring'] ?? 0) }}</div>
                <div class="db-stat-sub">{{ $fmtM($sum['expiring_value'] ?? 0) }}; ends between today and 2030</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-diagram-3"></i> Product families</div>
                <div class="db-stat-value">{{ number_format($sum['families'] ?? 0) }}</div>
                <div class="db-stat-sub">Across {{ number_format($sum['vendors'] ?? 0) }} vendors</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-building"></i> Agencies</div>
                <div class="db-stat-value">{{ number_format($sum['agencies'] ?? 0) }}</div>
                <div class="db-stat-sub">Buying licenses separately</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label"><i class="bi bi-signpost-split"></i> Most common route</div>
                <div class="db-stat-value" style="font-size: var(--db-text-lg); line-height: 1.2;">{{ $topMethodPct }}% of contracts</div>
                <div class="db-stat-sub">{{ $topMethodName }} &mdash; but only {{ $topMethodValPct }}% of the value</div>
            </div>
        </div>

        {{-- ---------- Concentration ---------- --}}
        @if(!empty($conc))
        <div class="db-chart-card mb-4">
            <div class="db-chart-head"><span class="db-chart-title"><i class="bi bi-pie-chart"></i> How concentrated is license spending?</span></div>
            <div style="padding: var(--db-space-3);">
                <div class="row">
                    @foreach($concLabels as $k => $label)
                        @if(isset($conc[$k]))
                        <div class="col">
                            <div class="lic-tag">{{ $label }}</div>
                            <div style="font-size: var(--db-text-xl); font-weight: var(--db-weight-bold);">{{ $conc[$k] }}%</div>
                            {{-- ⚠ Name the largest family. "47%" with no subject made
                                 the reader cross-reference a table 8,000px away. --}}
                            @if($k === 'top1' && $largestFamily !== '')
                                <div class="lic-sub">{{ $largestFamily }}</div>
                            @endif
                        </div>
                        @endif
                    @endforeach
                </div>
                <p class="lic-sub mt-2 mb-0">Share of total license value. Read alongside the family table below
                    &mdash; a high top-1 share means one vendor relationship dominates the City's license exposure.</p>
            </div>
        </div>
        @endif

        {{-- ---------- Awarded vs paid, by year ---------- --}}
        {{-- ⚠⚠ THE ONLY ACTUALS ON THIS PAGE. Every other figure here is AWARDED
             value: a ceiling on paper, over a multi-year term, which is why one
             Microsoft renewal puts $794.1M into a single award year. This chart is
             cash the City paid out, from the Checkbook lake, by City fiscal year.
             ⚠ It is a FLOOR and the caption says so in served numbers: payments key
             on the contract id, and a citywide MASTER agreement is not what
             agencies pay against — they raise their own purchase orders under their
             own ids. Do not "fix" the gap by scaling the series up to the awarded
             total; the missing payments are real, they are just filed elsewhere. --}}
        @if($awardOK || $spendOK || $spendPending)
        <div class="db-chart-card mb-4" id="spending">
            <div class="db-chart-head">
                <span class="db-chart-title"><i class="bi bi-graph-up"></i> What was committed, and what was actually paid</span>
                <span class="lic-sub">last {{ (int) ($award['window_years'] ?? $spend['window_years'] ?? 10) }} complete years, plus the year in progress</span>
            </div>
            <div class="lic-two-charts">
                @if($awardOK)
                <div>
                    <div class="lic-tag">Awarded &mdash; contracts starting that year</div>
                    {{-- ⚠ FIXED-HEIGHT WRAPPER IS LOAD-BEARING: a
                         maintainAspectRatio:false canvas with no bounded parent grows
                         without limit (#61). --}}
                    <div class="db-chart-body" style="height: 260px;">
                        <canvas id="licAwardChart"></canvas>
                    </div>
                </div>
                @endif
                @if($spendOK)
                <div>
                    <div class="lic-tag">Paid &mdash; Checkbook payments by City fiscal year</div>
                    <div class="db-chart-body" style="height: 260px;">
                        <canvas id="licSpendChart"></canvas>
                    </div>
                </div>
                @elseif($spendPending)
                {{-- ⚠ SAY SO, do not just omit the card. The payment series is scanned
                     off the request path (a cold scan is ~16s, past the page's API
                     timeout), so for the first few seconds after an API restart there
                     is genuinely nothing to draw. A silently missing chart is
                     indistinguishable from a feature that broke. --}}
                <div>
                    <div class="lic-tag">Paid &mdash; Checkbook payments by City fiscal year</div>
                    <div class="db-chart-body db-empty" style="height: 260px; display: flex; align-items: center; justify-content: center;">
                        <span class="lic-sub">Payment data is still loading &mdash; reload in a moment.</span>
                    </div>
                </div>
                @endif
            </div>
            <div style="padding: 0 var(--db-space-3) var(--db-space-3);">
                @if($awardOK)
                <p class="lic-sub mb-1">
                    <strong>Awarded is a commitment, not cash</strong> &mdash; the value of contracts whose
                    term starts in that year, spread over terms that run for years.
                    @if($awardTop && !empty($awardTop['top_family']))
                        {{ $awardTop['label'] }} reads {{ $fmtM($awardTop['value']) }} largely because of
                        one agreement: {{ $awardTop['top_family'] }},
                        {{ $fmtM($awardTop['top_family_value']) }}.
                    @endif
                    @foreach($awardPart as $p)
                        {{ $p['label'] }} is still in progress and is not drawn:
                        {{ $fmtM($p['value']) }} over {{ number_format($p['contracts']) }} contracts so far.
                    @endforeach
                    @if(($awardDrop['contracts'] ?? 0) > 0)
                        {{ number_format($awardDrop['contracts']) }} earlier contracts
                        ({{ $fmtM($awardDrop['value']) }}) start before {{ $awardDrop['before'] }} and are
                        outside the window.
                    @endif
                </p>
                @endif
                @if($spendOK)
                <p class="lic-sub mb-1">
                    <strong>Paid is cash out the door</strong>, by City fiscal year (July&ndash;June), so
                    {{ $spendFirst }} begins in the same calendar year as the first award bar.
                    @foreach($spendPart as $p)
                        {{ $p['label'] }} is in progress and is not drawn: {{ $fmtM($p['paid']) }} so far
                        over {{ number_format($p['payments']) }} payments.
                    @endforeach
                    @if(($spendDrop['paid'] ?? 0) > 0)
                        {{ $fmtM($spendDrop['paid']) }} was paid before FY{{ $spendDrop['before'] }} and is
                        outside the window.
                    @endif
                    @if(!empty($spend['as_of']))
                        Latest payment recorded {{ $spend['as_of'] }}.
                    @endif
                </p>
                {{-- ⚠⚠ THE HONEST ANSWER TO "why is paid so much smaller?", and it is
                     NOT a matching failure: a master agreement is a VEHICLE, and
                     agencies buy against it on their own purchase orders, which carry
                     their own contract ids. Every figure here is served. --}}
                <p class="lic-sub mb-0">
                    <strong>Why the two do not reconcile.</strong>
                    @if($spendMaster && $spendPlain)
                        All {{ number_format($spendMaster['contracts']) }} master agreements on this page
                        &mdash; {{ $fmtM($spendMaster['value']) }} of awarded value &mdash; have
                        {{ ($spendMaster['paid_contracts'] ?? 0) === 0 ? 'no payments at all' : number_format($spendMaster['paid_contracts']) . ' with payments' }}
                        filed under their own contract id, while
                        {{ number_format($spendPlain['paid_contracts']) }} of
                        {{ number_format($spendPlain['contracts']) }} ordinary contracts do.
                    @else
                        {{ number_format($spendCov['contracts_paid'] ?? 0) }} of
                        {{ number_format($spendCov['contracts'] ?? 0) }} contracts have at least one payment.
                    @endif
                    @if($spendBig)
                        The largest with none is {{ $fmtM($spendBig['value']) }}
                        {{ $spendBig['title'] }} ({{ $spendBig['vendor'] }}).
                    @endif
                    That spending is real and it is in Checkbook &mdash; under the purchase orders agencies
                    raise against the agreement, not under the agreement. So <strong>treat paid as a
                    floor</strong>: for the contracts it can see, it matches Checkbook's own per-contract
                    figure.
                </p>
                @endif
            </div>
        </div>
        @endif

        <div class="lic-chapter">
            <div class="lic-tag">Part 1</div>
            <h2 class="lic-h2">What kind of spend is this?</h2>
        </div>

        {{-- ---------- What kind of purchase (the view the rating hides) ---------- --}}
        @if(count($byClass))
        <div class="db-table-wrap mb-5" id="classes">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-tags"></i> What kind of purchase is this spend?</h2>
                <p class="lic-sub mb-0">
                    The replaceability rating asks "could the City build this itself?" &mdash; the wrong
                    question for hosting and cloud, which therefore rate <strong>low</strong> and drop out
                    of every replaceability view. Classifying the purchase is what lets the right question
                    be asked of each line. Each class carries its own lever.
                </p>
            </div>
            @php
                // The one visual anchor on an otherwise all-table page: the whole
                // argument of this section as a single bar.
                $mixTotal = 0;
                foreach ($byClass as $bc) { $mixTotal += (float) $bc['value']; }
            @endphp
            @if($mixTotal > 0)
            <div class="px-3 pt-3">
                <div class="lic-mix">
                    @foreach($byClass as $bc)
                        @php
                            $segPct = 100 * (float) $bc['value'] / $mixTotal;
                            $segCol = $classColors[$bc['key']] ?? '#b9bfc9';
                            $segLab = $classWords[$bc['key']] ?? $bc['key'];
                        @endphp
                        <div class="lic-mix-seg" style="width: {{ $segPct }}%; background: {{ $segCol }};"
                             title="{{ $segLab }}: {{ number_format($segPct, 1) }}%"></div>
                    @endforeach
                </div>
                <div class="lic-mix-key">
                    @foreach($byClass as $bc)
                        @php
                            $segPct = 100 * (float) $bc['value'] / $mixTotal;
                            $segCol = $classColors[$bc['key']] ?? '#b9bfc9';
                            $segLab = $classWords[$bc['key']] ?? $bc['key'];
                        @endphp
                        <span><i class="lic-swatch" style="background: {{ $segCol }};"></i>{{ $segLab }} {{ number_format($segPct, 1) }}%</span>
                    @endforeach
                </div>
            </div>
            @endif
            <table class="db-table">
                <thead><tr><th>Class</th><th class="lic-num">Contracts</th><th class="lic-num">Families</th><th class="lic-num">Value</th><th>The question to ask</th></tr></thead>
                <tbody>
                @foreach($byClass as $bc)
                    <tr>
                        {{-- ⚠ The page's headline lens was the one table with no
                             drill-down: families and functions both clicked
                             through, classes dead-ended. --}}
                        <td><strong><a href="{{ route('research.digital-reform.licenses') }}?class={{ urlencode($bc['key']) }}#family-detail">{{ $classWords[$bc['key']] ?? $bc['key'] }}</a></strong></td>
                        <td class="lic-num">{{ number_format($bc['contracts']) }}</td>
                        <td class="lic-num">{{ number_format($bc['families']) }}</td>
                        <td class="lic-num">{{ $fmtM($bc['value']) }}</td>
                        <td class="lic-sub">{{ $leverWords[$bc['lever']] ?? '' }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
            <div class="px-3 pb-3">
                <p class="lic-sub mb-2">
                    <i class="bi bi-exclamation-triangle"></i>
                    <strong>"Managed hosting" here spans two very different things.</strong>
                    Commodity hosting with a published rate card (WP Engine, Pantheon) sits in the
                    same class as bespoke hosted platforms (Axon Evidence, ShotSpotter, Ivalua),
                    and only the first can be benchmarked against a public price. The class says
                    "someone else runs it", which is the right question to start from; it does not
                    say the price is checkable.
                </p>
                <p class="lic-sub mb-0">
                    <i class="bi bi-robot"></i>
                    <strong>Most of these classifications are AI-assigned and unreviewed.</strong>
                    {{ number_format($reviewed['families'] ?? 0) }} families are hand-classified; the
                    rest were classified in bulk. A wrong class sends a reader to the wrong question,
                    so treat a large line's class as a claim to check.
                </p>
                <p class="lic-sub mb-0" style="margin-top: var(--db-space-2);">
                    <strong>Not yet classified</strong> is the remainder of the inventory: the classification file
                    covers the significant families, and unclassified spend is deliberately shown as its
                    own row rather than folded in, so this table never overstates how much has been assessed.
                </p>
            </div>
        </div>
        @endif

        {{-- ---------- Same job, many products, many agencies ---------- --}}
        @if(count($byCap))
        <div class="db-table-wrap mb-5" id="functions">
            <div class="px-3 pt-3">
                <div class="lic-section-head">
                    <div>
                        <h2 class="lic-h2"><i class="bi bi-grid-3x3-gap"></i> Software by function, across agencies</h2>
                        <p class="lic-sub mb-0">
                            Grouping by product answers "what do we buy". Grouping by <strong>function</strong>
                            answers "how many different things do we buy to do one job, and in how many
                            agencies" &mdash; the consolidation question, which no per-product view can show.
                            Ordered by <strong>distinct products per function</strong>, because that is the
                            sharper signal: 2 products across 18 agencies is a citywide agreement, while
                            32 products across 18 agencies is not. <strong>Click a column to re-sort</strong>
                            &mdash; by value, for instance, which the default ordering deliberately buries.
                        </p>
                    </div>
                    <a class="db-btn db-btn-ghost db-btn-sm" href="{{ rtrim(config('apis.fapi_public_entry', 'https://api.databook.nyc'), '/') }}/oce/licenses/capabilities/export"><i class="bi bi-download"></i> CSV</a>
                </div>
            </div>
            <table class="db-table" id="licFunctionTable">
                <thead>
                    <tr>
                        <th>Function</th>
                        <th class="lic-num">Distinct products</th>
                        <th class="lic-num">Agencies</th>
                        <th class="lic-num">Contracts</th>
                        <th class="lic-num">Value</th>
                        <th data-orderable="false"></th>
                    </tr>
                </thead>
                <tbody>
                @foreach($byCap as $bcap)
                    <tr>
                        {{-- ⚠ `label` comes from the API, which reads it from the
                             capability vocabulary seed. The map that used to live
                             here rendered 18 of these as raw kebab-case keys. --}}
                        <td><a href="{{ route('research.digital-reform.license-capability', ['cap' => $bcap['key']]) }}">{{ $bcap['label'] ?? $bcap['key'] }}</a></td>
                        <td class="lic-num"><strong>{{ number_format($bcap['products']) }}</strong></td>
                        <td class="lic-num">{{ number_format($bcap['agencies']) }}</td>
                        <td class="lic-num">{{ number_format($bcap['contracts']) }}</td>
                        <td class="lic-num" data-order="{{ (int) $bcap['value'] }}">{{ $fmtM($bcap['value']) }}</td>
                        <td>
                            @if($bcap['fragmented'])
                                <span class="db-badge db-badge-warning">worth consolidating?</span>
                            @endif
                        </td>
                    </tr>
                @endforeach
                </tbody>
            </table>
            <div class="px-3 pb-3">
                {{-- ⚠ The badge rule is stated where the badge appears. Without the
                     value floor and the top-10 cap this flag landed on 26 of 46
                     rows, which is wallpaper rather than a signal. --}}
                <p class="lic-sub mb-2">
                    <strong>"Worth consolidating?"</strong> flags the 10 strongest cases: at least 5 distinct
                    products, bought by at least 3 agencies, totalling at least $500K. It is a prompt to
                    look, not a finding.
                </p>
                <p class="lic-sub mb-0">
                    <i class="bi bi-exclamation-triangle"></i>
                    <strong>"Function not identified" is a real bucket, not a rounding error.</strong>
                    Some contracts describe themselves too vaguely to place, and they are shown rather
                    than distributed. It is listed last and never flagged for consolidation &mdash; you
                    cannot consolidate the functions you failed to identify. Function tags are AI-assigned
                    from contract text and unreviewed; a wrong tag puts a product in the wrong comparison.
                </p>
            </div>
        </div>
        @endif

        {{-- ---------- Gaps in the open-source commons ---------- --}}
        @if(count($gaps))
        <div class="lic-note mb-5">
            <div class="lic-tag">Gaps in the open-source commons</div>
            <p style="margin: 4px 0 6px;">
                Categories where the European public-sector catalogues have <strong>nothing</strong> &mdash;
                asserted by the catalogue itself, not merely a search that came back empty:
            </p>
            <ul style="margin: 0 0 6px; padding-left: 1.2rem;">
                @foreach($gaps as $g)
                    <li>{{ $g }}</li>
                @endforeach
            </ul>
            <div class="lic-sub">
                The two largest lines rated most replaceable fall in these gaps, so the absence is a
                finding about the commons rather than a failure of the search.
                @if($catDate !== '')
                    Catalogue data as of <strong>{{ $catDate }}</strong> &mdash; its
                    JSON is regenerated weekly but redeployed by hand, so this date is the honest
                    freshness signal.
                @endif
                @if(!empty($catMeta['mapped_products']))
                    <i class="bi bi-exclamation-triangle"></i> The catalogue's replacement index maps {{ $catMeta['mapped_products'] }} proprietary
                    products out of {{ number_format($catMeta['entries'] ?? 0) }} entries, so any OTHER
                    blank means "not mapped", never "no alternative exists".
                @endif
            </div>
        </div>
        @endif

        <div class="lic-chapter">
            <div class="lic-tag">Part 2</div>
            <h2 class="lic-h2">The inventory</h2>
        </div>

        {{-- ---------- Fragmentation: the headline ---------- --}}
        {{-- ⚠⚠ "One product, many separate contracts" MERGED INTO THE FAMILY TABLE
             (2026-08-13). It was a filtered, re-sorted subset of that table — same
             rows, same numbers, ranked by agencies instead of value — so a reader
             comparing the two had to work out that they were one dataset shown twice.
             The threshold now renders as a badge on the family rows and a filter above
             them, which keeps the finding and loses the duplicate. --}}
        {{-- ---------- Renewal calendar ---------- --}}
        <div class="db-table-wrap mb-5" id="calendar">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-calendar-event"></i> Renewal calendar</h2>
                <p class="lic-sub mb-0">License contracts by the year they end. Years before 2030 link into the
                    Renewal Review Queue.
                    {{-- ⚠ The two "expiring" figures on this page count different
                         things and a reader comparing them deserves to know why. --}}
                    The <strong>Expiring</strong> links use the review-queue window (today to 2030), so they
                    count fewer contracts than the year rows they sit beside.
                </p>
            </div>
            <table class="db-table">
                <thead><tr><th>Ends</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th><th style="width: 40%;">Largest line that year</th></tr></thead>
                <tbody>
                @foreach($years as $y)
                    @php $w = $maxYearVal > 0 ? max(2, round(100 * $y['value'] / $maxYearVal)) : 0; @endphp
                    <tr>
                        <td>
                            @if($y['expiring'] > 0)
                                <a href="{{ $expRoute }}?expiring_license=1&expiring_year={{ $y['year'] }}#expiring-contracts"><strong>{{ $y['year'] }}</strong></a>
                            @else
                                <strong>{{ $y['year'] }}</strong>
                            @endif
                        </td>
                        <td class="lic-num">{{ number_format($y['contracts']) }}</td>
                        <td class="lic-num">{{ $fmtM($y['value']) }}</td>
                        <td>
                            <div class="lic-bar-wrap"><div class="lic-bar is-accent" style="width: {{ $w }}%;"></div></div>
                            {{-- ⚠ Computed, not typed: 2030 is 97% one Microsoft
                                 agreement, and without naming it the row reads as a
                                 broad-based cliff. --}}
                            @if(!empty($y['top_family']))
                                <span class="lic-sub">{{ $y['top_family'] }} &middot; {{ $fmtM($y['top_family_value']) }}</span>
                            @endif
                        </td>
                    </tr>
                @endforeach
                </tbody>
            </table>
            {{-- ⚠⚠ THE DISCLOSURE THIS TABLE EXISTED WITHOUT. Contracts that already
                 ended were dropped from the calendar in silence while still counting
                 toward every headline figure, so 262 rows sat under a tile reading
                 948 with nothing explaining the gap. --}}
            <div class="px-3 pb-3">
                <p class="lic-sub mb-0">
                    <i class="bi bi-clock-history"></i>
                    <strong>{{ number_format($ended['contracts']) }} contracts ({{ $fmtM($ended['value']) }})
                    had already ended</strong> and are not in this table &mdash; {{ $endedPct }}% of the
                    contracts on this page. This analysis is largely <strong>historical</strong>: an
                    expired term is the norm here, not a finding.
                    @if($noEnd > 0)
                        A further <strong>{{ number_format($noEnd) }}</strong> have no usable end date.
                    @endif
                </p>
            </div>
        </div>

        {{-- ---------- Families ---------- --}}
        {{-- ⚠ `id="fragmented"` is kept as a second anchor so links to the merged-away
             table still land here rather than nowhere. --}}
        <div class="db-table-wrap mb-5" id="families"><span id="fragmented"></span>
            <div class="px-3 pt-3">
                <div class="lic-section-head">
                    <div>
                        <h2 class="lic-h2"><i class="bi bi-collection"></i> Product families</h2>
                        <p class="lic-sub mb-0">
                            @if($grouped)
                                All {{ number_format(count($fams)) }} families, grouped by the curated mapping.
                                Search, and <strong>sort by any column</strong>; 25 to a page.
                            @else
                                <strong>Ungrouped</strong> &mdash; the family mapping table is missing, so each spelling is its own row.
                            @endif
                            Families marked <span class="db-badge db-badge-neutral lic-legacy">legacy</span> are
                            mainframe-era platforms the City still licenses &mdash; an editorial call, not a
                            classifier output.
                        </p>
                        {{-- ⚠ THIS REPLACED A SEPARATE TABLE. "One product, many separate
                             contracts" showed the 8 strongest of these same rows, ranked by
                             agencies instead of value — one dataset, twice, with nothing
                             saying so. The finding survives as a badge, a count and a
                             filter; the ranking survives as a column you can sort. --}}
                        @if($fragCount > 0)
                        <p class="lic-sub mb-0" style="margin-top: var(--db-space-2);">
                            <span class="db-badge db-badge-warning lic-legacy">consolidate?</span>
                            marks the <strong>{{ number_format($fragCount) }}</strong> families bought by
                            {{ $fragRule['min_agencies'] }} or more agencies on
                            {{ $fragRule['min_contracts'] }} or more separate contracts &mdash; the strongest
                            candidates for a single citywide agreement.
                            <label style="margin-left: var(--db-space-2); font-size: var(--db-text-2xs);">
                                <input type="checkbox" id="licFragOnly"> show only these
                            </label>
                            Sort by <em>Agencies</em> to rank them the way the old shortlist did.
                        </p>
                        @endif
                    </div>
                    <a class="db-btn db-btn-ghost db-btn-sm" href="{{ rtrim(config('apis.fapi_public_entry', 'https://api.databook.nyc'), '/') }}/oce/licenses/export"><i class="bi bi-download"></i> CSV</a>
                </div>
            </div>
            <table class="db-table" id="licFamilyTable">
                <thead>
                    <tr>
                        <th>Family</th>
                        <th class="lic-num">Contracts</th>
                        <th class="lic-num">Agencies</th>
                        {{-- Carried over from the merged table: how many different
                             vendors sell the same family. --}}
                        <th class="lic-num">Vendors</th>
                        <th class="lic-num">Current value</th>
                        <th class="lic-num">Share</th>
                        <th class="lic-num">Expiring</th>
                        <th class="lic-num">Non-competitive</th>
                        <th>Term span</th>
                    </tr>
                </thead>
                <tbody>
                @foreach($fams as $f)
                    <tr data-frag="{{ !empty($f['consolidation_candidate']) ? '1' : '0' }}">
                        <td>
                            <a href="{{ $famUrl($f) }}">{{ $f['key'] }}</a>
                            @if(!empty($f['consolidation_candidate']))
                                <span class="db-badge db-badge-warning lic-legacy"
                                      title="Bought by {{ $fragRule['min_agencies'] }}+ agencies on {{ $fragRule['min_contracts'] }}+ separate contracts">consolidate?</span>
                            @endif
                            @if(!empty($f['legacy']))
                                <span class="db-badge db-badge-neutral lic-legacy">legacy</span>
                            @endif
                            @if($f['curated'])
                                <span class="lic-sub" title="Spellings merged by the curated mapping"><i class="bi bi-link-45deg"></i></span>
                            @endif
                            @if(!empty($f['summary']))
                                <span class="lic-prod" style="white-space: normal; max-width: 420px;">{{ $f['summary'] }}</span>
                            @elseif(count($f['products'] ?? []) > 1)
                                <span class="lic-prod">{{ implode(' / ', array_slice($f['products'], 0, 4)) }}</span>
                            @endif
                        </td>
                        <td class="lic-num" data-order="{{ (int) $f['contracts'] }}">{{ number_format($f['contracts']) }}</td>
                        <td class="lic-num" data-order="{{ (int) $f['agencies'] }}">{{ number_format($f['agencies']) }}</td>
                        <td class="lic-num" data-order="{{ (int) ($f['vendors'] ?? 0) }}">{{ number_format($f['vendors'] ?? 0) }}</td>
                        <td class="lic-num" data-order="{{ (int) $f['value'] }}">{{ $fmtM($f['value']) }}</td>
                        <td class="lic-num" data-order="{{ (int) $f['value'] }}">{{ $pctOf($f['value']) }}</td>
                        {{-- ⚠ `data-order` is what makes these SORT. Rendering "-" for zero
                             with no sort key made DataTables treat the column as text, so
                             "9" sorted after "12" — a sortable column that sorted wrongly.
                             The expiring cell also carries the queue link the merged table
                             had; a number you cannot click is a dead end. --}}
                        <td class="lic-num" data-order="{{ (int) $f['expiring'] }}">
                            @if($f['expiring'] > 0)
                                <a href="{{ $expRoute }}?expiring_license=1&expiring_product={{ urlencode($f['key']) }}#expiring-contracts">{{ number_format($f['expiring']) }}</a>
                            @else
                                <span class="lic-sub">-</span>
                            @endif
                        </td>
                        <td class="lic-num" data-order="{{ (int) $f['non_competitive'] }}">{{ $f['non_competitive'] > 0 ? number_format($f['non_competitive']) : '-' }}</td>
                        {{-- ⚠ Replaces the separate "Long-running relationships" table,
                             which listed the same families with the same spans. --}}
                        @php $s = $yr($f['first_start'] ?? ''); $e = $yr($f['last_end'] ?? ''); @endphp
                        <td class="lic-sub" data-order="{{ $s !== '' ? $s : '9999' }}">{{ $s !== '' && $e !== '' ? $s . '-' . $e : '-' }}</td>
                    </tr>
                @endforeach
                @if($generic)
                    <tr>
                        <td class="lic-generic">
                            (unidentified product)
                            <span class="lic-prod">the classifier could not name a product for these</span>
                        </td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['contracts'] }}">{{ number_format($generic['contracts']) }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['agencies'] }}">{{ number_format($generic['agencies']) }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) ($generic['vendors'] ?? 0) }}">{{ number_format($generic['vendors'] ?? 0) }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['value'] }}">{{ $fmtM($generic['value']) }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['value'] }}">{{ $pctOf($generic['value']) }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['expiring'] }}">{{ $generic['expiring'] > 0 ? number_format($generic['expiring']) : '-' }}</td>
                        <td class="lic-num lic-generic" data-order="{{ (int) $generic['non_competitive'] }}">{{ $generic['non_competitive'] > 0 ? number_format($generic['non_competitive']) : '-' }}</td>
                        <td class="lic-sub" data-order="9999">-</td>
                    </tr>
                @endif
                </tbody>
            </table>
        </div>

        {{-- ---------- Family / agency / class drill-down ---------- --}}
        <div id="family-detail"></div>
        @if($drill && ($drill['available'] ?? false))
        @php
            $drillLabel = $family !== '' ? $family : ($agencySel !== '' ? $agencySel
                          : ($classWords[$classSel] ?? $classSel));
            $drillRows  = $drill['rows'] ?? [];
        @endphp
        <div class="db-table-wrap mb-5">
            <div class="px-3 pt-3">
                <div class="lic-section-head">
                    <div>
                        <h2 class="lic-h2"><i class="bi bi-list-ul"></i> Contracts: {{ $drillLabel }}</h2>
                        <p class="lic-sub mb-0">
                            {{ number_format($drill['total'] ?? 0) }} contracts, {{ $fmtM($drill['value'] ?? 0) }}.
                            @if($drill['truncated'] ?? false)
                                <strong>Showing the first {{ number_format(count($drillRows)) }}</strong> by value.
                            @endif
                        </p>
                    </div>
                    <a class="db-btn db-btn-ghost db-btn-sm" href="{{ route('research.digital-reform.licenses') }}"><i class="bi bi-x-lg"></i> Clear</a>
                </div>
            </div>
            <table class="db-table">
                <thead>
                    <tr>
                        <th>Contract</th><th>Product</th><th>Agency</th><th>Vendor</th>
                        <th class="lic-num">Current value</th><th>Term</th><th>Method</th>
                    </tr>
                </thead>
                <tbody>
                @foreach($drillRows as $r)
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
                        <td>{{ $r['vendor_name'] ?? '' }}</td>
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
        @endif

        <div class="lic-chapter">
            <div class="lic-tag">Part 3</div>
            <h2 class="lic-h2">Context</h2>
        </div>

        {{-- ---------- How licenses are bought ---------- --}}
        @if(count($methods))
        <div class="db-table-wrap mb-5" id="routes">
            <div class="px-3 pt-3">
                <h2 class="lic-h2"><i class="bi bi-signpost-split"></i> How these licenses are bought</h2>
                <p class="lic-sub mb-0">
                    <strong>None</strong> of these {{ number_format($sum['contracts'] ?? 0) }} contracts used competitive
                    sealed bid or proposal. That sounds worse than it is: a license usually has one seller, so
                    competition happens when the platform is chosen, not when the renewal is bought.
                    <strong>Intergovernmental GSA/OGS</strong> means buying off an already-competed federal or state
                    schedule &mdash; {{ number_format($sum['intergov_contracts'] ?? 0) }} contracts here do that
                    &mdash; and <strong>small purchase</strong> is a deliberate simplified route for low-value buys.
                    The route worth questioning is a large <strong>Sole Source</strong>.
                </p>
                {{-- ⚠ The route name reads as either a scandal or an M/WBE program to
                     anyone who has not met it. It is neither. Grounded in PPB Rule
                     3-08 (nyc.gov/site/mocs), not in recall. --}}
                <p class="lic-sub mb-0" style="margin-top: var(--db-space-2);">
                    <strong>"MWBE Non Competitive Small Purchase"</strong> is a deliberate mechanism, not a
                    loophole: Procurement Policy Board Rule 3-08 lets agencies buy directly from
                    City-certified Minority and Women-owned Business Enterprises without competition, up to a
                    dollar threshold that has risen from $500,000 in 2020 to $1.5M in December 2023. The label
                    records which rule the purchase was made under and that it went to a certified firm.
                </p>
                @if(($amb['multi_method'] ?? 0) > 0)
                <p class="lic-sub mb-0" style="margin-top: var(--db-space-2);">
                    <i class="bi bi-exclamation-triangle"></i>
                    <strong>{{ number_format($amb['multi_method']) }} of these contracts record more than one
                    procurement route</strong> across their rows in the source data (amendment history).
                    This table keeps one row per contract &mdash; the one with the highest current value &mdash;
                    so those contracts are counted under a single route. Choosing a different row moves the
                    leading share by several points, which is why the shares below are indicative rather than exact.
                </p>
                @endif
            </div>
            <table class="db-table">
                <thead><tr><th>Procurement route</th><th class="lic-num">Contracts</th><th class="lic-num">Share</th><th class="lic-num">Value</th></tr></thead>
                <tbody>
                @foreach($methods as $m)
                    @php $pct = ($sum['contracts'] ?? 0) > 0 ? round(100 * $m['contracts'] / $sum['contracts'], 1) : 0; @endphp
                    <tr>
                        <td>{{ $m['key'] }}</td>
                        <td class="lic-num">{{ number_format($m['contracts']) }}</td>
                        <td class="lic-num">{{ $pct }}%</td>
                        <td class="lic-num">{{ $fmtM($m['value']) }}</td>
                    </tr>
                @endforeach
                </tbody>
            </table>
            @if(($totals['by_method'] ?? 0) > count($methods))
            <div class="px-3 pb-3">
                <p class="lic-sub mb-0">Showing the {{ count($methods) }} most-used of
                    {{ number_format($totals['by_method']) }} routes.</p>
            </div>
            @endif
        </div>
        @endif

        {{-- ---------- Unregistered purchasing vehicles: MOVED ---------- --}}
        {{-- ⚠⚠ THE BLOCK ITSELF NOW LIVES ON THE OVERVIEW, and this is a pointer
             rather than a second copy. The reason is a measured one: scoped to
             vendors who sell licences it was 121 agreements / $1.61B, while the
             same idea scoped to the whole technology universe is 257 / $3.22B.
             Two pages publishing two figures for one question is the defect this
             section spent a week removing, so there is exactly one now — and the
             wider one, because the blind spot is section-level, not licence-level.
             The anchor is kept so old links still land somewhere sensible. --}}
        <div class="db-table-wrap mb-5" id="pipeline">
            <div class="px-3 py-3">
                <h2 class="lic-h2"><i class="bi bi-hourglass"></i> Citywide agreements still in the pipeline</h2>
                <p class="lic-sub mb-0">
                    Everything on this page counts <strong>registered</strong> contracts. NYC assigns a
                    contract number at registration, so agreements still working through approval carry
                    none and this analysis cannot see them &mdash; including citywide vehicles that are
                    the answer to the fragmentation the tables above describe.
                    <strong>They are listed on the
                    <a href="{{ route('research.digital-reform') }}#pipeline">Overview</a></strong>,
                    where they cover the whole technology universe rather than only licence vendors,
                    stated as ceilings and added to nothing.
                </p>
            </div>
        </div>

        {{-- ---------- Agencies + vendors ---------- --}}
        <div class="row mb-5" id="agencies">
            <div class="col-lg-6">
                <div class="db-table-wrap">
                    <div class="px-3 pt-3">
                        <h2 class="lic-h2"><i class="bi bi-building"></i> By agency</h2>
                        <p class="lic-sub mb-0">License value per buying agency.
                            @if(($totals['by_agency'] ?? 0) > count($byAg))
                                Showing the top {{ count($byAg) }} of {{ number_format($totals['by_agency']) }};
                                the CSV has them all.
                            @endif
                        </p>
                    </div>
                    <table class="db-table">
                        <thead><tr><th>Agency</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                        <tbody>
                        @foreach($byAg as $a)
                            <tr>
                                <td>
                                    <a href="{{ route('research.digital-reform.licenses') }}?agency={{ urlencode($a['key']) }}#family-detail">{{ $a['key'] }}</a>
                                    <span class="lic-prod"><a href="{{ route('agency.procurement', ['name' => $a['key']]) }}">agency profile</a></span>
                                </td>
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
                        <h2 class="lic-h2"><i class="bi bi-briefcase"></i> By vendor</h2>
                        {{-- ⚠ Named, but NOT by rank: "the largest line is a reseller"
                             would become false the moment the ordering changed. --}}
                        <p class="lic-sub mb-0">Who the City buys licenses from. A reseller can appear larger than the
                            software maker: Dell Marketing LP resells the Microsoft enterprise agreement,
                            so it appears here far above Microsoft's own line.
                            @if(($totals['by_vendor'] ?? 0) > count($byVen))
                                Showing the top {{ count($byVen) }} of {{ number_format($totals['by_vendor']) }};
                                the CSV has them all.
                            @endif
                        </p>
                    </div>
                    <table class="db-table">
                        <thead><tr><th>Vendor</th><th class="lic-num">Contracts</th><th class="lic-num">Value</th></tr></thead>
                        <tbody>
                        @foreach($byVen as $v)
                            <tr>
                                <td>
                                    @if(!empty($v['vendor_id']))
                                        <a href="{{ route('procurement.vendor', $v['vendor_id']) }}">{{ $v['key'] }}</a>
                                    @else
                                        {{ $v['key'] }}
                                        <span class="lic-sub" title="Name does not resolve to exactly one PASSPort supplier id, so it is left unlinked rather than linked to a guess">(no unique profile)</span>
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

        {{-- ---------- Method + limits ---------- --}}
        <div class="lic-note" id="method">
            <strong><i class="bi bi-info-circle"></i> How this is built, and what it cannot tell you</strong>
            <ul style="margin: var(--db-space-2) 0 0; padding-left: 1.2rem;">
                <li><strong>License detection is AI.</strong> Two models agreed 92% on a 40-contract sample,
                    so roughly 1 row in 12 may be wrong in either direction. No row of the detection
                    itself is human-reviewed.</li>
                <li><strong>Classification review is partial and measured.</strong>
                    {{ number_format($reviewed['families'] ?? 0) }} families
                    ({{ $reviewed['share'] ?? 0 }}% of the value here) carry a hand-reviewed purchase
                    class held in a version-controlled seed; the rest were classified in bulk by the
                    same models.</li>
                <li><strong>Product grouping is curated.</strong> Case and punctuation variants merge
                    automatically; genuine aliases (Checkpoint / Check Point, ShotSpotter / SoundThinking)
                    come from a version-controlled mapping file, so a wrong merge is a reviewable change.</li>
                <li><strong>Unit prices are not knowable here.</strong> The data carries no seat or license
                    counts, only contract totals, so this page cannot say whether one agency pays more per
                    seat than another. Differences in value reflect scope as much as price.</li>
                <li><strong>Utilization is not shown.</strong> Only about 19% of these contracts have
                    Checkbook spend metadata, too few to say what share of licenses goes unused.</li>
                <li><strong>Value</strong> is the contract's current value where set, otherwise the original
                    award, summed over multi-year terms &mdash; it is not annual spend.
                    <strong>One row per contract</strong>, chosen as the row with the highest current
                    value &mdash; the source data holds several rows per contract for amendment history, and
                    joining them all would inflate totals by roughly 6%.</li>
                {{-- ⚠ Two structural blind spots, both stated because a reader
                     otherwise reads a licence total as a platform total. --}}
                <li><strong>Only registered contracts are counted.</strong> A contract gets its number
                    at registration, and this analysis keys on that number, so agreements still in
                    approval are absent from every figure here. The largest are listed under
                    <a href="#pipeline">agreements in the pipeline</a> &mdash; separately, and as
                    ceilings rather than spend.</li>
                <li><strong>Building on a platform is not licensing it.</strong> The staff and
                    integrators who implement a product are bought as services, not licenses, so they
                    are correctly outside this analysis &mdash; but it means a platform's line here can
                    be a small fraction of what the City spends on that platform overall. Read a
                    licence figure as the licence, not the relationship.</li>
                <li><strong>Most of it has already happened.</strong>
                    {{ number_format($ended['contracts']) }} of {{ number_format($sum['contracts'] ?? 0) }}
                    contracts ({{ $endedPct }}%) had ended before this page was built, so an expired term
                    here is the base rate and not, by itself, a finding.</li>
                {{-- ⚠ A CROSS-REFERENCE, not a second copy. The full argument lives
                     in the routes section, where it is load-bearing; restating it
                     here in full was the third place this page made the same point. --}}
                <li><strong>Procurement route is reported, not judged.</strong> A single "not
                    competitively bid" figure would read 100% and insinuate what the breakdown
                    disproves. See <a href="#routes">how these licenses are bought</a>.</li>
            </ul>
        </div>

        @endif
    </div>
</div>
@endsection

@section('scripts')
{{-- ⚠ Sorting/paging only. These tables are SERVER-RENDERED, so DataTables is
     enhancing existing markup, not fetching -- and `order: []` preserves the
     order the API chose. That matters: the function table is deliberately ranked
     by distinct products with "Function not identified" pinned last, and an
     initial client sort would undo both. Money columns carry `data-order` with
     the raw number, or "$643.5M" would sort as a string. --}}
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
{{-- ⚠ The series is passed as JSON, never re-derived here: the year buckets, the
     exclusion of the fiscal year in progress and the payment counts are all
     decided by the API. A chart that recomputed any of them could disagree with
     the caption printed directly beneath it. --}}
document.addEventListener('DOMContentLoaded', function () {
    if (typeof Chart === 'undefined') { return; }
    if (window.DBChart) { DBChart.apply(Chart); }
    var money = function (v) { return window.DBChart ? DBChart.money(v) : v; };

    // ⚠ ONE bar builder for both charts. Two copies is how the licences page came to
    // hold three divergent copies of a label map, 18 tags of which rendered raw.
    var bars = function (canvasId, rows, valueOf, tip) {
        var el = document.getElementById(canvasId);
        if (!el || !rows.length) { return; }
        new Chart(el, {
            type: 'bar',
            data: {
                labels: rows.map(function (y) { return y.label; }),
                datasets: [{
                    data: rows.map(valueOf),
                    // ⚠ Navy, not the section's orange: money is navy across the whole
                    // site, and the orange here is the Analysis identity rather than a
                    // data colour.
                    backgroundColor: (window.DBChart ? DBChart.navy : '#162e51'),
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { ticks: { callback: money } } },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: function (c) { return tip(rows[c.dataIndex]); } } }
                }
            }
        });
    };

    // Awarded. The tooltip names the year's largest family, because one agreement
    // can BE the bar.
    bars('licAwardChart', @json($awardYears),
        function (y) { return y.value; },
        function (y) {
            var out = ['$' + Math.round(y.value).toLocaleString() + ' awarded',
                       y.contracts.toLocaleString() + ' contracts'];
            if (y.top_family) {
                out.push('largest: ' + y.top_family + ' ' + money(y.top_family_value));
            }
            return out;
        });

    // Paid. The payment and contract counts say how many contracts the year's total
    // is spread across, which is what stops one big renewal reading as a trend.
    bars('licSpendChart', @json($spendYears),
        function (y) { return y.paid; },
        function (y) {
            return ['$' + Math.round(y.paid).toLocaleString() + ' paid',
                    y.payments.toLocaleString() + ' payments',
                    y.contracts.toLocaleString() + ' contracts'];
        });
});
</script>
<script>
$(document).ready(function () {
    if ($.fn.DataTable) {
        if ($('#licFamilyTable').length) {
            var famTable = $('#licFamilyTable').DataTable({
                order: [],
                pageLength: 25,
                deferRender: true,
                lengthChange: false,
                dom: '<"lic-dt-top"f>rtip'
            });
            // The merged-away "One product, many separate contracts" table, as a
            // filter over the one table. ⚠ Reads the row's own data-frag attribute,
            // which the API's flag rendered — the threshold is never re-derived here,
            // so the badge, the count and this filter cannot disagree.
            $.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
                if (settings.nTable.id !== 'licFamilyTable') { return true; }
                if (!$('#licFragOnly').prop('checked')) { return true; }
                return $(famTable.row(dataIndex).node()).attr('data-frag') === '1';
            });
            $('#licFragOnly').on('change', function () {
                famTable.draw();
                // Ranking by agencies is what the old shortlist did; applying it on
                // the way in means the filter reproduces that view in one click.
                if ($(this).prop('checked')) { famTable.order([2, 'desc'], [1, 'desc']).draw(); }
            });
        }
        if ($('#licFunctionTable').length) {
            $('#licFunctionTable').DataTable({
                order: [],
                paging: false,
                searching: false,
                info: false
            });
        }
    }
});
</script>
@endsection
