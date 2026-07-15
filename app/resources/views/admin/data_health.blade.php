@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        @php
            $checkedAt = $summary['checked_at'] ?? null;
            if ($checkedAt) {
                try {
                    $checkedDt = new \DateTime($checkedAt);
                    $checkedDt->setTimezone(new \DateTimeZone('America/New_York'));
                    $checkedLabel = $checkedDt->format('M j, g:ia');
                } catch (\Exception $e) {
                    $checkedLabel = $checkedAt;
                }
            } else {
                $checkedLabel = '—';
            }
        @endphp

        <div class="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4">
            <div>
                <div class="db-eyebrow">Admin</div>
                <h1>Data health</h1>
                <p class="db-page-lead">Freshness and status of every dataset feeding Databook.</p>
            </div>
            <div class="text-end">
                <div class="mb-2" style="font-size: var(--db-text-xs); color: var(--db-text-muted);">
                    <i class="bi bi-clock-history me-1"></i>Last checked {{ $checkedLabel }}
                </div>
                <button class="db-btn db-btn-outline db-btn-sm" id="refreshBtn" onclick="triggerCheck()">
                    <i class="bi bi-arrow-repeat me-1"></i> Run Data Check
                </button>
            </div>
        </div>

        {{-- Summary stats — IDs preserved for polling/refresh JS --}}
        <div class="db-stat-grid mb-4" id="summaryCards">
            <div class="db-stat is-accent">
                <div class="db-stat-label"><i class="bi bi-database me-1"></i>Datasets</div>
                <div class="db-stat-value" id="totalCount">{{ $summary['total_datasets'] ?? '—' }}</div>
                <div class="db-stat-sub">tracked</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Active</div>
                <div class="db-stat-value" id="activeCount" style="color: var(--db-success-fg);">{{ $summary['active'] ?? $summary['fresh'] ?? '—' }}</div>
                <div class="db-stat-sub">fresh &amp; complete</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Update Needed</div>
                <div class="db-stat-value" id="updateCount" style="color: var(--db-warning-fg);">{{ $summary['update_needed'] ?? $summary['aging'] ?? '—' }}</div>
                <div class="db-stat-sub">past refresh window</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Potential Issue</div>
                <div class="db-stat-value" id="errorCount" style="color: var(--db-danger-fg);">{{ $summary['error'] ?? $summary['stale'] ?? '—' }}</div>
                <div class="db-stat-sub">last run errored</div>
            </div>
        </div>

        @if(($summary['total_alerts'] ?? 0) > 0)
        <div class="alert alert-warning d-flex align-items-center mb-4" role="alert">
            <i class="bi bi-exclamation-triangle me-2"></i>
            <strong>{{ $summary['total_alerts'] }}</strong>&nbsp;normalizer alerts require attention
        </div>
        @endif

        {{-- Datasets Table --}}
        <div class="db-table-wrap">
            <div class="db-table-toolbar">
                <span class="db-table-count"><strong>{{ count($datasets ?? []) }}</strong> datasets</span>
                <span class="db-spacer"></span>
                <div class="db-filter-pills">
                    <button type="button" class="db-filter-pill is-active filter-btn active" data-filter="all">All</button>
                    <button type="button" class="db-filter-pill filter-btn" data-filter="active">Active</button>
                    <button type="button" class="db-filter-pill filter-btn" data-filter="update_needed">Update Needed</button>
                    <button type="button" class="db-filter-pill filter-btn" data-filter="error">Issues</button>
                </div>
            </div>
            <div class="table-responsive">
                <table class="db-table mb-0" id="healthTable">
                    <thead>
                        <tr>
                            <th>Status</th>
                            <th>UID</th>
                            <th>Table</th>
                            <th>Sections</th>
                            <th>Source</th>
                            <th>Source Updated</th>
                            <th class="db-num">Source Rows</th>
                            <th>Last Checked</th>
                            <th>Last Updated</th>
                            <th class="db-num">Our Rows</th>
                            <th class="db-num">Our Size</th>
                            <th>S3</th>
                            <th>Alerts</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($datasets ?? [] as $ds)
                        @php
                            // Determine status — support both new API (status field) and old API (freshness field)
                            $status = $ds['status'] ?? null;
                            $sourceType = $ds['source_type'] ?? '';
                            if (!$status) {
                                // Backward compat: derive from old freshness field
                                if ($sourceType === 'internal') {
                                    $status = 'none';
                                } else {
                                    $freshness = $ds['freshness'] ?? 'red';
                                    $status = $freshness === 'green' ? 'active'
                                        : ($freshness === 'yellow' ? 'update_needed' : 'error');
                                }
                            }
                        @endphp
                        <tr data-status="{{ $status }}">
                            <td>
                                @if($status === 'active')
                                    <span class="db-badge db-badge-success"><span class="db-dot"></span>Active</span>
                                @elseif($status === 'update_needed')
                                    <span class="db-badge db-badge-warning"><span class="db-dot"></span>Update Needed</span>
                                @elseif($status === 'none')
                                    <span class="text-muted">—</span>
                                @else
                                    <span class="db-badge db-badge-danger"><span class="db-dot"></span>{{ $ds['status_label'] ?? 'Potential Issue' }}</span>
                                @endif
                            </td>
                            <td><small class="text-muted">{{ $ds['id'] ?? '' }}</small></td>
                            <td><code>{{ $ds['table_name'] ?? '' }}</code></td>
                            <td>
                                @foreach(($ds['sections'] ?? []) as $section)
                                    <span class="db-tag">{{ $section }}</span>
                                @endforeach
                                @if(empty($ds['sections']))
                                    <span class="text-muted">—</span>
                                @endif
                            </td>
                            <td>
                                <span class="db-tag">{{ $ds['source_type'] ?? '' }}</span>
                                @if(!empty($ds['socrata_id']))
                                    <br><a href="https://data.cityofnewyork.us/d/{{ $ds['socrata_id'] }}"
                                           target="_blank"
                                           class="text-muted small"
                                           title="View on NYC Open Data">{{ $ds['socrata_id'] }} ↗</a>
                                @endif
                            </td>
                            <td><small>{{ $ds['source_updated_label'] ?? '—' }}</small></td>
                            <td class="db-num" data-socrata-id="{{ $ds['socrata_id'] ?? '' }}">
                                <span class="source-rows text-muted">…</span>
                            </td>
                            <td><small>{{ $ds['last_checked_label'] ?? '—' }}</small></td>
                            <td><small>{{ $ds['last_updated_label'] ?? '—' }}</small></td>
                            <td class="db-num">
                                @php
                                    $actual = $ds['actual_row_count'] ?? null;
                                    $estimated = $ds['estimated_rows'] ?? null;
                                    $displayRows = $actual ?? $estimated;
                                    $syncStatus = $ds['sync_status'] ?? 'ok';
                                @endphp
                                @if($displayRows)
                                    {{ number_format($displayRows) }}
                                    @if($syncStatus === 'mismatch')
                                        <span class="db-badge db-badge-warning" title="Row count mismatch: estimated {{ number_format($estimated ?? 0) }} vs actual {{ number_format($actual ?? 0) }}">⚠</span>
                                    @elseif($syncStatus === 'not_imported')
                                        <span class="db-badge db-badge-danger" title="Data not imported to Postgres">✗</span>
                                    @endif
                                @else
                                    —
                                @endif
                            </td>
                            <td class="db-num"><small>{{ $ds['actual_table_size'] ?? $ds['table_size'] ?? '—' }}</small></td>
                            <td>
                                @if(!empty($ds['s3_url']))
                                    <a href="{{ $ds['s3_url'] }}" target="_blank" title="{{ $ds['s3_url'] }}">↗</a>
                                @else
                                    <span class="text-muted">—</span>
                                @endif
                            </td>
                            <td>
                                @if(($ds['alert_count'] ?? 0) > 0)
                                    <a href="https://normalize.databook.nyc/admin/dataset/{{ $ds['normalizer_dataset_id'] ?? '' }}#alerts"
                                       class="db-badge db-badge-danger text-decoration-none"
                                       title="View alerts in normalizer">{{ $ds['alert_count'] }}</a>
                                @else
                                    <span class="text-muted">—</span>
                                @endif
                            </td>
                            <td>
                                <button class="db-btn db-btn-ghost db-btn-sm"
                                        onclick="checkDataset('{{ $ds['table_name'] ?? '' }}')"
                                        title="Check for updates">
                                    ↻ Check
                                </button>
                            </td>
                        </tr>
                        @empty
                        <tr>
                            <td colspan="14" class="text-center text-muted py-4">
                                <i class="bi bi-info-circle me-1"></i>
                                No datasets in registry. Run <code>setup_data_pipeline.py --populate</code> to seed.
                            </td>
                        </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
            <div class="db-table-footer">
                <span><i class="bi bi-clock-history me-1"></i>Checked at: {{ $summary['checked_at'] ?? 'N/A' }}</span>
            </div>
        </div>

    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const filter = this.dataset.filter;
            document.querySelectorAll('.filter-btn').forEach(b => { b.classList.remove('active'); b.classList.remove('is-active'); });
            this.classList.add('active');
            this.classList.add('is-active');

            document.querySelectorAll('#healthTable tbody tr').forEach(row => {
                if (filter === 'all' || row.dataset.status === filter) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    });
});

