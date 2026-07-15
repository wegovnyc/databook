@extends('layout')

@section('head')
	<meta name="description" content="NYC Jobs Dashboard — current openings, civil service exams, salary data, and hiring trends" />
	<style>
		/* titles_overview — db-* design system. Only page-specific glue lives here;
		   hero / stats / panels / list-items / cards / alert all use shared component classes. */

		/* Hero headline metric (right block) */
		.db-hero-metric { flex: 0 0 auto; text-align: right; min-width: 220px; }
		.db-hero-metric .db-hero-figure { color: #fff; font-size: var(--db-text-5xl, 3.2rem); font-weight: var(--db-weight-bold); line-height: 1; font-variant-numeric: tabular-nums; }
		.db-hero-metric .db-hero-figure-label { color: var(--db-accent); font-size: var(--db-text-2xs); font-weight: var(--db-weight-bold); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); margin-top: 6px; }
		.db-hero-metric .db-btn-primary { margin-top: var(--db-space-2); background: var(--db-link); }
		.db-hero-metric .db-btn-primary:hover { background: var(--db-link-hover); }
		@media (max-width: 840px) { .db-hero-metric { text-align: left; min-width: 0; } }

		/* Section head row */
		.db-section-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: var(--db-space-1); margin-bottom: var(--db-space-2); }
		.db-section-head h2 { margin: 0; }

		/* Loading state */
		.exams-loading { text-align: center; padding: var(--db-space-5) var(--db-space-2); color: var(--db-text-muted); }

		/* Ranked agency rows reuse .db-list-item; rank chip + count */
		.db-rank { flex: 0 0 auto; width: 22px; font-size: var(--db-text-2xs); color: var(--db-text-muted); font-weight: var(--db-weight-bold); text-align: center; }
		.db-list-item .db-list-count { flex: 0 0 auto; font-size: var(--db-text-sm); font-weight: var(--db-weight-bold); color: var(--db-primary); font-variant-numeric: tabular-nums; }

		/* Category bar rows (track = gray-100, fill = accent) */
		.db-bar-row { display: flex; align-items: center; gap: var(--db-space-1); margin-bottom: 8px; }
		.db-bar-label { flex: 0 0 132px; font-size: var(--db-text-2xs); color: var(--db-gray-700); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
		.db-bar-track { flex: 1 1 auto; height: 18px; background: var(--db-gray-100); border-radius: var(--db-radius-sm); overflow: hidden; }
		.db-bar-fill { height: 100%; background: var(--db-accent); border-radius: var(--db-radius-sm); transition: width 0.5s ease; }
		.db-bar-count { flex: 0 0 36px; font-size: var(--db-text-2xs); font-weight: var(--db-weight-semibold); color: var(--db-gray-700); text-align: right; font-variant-numeric: tabular-nums; }

		/* Salary distribution bars (navy/accent palette inside .db-chart-card) */
		.db-salary-chart { display: flex; align-items: flex-end; height: 150px; gap: 3px; padding: 0 2px; }
		.db-salary-bar { flex: 1; background: var(--db-primary); border-radius: var(--db-radius-sm) var(--db-radius-sm) 0 0; min-height: 2px; transition: opacity var(--db-transition); }
		.db-salary-bar:hover { opacity: 0.78; }
		.db-salary-axis { display: flex; justify-content: space-between; font-size: var(--db-text-2xs); color: var(--db-text-muted); margin-top: 6px; }
		.db-salary-note { text-align: center; font-size: var(--db-text-2xs); color: var(--db-text-muted); margin-top: 8px; }

		/* Popular-titles card inner layout */
		.db-title-card-name { font-weight: var(--db-weight-bold); font-size: var(--db-text-sm); color: var(--db-primary); line-height: var(--db-leading-snug); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
		.db-title-card-code { font-family: var(--db-font-mono); font-size: var(--db-text-2xs); color: var(--db-text-muted); margin-top: 2px; }
		.db-title-card-foot { display: flex; justify-content: space-between; align-items: baseline; margin-top: var(--db-space-1); }
		.db-title-card-salary { font-size: var(--db-text-xs); font-weight: var(--db-weight-semibold); color: var(--db-success-fg); font-variant-numeric: tabular-nums; }
		.db-title-card-pos { font-size: var(--db-text-2xs); color: var(--db-text-muted); }

		@media (max-width: 768px) {
			.db-bar-label { flex-basis: 96px; }
		}
	</style>
@endsection

@section('menubar')
	@include('sub.menubar', ['active' => 'titles'])
@endsection

@section('content')

{{-- Navy hero band (family-wide "Briefing" treatment) — carries the headline metric + CTA --}}
<div class="db-hero">
	<div class="inner_container">
		<div class="container db-hero-inner">
			<div class="db-hero-copy">
				<div class="db-eyebrow" style="color:var(--db-accent);">Jobs &amp; Exams</div>
				<h1>NYC Jobs Dashboard</h1>
				<p>Current openings, civil-service exams, salaries, and hiring trends across New York City government — updated daily from official sources.</p>
			</div>
			<div class="db-hero-metric">
				<div class="db-hero-figure gs_thousandscomma" id="trend-total">&mdash;</div>
				<div class="db-hero-figure-label">Open Positions Now</div>
				<a href="/jobs" class="db-btn db-btn-primary"><i class="bi bi-briefcase"></i> Browse all jobs</a>
			</div>
		</div>
	</div>
</div>

<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-5);">

		{{-- ACTIVE EXAM BANNER --}}
		<div id="exam-alert-banner" class="db-alert db-alert-success" style="display:none; margin-bottom: var(--db-space-3);">
			<i class="bi bi-lightning-charge-fill"></i>
			<div class="db-alert-body">
				<strong><span id="banner-count">0</span> Civil Service Exams Accepting Applications Now</strong>
				<div style="margin-top:4px;">Apply before the filing period closes:</div>
				<div class="db-tags" id="banner-exams" style="margin-top: var(--db-space-1);"></div>
			</div>
		</div>

		{{-- TREND STATS --}}
		<div class="db-stat-grid" id="trend-row" style="display:none; margin-bottom: var(--db-space-4);">
			<div class="db-stat is-accent">
				<div class="db-stat-label"><i class="bi bi-plus-circle"></i> New This Week</div>
				<div class="db-stat-value gs_thousandscomma" id="trend-new">&mdash;</div>
				<div class="db-stat-delta is-up"><i class="bi bi-arrow-up-short"></i> recent postings</div>
			</div>
			<div class="db-stat">
				<div class="db-stat-label"><i class="bi bi-clock-history"></i> Closing in 14 Days</div>
				<div class="db-stat-value gs_thousandscomma" id="trend-closing">&mdash;</div>
				<div class="db-stat-sub">apply soon</div>
			</div>
			<div class="db-stat">
				<div class="db-stat-label"><i class="bi bi-mortarboard"></i> Exam Required</div>
				<div class="db-stat-value gs_thousandscomma" id="trend-exam-req">&mdash;</div>
				<div class="db-stat-sub">competitive titles</div>
			</div>
			<div class="db-stat">
				<div class="db-stat-label"><i class="bi bi-briefcase"></i> Total Openings</div>
				<div class="db-stat-value gs_thousandscomma" id="stat-total">&mdash;</div>
				<div class="db-stat-sub">across all agencies</div>
			</div>
		</div>

		{{-- Hidden hooks the JS still writes into (layout migrated to stat grid above) --}}
		<div style="display:none" aria-hidden="true">
			<span id="stat-external"></span><span id="stat-internal"></span><span id="stat-intern"></span><span id="stat-competitive"></span>
			<span id="jobs-stats"></span>
		</div>

		{{-- CURRENT JOB OPENINGS --}}
		<div style="margin-bottom: var(--db-space-4);">
			<div class="db-section-head">
				<div>
					<div class="db-eyebrow">Current Openings</div>
					<h2>Where the jobs are right now</h2>
				</div>
				<a href="/jobs" class="db-btn-ghost db-btn-sm">All jobs <i class="bi bi-arrow-right"></i></a>
			</div>

			<div id="jobs-loading" class="exams-loading">
				<div class="db-spinner db-spinner-lg" style="margin: 0 auto;"></div>
				<div class="mt-2">Loading job postings…</div>
			</div>

			<div id="jobs-panels" class="row g-3" style="display:none">
				<div class="col-md-4">
					<div class="db-panel db-panel-fixed">
						<div class="db-panel-head">
							<i class="bi bi-globe2" style="color:var(--db-primary)"></i>
							<div>
								<div class="db-panel-title">External</div>
								<div class="db-panel-sub">Open to all applicants</div>
							</div>
							<span class="db-badge db-badge-navy" id="ext-count" style="margin-left:auto;">0</span>
						</div>
						<div class="db-panel-body" id="jobs-external-list"></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="db-panel db-panel-fixed">
						<div class="db-panel-head">
							<i class="bi bi-building" style="color:var(--db-gray-500)"></i>
							<div>
								<div class="db-panel-title">Internal</div>
								<div class="db-panel-sub">Current city employees only</div>
							</div>
							<span class="db-badge db-badge-neutral" id="int-count" style="margin-left:auto;">0</span>
						</div>
						<div class="db-panel-body" id="jobs-internal-list"></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="db-panel db-panel-fixed">
						<div class="db-panel-head">
							<i class="bi bi-clock-history" style="color:var(--db-info-fg)"></i>
							<div>
								<div class="db-panel-title">Recently Posted</div>
								<div class="db-panel-sub">Added in the last 30 days</div>
							</div>
							<span class="db-badge db-badge-info" id="recent-count" style="margin-left:auto;">0</span>
						</div>
						<div class="db-panel-body" id="jobs-recent-list"></div>
					</div>
				</div>
			</div>
		</div>

		{{-- INSIGHTS ROW: Agencies, Categories, Salary --}}
		<div class="row g-3" id="insights-row" style="display:none; margin-bottom: var(--db-space-4);">
			<div class="col-md-4">
				<div class="db-panel" style="height:380px">
					<div class="db-panel-head">
						<i class="bi bi-bank" style="color:var(--db-primary)"></i>
						<div>
							<div class="db-panel-title">Top Hiring Agencies</div>
							<div class="db-panel-sub">Most current openings</div>
						</div>
					</div>
					<div class="db-panel-body" id="agency-list"></div>
				</div>
			</div>
			<div class="col-md-4">
				<div class="db-panel" style="height:380px">
					<div class="db-panel-head">
						<i class="bi bi-list-ul" style="color:var(--db-gray-500)"></i>
						<div>
							<div class="db-panel-title">Jobs by Category</div>
							<div class="db-panel-sub">Distribution across departments</div>
						</div>
					</div>
					<div class="db-panel-body" id="category-list" style="padding: var(--db-space-15) var(--db-space-2);"></div>
				</div>
			</div>
			<div class="col-md-4">
				<div class="db-chart-card" style="height:380px; display:flex; flex-direction:column;">
					<div class="db-eyebrow" style="margin-bottom: var(--db-space-1);"><i class="bi bi-cash-stack"></i> Salary Distribution</div>
					<div class="db-panel-sub" style="margin-bottom: var(--db-space-2);">Annual salary ranges across all jobs</div>
					<div id="salary-chart-area" style="flex:1 1 auto;"></div>
				</div>
			</div>
		</div>

		@if($data && isset($data['top_lists']['agencies']))
		{{-- POPULAR TITLES CARDS --}}
		<div style="margin-bottom: var(--db-space-4);">
			<div class="db-section-head">
				<div>
					<div class="db-eyebrow">Civil Service</div>
					<h2>Popular Civil Service Titles</h2>
				</div>
				<a href="{{ route('titles') }}" class="db-btn-ghost db-btn-sm">See all titles <i class="bi bi-arrow-right"></i></a>
			</div>
			<div class="row g-3">
				@foreach(array_slice($data['top_lists']['agencies'], 0, 8) as $row)
				<div class="col-md-3 col-sm-6">
					<a href="{!! route('title', ['id' => $row['Title Code']]) !!}" class="text-decoration-none">
						<div class="db-card is-hoverable h-100">
							<div class="db-card-body">
								<div class="db-title-card-name" title="{!! $row['Title Description'] !!}">{!! $row['Title Description'] !!}</div>
								<div class="db-title-card-code">{!! $row['Title Code'] !!}</div>
								<div class="db-title-card-foot">
									<span class="db-title-card-salary">${{ number_format($row['Minimum Salary']) }} – ${{ number_format($row['Maximum Salary']) }}</span>
									<span class="db-title-card-pos">{!! number_format($row['Total Positions using this Title']) !!} pos.</span>
								</div>
							</div>
						</div>
					</a>
				</div>
				@endforeach
			</div>
		</div>
		@endif

		{{-- CIVIL SERVICE EXAMS --}}
		<div style="margin-bottom: var(--db-space-4);">
			<div class="db-section-head">
				<div>
					<div class="db-eyebrow">Civil Service</div>
					<h2>Civil Service Exams</h2>
				</div>
				<a href="{{ route('jobsExams') }}" class="db-btn-ghost db-btn-sm">All exams <i class="bi bi-arrow-right"></i></a>
			</div>

			<div id="exams-loading" class="exams-loading">
				<div class="db-spinner db-spinner-lg" style="margin: 0 auto;"></div>
				<div class="mt-2">Loading exam schedule…</div>
			</div>

			<div id="exams-panels" class="row g-3" style="display:none">
				<div class="col-md-6">
					<div class="db-panel" style="height:420px">
						<div class="db-panel-head">
							<i class="bi bi-lightning-charge-fill" style="color:var(--db-warning-fg)"></i>
							<div>
								<div class="db-panel-title">Accepting Applications</div>
								<div class="db-panel-sub">Currently open for application</div>
							</div>
							<span class="db-badge db-badge-success" id="now-count" style="margin-left:auto;">0</span>
						</div>
						<div class="db-panel-body" id="now-list"></div>
					</div>
				</div>
				<div class="col-md-6">
					<div class="db-panel" style="height:420px">
						<div class="db-panel-head">
							<i class="bi bi-calendar-event" style="color:var(--db-primary)"></i>
							<div>
								<div class="db-panel-title">Upcoming</div>
								<div class="db-panel-sub">Scheduled for future application periods</div>
							</div>
							<span class="db-badge db-badge-navy" id="future-count" style="margin-left:auto;">0</span>
						</div>
						<div class="db-panel-body" id="future-list"></div>
					</div>
				</div>
			</div>
		</div>

	</div>
</div>

<script>
$(document).ready(function() {
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
		var dt = parseFlexDate ? parseFlexDate(d) : new Date(d); var now = new Date();
		if (!dt || isNaN(dt)) return null;
		now.setHours(0,0,0,0); dt.setHours(0,0,0,0);
		return Math.ceil((dt - now) / 86400000);
	}
	function daysSince(d) {
		if (!d) return 9999;
		var dt = parseFlexDate(d); var now = new Date();
		if (!dt || isNaN(dt)) return 9999;
		now.setHours(0,0,0,0); dt.setHours(0,0,0,0);
		return Math.floor((now - dt) / 86400000);
	}
	// Parse dates in MM/DD/YYYY, DD-MMM-YYYY, or ISO formats
	function parseFlexDate(d) {
		if (!d) return null;
		var s = d.toString().trim();
		// MM/DD/YYYY
		var m1 = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
		if (m1) return new Date(parseInt(m1[3]), parseInt(m1[1])-1, parseInt(m1[2]));
		// DD-MMM-YYYY (e.g. 01-APR-2026)
		var months = {JAN:0,FEB:1,MAR:2,APR:3,MAY:4,JUN:5,JUL:6,AUG:7,SEP:8,OCT:9,NOV:10,DEC:11};
		var m2 = s.match(/^(\d{1,2})-(\w{3})-(\d{4})/);
		if (m2 && months[m2[2].toUpperCase()] !== undefined) return new Date(parseInt(m2[3]), months[m2[2].toUpperCase()], parseInt(m2[1]));
		// ISO fallback
		return new Date(s);
	}
	function slugify(str) {
		return (str||'').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
	}
	function noeUrl(n) { return 'https://a856-exams.nyc.gov/OASysWeb/noe/' + YEAR + n + '000.pdf'; }
	function applyUrl(n) { return 'https://a856-exams.nyc.gov/OASysWeb/login?returnUrl=%2Fexam-application%2F' + n; }

	// Title matching
	var titleExact = {};
	var titleDescrs = [];

	function cleanExamTitle(t) {
		var c = (t || '').split('\n')[0];
		while (/\s*\([^)]*\)\s*$/.test(c)) c = c.replace(/\s*\([^)]*\)\s*$/, '');
		return c.trim().toUpperCase();
	}
	function findTitleInfo(t) {
		var c = cleanExamTitle(t);
		if (!c) return null;
		if (titleExact[c]) return titleExact[c];
		for (var i = 0; i < titleDescrs.length; i++) {
			var d = titleDescrs[i];
			if (c.indexOf(d.descr) === 0 || d.descr.indexOf(c) === 0) return d;
		}
		return null;
	}
	function titleHrefFor(t) {
		var info = findTitleInfo(t);
		if (info) return '/t/' + info.code;
		return '/titles?search=' + encodeURIComponent(cleanExamTitle(t));
	}
	function salaryFor(t) {
		var info = findTitleInfo(t);
		if (!info || !info.min_rate) return null;
		var min = parseInt(info.min_rate) || 0, max = parseInt(info.max_rate) || 0;
		if (!min && !max) return null;
		if (min && max && min !== max) return '$' + min.toLocaleString() + ' – $' + max.toLocaleString();
		return '$' + (max || min).toLocaleString();
	}

	// Load titles for matching
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
		$('[data-exam-resolve]').each(function() {
			$(this).attr('href', titleHrefFor($(this).attr('data-exam-resolve')));
		});
		$('[data-salary-resolve]').each(function() {
			var sal = salaryFor($(this).attr('data-salary-resolve'));
			if (sal) $(this).html('<i class="bi bi-cash-stack"></i> ' + sal).show();
		});
	});

	// Load exams
	$.getJSON(API + '?$limit=50000', function(rawData) {
		var map = {};
		rawData.forEach(function(r) {
			var k = r.exam_number;
			if (!map[k] || (r.data_current_as_of || '') > (map[k].data_current_as_of || '')) map[k] = r;
		});
		var data = Object.values(map);
		var now = [], future = [];

		data.forEach(function(r) {
			var status = (r.open_competitive_promotion || '').toLowerCase();
			if (status === 'canceled' || status === 'postponed') return;
			var start = r.application_period_start, end = r.application_period_end_date;
			if (start && end) {
				var s = start.substring(0,10), e = end.substring(0,10);
				if (s <= TODAY && e >= TODAY) now.push(r);
				else if (s > TODAY) future.push(r);
			}
		});

		now.sort(function(a,b) { return (a.application_period_end_date||'').localeCompare(b.application_period_end_date||''); });
		future.sort(function(a,b) { return (a.application_period_start||'').localeCompare(b.application_period_start||''); });

		$('#exams-loading').hide();
		$('#exams-panels').show();

		$('#now-count').text(now.length);
		$('#future-count').text(future.length);

		// Active Exam Banner
		if (now.length > 0) {
			$('#banner-count').text(now.length);
			var bannerHtml = '';
			now.forEach(function(r) {
				var days = daysUntil(r.application_period_end_date);
				var label = (r.exam_title || '') + (days !== null ? ' (' + days + 'd left)' : '');
				bannerHtml += '<a class="db-tag" href="' + noeUrl(r.exam_number) + '" target="_blank"><i class="bi bi-file-earmark-pdf"></i> ' + label + '</a>';
			});
			$('#banner-exams').html(bannerHtml);
			$('#exam-alert-banner').css('display', 'flex');
		}

		function renderExamItem(r, isActive) {
			var sal = salaryFor(r.exam_title);
			var salBit = sal ? ' · <span class="db-money">' + sal + '</span>' : '';
			var days = isActive ? daysUntil(r.application_period_end_date) : null;
			var dateText = isActive
				? (days === 0 ? 'Last day!' : (days !== null ? days + 'd left' : ''))
				: fmtDate(r.application_period_start);
			var titleHref = titleHrefFor(r.exam_title);
			var esc = (r.exam_title||'').replace(/"/g,'&quot;');

			return '<div class="db-list-item">' +
				'<div class="db-list-item-main">' +
					'<div class="db-list-item-title"><a href="' + titleHref + '" data-exam-resolve="' + esc + '">' + (r.exam_title||'') + '</a></div>' +
					'<div class="db-list-item-meta">Exam #' + (r.exam_number||'') + ' · ' + (r.open_competitive_promotion||'') + salBit + '</div>' +
				'</div>' +
				(dateText ? '<div class="db-list-item-aside is-swap">' + dateText + '</div>' : '') +
				'<div class="db-list-item-actions">' +
				'<a class="db-btn db-btn-outline db-btn-sm" href="' + noeUrl(r.exam_number) + '" target="_blank"><i class="bi bi-file-earmark-pdf"></i> Notice</a>' +
				'<a class="db-btn db-btn-primary db-btn-sm" href="' + applyUrl(r.exam_number) + '" target="_blank"><i class="bi bi-pencil"></i> Apply</a>' +
				'<a class="db-btn db-btn-ghost db-btn-sm" href="' + titleHref + '" data-exam-resolve="' + esc + '"><i class="bi bi-person-badge"></i> Title</a>' +
				'</div></div>';
		}

		var nowHtml = '';
		now.forEach(function(r) { nowHtml += renderExamItem(r, true); });
		$('#now-list').html(nowHtml);

		var futureHtml = '';
		future.forEach(function(r) { futureHtml += renderExamItem(r, false); });
		$('#future-list').html(futureHtml);

	}).fail(function() {
		$('#exams-loading').html('<div class="text-danger">Failed to load exam data.</div>');
	});

	// ===== LOAD JOBS =====
	function normalizeJob(j) {
		return {
			jobId: j['Job ID'] || j['job_id'] || '',
			title: j['Business Title'] || j['business_title'] || j['Civil Service Title'] || j['civil_service_title'] || '',
			agency: j['wegov-org-name'] || j['Agency'] || j['agency'] || '',
			agencyId: j['wegov-org-id'] || '',
			salaryFrom: j['Salary Range From'] || j['salary_range_from'] || '',
			salaryTo: j['Salary Range To'] || j['salary_range_to'] || '',
			salaryFreq: j['Salary Frequency'] || j['salary_frequency'] || '',
			postingType: j['Posting Type'] || j['posting_type'] || '',
			careerLevel: j['Career Level'] || j['career_level'] || '',
			titleCode: j['Title Code No'] || j['title_code_no'] || '',
			postingDate: j['Posting Date'] || j['posting_date'] || '',
			postUntil: j['Post Until'] || j['post_until'] || '',
			category: j['Job Category'] || j['job_category'] || '',
			classification: j['Title Classification'] || j['title_classification'] || ''
		};
	}

	function processJobs(jobs) {
		$('#jobs-loading').hide();
		var allNorm = jobs.map(normalizeJob);
		var external = [], internal = [], recent = [];
		var agencyCount = {}, catCount = {};
		var salaryBuckets = [0,0,0,0,0,0,0,0]; // <30k, 30-50, 50-70, 70-90, 90-110, 110-130, 130-150, 150+
		var salaryLabels = ['<30K','30-50K','50-70K','70-90K','90-110K','110-130K','130-150K','150K+'];
		var competitiveCount = 0;
		var newThisWeek = 0;
		var closingSoon = 0;

		allNorm.forEach(function(j) {
			var isHourly = j.salaryFreq.toLowerCase() !== 'annual';
			var isStudent = j.careerLevel.toLowerCase() === 'student';
			var isInternal = j.postingType.toLowerCase().indexOf('internal') >= 0;

			// Classify for panels
			if (isInternal) internal.push(j);
			else external.push(j);

			// Recently posted (last 30 days)
			if (daysSince(j.postingDate) <= 30) {
				recent.push(j);
			}
			if (daysSince(j.postingDate) <= 7) newThisWeek++;

			// Closing soon
			if (j.postUntil) {
				var dClose = daysUntil(j.postUntil);
				if (dClose !== null && dClose >= 0 && dClose <= 14) closingSoon++;
			}

			// Competitive / Exam Required
			if (j.classification && j.classification.indexOf('Competitive') === 0) competitiveCount++;

			// Agency counts
			var ag = j.agency || 'Unknown';
			agencyCount[ag] = (agencyCount[ag] || 0) + 1;

			// Category counts
			var cat = j.category || 'Other';
			catCount[cat] = (catCount[cat] || 0) + 1;

			// Salary distribution (annual only)
			if (!isHourly) {
				var sal = parseInt(j.salaryTo) || parseInt(j.salaryFrom) || 0;
				if (sal > 0) {
					var k = sal / 1000;
					if (k < 30) salaryBuckets[0]++;
					else if (k < 50) salaryBuckets[1]++;
					else if (k < 70) salaryBuckets[2]++;
					else if (k < 90) salaryBuckets[3]++;
					else if (k < 110) salaryBuckets[4]++;
					else if (k < 130) salaryBuckets[5]++;
					else if (k < 150) salaryBuckets[6]++;
					else salaryBuckets[7]++;
				}
			}
		});

		// Sort recent by posting date descending
		recent.sort(function(a,b) { return (b.postingDate||'').localeCompare(a.postingDate||''); });

		// Stats bar
		$('#stat-total').text(allNorm.length.toLocaleString());
		$('#stat-external').text(external.length.toLocaleString());
		$('#stat-internal').text(internal.length.toLocaleString());
		$('#stat-intern').text((allNorm.length - external.length - internal.length).toLocaleString());
		$('#stat-competitive').text(competitiveCount.toLocaleString());
		$('#ext-count').text(external.length);
		$('#int-count').text(internal.length);
		$('#recent-count').text(recent.length);
		$('#jobs-stats').css('display','flex');
		$('#jobs-panels').show();

		// Trend indicators
		$('#trend-total').text(allNorm.length.toLocaleString());
		$('#trend-new').html('<i class="bi bi-arrow-up-short"></i> ' + newThisWeek);
		$('#trend-closing').html('<i class="bi bi-clock-history"></i> ' + closingSoon);
		$('#trend-exam-req').text(competitiveCount.toLocaleString());
		$('#trend-row').css('display', 'grid');

		function fmtSal(from, to, freq) {
			var f = parseInt(from)||0, t = parseInt(to)||0;
			var s = (freq||'').toLowerCase()==='hourly' ? '/hr' : '';
			if (f && t && f!==t) return '$'+f.toLocaleString()+'–$'+t.toLocaleString()+s;
			return '$'+(t||f).toLocaleString()+s;
		}

		function renderItems(arr, target) {
			var html = '';
			arr.forEach(function(j) {
				var tc = (j.titleCode||'').trim();
				var th = tc ? '/t/'+tc : '/titles';
				var sal = (j.salaryFrom||j.salaryTo) ? fmtSal(j.salaryFrom,j.salaryTo,j.salaryFreq) : '';
				var salBit = sal ? ' · <span class="db-money">'+sal+'</span>' : '';
				var posted = j.postingDate ? fmtDate(j.postingDate) : '';
				html += '<div class="db-list-item">' +
					'<div class="db-list-item-main">' +
						'<div class="db-list-item-title" title="'+(j.title||'').replace(/"/g,'&quot;')+'">'+(j.title||'')+'</div>' +
						'<div class="db-list-item-meta">'+(j.agency||'')+salBit+'</div>' +
					'</div>' +
					(posted ? '<div class="db-list-item-aside is-swap">'+posted+'</div>' : '') +
					'<div class="db-list-item-actions">' +
					'<a class="db-btn db-btn-outline db-btn-sm" href="https://cityjobs.nyc.gov/jobs?q='+(j.jobId||'')+'" target="_blank"><i class="bi bi-box-arrow-up-right"></i> View</a>' +
					'<a class="db-btn db-btn-ghost db-btn-sm" href="'+th+'"><i class="bi bi-person-badge"></i> Title</a>' +
					'</div></div>';
			});
			$(target).html(html);
		}

		renderItems(external, '#jobs-external-list');
		renderItems(internal, '#jobs-internal-list');
		renderItems(recent, '#jobs-recent-list');

		// ===== INSIGHTS =====
		$('#insights-row').show();

		// Top Hiring Agencies (top 10)
		var agSorted = Object.entries(agencyCount).sort(function(a,b) { return b[1] - a[1]; }).slice(0, 10);
		var agHtml = '';
		agSorted.forEach(function(a, i) {
			var name = a[0], count = a[1];
			agHtml += '<div class="db-list-item">' +
				'<div class="db-rank">' + (i+1) + '</div>' +
				'<div class="db-list-item-main"><div class="db-list-item-title"><a href="/organizations?search=' + encodeURIComponent(name) + '">' + name + '</a></div></div>' +
				'<div class="db-list-count">' + count + '</div>' +
				'</div>';
		});
		$('#agency-list').html(agHtml);

		// Jobs by Category (top 8)
		var catSorted = Object.entries(catCount).sort(function(a,b) { return b[1] - a[1]; }).slice(0, 8);
		var maxCat = catSorted.length ? catSorted[0][1] : 1;
		var catHtml = '';
		catSorted.forEach(function(c) {
			var pct = Math.round((c[1] / maxCat) * 100);
			catHtml += '<div class="db-bar-row">' +
				'<div class="db-bar-label" title="' + c[0] + '">' + c[0] + '</div>' +
				'<div class="db-bar-track"><div class="db-bar-fill" style="width:' + pct + '%"></div></div>' +
				'<div class="db-bar-count">' + c[1] + '</div>' +
				'</div>';
		});
		$('#category-list').html(catHtml);

		// Salary Distribution Chart (navy bars inside .db-chart-card)
		var maxBucket = Math.max.apply(null, salaryBuckets) || 1;
		var chartHtml = '<div class="db-salary-chart">';
		salaryBuckets.forEach(function(count, i) {
			var pct = Math.round((count / maxBucket) * 100);
			chartHtml += '<div class="db-salary-bar" style="height:' + Math.max(pct, 2) + '%" title="' + salaryLabels[i] + ': ' + count + ' jobs"></div>';
		});
		chartHtml += '</div>';
		chartHtml += '<div class="db-salary-axis">';
		salaryLabels.forEach(function(l) {
			chartHtml += '<span>' + l + '</span>';
		});
		chartHtml += '</div>';
		chartHtml += '<div class="db-salary-note">' + allNorm.filter(function(j){return j.salaryFreq.toLowerCase()==='annual';}).length + ' salaried positions</div>';
		$('#salary-chart-area').html(chartHtml);
	}

	// Try Databook API first, fall back to Socrata
	fapireq('{!! $jobsUrl !!}', function(resp) {
		var jobs = resp.data || [];
		if (jobs.length > 0) {
			processJobs(jobs);
		} else {
			// Fallback to Socrata API
			$.getJSON('https://data.cityofnewyork.us/resource/kpav-sd4t.json?$limit=5000&$order=posting_date DESC', function(sJobs) {
				processJobs(sJobs);
			}).fail(function() {
				$('#jobs-loading').html('<div class="text-danger">Failed to load job data.</div>');
			});
		}
	});
});
</script>

@endsection
