@extends('layout')

@section('head')
	<meta name="description" content="{{ $snippet }}" />
	<meta rel="canonical" href="{!! route('titles') !!}" />
	<style>
		/* Exams tab (View D) — db-* design system. Reuses the Civil Service Exams (View C)
		   card/row treatment. Only tab-specific glue lives here. */
		.exams-loading { text-align: center; padding: var(--db-space-5) var(--db-space-2); color: var(--db-text-muted); }
		.exam-card-badges { display: flex; align-items: center; gap: var(--db-space-1); flex-wrap: wrap; margin-bottom: var(--db-space-1); }
		.exam-card-title { font-size: var(--db-text-md); font-weight: var(--db-weight-bold); line-height: var(--db-leading-snug); margin: 2px 0; }
		.exam-card-title a { color: var(--db-primary); }
		.exam-card-examno { font-family: var(--db-font-mono); font-size: var(--db-text-xs); color: var(--db-text-muted); }
		.exam-card-salary { font-weight: var(--db-weight-bold); color: var(--db-primary); font-variant-numeric: tabular-nums; margin: var(--db-space-1) 0; }
		.exam-card-deadline { font-size: var(--db-text-sm); color: var(--db-text-muted); display: flex; align-items: center; gap: 6px; }
		.exam-card-deadline strong { color: var(--db-warning-fg); }
		.exam-card-foot { display: flex; gap: var(--db-space-1); margin-top: var(--db-space-15); padding-top: var(--db-space-15); border-top: 1px solid var(--db-border); flex-wrap: wrap; }
	</style>
@endsection

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	@include('sub.titleheader', ['active' => $section])

	<div class="inner_container">
		<div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-5);">
			<div class="row justify-content-center">
				<div class="col-md-12">
					<div id="exams-loading" class="exams-loading">
						<div class="db-spinner db-spinner-lg"></div>
						<div class="mt-2">Loading exam schedule for this title…</div>
					</div>
					<div id="exams-content"></div>
				</div>
			</div>
		</div>
	</div>

