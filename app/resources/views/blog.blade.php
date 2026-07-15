@extends('layout')

@section('head')
    <meta name="description" content="Blog posts and updates from WeGovNYC Databook." />
    <meta rel="canonical" href="{!! route('blog') !!}" />
@endsection

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@php
    // Normalize a free-text category into one of the filter buckets.
    $catKey = function ($cat) {
        $c = strtolower(trim($cat ?? ''));
        if (str_contains($c, 'data')) return 'data';
        if (str_contains($c, 'product')) return 'product';
        if (str_contains($c, 'civic')) return 'civic';
        return 'other';
    };
    $catBadge = function ($cat) use ($catKey) {
        return ['data' => 'db-badge-info', 'product' => 'db-badge-navy', 'civic' => 'db-badge-success'][$catKey($cat)] ?? 'db-badge-neutral';
    };
@endphp

@section('content')

{{-- Navy hero band --}}
<div class="db-hero">
    <div class="inner_container">
        <div class="container db-hero-inner">
            <div class="db-hero-copy">
                <div class="db-eyebrow" style="color:var(--db-accent);">Blog</div>
                <h1>News &amp; updates from WeGovNYC</h1>
                <p>Product updates, data releases, and notes on how NYC government works — from the team behind Databook.</p>
            </div>
        </div>
    </div>
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-5);">

        @if(isset($articles) && count($articles) > 0)

            @php $featured = $articles[0]; @endphp

            {{-- Featured post — latest article (always shown; not filtered) --}}
            <a href="{{ route('article', ['slug' => $featured['slug']]) }}" class="db-card is-hoverable blog-featured d-block text-decoration-none" style="overflow: hidden; margin-bottom: var(--db-space-5);">
                <div class="row g-0 align-items-stretch">
                    <div class="col-md-7" style="position: relative; min-height: 320px; background: linear-gradient(135deg, var(--db-navy-800), var(--db-primary)); display: grid; place-items: center;">
                        @if(!empty($featured['image']['url']))
                            <div style="position:absolute; inset:0; background-image: url('{{ $featured['image']['url'] }}'); background-size: cover; background-position: center;"></div>
                        @else
                            <i class="bi bi-mortarboard" style="font-size: 3.5rem; color: rgba(255,255,255,0.3);"></i>
                        @endif
                    </div>
                    <div class="col-md-5 d-flex">
                        <div class="db-card-body d-flex flex-column justify-content-center" style="padding: var(--db-space-4);">
                            <div class="db-eyebrow" style="margin-bottom: var(--db-space-15);">Featured · {{ $featured['category'] ?? 'Update' }} · {{ strtoupper(date('M d, Y', strtotime($featured['originalPublishDate'] ?? $featured['publishedAt']))) }}</div>
                            <h2 class="db-card-title" style="font-size: var(--db-text-2xl); line-height: var(--db-leading-tight); margin-bottom: var(--db-space-15);">{{ $featured['title'] }}</h2>
                            <p style="color: var(--db-text-muted); margin-bottom: var(--db-space-3);">
                                {{ \Illuminate\Support\Str::limit(strip_tags($featured['description'] ?? $featured['content'] ?? ''), 200) }}
                            </p>
                            <span class="db-btn db-btn-primary align-self-start">Read post <i class="bi bi-arrow-right"></i></span>
                        </div>
                    </div>
                </div>
            </a>

            {{-- Filter row (functional — filters the grid client-side by category) --}}
            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap" style="gap: var(--db-space-2);">
                <h3 style="margin: 0;">All posts</h3>
                <div class="db-filter-pills" id="blogFilter">
                    <button type="button" class="db-filter-pill is-active" data-cat="all">All</button>
                    <button type="button" class="db-filter-pill" data-cat="data">Data releases</button>
                    <button type="button" class="db-filter-pill" data-cat="product">Product</button>
                    <button type="button" class="db-filter-pill" data-cat="civic">Civic notes</button>
                </div>
            </div>

            {{-- Post grid (excludes the featured post to avoid duplication) --}}
            <div class="row" id="blogGrid">
                @foreach($articles as $i => $article)
                    @continue($i === 0)
                    <div class="col-md-4 mb-4 d-flex align-items-stretch blog-post" data-cat="{{ $catKey($article['category'] ?? null) }}">
                        <a href="{{ route('article', ['slug' => $article['slug']]) }}" class="db-card is-hoverable w-100 d-flex flex-column text-decoration-none" style="overflow: hidden;">
                            <div style="height: 160px; position: relative; background: linear-gradient(135deg, var(--db-navy-800), var(--db-primary)); display: grid; place-items: center;">
                                @if(!empty($article['image']['url']))
                                    <div style="position:absolute; inset:0; background-image: url('{{ $article['image']['url'] }}'); background-size: cover; background-position: center;"></div>
                                @else
                                    <i class="bi bi-mortarboard" style="font-size: 2.5rem; color: rgba(255,255,255,0.3);"></i>
                                @endif
                            </div>
                            <div class="db-card-body d-flex flex-column flex-grow-1" style="padding: var(--db-space-2);">
                                <div class="d-flex align-items-center mb-2" style="gap: var(--db-space-1);">
                                    <span class="db-badge {{ $catBadge($article['category'] ?? null) }}">{{ $article['category'] ?? 'Update' }}</span>
                                    <small style="color: var(--db-text-muted); font-size: var(--db-text-2xs);">{{ date('M d, Y', strtotime($article['originalPublishDate'] ?? $article['publishedAt'])) }}</small>
                                </div>
                                <h5 class="db-card-title">{{ $article['title'] }}</h5>
                                <p class="flex-grow-1" style="color: var(--db-text-muted); font-size: var(--db-text-sm);">
                                    {{ \Illuminate\Support\Str::limit(strip_tags($article['description'] ?? $article['content'] ?? ''), 120) }}
                                </p>
                                <span class="db-btn db-btn-ghost db-btn-sm align-self-start" style="padding-left: 0;">Read <i class="bi bi-arrow-right"></i></span>
                            </div>
                        </a>
                    </div>
                @endforeach
            </div>
            <div id="blogNoResults" class="db-empty" style="display:none;">
                <div class="db-empty-icon"><i class="bi bi-journal-text"></i></div>
                <div class="db-empty-title">No posts in this category yet</div>
            </div>

        @else
            <div class="db-empty text-center py-5">
                <div class="db-empty-icon"><i class="bi bi-journal-text"></i></div>
                <p style="color: var(--db-text-muted);">No articles found.</p>
            </div>
        @endif

    </div>
</div>

<script>
(function () {
    var bar = document.getElementById('blogFilter');
    if (!bar) return;
    var posts = Array.prototype.slice.call(document.querySelectorAll('#blogGrid .blog-post'));
    var none = document.getElementById('blogNoResults');
    bar.addEventListener('click', function (e) {
        var btn = e.target.closest('.db-filter-pill');
        if (!btn) return;
        bar.querySelectorAll('.db-filter-pill').forEach(function (b) { b.classList.remove('is-active'); });
        btn.classList.add('is-active');
        var cat = btn.getAttribute('data-cat');
        var shown = 0;
        posts.forEach(function (p) {
            var match = (cat === 'all' || p.getAttribute('data-cat') === cat);
            p.style.display = match ? '' : 'none';
            if (match) shown++;
        });
        if (none) none.style.display = shown ? 'none' : 'block';
    });
})();
</script>
@endsection
