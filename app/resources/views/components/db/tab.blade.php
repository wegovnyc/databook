{{-- <x-db.tab href="…" :active>Label</x-db.tab> --}}
@props(['href' => '#', 'active' => false])
@php $classes = 'db-tab' . ($active ? ' is-active' : ''); @endphp
<a href="{{ $href }}" {{ $attributes->merge(['class' => $classes]) }}>{{ $slot }}</a>
