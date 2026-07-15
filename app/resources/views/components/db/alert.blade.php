{{-- <x-db.alert tone="info|success|warning|danger" :dismissible icon="…"> --}}
@props(['tone' => 'info', 'dismissible' => false, 'icon' => null])
@php
    $icons = ['info' => 'info-circle', 'success' => 'check-circle', 'warning' => 'exclamation-triangle', 'danger' => 'exclamation-circle'];
    $ico = $icon ?: ($icons[$tone] ?? 'info-circle');
@endphp
<div {{ $attributes->merge(['class' => 'db-alert db-alert-' . $tone]) }} role="alert">
    <i class="bi bi-{{ $ico }}"></i>
    <div class="db-alert-body">{{ $slot }}</div>
    @if($dismissible)<button type="button" class="db-alert-close" aria-label="Dismiss" onclick="this.closest('.db-alert').remove()"><i class="bi bi-x-lg"></i></button>@endif
</div>
