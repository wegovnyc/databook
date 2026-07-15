{{-- <x-db.button variant="primary|outline|ghost" size="sm|lg" href="…"> --}}
@props(['variant' => 'primary', 'size' => null, 'href' => null])
@php
    $classes = 'db-btn db-btn-' . $variant . ($size ? ' db-btn-' . $size : '');
@endphp
@if($href)
<a href="{{ $href }}" {{ $attributes->merge(['class' => $classes]) }}>{{ $slot }}</a>
@else
<button {{ $attributes->merge(['class' => $classes, 'type' => 'button']) }}>{{ $slot }}</button>
@endif
