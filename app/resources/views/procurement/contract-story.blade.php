@extends('layout')

@section('menubar')
@include('sub.menubar')
@endsection

@section('content')
@php
    $storyDate = \Carbon\Carbon::parse($story['date'])->format('F j, Y');
@endphp

<div class="db-hero">
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                <x-db.eyebrow style="color:var(--db-brand);">{{ $story['eyebrow'] }}</x-db.eyebrow>
                <h1 style="max-width:30ch; color:var(--db-text-on-navy);">{{ $story['title'] }}</h1>
                <p class="db-hero-lead" style="max-width:66ch; color:var(--db-text-on-navy-muted);">{{ $story['dek'] }}</p>
                <p style="margin:var(--db-space-2) 0 0; font-size:var(--db-text-sm); color:var(--db-text-on-navy-muted);">
                    {{ $story['byline'] }} &middot; {{ $storyDate }} &middot; {{ $story['read_time'] }}
                </p>
            </div>
        </div>
    </div>
</div>

<div style="display:flex; align-items:center; gap:var(--db-space-2); padding:var(--db-space-2) 0; border-bottom:1px solid var(--db-border);">
    <a href="{{ route('renewals') }}" style="font-size:var(--db-text-sm); font-weight:600;">
        <x-db.icon name="arrow-left" /> Back to the renewal queue
    </a>
    <span style="margin-left:auto; font-family:var(--db-font-mono); font-size:var(--db-text-2xs); color:var(--db-text-muted);">{{ $contract['id'] }}</span>
    <x-db.badge tone="danger" dot>Expires in {{ $daysLeft }} days</x-db.badge>
</div>

<x-db.stat-grid style="margin-top:var(--db-space-3); margin-bottom:var(--db-space-5);">
    @foreach($story['stats'] as $s)
        <x-db.stat :label="$s['label']" :sub="$s['sub']" :accent="$s['accent'] ?? false">{{ $s['value'] }}</x-db.stat>
    @endforeach
</x-db.stat-grid>

<div class="db-story-body">
    <div class="db-prose" style="max-width:72ch;">
        @foreach($story['sections'] as $section)
            <section id="{{ $section['id'] }}" class="db-story-section">
                <x-db.eyebrow style="color:var(--db-brand); margin-bottom:var(--db-space-1);">{{ $section['kicker'] }}</x-db.eyebrow>
                <h2 style="margin:0 0 var(--db-space-2); font-size:var(--db-text-2xl); color:var(--db-primary);">{{ $section['title'] }}</h2>
                {!! $section['html'] !!}
            </section>
        @endforeach
    </div>

    <aside class="db-story-sidebar">
        <div class="db-card">
            <x-db.eyebrow style="margin-bottom:var(--db-space-1);">In this story</x-db.eyebrow>
            <ul style="list-style:none; padding:0; margin:0; display:grid; gap:6px; font-size:var(--db-text-sm);">
                @foreach($story['sections'] as $section)
                    <li><a href="#{{ $section['id'] }}">{{ $section['title'] }}</a></li>
                @endforeach
            </ul>
        </div>
        <div class="db-card">
            <x-db.eyebrow style="margin-bottom:var(--db-space-1);">Contract at a glance</x-db.eyebrow>
            <dl class="db-detail-grid" style="grid-template-columns:1fr;">
                <div><dt>Agency</dt><dd>{{ \App\Custom\RenewalsDatasets::agencyName($contract['agency']) ?? $contract['agency'] }}</dd></div>
                <div><dt>Vendor</dt><dd>{{ $contract['vendor'] }}</dd></div>
                <div><dt>Method</dt><dd>{{ $contract['method'] }}</dd></div>
                <div><dt>Renewal term</dt><dd>{{ $contract['term'] }}</dd></div>
                <div><dt>Renewal value</dt><dd style="font-variant-numeric:tabular-nums;">{{ \App\Custom\RenewalsDatasets::full($contract['renewal']) }}</dd></div>
                <div><dt>Expires</dt><dd>{{ \App\Custom\RenewalsDatasets::dateFmt($contract['expires']) }}</dd></div>
            </dl>
            <div style="display:grid; gap:6px; margin-top:var(--db-space-2);">
                <x-db.button variant="outline" size="sm" href="{{ route('procurement.contract', ['id' => $contract['id']]) }}">
                    Open contract record <x-db.icon name="arrow-right" />
                </x-db.button>
                <x-db.button variant="ghost" size="sm"><x-db.icon name="download" /> Download the data</x-db.button>
            </div>
        </div>
    </aside>
</div>
@endsection
