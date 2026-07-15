@extends('layout')

@section('head')
    <meta name="robots" content="noindex, nofollow" />
@endsection

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <div class="db-eyebrow">Admin</div>
        <h1>Ingestion log</h1>
        <p class="db-page-lead">Every pipeline run — source, outcome, records processed, and status.</p>

        @php
            $logRows = (isset($logs) && count($logs) > 0) ? $logs : [];
            $runCount = count($logRows);
            $succeeded = 0; $failed = 0; $totalRecords = 0;
            foreach ($logRows as $l) {
                $st = $l['status'] ?? '';
                if ($st === 'success') { $succeeded++; }
                elseif ($st === 'fail' || $st === 'failed') { $failed++; }
                $totalRecords += (int)($l['row_count'] ?? 0);
            }
        @endphp

        {{-- Summary stats --}}
        <div class="db-stat-grid mb-4 mt-4">
            <div class="db-stat is-accent">
                <div class="db-stat-label">Runs</div>
                <div class="db-stat-value">{{ number_format($runCount) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Succeeded</div>
                <div class="db-stat-value" style="color: var(--db-success-fg);">{{ number_format($succeeded) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Failed</div>
                <div class="db-stat-value" style="color: var(--db-danger-fg);">{{ number_format($failed) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Records Processed</div>
                <div class="db-stat-value">{{ number_format($totalRecords) }}</div>
            </div>
        </div>

        {{-- Filter bar (client-side over rendered rows) --}}
        <div class="db-filter-bar mb-4">
            <div class="db-search"><i class="bi bi-search"></i><input type="search" id="logSearch" placeholder="Filter by table…" aria-label="Filter by table"></div>
            <div class="db-field">
                <label>Status</label>
                <select id="logStatus">
                    <option value="">Any</option>
                    <option value="success">Success</option>
                    <option value="fail">Failed</option>
                </select>
            </div>
        </div>

        @if($runCount > 0)
        <div class="db-table-wrap">
            <div class="db-table-toolbar">
                <span class="db-table-count"><strong id="logVisibleCount">{{ $runCount }}</strong> runs</span>
            </div>
            <div class="table-responsive">
                <table class="db-table table-striped" id="logTable">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Table Name</th>
                            <th>S3 URL</th>
                            <th>Ingested At</th>
                            <th>Status</th>
                            <th class="db-num">Row Count</th>
                            <th>Error</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach($logs as $log)
                        @php $logStatus = $log['status'] ?? ''; @endphp
                        <tr data-status="{{ $logStatus }}" data-table="{{ strtolower($log['table_name'] ?? '') }}">
                            <td>{{ $log['id'] ?? '-' }}</td>
                            <td><code>{{ $log['table_name'] ?? '-' }}</code></td>
                            <td>
                                <span class="d-inline-block text-truncate" style="max-width: 200px;" title="{{ $log['s3_url'] ?? '' }}">
                                    {{ $log['s3_url'] ?? '-' }}
                                </span>
                            </td>
                            <td>{{ isset($log['ingested_at']) ? date('M d, Y H:i', strtotime($log['ingested_at'])) : '-' }}</td>
                            <td>
                                @if($logStatus === 'success')
                                    <span class="db-badge db-badge-success"><span class="db-dot"></span>Success</span>
                                @elseif($logStatus === 'fail' || $logStatus === 'failed')
                                    <span class="db-badge db-badge-danger"><span class="db-dot"></span>Failed</span>
                                @elseif($logStatus === 'running')
                                    <span class="db-badge db-badge-info"><span class="db-dot"></span>Running</span>
                                @else
                                    <span class="db-badge db-badge-neutral">{{ $logStatus ?: '-' }}</span>
                                @endif
                            </td>
                            <td class="db-num">{{ isset($log['row_count']) ? number_format($log['row_count']) : '-' }}</td>
                            <td class="text-danger">{{ $log['error_message'] ?? '' }}</td>
                        </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
        @else
        <div class="db-empty">
            <div class="db-empty-icon"><i class="bi bi-inbox"></i></div>
            <div class="db-empty-title">No ingestion logs found</div>
            <div class="db-empty-text">No pipeline runs have been recorded yet.</div>
        </div>
        @endif

    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    var search = document.getElementById('logSearch');
    var statusSel = document.getElementById('logStatus');
    var rows = Array.prototype.slice.call(document.querySelectorAll('#logTable tbody tr'));
    var countEl = document.getElementById('logVisibleCount');

    function apply() {
        if (!rows.length) return;
        var q = (search.value || '').trim().toLowerCase();
        var st = statusSel.value;
        var visible = 0;
        rows.forEach(function(row) {
            var tableName = row.getAttribute('data-table') || '';
            var rowStatus = row.getAttribute('data-status') || '';
            var matchSearch = !q || tableName.indexOf(q) !== -1;
            var matchStatus = !st || rowStatus === st || (st === 'fail' && rowStatus === 'failed');
            var show = matchSearch && matchStatus;
            row.style.display = show ? '' : 'none';
            if (show) visible++;
        });
        if (countEl) countEl.textContent = visible;
    }

    if (search) search.addEventListener('input', apply);
    if (statusSel) statusSel.addEventListener('change', apply);
});
</script>
@endsection
