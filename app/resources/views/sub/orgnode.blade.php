{{-- Recursive org-chart node (db-tree). $node = {name (HTML <a>), children}.
     Nodes deeper than 2 levels start collapsed so the 256-node citywide tree
     is navigable; JS toggles .is-collapsed. $node['name'] is curated static
     HTML from public/data/orgChart.json. --}}
@php
    $depth = $depth ?? 0;
    $children = (isset($node['children']) && is_array($node['children'])) ? $node['children'] : [];
    $hasKids = count($children) > 0;
    $isRoot = $depth === 0;
    $collapsed = $hasKids && $depth >= 2;
@endphp
<li class="{{ $collapsed ? 'is-collapsed' : '' }}">
    <div class="db-node{{ $isRoot ? ' is-root' : '' }}">
        @if ($hasKids)
            <button type="button" class="db-node-toggle" aria-label="Expand or collapse"><i class="bi bi-chevron-down"></i></button>
        @else
            <span class="db-node-toggle" aria-hidden="true"></span>
        @endif
        <span class="db-node-ico"><i class="bi {{ $isRoot ? 'bi-people-fill' : 'bi-building' }}"></i></span>
        <div class="db-node-main">
            <div class="db-node-name">{!! $node['name'] ?? '' !!}</div>
        </div>
        @if ($hasKids)
            <div class="db-node-stat">{{ count($children) }} {{ \Illuminate\Support\Str::plural('unit', count($children)) }}</div>
        @endif
    </div>
    @if ($hasKids)
        <ul>
            @foreach ($children as $child)
                @include('sub.orgnode', ['node' => $child, 'depth' => $depth + 1, 'defId' => $defId ?? null])
            @endforeach
        </ul>
    @endif
</li>
