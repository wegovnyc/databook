@extends('layout')

@section('head')
	<meta name="description" content="Browse all current NYC job postings with filters by agency, category, salary, and more" />
	<style>
		/* Jobs Browser — db-* design system. Only page-specific glue lives here;
		   facets/pills/range/cards/badges all use the shared component classes. */

		/* Job card (light .db-card) inner layout */
		.jc-badges { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: var(--db-space-1); }
		.jc-title { font-size: var(--db-text-md); font-weight: var(--db-weight-bold); color: var(--db-primary); line-height: var(--db-leading-snug); margin: 2px 0;
			display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
		.jc-agency { font-size: var(--db-text-sm); color: var(--db-text-muted); margin: 4px 0; display: flex; align-items: center; gap: 6px;
			white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
		.jc-agency a { color: var(--db-link); }
		.jc-agency a:hover { color: var(--db-link-hover); }
		.jc-salary { font-weight: var(--db-weight-bold); color: var(--db-primary); font-variant-numeric: tabular-nums; margin: var(--db-space-1) 0; }
		.jc-footer { display: flex; justify-content: space-between; align-items: center; gap: var(--db-space-1);
			margin-top: var(--db-space-15); padding-top: var(--db-space-15); border-top: 1px solid var(--db-border); }
		.jc-date { font-size: var(--db-text-2xs); color: var(--db-text-muted); display: flex; align-items: center; gap: 5px; }
		.jc-links { display: inline-flex; gap: 6px; flex-shrink: 0; }
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
				<h1>NYC Jobs</h1>
				<p>Browse <strong id="hero-count" style="color:#fff;">—</strong> current openings across NYC government agencies — filter by agency, salary, category, and exam status.</p>
			</div>
		</div>
	</div>
</div>

<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

		{{-- Mobile filters toggle --}}
		<button class="db-btn db-btn-outline db-btn-sm db-facets-toggle" id="facets-toggle" style="margin-bottom: var(--db-space-2);">
			<i class="bi bi-funnel"></i> Filters
		</button>

		<div class="db-layout-facets">
			{{-- SIDEBAR --}}
			<aside class="db-facets" id="jobs-sidebar">
				<div class="db-facet">
					<label class="db-facet-label">Search</label>
					<div class="db-search" style="max-width:100%;">
						<i class="bi bi-search"></i>
						<input type="text" id="f-search" placeholder="Job title or keyword…">
					</div>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Career Level</label>
					<div class="db-filter-pills" id="f-career">
						<div class="db-filter-pill" data-val="">All</div>
						<div class="db-filter-pill" data-val="Entry-Level">Entry</div>
						<div class="db-filter-pill" data-val="Experienced (non-manager)">Experienced</div>
						<div class="db-filter-pill" data-val="Manager">Manager</div>
						<div class="db-filter-pill" data-val="Executive">Executive</div>
						<div class="db-filter-pill" data-val="Student">Student</div>
					</div>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Posting Type</label>
					<div class="db-filter-pills" id="f-posting">
						<div class="db-filter-pill" data-val="">All</div>
						<div class="db-filter-pill" data-val="External">External</div>
						<div class="db-filter-pill" data-val="Internal">Internal</div>
					</div>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Pay Type</label>
					<div class="db-filter-pills" id="f-salfreq">
						<div class="db-filter-pill" data-val="">All</div>
						<div class="db-filter-pill" data-val="Annual">Annual</div>
						<div class="db-filter-pill" data-val="Hourly">Hourly</div>
						<div class="db-filter-pill" data-val="Daily">Daily</div>
					</div>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Full / Part Time</label>
					<div class="db-filter-pills" id="f-fullpart">
						<div class="db-filter-pill" data-val="">All</div>
						<div class="db-filter-pill" data-val="F">Full-Time</div>
						<div class="db-filter-pill" data-val="P">Part-Time</div>
					</div>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Salary Minimum</label>
					<div class="db-range">
						<div class="db-range-display" id="sal-display">Any</div>
						<input type="range" id="f-salary" min="0" max="250000" step="5000" value="0">
						<div style="display:flex; justify-content:space-between; font-size:var(--db-text-2xs); color:var(--db-text-muted);"><span>$0</span><span>$250K+</span></div>
					</div>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Agency</label>
					<select id="f-agency" class="db-input"><option value="">All Agencies</option></select>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Job Category</label>
					<select id="f-category" class="db-input"><option value="">All Categories</option></select>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Title Classification</label>
					<select id="f-classification" class="db-input"><option value="">All Classifications</option></select>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Civil Service Exam</label>
					<div class="db-filter-pills" id="f-exam">
						<div class="db-filter-pill" data-val="">All</div>
						<div class="db-filter-pill" data-val="active">Active Exam</div>
						<div class="db-filter-pill" data-val="upcoming">Upcoming Exam</div>
					</div>
				</div>

				<div class="db-facet">
					<label class="db-facet-label">Posted</label>
					<div class="db-filter-pills" id="f-posted">
						<div class="db-filter-pill" data-val="">Any</div>
						<div class="db-filter-pill" data-val="7">7d</div>
						<div class="db-filter-pill" data-val="30">30d</div>
						<div class="db-filter-pill" data-val="90">90d</div>
					</div>
				</div>

				<button class="db-btn db-btn-ghost db-btn-sm" id="clear-all"><i class="bi bi-x-circle"></i> Clear All Filters</button>
			</aside>

			{{-- CONTENT --}}
			<div class="jobs-content" style="min-width:0;">
				<div class="db-results-head">
					<div class="db-results-count">
						Showing <strong id="shown-count">—</strong> of <strong id="total-count">—</strong> jobs
					</div>
					<div class="db-active-filters" id="active-filters"></div>
					<div class="db-spacer"></div>
					<label class="db-facet-label" for="sort-by" style="margin:0;">Sort</label>
					<select id="sort-by" class="db-input" style="width:auto;">
						<option value="date-desc">Newest First</option>
						<option value="date-asc">Oldest First</option>
						<option value="salary-desc">Highest Salary</option>
						<option value="salary-asc">Lowest Salary</option>
						<option value="agency-asc">Agency A–Z</option>
						<option value="title-asc">Title A–Z</option>
					</select>
				</div>

				<div id="jobs-loading" style="text-align:center; padding: var(--db-space-5) var(--db-space-2); color: var(--db-text-muted);">
					<div class="db-spinner db-spinner-lg" style="margin:0 auto var(--db-space-1);"></div>
					<div>Loading job postings…</div>
				</div>

				<div class="db-jobs-grid" id="job-cards" style="display:none"></div>

				<div class="db-empty" id="no-results" style="display:none">
					<div class="db-empty-icon"><i class="bi bi-search"></i></div>
					<div class="db-empty-title">No jobs match your filters</div>
					<div class="db-empty-text">Try adjusting your criteria.</div>
				</div>
			</div>
		</div>
	</div>
</div>

<script>
$(document).ready(function() {
	var ALL_JOBS = [];
	var EXAMS_MAP = {}; // title_code => exam info

	// ===== Normalize job row (handles both Databook API and Socrata column names) =====
	function norm(j) {
		return {
			jobId: j['Job ID'] || j['job_id'] || '',
			title: j['Business Title'] || j['business_title'] || '',
			csTitle: j['Civil Service Title'] || j['civil_service_title'] || '',
			agency: j['wegov-org-name'] || j['Agency'] || j['agency'] || '',
			agencyId: j['wegov-org-id'] || '',
			salaryFrom: parseFloat(j['Salary Range From'] || j['salary_range_from'] || 0) || 0,
			salaryTo: parseFloat(j['Salary Range To'] || j['salary_range_to'] || 0) || 0,
			salaryFreq: j['Salary Frequency'] || j['salary_frequency'] || '',
			postingType: j['Posting Type'] || j['posting_type'] || '',
			careerLevel: j['Career Level'] || j['career_level'] || '',
			titleCode: (j['Title Code No'] || j['title_code_no'] || '').trim(),
			postingDate: j['Posting Date'] || j['posting_date'] || '',
			postUntil: j['Post Until'] || j['post_until'] || '',
			fullPart: j['Full-Time/Part-Time indicator'] || j['full_time_part_time_indicator'] || '',
			category: j['Job Category'] || j['job_category'] || '',
			classification: j['Title Classification'] || j['title_classification'] || '',
			location: j['Work Location'] || j['work_location'] || '',
			positions: j['# Of Positions'] || j['_of_positions'] || '1',
			level: j['Level'] || j['level'] || ''
		};
	}

	// ===== Format helpers =====
	function slugify(str) {
		return (str||'').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
	}

	// NOE PDF: https://a856-exams.nyc.gov/OASysWeb/noe/{year}{examNumber}000.pdf
	function noeUrl(exam) {
		var year = exam.start ? exam.start.substring(0, 4) : new Date().getFullYear().toString();
		return 'https://a856-exams.nyc.gov/OASysWeb/noe/' + year + exam.number + '000.pdf';
	}
	var DCAS_UPDATES_URL = 'https://www.nyc.gov/site/dcas/about/citywide-administrative-services-newsletter-sign-up.page';

	function fmtSalary(from, to, freq) {
		var f = Math.round(from), t = Math.round(to);
		var suffix = freq.toLowerCase() === 'hourly' ? '/hr' : freq.toLowerCase() === 'daily' ? '/day' : '';
		if (f && t && f !== t) return '$' + f.toLocaleString() + ' – $' + t.toLocaleString() + suffix;
		return '$' + (t || f).toLocaleString() + suffix;
	}

	function relDate(dateStr) {
		if (!dateStr) return '';
		var parts = dateStr.split('/');
		if (parts.length < 3) return dateStr;
		var d = new Date(parts[2].length === 2 ? '20'+parts[2] : parts[2], parts[0]-1, parts[1]);
		var diff = Math.floor((Date.now() - d.getTime()) / 86400000);
		if (diff < 0) return 'Just posted';
		if (diff === 0) return 'Today';
		if (diff === 1) return 'Yesterday';
		if (diff < 7) return diff + 'd ago';
		if (diff < 30) return Math.floor(diff/7) + 'w ago';
		if (diff < 365) return Math.floor(diff/30) + 'mo ago';
		return Math.floor(diff/365) + 'y ago';
	}

	function parseDateForSort(dateStr) {
		if (!dateStr) return 0;
		var parts = dateStr.split('/');
		if (parts.length < 3) return 0;
		var y = parts[2].length === 2 ? '20'+parts[2] : parts[2];
		return new Date(y, parts[0]-1, parts[1]).getTime();
	}

	function daysSince(dateStr) {
		if (!dateStr) return 9999;
		var parts = dateStr.split('/');
		if (parts.length < 3) return 9999;
		var d = new Date(parts[2].length === 2 ? '20'+parts[2] : parts[2], parts[0]-1, parts[1]);
		return Math.floor((Date.now() - d.getTime()) / 86400000);
	}

	// ===== Build dropdowns from data =====
	function populateDropdowns(jobs) {
		var agencies = {}, categories = {}, classifications = {};
		jobs.forEach(function(j) {
			if (j.agency) agencies[j.agency] = (agencies[j.agency]||0) + 1;
			if (j.category) categories[j.category] = (categories[j.category]||0) + 1;
			if (j.classification) classifications[j.classification] = (classifications[j.classification]||0) + 1;
		});

		function fillSelect(sel, map) {
			var sorted = Object.entries(map).sort(function(a,b) { return b[1]-a[1]; });
			sorted.forEach(function(entry) {
				$(sel).append('<option value="'+entry[0]+'">'+entry[0]+' ('+entry[1]+')</option>');
			});
		}
		fillSelect('#f-agency', agencies);
		fillSelect('#f-category', categories);
		fillSelect('#f-classification', classifications);
	}

	// ===== Filter & Render =====
	function getFilters() {
		return {
			search: $('#f-search').val().toLowerCase().trim(),
			career: $('#f-career .db-filter-pill.is-active').data('val') || '',
			posting: $('#f-posting .db-filter-pill.is-active').data('val') || '',
			salfreq: $('#f-salfreq .db-filter-pill.is-active').data('val') || '',
			fullpart: $('#f-fullpart .db-filter-pill.is-active').data('val') || '',
			salaryMin: parseInt($('#f-salary').val()) || 0,
			agency: $('#f-agency').val() || '',
			category: $('#f-category').val() || '',
			classification: $('#f-classification').val() || '',
			posted: parseInt($('#f-posted .db-filter-pill.is-active').data('val')) || 0,
			hasExam: $('#f-exam .db-filter-pill.is-active').data('val') || '',
			sort: $('#sort-by').val()
		};
	}

	function matchesFilter(j, f) {
		if (f.search && j.title.toLowerCase().indexOf(f.search) < 0 &&
			j.csTitle.toLowerCase().indexOf(f.search) < 0 &&
			j.agency.toLowerCase().indexOf(f.search) < 0) return false;
		if (f.career && j.careerLevel !== f.career) return false;
		if (f.posting && j.postingType !== f.posting) return false;
		if (f.salfreq && j.salaryFreq !== f.salfreq) return false;
		if (f.fullpart && j.fullPart !== f.fullpart) return false;
		if (f.salaryMin > 0) {
			var sal = j.salaryTo || j.salaryFrom;
			if (sal < f.salaryMin) return false;
		}
		if (f.agency && j.agency !== f.agency) return false;
		if (f.category && j.category !== f.category) return false;
		if (f.classification && j.classification !== f.classification) return false;
		if (f.posted && daysSince(j.postingDate) > f.posted) return false;
		if (f.hasExam === 'active' && !j._activeExam) return false;
		if (f.hasExam === 'upcoming' && !j._upcomingExam) return false;
		if (f.hasExam === 'any' && !j._exam) return false;
		return true;
	}

	function sortJobs(jobs, sortKey) {
		var sorted = jobs.slice();
		switch(sortKey) {
			case 'date-desc': sorted.sort(function(a,b) { return parseDateForSort(b.postingDate) - parseDateForSort(a.postingDate); }); break;
			case 'date-asc': sorted.sort(function(a,b) { return parseDateForSort(a.postingDate) - parseDateForSort(b.postingDate); }); break;
			case 'salary-desc': sorted.sort(function(a,b) { return (b.salaryTo||b.salaryFrom) - (a.salaryTo||a.salaryFrom); }); break;
			case 'salary-asc': sorted.sort(function(a,b) { return (a.salaryTo||a.salaryFrom) - (b.salaryTo||b.salaryFrom); }); break;
			case 'agency-asc': sorted.sort(function(a,b) { return a.agency.localeCompare(b.agency); }); break;
			case 'title-asc': sorted.sort(function(a,b) { return a.title.localeCompare(b.title); }); break;
		}
		return sorted;
	}

	function renderCards(jobs) {
		if (!jobs.length) {
			$('#job-cards').hide();
			$('#no-results').show();
			$('#shown-count').text('0');
			return;
		}
		$('#no-results').hide();
		var html = '';
		jobs.forEach(function(j) {
			var sal = (j.salaryFrom || j.salaryTo) ? fmtSalary(j.salaryFrom, j.salaryTo, j.salaryFreq) : '';
			var titleUrl = j.titleCode ? '/t/' + j.titleCode : null;
			var activeEx = j._activeExam;
			var upcomingEx = j._upcomingExam;
			var exam = j._exam;
			var typeBadgeCls = j.postingType.toLowerCase().indexOf('internal') >= 0 ? 'db-badge-neutral' : 'db-badge-navy';

			html += '<div class="db-card is-hoverable"><div class="db-card-body">';

			html += '<div class="jc-badges">';
			if (j.postingType) html += '<span class="db-badge ' + typeBadgeCls + '">' + j.postingType + '</span>';
			if (activeEx) {
				html += '<span class="db-badge db-badge-success"><span class="db-dot"></span> Exam Open — Apply by ' + activeEx.end.substring(5) + '</span>';
			} else if (upcomingEx) {
				html += '<span class="db-badge db-badge-warning"><i class="bi bi-card-checklist"></i> Exam: ' + upcomingEx.start.substring(5) + ' to ' + upcomingEx.end.substring(5) + '</span>';
			} else if (j.classification && j.classification.indexOf('Competitive') === 0) {
				html += '<span class="db-badge db-badge-warning"><i class="bi bi-mortarboard"></i> Exam req\'d</span>';
			} else {
				html += '<span class="db-badge db-badge-success">No exam</span>';
			}
			if (j.careerLevel) html += '<span class="db-badge db-badge-neutral">' + j.careerLevel.replace(' (non-manager)','') + '</span>';
			if (j.fullPart === 'P') html += '<span class="db-badge db-badge-neutral">Part-Time</span>';
			html += '</div>';

			html += '<div class="jc-title">' + (j.title || j.csTitle) + '</div>';

			html += '<div class="jc-agency"><i class="bi bi-building"></i> ';
			if (j.agencyId) html += '<a href="/o/' + j.agencyId + '-' + slugify(j.agency) + '/jobs">' + j.agency + '</a>';
			else html += j.agency;
			html += '</div>';

			if (sal) html += '<div class="jc-salary">' + sal + '</div>';

			html += '<div class="jc-footer">';
			html += '<div class="jc-date"><i class="bi bi-calendar-event"></i> Posted ' + relDate(j.postingDate) + (parseInt(j.positions) > 1 ? ' \u00b7 ' + j.positions + ' pos.' : '') + '</div>';
			html += '<div class="jc-links">';
			html += '<a class="db-btn db-btn-primary db-btn-sm" href="https://cityjobs.nyc.gov/jobs?q=' + j.jobId + '" target="_blank"><i class="bi bi-box-arrow-up-right"></i> Details</a>';
			if (titleUrl) html += '<a class="db-btn db-btn-ghost db-btn-sm" href="' + titleUrl + '">Title</a>';
			if (activeEx) {
				html += '<a class="db-btn db-btn-outline db-btn-sm" href="' + noeUrl(activeEx) + '" target="_blank">Notice</a>';
			} else if (upcomingEx) {
				html += '<a class="db-btn db-btn-outline db-btn-sm" href="' + DCAS_UPDATES_URL + '" target="_blank">Updates</a>';
			}
			html += '</div></div></div></div>';
		});
		$('#job-cards').html(html).show();
		$('#shown-count').text(jobs.length.toLocaleString());
	}

	function renderActiveTags(f) {
		var tags = [];
		if (f.search) tags.push({label: 'Search: ' + f.search, clear: function(){ $('#f-search').val(''); }});
		if (f.career) tags.push({label: f.career, clear: function(){ selectPill('#f-career', ''); }});
		if (f.posting) tags.push({label: f.posting, clear: function(){ selectPill('#f-posting', ''); }});
		if (f.salfreq) tags.push({label: f.salfreq, clear: function(){ selectPill('#f-salfreq', ''); }});
		if (f.fullpart) tags.push({label: f.fullpart === 'F' ? 'Full-Time' : 'Part-Time', clear: function(){ selectPill('#f-fullpart', ''); }});
		if (f.salaryMin > 0) tags.push({label: '$' + f.salaryMin.toLocaleString() + '+', clear: function(){ $('#f-salary').val(0).trigger('input'); }});
		if (f.agency) tags.push({label: f.agency, clear: function(){ $('#f-agency').val(''); }});
		if (f.category) tags.push({label: f.category, clear: function(){ $('#f-category').val(''); }});
		if (f.classification) tags.push({label: f.classification, clear: function(){ $('#f-classification').val(''); }});
		if (f.posted) tags.push({label: 'Last ' + f.posted + 'd', clear: function(){ selectPill('#f-posted', ''); }});
		if (f.hasExam) tags.push({label: f.hasExam === 'active' ? 'Active Exam' : f.hasExam === 'upcoming' ? 'Upcoming Exam' : 'Has Exam', clear: function(){ selectPill('#f-exam', ''); }});

		var html = '';
		tags.forEach(function(t, i) {
			html += '<span class="db-tag" data-idx="'+i+'">' + t.label + ' <i class="bi bi-x"></i></span>';
		});
		$('#active-filters').html(html);
		$('#active-filters .db-tag').each(function(i) {
			$(this).on('click', function() { tags[i].clear(); applyFilters(); });
		});
	}

	function applyFilters() {
		var f = getFilters();
		var filtered = ALL_JOBS.filter(function(j) { return matchesFilter(j, f); });
		filtered = sortJobs(filtered, f.sort);
		renderCards(filtered);
		renderActiveTags(f);
	}

	// ===== Pill interaction =====
	function selectPill(group, val) {
		$(group + ' .db-filter-pill').removeClass('is-active');
		$(group + ' .db-filter-pill').each(function() {
			if ($(this).data('val') === val || (val === '' && $(this).data('val') === ''))
				$(this).addClass('is-active');
		});
	}

	$('.db-filter-pills .db-filter-pill').on('click', function() {
		var group = '#' + $(this).parent().attr('id');
		$(group + ' .db-filter-pill').removeClass('is-active');
		$(this).addClass('is-active');
		applyFilters();
	});

	// Initialize "All" pills as active
	$('.db-filter-pills').each(function() {
		$(this).find('.db-filter-pill').first().addClass('is-active');
	});

	// Text search (debounced)
	var searchTimer;
	$('#f-search').on('input', function() {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(applyFilters, 250);
	});

	// Dropdowns
	$('#f-agency, #f-category, #f-classification').on('change', applyFilters);

	// Salary slider
	$('#f-salary').on('input', function() {
		var v = parseInt($(this).val());
		$('#sal-display').text(v > 0 ? '$' + v.toLocaleString() + '+' : 'Any');
	});
	$('#f-salary').on('change', applyFilters);

	// Sort
	$('#sort-by').on('change', applyFilters);

	// Clear all
	$('#clear-all').on('click', function() {
		$('#f-search').val('');
		$('#f-agency, #f-category, #f-classification').val('');
		$('#f-salary').val(0).trigger('input');
		$('.db-filter-pills').each(function() {
			$(this).find('.db-filter-pill').removeClass('is-active').first().addClass('is-active');
		});
		applyFilters();
	});

	// Mobile facets drawer toggle
	$('#facets-toggle').on('click', function() {
		$('#jobs-sidebar').toggleClass('is-open');
	});

	// ===== Load exams for cross-reference (match by civil service title name) =====
	function loadExams() {
		$.getJSON('https://data.cityofnewyork.us/resource/4ptz-hmtc.json?$limit=5000', function(exams) {
			var now = new Date().toISOString().substring(0, 10);
			var dominated = ['canceled', 'postponed'];
			exams.forEach(function(e) {
				var title = (e.exam_title || '').trim().toUpperCase();
				var status = (e.open_competitive_promotion || '').toLowerCase();
				if (!title) return;
				// Skip canceled/postponed exams
				if (dominated.indexOf(status) >= 0) return;
				var entry = {
					title: e.exam_title || '',
					number: e.exam_number || '',
					type: e.open_competitive_promotion || '',
					start: (e.application_period_start || '').substring(0, 10),
					end: (e.application_period_end_date || '').substring(0, 10)
				};
				if (!EXAMS_MAP[title]) EXAMS_MAP[title] = [];
				EXAMS_MAP[title].push(entry);
			});

			// Attach exam info to each job: Active / Upcoming / Any
			ALL_JOBS.forEach(function(j) {
				var cs = j.csTitle.toUpperCase();
				var matched = EXAMS_MAP[cs];
				if (matched && matched.length) {
					// Active: filing period includes today (start <= today <= end)
					var active = matched.filter(function(ex) { return ex.start && ex.end && ex.start <= now && ex.end >= now; });
					// Upcoming: filing starts in the future (start > today)
					var upcoming = matched.filter(function(ex) { return ex.start && ex.start > now; });

					if (active.length) {
						active.sort(function(a,b) { return a.end.localeCompare(b.end); });
						j._activeExam = active[0];
						j._exam = active[0];
					} else if (upcoming.length) {
						upcoming.sort(function(a,b) { return a.start.localeCompare(b.start); });
						j._upcomingExam = upcoming[0];
						j._exam = upcoming[0];
					} else {
						j._exam = matched[0];
					}
				}
			});

			// Update exam counts in filter pills
			var actCount = ALL_JOBS.filter(function(j){return j._activeExam;}).length;
			var upCount = ALL_JOBS.filter(function(j){return j._upcomingExam;}).length;
			var anyCount = ALL_JOBS.filter(function(j){return j._exam;}).length;
			$('#f-exam .db-filter-pill[data-val="active"]').text('Active (' + actCount + ')');
			$('#f-exam .db-filter-pill[data-val="upcoming"]').text('Upcoming (' + upCount + ')');
			$('#f-exam .db-filter-pill[data-val="any"]').text('Any Exam (' + anyCount + ')');

			applyFilters();
		});
	}

	// ===== Load jobs from Databook API =====
	fapireq('{!! $jobsUrl !!}', function(resp) {
		var jobs = resp.data || [];
		if (jobs.length > 0) {
			processJobs(jobs);
		} else {
			$('#jobs-loading').html('<div class="text-danger">No job data available. Please try again later.</div>');
		}
	});

	function processJobs(rawJobs) {
		ALL_JOBS = rawJobs.map(norm);
		$('#jobs-loading').hide();
		$('#total-count').text(ALL_JOBS.length.toLocaleString());
		$('#hero-count').text(ALL_JOBS.length.toLocaleString());
		populateDropdowns(ALL_JOBS);
		applyFilters();
		loadExams();
	}
});
</script>
@endsection
