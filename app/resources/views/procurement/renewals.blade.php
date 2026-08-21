@extends('layout')

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    $agencyNames = \App\Custom\RenewalsDatasets::AGENCY_NAMES;
    $windowOptions = ['' => 'Any date', '30' => 'Next 30 days', '90' => 'Next 90 days', '180' => 'Next 6 months'];
    $hasFilters = $filters['agency'] || $filters['window'] || $filters['replaceable'];
@endphp

<div class="db-hero">
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                <x-db.eyebrow style="color:var(--db-brand);">Digital Services Analysis</x-db.eyebrow>
                <h1 style="max-width:26ch; color:var(--db-text-on-navy);">The city's next $70M in software renewals</h1>
                <p class="db-hero-lead" style="max-width:64ch; color:var(--db-text-on-navy-muted);">
                    Every contract below renews on a fixed date unless an agency decides otherwise. We rank them three ways &mdash;
                    by how soon that decision lands, by how much a lapse would save, and by how ready an open-source
                    replacement is. All figures come from Checkbook NYC, the City Record and agency budget schedules.
                </p>
            </div>
        </div>
    </div>
</div>

<x-db.stat-grid style="margin-top:var(--db-space-4);">
    <x-db.stat label="Renewal value in the queue" accent :sub="$stats['contractCount'] . ' contracts under review'">{{ $stats['totalAtStake'] }}</x-db.stat>
    <x-db.stat label="Has an open-source path" sub="Replaceable with existing tools">{{ $stats['replaceableValue'] }}</x-db.stat>
    <x-db.stat label="Decisions in 90 days" sub="Renews automatically if missed">{{ $stats['soon'] }}</x-db.stat>
    <x-db.stat label="Fastest deadline" :sub="$stats['fastestSub']">{{ $stats['fastestDays'] }} days</x-db.stat>
</x-db.stat-grid>

<x-db.tabs style="margin-top:var(--db-space-4);">
    @foreach($views as $key => $v)
        <x-db.tab :href="request()->fullUrlWithQuery(['rank' => $key])" :active="$key === $rank" :aria-current="$key === $rank ? 'page' : null">{{ $v['label'] }}</x-db.tab>
    @endforeach
</x-db.tabs>
<p style="font-size:var(--db-text-sm); color:var(--db-text-muted); max-width:78ch; margin:var(--db-space-2) 0 var(--db-space-3); text-wrap:pretty;">{{ $view['blurb'] }}</p>

<form method="GET" action="{{ route('renewals') }}" class="db-filter-bar">
    <input type="hidden" name="rank" value="{{ $rank }}">
    <div class="db-field">
        <label for="r-agency">Agency</label>
        <select id="r-agency" name="agency" class="db-select" onchange="this.form.submit()">
            <option value="">All agencies</option>
            @foreach($agencies as $a)
                <option value="{{ $a }}" {{ $filters['agency'] === $a ? 'selected' : '' }}>{{ $a }} &mdash; {{ $agencyNames[$a] ?? $a }}</option>
            @endforeach
        </select>
    </div>
    <div class="db-field">
        <label for="r-window">Decision window</label>
        <select id="r-window" name="window" class="db-select" onchange="this.form.submit()">
            @foreach($windowOptions as $val => $label)
                <option value="{{ $val }}" {{ $filters['window'] === $val ? 'selected' : '' }}>{{ $label }}</option>
            @endforeach
        </select>
    </div>
    <label style="display:flex; flex-direction:row; align-items:center; gap:8px; align-self:end; padding-bottom:8px; cursor:pointer;">
        <input type="checkbox" name="replaceable" value="1" {{ $filters['replaceable'] ? 'checked' : '' }} onchange="this.form.submit()" style="width:16px; height:16px; flex:0 0 auto; margin:0;">
        <span style="font-size:var(--db-text-sm);">Only contracts with an open-source replacement</span>
    </label>
    <div style="margin-left:auto; display:flex; gap:var(--db-space-1); align-self:end;">
        <x-db.button variant="outline"><x-db.icon name="download" /> Export CSV</x-db.button>
    </div>
</form>

