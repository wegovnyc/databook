{{-- Generic NYCHA record explorer (search / filter / sort / paginate / expand / export).
     Server-rendered (filter form GET → reload). Expects:
       $records   — {data,total,page,pages}
       $recFilters— ['q','fiscal_year','sort','order']
       $recCols   — [['label','key','money'=>bool]]  main table columns
       $recDetail — [['label','key','money'=>bool]]  expandable detail fields
       $recSorts  — ['key' => 'Label', ...]           sort options
       $recTitle  — heading (e.g. "Budget lines")
       $recNoun   — count noun (e.g. "line")
       $recExportPath — API export path (e.g. "/oce/nycha/budget/records/export")
       $recSearchPlaceholder, $recFyOpts, $section, $id, $orgslug --}}
@php
    $compactRT = function ($n) {
        $n = (float) $n;
        if (abs($n) >= 1e9) return '$' . number_format($n / 1e9, 1) . 'B';
        if (abs($n) >= 1e6) return '$' . number_format($n / 1e6, 1) . 'M';
        if (abs($n) >= 1e3) return '$' . number_format($n / 1e3, 0) . 'K';
        return '$' . number_format($n);
    };
    $rt      = $recFilters ?? [];
    $rtRows  = $records['data'] ?? [];
    $rtQ     = $rt['q'] ?? '';
    $rtFy    = (string) ($rt['fiscal_year'] ?? '');
    $rtSort  = $rt['sort'] ?? array_key_first($recSorts);
    $rtOrder = ($rt['order'] ?? 'desc') === 'asc' ? 'asc' : 'desc';
    $rtPage  = (int) ($records['page'] ?? 1);
    $rtPages = (int) ($records['pages'] ?? 1);
    $rtTotal = (int) ($records['total'] ?? count($rtRows));
    $rtBase  = route('orgSection', ['id' => $id, 'orgslug' => $orgslug ?? \Illuminate\Support\Str::slug($org['name'], '-'), 'section' => $section]);
    $rtActive = array_filter(['q' => $rtQ, 'fiscal_year' => $rtFy, 'sort' => $rtSort, 'order' => $rtOrder], fn($v) => $v !== '' && $v !== null);
    $rtPageUrl = fn($p) => $rtBase . '?' . http_build_query(array_merge($rtActive, ['page' => $p]));
    $rtExport = \App\Custom\DatabookAPI::url($recExportPath . '?' . http_build_query($rtActive));
    $rtSpan = count($recCols) + 1;
@endphp

<div class="d-flex align-items-center flex-wrap mt-5 mb-1" style="gap: var(--db-space-2);">
    <h3 class="mb-0" style="font-size: var(--db-text-lg);">{{ $recTitle }}</h3>
    <span class="db-badge db-badge-neutral">{{ number_format($rtTotal) }} {{ $recNoun }}{{ $rtTotal == 1 ? '' : 's' }}</span>
    <a href="{{ $rtExport }}" class="db-btn db-btn-outline db-btn-sm ms-auto"><i class="bi bi-download"></i> Export CSV</a>
</div>

<form method="GET" action="{{ $rtBase }}" class="db-filter-bar mb-3">
    <input class="db-input" type="search" name="q" value="{{ $rtQ }}" placeholder="{{ $recSearchPlaceholder ?? 'Search…' }}" style="min-width: 240px;" autocomplete="off">
    <select class="db-select" name="fiscal_year" aria-label="Fiscal year">
        <option value="">All fiscal years</option>
        @foreach($recFyOpts ?? [] as $y)
        <option value="{{ $y }}" {{ $rtFy === (string) $y ? 'selected' : '' }}>FY{{ $y }}</option>
        @endforeach
    </select>
    <select class="db-select" name="sort" aria-label="Sort by">
        @foreach($recSorts as $k => $lbl)<option value="{{ $k }}" {{ $rtSort === $k ? 'selected' : '' }}>{{ $lbl }}</option>@endforeach
    </select>
    <select class="db-select" name="order" aria-label="Order">
        <option value="desc" {{ $rtOrder === 'desc' ? 'selected' : '' }}>High → low</option>
        <option value="asc" {{ $rtOrder === 'asc' ? 'selected' : '' }}>Low → high</option>
    </select>
    <button type="submit" class="db-btn db-btn-primary">Apply</button>
    @if(count($rtActive))<a href="{{ $rtBase }}" class="db-btn db-btn-outline">Clear</a>@endif
