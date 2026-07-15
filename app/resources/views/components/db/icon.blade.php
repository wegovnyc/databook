{{-- <x-db.icon name="arrow-right" /> — enforces Bootstrap Icons (bi-*). --}}
@props(['name'])
<i {{ $attributes->merge(['class' => 'bi bi-' . $name]) }}></i>