<div class="db-toolbar" style="border-bottom:1px solid var(--db-border);">
    <div class="db-toolbar-info"><strong>{{ count($rows) }}</strong> contracts &middot; ranked by {{ strtolower($view['label']) }}</div>
    <div class="db-toolbar-actions">
        <button type="button" class="db-chip-clear" id="renewalsCollapseAll">Collapse all</button>
    </div>
</div>

@if(count($rows))
    <div style="display:grid; gap:var(--db-space-1); margin-top:var(--db-space-2);" id="renewalsRowList">
        @foreach($rows as $i => $c)
            <x-db.renewal-row :c="$c" :rank="$i + 1" :open="$i === 0" />
        @endforeach
    </div>
@else
    <x-db.empty icon="funnel" title="No contracts match these filters">
        Try a wider decision window. <a href="{{ route('renewals', ['rank' => $rank]) }}">Reset filters</a>.
    </x-db.empty>
@endif

<div class="db-card" style="margin-top:var(--db-space-4); margin-bottom:var(--db-space-4); background:var(--db-bg-band);">
    <h3 style="margin-top:0; font-size:var(--db-text-lg);">How we rank these</h3>
    <p style="font-size:var(--db-text-sm); color:var(--db-text-muted); margin:0; max-width:88ch; text-wrap:pretty;">
        Expiration dates and renewal values are taken from registered contract records in Checkbook NYC and MOCS award
        notices. Replaceability is an analyst assessment, not an official finding: we count maintained open-source
        projects that cover the contract's core function, then rate switching effort as low, medium or high based on
        integration count, data portability and how many staff use the system daily. Where the city has no practical
        alternative we say so. Every assessment links to the records it was built from.
    </p>
</div>

<script>
(function () {
    // Agency code <-> full name toggle. stopPropagation so it never bubbles
    // to the row-toggle button it sits inside.
    function toggleAgency(el) {
        var showingFull = el.dataset.expanded === '1';
        el.textContent = showingFull ? el.dataset.code : el.dataset.full;
        el.title = showingFull ? el.dataset.full : 'Show abbreviation';
        el.dataset.expanded = showingFull ? '0' : '1';
    }
    document.querySelectorAll('[data-agency-toggle]').forEach(function (el) {
        el.addEventListener('click', function (e) { e.stopPropagation(); toggleAgency(el); });
        el.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); toggleAgency(el); }
        });
    });

    // Single-open accordion over the row list, persisted across page
    // reloads (re-ranking/filtering) via localStorage since ranking/filtering
    // are server-side navigations here.
    var STORAGE_KEY = 'renewalsOpenRow';
    var rows = Array.prototype.slice.call(document.querySelectorAll('[data-renewal-row]'));

    function setOpen(row, open) {
        var btn = row.querySelector('.db-renewal-row-btn');
        var panel = row.querySelector('.db-renewal-panel');
        var toggle = row.querySelector('.db-row-toggle');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        panel.hidden = !open;
        toggle.classList.toggle('is-open', open);
    }

    function openOnly(id) {
        rows.forEach(function (row) { setOpen(row, row.dataset.renewalId === id); });
    }

    // Restore persisted state (falls back to the server-rendered default —
    // the top-ranked row open — when nothing stored or the id isn't in this
    // filtered set).
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'none') {
        openOnly(null);
    } else if (stored && rows.some(function (r) { return r.dataset.renewalId === stored; })) {
        openOnly(stored);
    }

    rows.forEach(function (row) {
        var btn = row.querySelector('.db-renewal-row-btn');
        btn.addEventListener('click', function () {
            var isOpen = btn.getAttribute('aria-expanded') === 'true';
            if (isOpen) {
                setOpen(row, false);
                localStorage.setItem(STORAGE_KEY, 'none');
            } else {
                openOnly(row.dataset.renewalId);
                localStorage.setItem(STORAGE_KEY, row.dataset.renewalId);
            }
        });
    });

    var collapseAll = document.getElementById('renewalsCollapseAll');
    if (collapseAll) {
        collapseAll.addEventListener('click', function () {
            openOnly(null);
            localStorage.setItem(STORAGE_KEY, 'none');
        });
    }
})();
</script>
@endsection
