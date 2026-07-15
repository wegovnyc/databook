@extends('layout')

@section('head')
	<meta name="description" content="NYC civil service exams — apply now, upcoming exams, and exam schedule" />
	<meta rel="canonical" href="{{ route('jobsExams') }}" />
	<style>
		/* Exams page — db-* design system. Only page-specific glue lives here;
		   cards/rows/table/badges all use the shared component classes. */
		.exams-now-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--db-space-2); }
		/* Exam card (light .db-card) inner layout */
		.exam-card-badges { display: flex; align-items: center; gap: var(--db-space-1); flex-wrap: wrap; margin-bottom: var(--db-space-1); }
		.exam-card-title { font-size: var(--db-text-md); font-weight: var(--db-weight-bold); line-height: var(--db-leading-snug); margin: 2px 0; }
		.exam-card-title a { color: var(--db-primary); }
		.exam-card-examno { font-family: var(--db-font-mono); font-size: var(--db-text-xs); color: var(--db-text-muted); }
		.exam-card-salary { font-weight: var(--db-weight-bold); color: var(--db-primary); font-variant-numeric: tabular-nums; margin: var(--db-space-1) 0; }
		.exam-card-deadline { font-size: var(--db-text-sm); color: var(--db-text-muted); display: flex; align-items: center; gap: 6px; }
		.exam-card-deadline strong { color: var(--db-warning-fg); }
		.exam-card-foot { display: flex; gap: var(--db-space-1); margin-top: var(--db-space-15); padding-top: var(--db-space-15); border-top: 1px solid var(--db-border); flex-wrap: wrap; }
		/* Upcoming + table action links reuse db-btn sizing */
		.exam-actions { display: inline-flex; gap: 6px; flex-shrink: 0; }
		.exams-loading { text-align: center; padding: var(--db-space-5) var(--db-space-2); color: var(--db-text-muted); }
	</style>
@endsection

@section('menubar')
	@include('sub.menubar', ['active' => 'titles'])
@endsection

@section('content')

{{-- Navy hero band (family-wide "Briefing" treatment) --}}
<div class="db-hero">
	<div class="inner_container">
		<div class="container db-hero-inner">
			<div class="db-hero-copy">
				<div class="db-eyebrow" style="color:var(--db-accent);">Jobs &amp; Exams</div>
				<h1>Civil Service Exams</h1>
				<p>NYC civil service exams currently accepting applications and the upcoming exam schedule. Apply, review the Notice of Examination, or view the related civil service title profile.</p>
			</div>
		</div>
	</div>
</div>

<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-5);">

		<div id="exams-section">
			{{-- Section head --}}
			<div class="d-flex align-items-center flex-wrap" style="gap: var(--db-space-2); margin-bottom: var(--db-space-2);">
				<h2 style="margin:0;">Accepting applications now</h2>
				<span class="db-badge db-badge-success" id="exams-count"><span class="db-dot"></span>…</span>
				<div class="db-spacer" style="margin-left:auto;"></div>
				<div class="db-search" style="max-width:280px;">
					<i class="bi bi-search"></i>
					<input type="search" id="exam-search" placeholder="Search exams…" aria-label="Search exams">
				</div>
				<div class="db-filter-pills" id="exam-filters">
					<button class="db-filter-pill is-active" data-filter="all">All</button>
					<button class="db-filter-pill" data-filter="open">Open Competitive</button>
					<button class="db-filter-pill" data-filter="promo">Promotion</button>
				</div>
			</div>

			<div id="exams-loading" class="exams-loading">
				<div class="db-spinner db-spinner-lg"></div>
				<div class="mt-2">Loading exam schedule…</div>
			</div>

			{{-- Active exams as light feature cards --}}
			<div id="now-header" style="display:none">
				<div class="db-eyebrow" style="margin-bottom: var(--db-space-1);"><i class="bi bi-lightning-charge-fill"></i> Accepting applications now <span class="db-badge db-badge-success" id="now-count">0</span></div>
			</div>
			<div class="exams-now-grid" id="now-cards"></div>

			{{-- Upcoming exams as compact rows --}}
			<div id="future-header" style="display:none">
				<div class="db-eyebrow" style="margin: var(--db-space-3) 0 var(--db-space-1);"><i class="bi bi-calendar-event"></i> Upcoming <span class="db-badge db-badge-neutral" id="future-count">0</span></div>
			</div>
			<div id="future-list" class="db-panel" style="margin-top: var(--db-space-1);"></div>

			<div id="no-results" class="db-alert db-alert-info mt-3" style="display:none"><div class="db-alert-body">No exams match your search.</div></div>

			<div class="text-center mt-4">
				<button class="db-btn db-btn-outline" id="toggle-full-schedule">
					<i class="bi bi-clock-history"></i> Show Full Exam Schedule
				</button>
			</div>
		</div>

		{{-- SECTION: Full Exam Schedule (hidden by default) --}}
		<div class="mt-5" id="all-section" style="display:none">
			<div class="d-flex align-items-center" style="gap: var(--db-space-15); margin-bottom: var(--db-space-2);">
				<h2 style="margin:0;">Full Exam Schedule</h2>
				<span class="db-badge db-badge-navy" id="all-count">…</span>
			</div>
			<div id="all-loading" class="exams-loading">
				<div class="db-spinner db-spinner-lg"></div>
				<div class="mt-2">Loading full schedule…</div>
			</div>
			<div class="db-table-wrap" id="all-table-wrapper" style="display:none;">
				<div class="table-responsive">
					<table id="all-table" class="db-table display table-striped table-hover" style="width:100%">
						<thead>
							<tr>
								<th>Exam Title</th>
								<th>Exam #</th>
								<th>Type</th>
								<th>Application Opens</th>
								<th>Application Closes</th>
								<th>Actions</th>
							</tr>
						</thead>
					</table>
				</div>
			</div>
		</div>

		{{-- Source --}}
		<div class="db-alert db-alert-info mt-4">
			<div class="db-alert-body">
				<i class="bi bi-info-circle"></i> <strong>Data Source:</strong>
				<a href="https://data.cityofnewyork.us/City-Government/Annual-Examination-Schedule-of-Each-Fiscal-Year/4ptz-hmtc" target="_blank" rel="nofollow">DCAS Annual Examination Schedule (4ptz-hmtc)</a>
				— exam schedule fetched live from NYC Open Data.
			</div>
		</div>

	</div>
