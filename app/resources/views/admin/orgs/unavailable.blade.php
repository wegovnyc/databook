@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">
        @php
            // ⚠ Precomputed, per the Blade directive-glued-to-a-word-char trap.
            $isAuth = in_array((int)$status, [401, 403], true);
            $detailText = is_string($detail) ? $detail : json_encode($detail);
        @endphp
        <div class="db-eyebrow"><a href="{{ route('admin.orgs') }}">Org register</a></div>
        <h1>The register could not be read</h1>
        <x-db.alert type="danger" class="mt-3">
            The API answered <code>{{ $status }}</code>.
            @if ($isAuth)
                That is an authorization answer, which means this app's API
                credential is missing or is not permitted to edit the register —
                not that anything is wrong with the organization.
            @else
                This page is a consumer of <code>/admin/orgs</code>; if the API is
                mid-deploy it will 502 for 15–30 seconds, so retrying shortly is
                usually enough.
            @endif
            @if ($detailText)
                <div class="db-meta mt-2">{{ $detailText }}</div>
            @endif
        </x-db.alert>
        <a class="db-btn db-btn-secondary mt-3" href="{{ route('admin.orgs') }}">Back to the register</a>
    </div>
</div>
@endsection
