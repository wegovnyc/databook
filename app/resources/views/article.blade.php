@extends('layout')

@section('head')
    <meta name="description" content="{{ \Illuminate\Support\Str::limit(strip_tags($article['description'] ?? $article['content'] ?? ''), 155) }}" />
    <meta property="og:title" content="{{ $article['title'] }}" />
    <meta property="og:description" content="{{ \Illuminate\Support\Str::limit(strip_tags($article['description'] ?? $article['content'] ?? ''), 155) }}" />
    @if(isset($article['image']['url']))
    <meta property="og:image" content="{{ $article['image']['url'] }}" />
    @endif
@endsection

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')

{{-- Hero image band (cover image or gradient) --}}
<div style="height: 280px; position: relative; background: linear-gradient(135deg, var(--db-navy-800), var(--db-primary)); display: grid; place-items: center;">
    @if(isset($article['image']['url']))
        <div style="position:absolute; inset:0; background-image: url('{{ $article['image']['url'] }}'); background-size: cover; background-position: center;"></div>
    @else
        <i class="bi bi-mortarboard" style="font-size: 4rem; color: rgba(255,255,255,0.30);"></i>
    @endif
</div>

<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        {{-- Breadcrumb --}}
        <nav class="db-breadcrumb">
            <a href="{{ route('root') }}">Home</a>
            <span class="db-breadcrumb-sep">/</span>
            <a href="{{ route('blog') }}">Blog</a>
            <span class="db-breadcrumb-sep">/</span>
            <span class="is-current">{{ $article['title'] }}</span>
        </nav>

        <div class="row">
            {{-- Article column --}}
            <div class="col-lg-8">

                {{-- Header --}}
                <div class="mb-4" style="max-width: 760px;">
                    <span class="db-badge db-badge-info mb-2">{{ $article['category'] ?? 'Update' }}</span>
                    <h1 class="mt-2 mb-3">{{ $article['title'] }}</h1>

                    {{-- Byline --}}
                    <div class="d-flex align-items-center justify-content-between flex-wrap" style="gap: var(--db-space-2);">
                        <div class="d-flex align-items-center" style="gap: var(--db-space-15);">
                            @php $author = $article['author']['name'] ?? 'WeGovNYC Team'; @endphp
                            <div class="db-avatar db-avatar-sm">{{ strtoupper(substr($author, 0, 2)) }}</div>
                            <div>
                                <div style="font-weight: var(--db-weight-semibold); color: var(--db-text); font-size: var(--db-text-sm);">{{ $author }}</div>
                                <div style="color: var(--db-text-muted); font-size: var(--db-text-xs);">
                                    {{ date('M d, Y', strtotime($article['originalPublishDate'] ?? $article['publishedAt'])) }}
                                    @if(isset($article['readingTime'])) · {{ $article['readingTime'] }} min read @endif
                                </div>
                            </div>
                        </div>
                        <div class="d-flex align-items-center" style="gap: 6px;">
                            <a class="db-icon-btn" target="_blank" rel="noopener" href="https://twitter.com/intent/tweet?url={{ urlencode(route('article', ['slug' => $article['slug']])) }}&text={{ urlencode($article['title']) }}" title="Share on X"><i class="bi bi-twitter-x"></i></a>
                            <a class="db-icon-btn" href="{{ route('article', ['slug' => $article['slug']]) }}" title="Copy link"><i class="bi bi-link-45deg"></i></a>
                        </div>
                    </div>
                </div>

                {{-- Body --}}
                <div class="db-db-prose">
                    {!! $article['content'] !!}
                </div>

                <hr class="my-5">
                <a href="{{ route('blog') }}" class="db-btn db-btn-outline">
                    <i class="bi bi-arrow-left"></i> Back to Blog
                </a>
            </div>

            {{-- Sidebar --}}
            <div class="col-lg-4">
                <div style="padding-left: var(--db-space-2);">
                    <h5 class="db-card-title mb-2">Related posts</h5>
                    <div class="mb-4">
                        <div class="db-list-row">
                            <div class="db-list-main">
                                <a href="{{ route('blog') }}">More from the Databook blog</a>
                            </div>
                        </div>
                    </div>

                    <div class="db-card">
                        <div class="db-card-body">
                            <div class="db-eyebrow mb-1">Explore the data</div>
                            <p class="mb-3" style="color: var(--db-text-muted); font-size: var(--db-text-sm);">Get normalized NYC government data from our datasets.</p>
                            <a href="{{ route('about.data') }}" class="db-btn db-btn-primary db-btn-sm">View datasets <i class="bi bi-arrow-right"></i></a>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </div>
</div>
@endsection