</div>

<script>
$(document).ready(function() {
	var API = 'https://data.cityofnewyork.us/resource/4ptz-hmtc.json';
	var TODAY = new Date().toISOString().substring(0, 10);
	var CURRENT_YEAR = new Date().getFullYear().toString();

	// Deduplicate by exam_number (keep latest data_current_as_of)
	function dedup(data) {
		var map = {};
		data.forEach(function(r) {
			var key = r.exam_number;
			if (!map[key] || (r.data_current_as_of || '') > (map[key].data_current_as_of || '')) {
				map[key] = r;
			}
		});
		return Object.values(map);
	}

	// Format date
	function fmtDate(d) {
		if (!d) return '—';
		var dt = new Date(d);
		var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
		return months[dt.getMonth()] + ' ' + dt.getDate() + ', ' + dt.getFullYear();
	}

	// Days until date
	function daysUntil(d) {
		if (!d) return null;
		var dt = new Date(d);
		var now = new Date();
		now.setHours(0,0,0,0);
		dt.setHours(0,0,0,0);
		return Math.ceil((dt - now) / (1000 * 60 * 60 * 24));
	}

	// Build NOE PDF URL
	function noeUrl(examNo) {
		return 'https://a856-exams.nyc.gov/OASysWeb/noe/' + CURRENT_YEAR + examNo + '000.pdf';
	}

	// Build Apply URL
	function applyUrl(examNo) {
		return 'https://a856-exams.nyc.gov/OASysWeb/login?returnUrl=%2Fexam-application%2F' + examNo;
	}

	// Title matching: multi-strategy (exact, startsWith, search fallback)
	// The nzjr-3966 dataset uses 'descr' (truncated ~30 chars) and 'title' (code)
	var titleExact = {};   // descr -> {code, min_rate, max_rate}
	var titleDescrs = [];  // [{descr, code, min_rate, max_rate}] for startsWith matching
	var titleReady = false;

	function cleanExamTitle(examTitle) {
		var clean = (examTitle || '');
		// Strip everything after first newline (some titles have sub-lists)
		clean = clean.split('\n')[0];
		while (/\s*\([^)]*\)\s*$/.test(clean)) {
			clean = clean.replace(/\s*\([^)]*\)\s*$/, '');
		}
		return clean.trim().toUpperCase();
	}

	function findTitleInfo(examTitle) {
		var clean = cleanExamTitle(examTitle);
		if (!clean) return null;
		// Strategy 1: Exact match
		if (titleExact[clean]) return titleExact[clean];
		// Strategy 2: startsWith (handles truncated descriptions)
		for (var i = 0; i < titleDescrs.length; i++) {
			var d = titleDescrs[i];
			if (clean.indexOf(d.descr) === 0 || d.descr.indexOf(clean) === 0) {
				return d;
			}
		}
		return null;
	}

	function titleHrefFor(examTitle) {
		var info = findTitleInfo(examTitle);
		if (info) return '/t/' + info.code;
		var clean = cleanExamTitle(examTitle);
		return '/titles?search=' + encodeURIComponent(clean);
	}

	function salaryFor(examTitle) {
		var info = findTitleInfo(examTitle);
		if (!info || !info.min_rate) return null;
		var min = parseInt(info.min_rate) || 0;
		var max = parseInt(info.max_rate) || 0;
		if (!min && !max) return null;
		if (min && max && min !== max) return '$' + min.toLocaleString() + ' – $' + max.toLocaleString();
		return '$' + (max || min).toLocaleString();
	}

	// Load title codes + salary from civil service titles dataset
	$.getJSON('https://data.cityofnewyork.us/resource/nzjr-3966.json?$limit=50000&$select=title,descr,min_rate,max_rate', function(data) {
		data.forEach(function(r) {
			var desc = (r.descr || '').toUpperCase().trim();
			var code = r.title || '';
			if (desc && code) {
				var entry = {code: code, descr: desc, min_rate: r.min_rate, max_rate: r.max_rate};
				titleExact[desc] = entry;
				titleDescrs.push(entry);
			}
		});
		titleReady = true;
		// Re-render any already-displayed links & salary
		$('[data-exam-resolve]').each(function() {
			var examTitle = $(this).attr('data-exam-resolve');
			$(this).attr('href', titleHrefFor(examTitle));
		});
		$('[data-salary-resolve]').each(function() {
			var examTitle = $(this).attr('data-salary-resolve');
			var sal = salaryFor(examTitle);
			if (sal) $(this).text(sal).show();
		});
	});

	// ===== LOAD ALL EXAMS =====
	$.getJSON(API + '?$limit=50000', function(rawData) {
		var data = dedup(rawData);
		var now = [], future = [], all = [];

		data.forEach(function(r) {
			var start = r.application_period_start;
			var end = r.application_period_end_date;

			// Classify
			if (start && end) {
				var s = start.substring(0, 10);
				var e = end.substring(0, 10);
				if (s <= TODAY && e >= TODAY) {
					now.push(r);
				} else if (s > TODAY) {
					future.push(r);
				}
			}
			all.push(r);
		});

		// Sort
		now.sort(function(a, b) { return (a.application_period_end_date || '').localeCompare(b.application_period_end_date || ''); });
		future.sort(function(a, b) { return (a.application_period_start || '').localeCompare(b.application_period_start || ''); });

		// ===== UNIFIED RENDER =====
		$('#exams-loading').hide();

		var allNowExams = now;
		var allFutureExams = future;
		var currentFilter = 'all';
		var currentSearch = '';

		function applyFilters(items) {
			var filtered = items;
			if (currentFilter === 'open') {
				filtered = filtered.filter(function(r) { return (r.open_competitive_promotion || '').toLowerCase().indexOf('open') >= 0; });
			} else if (currentFilter === 'promo') {
				filtered = filtered.filter(function(r) { return (r.open_competitive_promotion || '').toLowerCase().indexOf('promo') >= 0; });
			}
			if (currentSearch) {
				var q = currentSearch.toLowerCase();
				filtered = filtered.filter(function(r) {
					return ((r.exam_title || '').toLowerCase().indexOf(q) >= 0) ||
						((r.exam_number || '').indexOf(q) >= 0) ||
						((r.open_competitive_promotion || '').toLowerCase().indexOf(q) >= 0);
				});
			}
			return filtered;
		}

		function renderAll() {
			var filteredNow = applyFilters(allNowExams);
			var filteredFuture = applyFilters(allFutureExams);
			var total = filteredNow.length + filteredFuture.length;
			$('#exams-count').text(total);
			$('#no-results').toggle(total === 0);

			// Active cards
			$('#now-count').text(filteredNow.length);
			$('#now-header').toggle(filteredNow.length > 0);
			var html = '';
			filteredNow.forEach(function(r) {
				var days = daysUntil(r.application_period_end_date);
				var daysText = days !== null ? (days === 0 ? 'Last day!' : days + ' days left') : '';
				var titleHref = titleHrefFor(r.exam_title);
				var sal = salaryFor(r.exam_title);
				var esc = (r.exam_title || '').replace(/"/g, '&quot;');
				var salaryHtml = sal
					? '<div class="exam-card-salary">' + sal + '</div>'
					: '<div class="exam-card-salary" data-salary-resolve="' + esc + '" style="display:none"></div>';

				html += '<div class="db-card is-hoverable">' +
					'<div class="db-card-body">' +
						'<div class="exam-card-badges">' +
							'<span class="db-badge db-badge-success"><span class="db-dot"></span> Accepting</span>' +
							((r.open_competitive_promotion) ? '<span class="db-type-label">' + r.open_competitive_promotion + '</span>' : '') +
						'</div>' +
						'<div class="exam-card-title"><a href="' + titleHref + '" data-exam-resolve="' + esc + '">' + (r.exam_title || 'Untitled') + '</a></div>' +
						'<div class="exam-card-examno">Exam #' + (r.exam_number || '') + '</div>' +
						salaryHtml +
						'<div class="exam-card-deadline"><i class="bi bi-calendar-event"></i> Apply by <strong>' + fmtDate(r.application_period_end_date) + '</strong>' +
							(daysText ? ' · ' + daysText : '') +
						'</div>' +
						'<div class="exam-card-foot">' +
							'<a href="' + applyUrl(r.exam_number) + '" target="_blank" class="db-btn db-btn-primary db-btn-sm"><i class="bi bi-box-arrow-up-right"></i> Apply</a>' +
							'<a href="' + noeUrl(r.exam_number) + '" target="_blank" class="db-btn db-btn-outline db-btn-sm">Notice</a>' +
							'<a href="' + titleHref + '" data-exam-resolve="' + esc + '" class="db-btn db-btn-ghost db-btn-sm">Title</a>' +
						'</div>' +
					'</div>' +
				'</div>';
			});
			$('#now-cards').html(html);

			// Upcoming rows
			$('#future-count').text(filteredFuture.length);
			$('#future-header').toggle(filteredFuture.length > 0);
			var fhtml = '';
			filteredFuture.forEach(function(r) {
				var titleHref = titleHrefFor(r.exam_title);
				var sal = salaryFor(r.exam_title);
				var esc = (r.exam_title || '').replace(/"/g, '&quot;');
				var salaryBit = sal ? ' · <span class="db-money">' + sal + '</span>' : '';

				fhtml += '<div class="db-list-item">' +
					'<div class="db-list-item-main">' +
						'<div class="db-list-item-title"><a href="' + titleHref + '" data-exam-resolve="' + esc + '">' + (r.exam_title || 'Untitled') + '</a></div>' +
						'<div class="db-list-item-meta">Exam #' + (r.exam_number || '') + ' · ' + (r.open_competitive_promotion || '') + salaryBit + '</div>' +
					'</div>' +
					'<div class="db-list-item-aside">' + fmtDate(r.application_period_start) + ' – ' + fmtDate(r.application_period_end_date) + '</div>' +
					'<div class="exam-actions">' +
						'<a class="db-btn db-btn-outline db-btn-sm" href="' + noeUrl(r.exam_number) + '" target="_blank">NOE</a>' +
						'<a class="db-btn db-btn-primary db-btn-sm" href="' + applyUrl(r.exam_number) + '" target="_blank">Apply</a>' +
					'</div>' +
				'</div>';
			});
			$('#future-list').html(fhtml);
		}

		renderAll();

		// Filter buttons
		$('#exam-filters .db-filter-pill').on('click', function() {
			$('#exam-filters .db-filter-pill').removeClass('is-active');
			$(this).addClass('is-active');
			currentFilter = $(this).data('filter');
			renderAll();
		});

		// Search
		var searchTimer;
		$('#exam-search').on('input', function() {
			var self = this;
			clearTimeout(searchTimer);
			searchTimer = setTimeout(function() {
				currentSearch = $(self).val().trim();
				renderAll();
			}, 200);
		});

		// Toggle full schedule
		$('#toggle-full-schedule').on('click', function() {
			var section = $('#all-section');
			if (section.is(':visible')) {
				section.slideUp(300);
				$(this).html('<i class="bi bi-clock-history"></i> Show Full Exam Schedule');
			} else {
				section.slideDown(300);
				$(this).html('<i class="bi bi-chevron-up"></i> Hide Full Exam Schedule');
			}
		});

		// ===== RENDER: Full Schedule Table =====
		$('#all-loading').hide();
		$('#all-count').text(all.length);
		$('#all-table-wrapper').show();

		$('#all-table').DataTable({
			data: all,
			deferRender: true,
			pageLength: 25,
			order: [[4, 'desc']],
			columns: [
				{data: function(r) { return r.exam_title || ''; }},
				{data: function(r) { return r.exam_number || ''; }},
				{data: function(r) { return r.open_competitive_promotion || ''; }},
				{data: function(r) { return r.application_period_start ? r.application_period_start.substring(0,10) : '—'; }},
				{data: function(r) { return r.application_period_end_date ? r.application_period_end_date.substring(0,10) : '—'; }},
				{data: function(r) {
					return '<a class="db-btn db-btn-outline db-btn-sm" href="' + noeUrl(r.exam_number) + '" target="_blank" style="margin-right:4px">NOE</a>' +
						'<a class="db-btn db-btn-primary db-btn-sm" href="' + applyUrl(r.exam_number) + '" target="_blank">Apply</a>';
				}}
			]
		});

	}).fail(function() {
		$('#now-loading, #future-loading, #all-loading').html('<div class="text-danger">Failed to load exam data. Please try again later.</div>');
	});
});
</script>

@endsection
