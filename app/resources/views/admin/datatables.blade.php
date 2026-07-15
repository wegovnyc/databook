@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        <div class="db-eyebrow">Admin</div>
        <h1>Database tables</h1>
        <p class="db-page-lead">Every table in the Databook datastore — row counts, size on disk, and last write.</p>

        {{-- Summary stats --}}
        @php
            $totalRows = 0;
            foreach (($tables ?? []) as $t) { $totalRows += (int)($t['row_count'] ?? 0); }
        @endphp
        <div class="db-stat-grid mb-4 mt-4">
            <div class="db-stat is-accent">
                <div class="db-stat-label">Tables</div>
                <div class="db-stat-value">{{ number_format($total_tables ?? count($tables ?? [])) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Total Rows</div>
                <div class="db-stat-value">{{ number_format($totalRows) }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">On Disk</div>
                <div class="db-stat-value">{{ $total_size ?? '—' }}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Engine</div>
                <div class="db-stat-value">{{ $engine ?? 'PostgreSQL' }}</div>
            </div>
        </div>

        <div class="db-table-wrap">
            <div class="table-responsive">
                <table id="tablesTable" class="db-table table-striped" style="width:100%">
                    <thead>
                        <tr>
                            <th>Table Name</th>
                            <th class="db-num">Row Count</th>
                            <th class="db-num">Size</th>
                            <th class="db-num">Last Ingested</th>
                            <th>Status</th>
                            <th>Source</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach($tables as $table)
                        <tr>
                            <td>
                                <code>{{ $table['table_name'] }}</code>
                            </td>
                            <td class="db-num" data-order="{{ $table['row_count'] ?? 0 }}">
                                {{ number_format($table['row_count'] ?? 0) }}
                            </td>
                            <td class="db-num" data-order="{{ $table['size_bytes'] ?? 0 }}">
                                {{ $table['size'] ?? 'Unknown' }}
                            </td>
                            <td class="db-num" data-order="{{ $table['last_ingested'] ?? '1970-01-01' }}">
                                @if($table['last_ingested'])
                                    {{ \Carbon\Carbon::parse($table['last_ingested'])->format('M d, Y H:i') }}
                                @else
                                    <span class="text-danger">Never</span>
                                @endif
                            </td>
                            <td>
                                @if($table['ingestion_status'] === 'success')
                                    <span class="db-badge db-badge-success"><span class="db-dot"></span>Success</span>
                                @elseif($table['ingestion_status'] === 'failed')
                                    <span class="db-badge db-badge-danger"><span class="db-dot"></span>Failed</span>
                                @elseif($table['ingestion_status'])
                                    <span class="db-badge db-badge-warning"><span class="db-dot"></span>{{ $table['ingestion_status'] }}</span>
                                @else
                                    <span class="db-badge db-badge-neutral">N/A</span>
                                @endif
                            </td>
                            <td>
                                @if($table['source_url'])
                                    <a href="{{ $table['source_url'] }}" target="_blank" class="small">
                                        {{ $table['source_url'] }}
                                    </a>
                                @else
                                    <span class="text-muted">-</span>
                                @endif
                            </td>
                        </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
            <div class="db-table-footer">
                <span><i class="bi bi-info-circle me-1"></i>Row counts may be estimates for tables not recently analyzed. Last updated: {{ now()->format('M d, Y H:i:s') }}</span>
            </div>
        </div>

    </div>
</div>

<!-- DataTables CSS -->
<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css">
<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/2.4.2/css/buttons.bootstrap5.min.css">

<!-- DataTables JS -->
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.4.2/js/dataTables.buttons.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.4.2/js/buttons.bootstrap5.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.4.2/js/buttons.html5.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>

<script>
$(document).ready(function() {
    $('#tablesTable').DataTable({
        pageLength: -1,  // Show all rows
        lengthMenu: [[25, 50, 100, -1], [25, 50, 100, "All"]],
        order: [[2, 'desc']], // Sort by size descending
        dom: '<"db-table-toolbar"f<"db-spacer">B>rt<"db-table-footer"lip>',
        buttons: [
            {
                extend: 'csv',
                text: '<i class="bi bi-download"></i> Export',
                className: 'db-btn db-btn-outline db-btn-sm'
            }
        ],
        language: {
            search: "",
            searchPlaceholder: "Filter tables…",
            lengthMenu: "Show _MENU_ tables",
            info: "Showing _START_ to _END_ of _TOTAL_ tables"
        }
    });
});
</script>
@endsection
