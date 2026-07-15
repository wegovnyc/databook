{{-- <x-db.hero title="…" eyebrow="…"> optional extra content </x-db.hero> --}}
@props(['title' => null, 'eyebrow' => null])
<div {{ $attributes->merge(['class' => 'db-hero']) }}>
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                @if($eyebrow)<div class="db-eyebrow" style="color:var(--db-accent);">{{ $eyebrow }}</div>@endif
                @if($title)<h1>{{ $title }}</h1>@endif
                {{ $slot }}
            </div>
        </div>
    </div>
</div>
