{{-- <x-db.card :hoverable title="…"> … </x-db.card>
     Pass href to make the whole card a link (clickable-card pattern). --}}
@props(['hoverable' => false, 'title' => null, 'href' => null])
@php
    $classes = 'db-card'
        . ($hoverable ? ' is-hoverable' : '')
        . ($href ? ' d-block text-decoration-none' : '');
@endphp
@if($href)
<a href="{{ $href }}" {{ $attributes->merge(['class' => $classes]) }}>
    <div class="db-card-body">
        @if($title)<div class="db-card-title">{{ $title }}</div>@endif
        {{ $slot }}
    </div>
</a>
@else
<div {{ $attributes->merge(['class' => $classes]) }}>
    <div class="db-card-body">
        @if($title)<div class="db-card-title">{{ $title }}</div>@endif
        {{ $slot }}
    </div>
</div>
@endif