/**
 * Trigger a data check for all datasets via the pipeline API.
 *
 * Why: Allows admins to manually trigger a full refresh cycle without
 * waiting for the scheduler background loop.
 */
function triggerCheck() {
    const btn = document.getElementById('refreshBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Running...';

    fetch('/api/pipeline/check', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            btn.innerHTML = '<i class="bi bi-check2 me-1"></i> Started!';
            setTimeout(() => location.reload(), 3000);
        })
        .catch(err => {
            btn.innerHTML = '<i class="bi bi-x me-1"></i> Error';
            console.error(err);
        });
}

/**
 * Trigger a data check for a single dataset.
 *
 * Why: Enables targeted refresh of individual datasets for debugging
 * or when a specific dataset is known to have been updated.
 */
function checkDataset(tableName) {
    if (!confirm(`Check "${tableName}" for updates?`)) return;

    fetch(`/api/pipeline/check/${tableName}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            alert(data.result === 'OK' ? 'Check complete!' : 'Error: ' + JSON.stringify(data));
            location.reload();
        })
        .catch(err => alert('Error: ' + err.message));
}
/**
 * Fetch Socrata row counts for all datasets with socrata IDs.
 *
 * Why: Compares our ingested row count against the source to detect
 * incomplete imports or missing data.
 */
function fetchSocrataRowCounts() {
    const cells = document.querySelectorAll('td[data-socrata-id]');
    const ids = [];
    cells.forEach(cell => {
        const sid = cell.dataset.socrataId;
        if (sid) ids.push({ sid, cell });
    });

    // Batch fetch — use Socrata metadata API (public, no auth needed)
    ids.forEach(({ sid, cell }) => {
        fetch(`https://data.cityofnewyork.us/api/views/${sid}.json`)
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (!data) {
                    cell.querySelector('.source-rows').textContent = '?';
                    return;
                }
                const columns = data.columns || [];
                const rowCount = data.rowsUpdatedAt ? null : null;
                // The view metadata has cachedContents.non_null on columns,
                // but the simplest source of row count is via SODA $query=SELECT count(*)
                return fetch(`https://data.cityofnewyork.us/resource/${sid}.json?$select=count(*)%20as%20cnt&$limit=1`)
                    .then(r2 => r2.ok ? r2.json() : null)
                    .then(countData => {
                        if (countData && countData[0] && countData[0].cnt) {
                            const sourceCount = parseInt(countData[0].cnt);
                            const span = cell.querySelector('.source-rows');
                            span.textContent = sourceCount.toLocaleString();

                            // Compare with our row count (3 cells after: Source Rows → Last Checked → Last Updated → Our Rows)
                            const checkedCell = cell.nextElementSibling;
                            const updatedCell = checkedCell ? checkedCell.nextElementSibling : null;
                            const ourCell = updatedCell ? updatedCell.nextElementSibling : null;
                            const ourText = ourCell ? ourCell.textContent.trim().replace(/[^0-9]/g, '') : '';
                            const ourCount = ourText ? parseInt(ourText) : 0;

                            if (ourCount > 0 && sourceCount > 0) {
                                const ratio = ourCount / sourceCount;
                                if (ratio >= 0.95) {
                                    span.classList.remove('text-muted');
                                    span.classList.add('text-success');
                                    span.title = `${(ratio * 100).toFixed(1)}% complete`;
                                } else if (ratio >= 0.5) {
                                    span.classList.remove('text-muted');
                                    span.classList.add('text-warning');
                                    span.title = `Only ${(ratio * 100).toFixed(1)}% of source data`;
                                } else {
                                    span.classList.remove('text-muted');
                                    span.classList.add('text-danger');
                                    span.title = `Only ${(ratio * 100).toFixed(1)}% of source data`;
                                }
                            }
                        } else {
                            cell.querySelector('.source-rows').textContent = '—';
                        }
                    });
            })
            .catch(() => {
                cell.querySelector('.source-rows').textContent = '?';
            });
    });
}

// Fetch after page loads (stagger to avoid rate limiting)
setTimeout(fetchSocrataRowCounts, 500);
</script>
@endsection