<script>
$(document).ready(function() {
	var TITLE_DESC = @json($titles[0]['Title Description']);
	var TITLE_CODE = @json($titles[0]['Title Code']);
	var API = 'https://data.cityofnewyork.us/resource/4ptz-hmtc.json';
	var TODAY = new Date().toISOString().substring(0, 10);
	var YEAR = new Date().getFullYear().toString();

	function fmtDate(d) {
		if (!d) return '—';
		var dt = new Date(d);
		var m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
		return m[dt.getMonth()] + ' ' + dt.getDate() + ', ' + dt.getFullYear();
	}

	function daysUntil(d) {
		if (!d) return null;
		var dt = new Date(d); var now = new Date();
		now.setHours(0,0,0,0); dt.setHours(0,0,0,0);
		return Math.ceil((dt - now) / 86400000);
	}

	function noeUrl(n) { return 'https://a856-exams.nyc.gov/OASysWeb/noe/' + YEAR + n + '000.pdf'; }
	function applyUrl(n) { return 'https://a856-exams.nyc.gov/OASysWeb/login?returnUrl=%2Fexam-application%2F' + n; }

	// Fetch all exams, filter by title description match
	$.getJSON(API + '?$limit=50000', function(rawData) {
		// Dedup by exam_number (latest snapshot)
		var map = {};
		rawData.forEach(function(r) {
			var k = r.exam_number;
			if (!map[k] || (r.data_current_as_of || '') > (map[k].data_current_as_of || '')) map[k] = r;
		});
		var allExams = Object.values(map);

		// Match: exam title contains or starts with the title description (case-insensitive)
		var clean = TITLE_DESC.toUpperCase().trim();
		var matched = allExams.filter(function(r) {
			var et = (r.exam_title || '').toUpperCase().trim();
			// Strip trailing parentheticals for comparison
			var stripped = et.replace(/\s*\([^)]*\)\s*$/g, '').trim();
			stripped = stripped.replace(/\s*\([^)]*\)\s*$/g, '').trim();
			return stripped === clean || stripped.indexOf(clean) === 0 || clean.indexOf(stripped) === 0;
		});

		// Also get salary from title data for display
		$.getJSON('https://data.cityofnewyork.us/resource/nzjr-3966.json?$limit=5&$where=title=%27' + encodeURIComponent(TITLE_CODE) + '%27', function(titleData) {
			var sal = '';
			if (titleData.length > 0) {
				var min = parseInt(titleData[0].min_rate) || 0;
				var max = parseInt(titleData[0].max_rate) || 0;
				if (min && max && min !== max) sal = '$' + min.toLocaleString() + ' – $' + max.toLocaleString();
				else if (max || min) sal = '$' + (max || min).toLocaleString();
			}

			$('#exams-loading').hide();

			if (matched.length === 0) {
				$('#exams-content').html('<div class="db-empty"><i class="bi bi-card-checklist db-empty-icon"></i><div class="db-empty-title">No exams found for this title.</div><div class="db-empty-text">Check the <a href="/jobs-exams">full exam schedule</a> for all available exams.</div></div>');
				return;
			}

			// Sort: active first, then upcoming, then past
			matched.sort(function(a, b) {
				var aStart = (a.application_period_start || '').substring(0,10);
				var aEnd = (a.application_period_end_date || '').substring(0,10);
				var bStart = (b.application_period_start || '').substring(0,10);
				var bEnd = (b.application_period_end_date || '').substring(0,10);
				var aActive = (aStart <= TODAY && aEnd >= TODAY) ? 0 : (aStart > TODAY ? 1 : 2);
				var bActive = (bStart <= TODAY && bEnd >= TODAY) ? 0 : (bStart > TODAY ? 1 : 2);
				if (aActive !== bActive) return aActive - bActive;
				return (bEnd || '').localeCompare(aEnd || '');
			});

			var html = '<div class="db-table-count"><i class="bi bi-card-checklist"></i> ' + matched.length + ' Exam' + (matched.length > 1 ? 's' : '') + ' Found</div>';
			matched.forEach(function(r) {
				var start = (r.application_period_start || '').substring(0,10);
				var end = (r.application_period_end_date || '').substring(0,10);
				var isActive = start <= TODAY && end >= TODAY;
				var isUpcoming = start > TODAY;
				var badge = isActive ? '<span class="db-badge db-badge-success"><span class="db-dot"></span> Accepting Applications</span>'
					: isUpcoming ? '<span class="db-badge db-badge-navy">Upcoming</span>'
					: '<span class="db-badge db-badge-neutral">Closed</span>';
				var deadlineHtml = '';
				if (isActive) {
					var d = daysUntil(r.application_period_end_date);
					deadlineHtml = '<div class="exam-card-deadline"><i class="bi bi-calendar-event"></i> Apply by <strong>' + fmtDate(r.application_period_end_date) + '</strong>' +
						(d !== null ? ' · ' + (d === 0 ? 'Last day!' : d + ' days left') : '') + '</div>';
				} else if (start && end) {
					deadlineHtml = '<div class="exam-card-deadline"><i class="bi bi-calendar-event"></i> ' + fmtDate(r.application_period_start) + ' – ' + fmtDate(r.application_period_end_date) + '</div>';
				}

				html += '<div class="db-card" style="margin-bottom: var(--db-space-15);">' +
					'<div class="db-card-body">' +
						'<div class="exam-card-badges">' +
							badge +
							((r.open_competitive_promotion) ? '<span class="db-type-label">' + r.open_competitive_promotion + '</span>' : '') +
						'</div>' +
						'<div class="exam-card-title">' + (r.exam_title || 'Untitled') + '</div>' +
						'<div class="exam-card-examno">Exam #' + (r.exam_number || '') + '</div>' +
						(sal ? '<div class="exam-card-salary">' + sal + '</div>' : '') +
						deadlineHtml +
						'<div class="exam-card-foot">' +
							'<a class="db-btn db-btn-outline db-btn-sm" href="' + noeUrl(r.exam_number) + '" target="_blank"><i class="bi bi-box-arrow-up-right"></i> Notice of Exam</a>' +
							'<a class="db-btn db-btn-primary db-btn-sm" href="' + applyUrl(r.exam_number) + '" target="_blank"><i class="bi bi-box-arrow-up-right"></i> Apply</a>' +
						'</div>' +
					'</div>' +
				'</div>';
			});

			html += '<div class="db-alert db-alert-info mt-3"><div class="db-alert-body"><i class="bi bi-info-circle"></i> Data from <a href="https://data.cityofnewyork.us/City-Government/Annual-Examination-Schedule-of-Each-Fiscal-Year/4ptz-hmtc" target="_blank">DCAS Annual Examination Schedule</a>. See all exams on the <a href="/jobs-exams">Exams page</a>.</div></div>';
			$('#exams-content').html(html);
		});
	}).fail(function() {
		$('#exams-loading').html('<div class="text-danger">Failed to load exam data.</div>');
	});
});
</script>

@endsection
