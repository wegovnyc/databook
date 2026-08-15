{{-- <x-db.renewal-row :c="$contract" :rank="$i + 1" :open="$open"> — one row of the Renewal Review Queue. --}}
@props(['c', 'rank', 'open' => false])
@php
    $daysLeft = \App\Custom\RenewalsDatasets::daysLeft($c);
    $urgent = $daysLeft <= 30;
    $agencyName = \App\Custom\RenewalsDatasets::agencyName($c['agency']);
    $panelId = 'renewal-panel-' . $c['id'];
@endphp
<div class="db-card" style="padding:0; overflow:hidden;" data-renewal-row data-renewal-id="{{ $c['id'] }}">
    <button type="button" class="db-renewal-row-btn" aria-expanded="{{ $open ? 'true' : 'false' }}" aria-controls="{{ $panelId }}">
        <span class="db-renewal-rank">{{ $rank }}</span>
        <span class="db-renewal-identity">
            <span class="db-renewal-purpose">{{ $c['purpose'] }}</span>
            <span class="db-renewal-meta">
                @if($agencyName)
                    <span data-agency-toggle data-full="{{ $agencyName }}" data-code="{{ $c['agency'] }}" role="button" tabindex="0" title="{{ $agencyName }}">{{ $c['agency'] }}</span>
                @else
                    {{ $c['agency'] }}
                @endif
                &middot; {{ $c['vendor'] }} &middot; <span class="db-renewal-id">{{ $c['id'] }}</span>
            </span>
        </span>
        <span class="db-renewal-metric">
            <span class="db-renewal-metric-label">Expires</span>
            <span class="db-renewal-metric-value{{ $urgent ? ' is-urgent' : '' }}">
                {{ \App\Custom\RenewalsDatasets::dateFmt($c['expires']) }}
                <span class="db-renewal-metric-sub{{ $urgent ? ' is-urgent' : '' }}">in {{ $daysLeft }} days</span>
            </span>
        </span>
        <span class="db-renewal-metric">
            <span class="db-renewal-metric-label">Renewal value</span>
            <span class="db-renewal-metric-value">
                {{ \App\Custom\RenewalsDatasets::compact($c['renewal']) }}
                <span class="db-renewal-metric-sub">saved if cancelled</span>
            </span>
        </span>
        <span class="db-renewal-oss">
            <span class="db-renewal-metric-label">Open source replacement</span>
            @if($c['replaceable'])
                <span class="db-renewal-oss-badges">
                    <x-db.badge tone="success" dot>{{ $c['ossCount'] }} available</x-db.badge>
                    <x-db.badge :tone="\App\Custom\RenewalsDatasets::EFFORT_TONE[$c['effort']]">{{ $c['effort'] }} effort</x-db.badge>
                </span>
            @else
                <x-db.badge tone="neutral">Partial only</x-db.badge>
            @endif
        </span>
        <span class="db-row-toggle{{ $open ? ' is-open' : '' }}" aria-hidden="true"><x-db.icon name="chevron-right" /></span>
    </button>

    <div id="{{ $panelId }}" class="db-renewal-panel" @if(!$open) hidden @endif>
        <dl class="db-detail-grid" style="margin-bottom:var(--db-space-3);">
            <div><dt>Contract ID</dt><dd style="font-family:var(--db-font-mono); font-size:var(--db-text-xs);">{{ $c['id'] }}</dd></div>
            <div><dt>Agency</dt><dd>
                @if($agencyName)
                    <span data-agency-toggle data-full="{{ $agencyName }}" data-code="{{ $c['agency'] }}" role="button" tabindex="0" title="{{ $agencyName }}">{{ $c['agency'] }}</span>
                @else
                    {{ $c['agency'] }}
                @endif
            </dd></div>
            <div><dt>Vendor</dt><dd><a href="{{ route('procurement.vendors') }}?q={{ urlencode($c['vendor']) }}">{{ $c['vendor'] }}</a></dd></div>
            <div><dt>Renewal term</dt><dd>{{ $c['term'] }}</dd></div>
            <div><dt>Value of renewal</dt><dd style="font-variant-numeric:tabular-nums;">{{ \App\Custom\RenewalsDatasets::full($c['renewal']) }}</dd></div>
            <div><dt>Spent since {{ $c['since'] }}</dt><dd style="font-variant-numeric:tabular-nums;">{{ \App\Custom\RenewalsDatasets::full($c['spend']) }}</dd></div>
            <div><dt>Procurement method</dt><dd>{{ $c['method'] }}</dd></div>
            <div><dt>Scale of use</dt><dd>{{ $c['users'] }}</dd></div>
            <div><dt>Expiration</dt><dd>{{ \App\Custom\RenewalsDatasets::dateFmt($c['expires']) }}</dd></div>
        </dl>

        <div class="db-renewal-detail-grid">
            <div>
                <x-db.eyebrow style="color:var(--db-brand); margin-bottom:var(--db-space-1);">Replacement assessment</x-db.eyebrow>
                <p style="font-size:var(--db-text-sm); color:var(--db-text); margin:0 0 var(--db-space-2); max-width:68ch; text-wrap:pretty;">{{ $c['effortNote'] }}</p>
                <ul class="db-renewal-options">
                    @foreach($c['options'] as $o)
                        <li>
                            <a href="#" style="font-weight:600; font-size:var(--db-text-sm);">{{ $o['n'] }}</a>
                            <span style="font-family:var(--db-font-mono); font-size:var(--db-text-2xs); color:var(--db-text-muted);">{{ $o['l'] }}</span>
                            <span style="font-size:var(--db-text-xs); color:var(--db-text-muted); margin-left:auto; text-align:right;">{{ $o['note'] }}</span>
                        </li>
                    @endforeach
                </ul>
            </div>
            <div>
                <x-db.eyebrow style="margin-bottom:var(--db-space-1);">Sources</x-db.eyebrow>
                <ul class="db-renewal-sources">
                    @foreach($c['sources'] as $s)
                        <li><x-db.icon name="file-earmark-text" style="color:var(--db-gray-500); margin-top:2px;" /><a href="#">{{ $s }}</a></li>
                    @endforeach
                </ul>
                <div style="display:flex; gap:var(--db-space-1); flex-wrap:wrap;">
                    @if($c['story'])
                        <x-db.button variant="primary" size="sm" href="{{ route('renewals.story', ['contract' => $c['id']]) }}">
                            <x-db.icon name="file-earmark-text" /> View story
                        </x-db.button>
                    @else
                        <x-db.button variant="outline" size="sm" disabled title="Story not published yet">
                            <x-db.icon name="file-earmark-text" /> Story in progress
                        </x-db.button>
                    @endif
                    <x-db.button variant="outline" size="sm" href="{{ route('procurement.contract', ['id' => $c['id']]) }}">
                        Open contract <x-db.icon name="arrow-right" />
                    </x-db.button>
                    <x-db.button variant="ghost" size="sm"><x-db.icon name="download" /> Data</x-db.button>
                </div>
            </div>
        </div>
    </div>
</div>
