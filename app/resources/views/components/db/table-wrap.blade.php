{{-- Horizontal-scroll wrapper for wide tables. --}}
<div {{ $attributes->merge(['class' => 'db-table-wrap']) }}>{{ $slot }}</div>
