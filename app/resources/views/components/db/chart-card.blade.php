{{-- <x-db.chart-card title="…"> <canvas>…</canvas> </x-db.chart-card>
     The .db-chart-body wrapper gives the canvas a fixed height (required for
     Chart.js maintainAspectRatio:false — else it grows unboundedly). --}}
@props(['title' => null])
<div {{ $attributes->merge(['class' => 'db-chart-card']) }}>
    @if($title)<div class="db-chart-head"><div class="db-chart-title">{{ $title }}</div></div>@endif
    <div class="db-chart-body">{{ $slot }}</div>
</div>
