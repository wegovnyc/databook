{{-- <x-db.tabs> <x-db.tab href active>Overview</x-db.tab> … </x-db.tabs>
     Add :scroll for horizontal overflow (flat navs only). --}}
@props(['scroll' => false])
@php $wrap = 'db-tabs-wrap' . ($scroll ? ' is-scroll' : ''); @endphp
<div class="{{ $wrap }}"><nav {{ $attributes->merge(['class' => 'db-tabs']) }}>{{ $slot }}</nav></div>
