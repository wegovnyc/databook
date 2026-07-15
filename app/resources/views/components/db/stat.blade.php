{{-- <x-db.stat label="Agencies" sub="FY25" :accent>167</x-db.stat>
     Value is the slot so callers keep hooks, e.g. <span id="agencies_no" class="prj_stat">. --}}
@props(['label' => null, 'sub' => null, 'accent' => false])
@php $classes = 'db-stat' . ($accent ? ' is-accent' : ''); @endphp
<div {{ $attributes->merge(['class' => $classes]) }}>
    @if($label)<div class="db-stat-label">{{ $label }}</div>@endif
    <div class="db-stat-value">{{ $slot }}</div>
    @if($sub)<div class="db-stat-sub">{{ $sub }}</div>@endif
</div>
