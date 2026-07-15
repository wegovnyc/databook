{{-- <x-db.empty icon="inbox" title="No results">Try a different filter.</x-db.empty> --}}
@props(['icon' => 'inbox', 'title' => null])
<div {{ $attributes->merge(['class' => 'db-empty']) }}>
    <div class="db-empty-icon"><i class="bi bi-{{ $icon }}"></i></div>
    @if($title)<div class="db-empty-title">{{ $title }}</div>@endif
    <div class="db-empty-text">{{ $slot }}</div>
</div>
