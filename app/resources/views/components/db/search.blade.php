{{-- <x-db.search name="q" placeholder="Search…" /> — attributes pass to the input. --}}
@props(['placeholder' => 'Search…'])
<div class="db-search"><i class="bi bi-search"></i><input type="search" placeholder="{{ $placeholder }}" aria-label="{{ $placeholder }}" {{ $attributes }}></div>
