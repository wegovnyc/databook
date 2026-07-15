{{-- Source indicator tooltip icon
     Usage: @include('procurement.partials.source_badge', ['source' => 'mocs'])
     or:    @include('procurement.partials.source_badge', ['source' => 'checkbook'])
--}}
@php
$sources = [
    'mocs' => [
        'label' => 'MOCS Contracts',
        'tip' => 'Based on contract award amounts from the Mayor\'s Office of Contract Services (PASSPort)',
        'icon' => 'bi-file-earmark-text',
        'color' => '#6c757d'
    ],
    'checkbook' => [
        'label' => 'Checkbook NYC',
        'tip' => 'Based on actual payments from NYC Checkbook (Office of the Comptroller)',
        'icon' => 'bi-receipt',
        'color' => '#28a745'
    ],
];
$src = $sources[$source ?? 'mocs'] ?? $sources['mocs'];
@endphp
<span class="source-badge d-inline-block ms-1" data-bs-toggle="tooltip" data-bs-placement="top"
      title="{{ $src['tip'] }}" style="cursor:help;">
    <i class="{{ $src['icon'] }}" style="font-size: 0.75em; color: {{ $src['color'] }};"></i>
    <small class="text-muted" style="font-size: 0.65em; vertical-align: middle;">{{ $src['label'] }}</small>
</span>
@once
<script>
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function(el) {
        new bootstrap.Tooltip(el);
    });
});
</script>
@endonce
