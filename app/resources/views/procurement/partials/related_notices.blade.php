{{-- Reverse notice↔procurement link: City Record notices matched to this
     solicitation/contract/vendor by PIN/EPIN. Expects $relatedNotices.
     Renders nothing when there are no matches. --}}
@if(count($relatedNotices ?? []) > 0)
<div id="notices" class="db-anchor mb-5">
    <div class="d-flex align-items-center mb-3" style="gap: var(--db-space-15);">
        <h4 class="mb-0">City Record Notices</h4>
        <span class="db-badge db-badge-neutral">{{ count($relatedNotices) }}</span>
    </div>
    <div class="db-table-wrap">
        <div class="table-responsive">
            <table class="db-table">
                <thead>
                    <tr><th>Notice</th><th>Type</th><th>Agency</th><th>Posted</th></tr>
                </thead>
                <tbody>
                    @foreach($relatedNotices as $n)
                    <tr>
                        <td><a href="{{ $n['url'] }}" target="_blank" rel="nofollow" class="fw-semibold">{{ $n['title'] ?: 'Notice' }} <i class="bi bi-box-arrow-up-right" style="font-size:11px;"></i></a></td>
                        <td>@if($n['type'])<span class="db-badge db-badge-navy">{{ $n['type'] }}</span>@endif</td>
                        <td class="text-muted">{{ $n['agency'] }}</td>
                        <td>{{ $n['date'] }}</td>
                    </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
    </div>
    <p class="db-page-lead" style="font-size: var(--db-text-xs); margin-top: var(--db-space-1);"><i class="bi bi-info-circle"></i> Matched by PIN/EPIN; notices open in The City Record.</p>
</div>
@endif
