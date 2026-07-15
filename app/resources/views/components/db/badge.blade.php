{{-- <x-db.badge tone="navy|neutral|success|warning|danger|info" :dot> --}}
@props(['tone' => 'neutral', 'dot' => false])
<span {{ $attributes->merge(['class' => 'db-badge db-badge-' . $tone]) }}>@if($dot)<span class="db-dot"></span> @endif{{ $slot }}</span>