</form>

<div class="db-table-wrap">
    <div class="table-responsive">
        <table class="db-table">
            <thead>
                <tr>
                    <th style="width: 28px;"></th>
                    @foreach($recCols as $col)<th class="{{ ($col['money'] ?? false) ? 'db-num' : '' }}">{{ $col['label'] }}</th>@endforeach
                </tr>
            </thead>
            <tbody>
                @forelse($rtRows as $i => $r)
                <tr class="nycha-rt-row" data-det="rtdet-{{ $i }}" style="cursor: pointer;">
                    <td class="text-center"><i class="bi bi-chevron-right nycha-rt-caret" style="color: var(--db-text-muted); transition: transform .15s;"></i></td>
                    @foreach($recCols as $col)
                        @php $v = $r[$col['key']] ?? null; @endphp
                        <td class="{{ ($col['money'] ?? false) ? 'db-num' : '' }}" style="{{ ($col['money'] ?? false) ? '' : 'max-width: 300px; overflow: hidden; text-overflow: ellipsis;' }}" title="{{ ($col['money'] ?? false) ? '' : $v }}">{{ ($col['money'] ?? false) ? $compactRT($v ?? 0) : ($v !== '' && $v !== null ? $v : '—') }}</td>
                    @endforeach
                </tr>
                <tr class="db-row-detail" id="rtdet-{{ $i }}" style="display: none;">
                    <td colspan="{{ $rtSpan }}" style="background: var(--db-gray-50);">
                        <div class="row" style="font-size: var(--db-text-sm);">
                            @foreach($recDetail as $d)
                            @php $dv = $r[$d['key']] ?? null; $dv = ($d['money'] ?? false) ? $compactRT($dv ?? 0) : $dv; @endphp
                            <div class="col-md-4 mb-1"><span style="color: var(--db-text-muted);">{{ $d['label'] }}:</span> {{ $dv !== '' && $dv !== null ? $dv : '—' }}</div>
                            @endforeach
                        </div>
                    </td>
                </tr>
                @empty
                <tr><td colspan="{{ $rtSpan }}" class="text-muted text-center py-4">No records match your filters.</td></tr>
                @endforelse
            </tbody>
        </table>
    </div>
</div>

@if($rtPages > 1)
<div class="d-flex align-items-center justify-content-center mt-3" style="gap: var(--db-space-1);">
    <a class="db-page {{ $rtPage <= 1 ? 'is-disabled' : '' }}" href="{{ $rtPage <= 1 ? '#' : $rtPageUrl(max($rtPage - 1, 1)) }}">Previous</a>
    <span class="db-page is-disabled">Page {{ number_format($rtPage) }} of {{ number_format($rtPages) }}</span>
    <a class="db-page {{ $rtPage >= $rtPages ? 'is-disabled' : '' }}" href="{{ $rtPage >= $rtPages ? '#' : $rtPageUrl(min($rtPage + 1, $rtPages)) }}">Next</a>
</div>
@endif

<script>
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.nycha-rt-row').forEach(function (row) {
        row.addEventListener('click', function () {
            var det = document.getElementById(row.getAttribute('data-det'));
            if (!det) return;
            var open = det.style.display !== 'none';
            det.style.display = open ? 'none' : 'table-row';
            var caret = row.querySelector('.nycha-rt-caret');
            if (caret) caret.style.transform = open ? '' : 'rotate(90deg)';
        });
    });
});
</script>
