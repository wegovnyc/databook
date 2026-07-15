@extends('layout')

@section('head')
	<meta name="description" content="NYC City Council hearing calendar — upcoming committee hearings with linked legislation from intro.nyc" />
	<meta rel="canonical" href="{!! url('/council') !!}" />
	<style>
		.hearing-card {
			background: #fff;
			border: 1px solid #e3e7ee;
			border-radius: 8px;
			padding: 16px 20px;
			margin-bottom: 12px;
			transition: box-shadow 0.15s ease;
		}
		.hearing-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
		.hearing-card.past { opacity: 0.92; }
		.hearing-card.today { border-left: 4px solid #162E51; }
		.hearing-date { font-weight: 600; color: #162E51; }
		.hearing-committee { font-size: 1.1rem; font-weight: 600; }
		.hearing-meta { font-size: 0.85rem; color: #6c757d; }
		.hearing-agenda-toggle { cursor: pointer; color: #162E51; font-size: 0.85rem; }
		.hearing-agenda-toggle:hover { text-decoration: underline; }
		.hearing-agenda { display: none; margin-top: 10px; padding: 10px 14px; background: #f8f9fa; border-radius: 6px; }
		.hearing-agenda.show { display: block; }
		.agenda-item { margin-bottom: 6px; font-size: 0.9rem; }
		.agenda-item .matter-file { font-weight: 600; color: #162E51; }
		.badge-upcoming { background: #162E51; color: #fff; }
		.badge-past { background: #adb5bd; color: #fff; }
		.badge-today { background: #28a745; color: #fff; }
		.hearing-links a { font-size: 0.85rem; margin-right: 12px; }
		.date-group { margin-top: 24px; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 2px solid #162E51; }
		.date-group h5 { margin: 0; color: #162E51; font-weight: 700; }
		.filter-bar { margin-bottom: 20px; }
		#hearing-count { font-weight: 600; color: #162E51; }
		.skeleton { background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 6px; height: 80px; margin-bottom: 12px; }
		@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
		.briefing-callout { background: linear-gradient(135deg, #162E51 0%, #1a3a6a 100%); color: #fff; border-radius: 8px; padding: 20px 24px; margin-bottom: 24px; }
		.briefing-callout h5 { color: #fff; margin-bottom: 8px; }
		.briefing-callout p { opacity: 0.9; margin-bottom: 0; font-size: 0.95rem; }
	</style>
@endsection

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-11 organization_data">
					<h1 class="main_hdr">City Council Hearings</h1>
					<p>Upcoming and recent NYC City Council committee hearings with linked legislation. Data sourced from <a href="https://github.com/jehiah/nyc_legislation" target="_blank">NYC Legislation</a> (Legistar mirror, updated every 6 hours). View legislation details on <a href="https://intro.nyc" target="_blank">intro.nyc</a>.</p>
				</div>
			</div>

			{{-- Briefing callout --}}
			<div class="row justify-content-center">
				<div class="col-md-11">
					<div class="briefing-callout">
						<h5><i class="bi bi-file-earmark-bar-graph"></i> Hearing Data Briefings</h5>
						<p>Generate a data brief for any hearing below — it cross-references the hearing's legislation with Databook's contracts, budgets, capital projects, city record notices, and job postings. Use the <strong>"Generate Briefing"</strong> link on any hearing card, or ask the <a href="{{ route('mcp') }}" style="color: #7db8ff;">Databook MCP</a> to <code style="color: #cde;">get_hearing_briefing</code>.</p>
					</div>
				</div>
			</div>

			{{-- Filter --}}
			<div class="row justify-content-center">
				<div class="col-md-11 filter-bar">
					<div class="d-flex align-items-center gap-3">
						<span id="hearing-count">Loading...</span>
						<div class="form-check form-switch ms-3">
							<input class="form-check-input" type="checkbox" id="showPast" checked>
							<label class="form-check-label small" for="showPast">Show past hearings</label>
						</div>
						<input type="text" class="form-control form-control-sm ms-3" id="committeeFilter" placeholder="Filter by committee..." style="max-width: 250px;">
					</div>
				</div>
			</div>

			{{-- Hearing list --}}
			<div class="row justify-content-center">
				<div class="col-md-11" id="hearing-list">
					<div class="skeleton"></div>
					<div class="skeleton"></div>
					<div class="skeleton"></div>
				</div>
			</div>
		</div>
	</div>
@endsection

@section('scripts')
<script>
$(document).ready(function() {
	var hearingsData = [];
	var apiBase = {!! json_encode(config('apis.fapi_public_entry', 'https://api.databook.nyc')) !!};

	function fetchHearings() {
		$.ajax({
			url: apiBase + '/pipeline/hearings?days_ahead=30&days_behind=14',
			success: function(data) {
				hearingsData = data.events || [];
				renderHearings();
			},
			error: function() {
				$('#hearing-list').html('<div class="alert alert-warning">Unable to load hearing data. Please try again later.</div>');
				$('#hearing-count').text('Error');
			}
		});
	}

	function renderHearings() {
		var showPast = $('#showPast').is(':checked');
		var filter = $('#committeeFilter').val().toLowerCase();
		var today = new Date().toISOString().slice(0, 10);

		var filtered = hearingsData.filter(function(h) {
			if (!showPast && h.is_past) return false;
			if (filter && h.committee.toLowerCase().indexOf(filter) === -1) return false;
			return true;
		});

		$('#hearing-count').text(filtered.length + ' hearing' + (filtered.length !== 1 ? 's' : ''));

		if (filtered.length === 0) {
			$('#hearing-list').html('<p class="text-muted">No hearings match your filters.</p>');
			return;
		}

		var html = '';
		var currentDate = '';

		filtered.forEach(function(h, idx) {
			// Date group header
			if (h.date !== currentDate) {
				currentDate = h.date;
				var d = new Date(h.date + 'T12:00:00');
				var dateLabel = d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
				var isToday = h.date === today;
				var todayBadge = isToday ? ' <span class="badge badge-today">Today</span>' : '';
				html += '<div class="date-group"><h5>' + dateLabel + todayBadge + '</h5></div>';
			}

			var pastClass = h.is_past ? ' past' : '';
			var todayClass = h.date === today ? ' today' : '';
			var statusBadge = h.date === today ? '<span class="badge badge-today">Today</span>'
				: h.is_past ? '<span class="badge badge-past">Past</span>'
				: '<span class="badge badge-upcoming">Upcoming</span>';

			html += '<div class="hearing-card' + pastClass + todayClass + '" id="hearing-' + h.event_id + '">';
			html += '<div class="d-flex justify-content-between align-items-start">';
			html += '<div>';
			html += '<div class="hearing-committee">' + h.committee + '</div>';
			html += '<div class="hearing-meta">';
			html += '<i class="bi bi-clock"></i> ' + (h.time || 'TBD');
			if (h.location) html += ' &middot; <i class="bi bi-geo-alt"></i> ' + h.location;
			if (h.agenda_count > 0) html += ' &middot; ' + h.agenda_count + ' agenda item' + (h.agenda_count !== 1 ? 's' : '');
			html += '</div>';
			html += '</div>';
			html += '<div>' + statusBadge + '</div>';
			html += '</div>';

			// Links row
			html += '<div class="hearing-links mt-2">';
			if (h.legistar_url) html += '<a href="' + h.legistar_url + '" target="_blank"><i class="bi bi-box-arrow-up-right"></i> Legistar</a>';
			if (h.agenda_file) html += '<a href="' + h.agenda_file + '" target="_blank"><i class="bi bi-file-pdf"></i> Agenda PDF</a>';
			if (h.video_path) html += '<a href="' + h.video_path + '" target="_blank"><i class="bi bi-camera-video"></i> Video</a>';
			if (h.event_id) html += '<a href="#" class="briefing-link" data-event-id="' + h.event_id + '"><i class="bi bi-file-earmark-bar-graph"></i> Generate Briefing</a>';
			html += '</div>';

			// Agenda items collapsible
			if (h.agenda_items && h.agenda_items.length > 0) {
				html += '<div class="hearing-agenda-toggle mt-2" onclick="toggleAgenda(\'' + h.event_id + '\')"><i class="bi bi-chevron-down"></i> View Agenda (' + h.agenda_items.length + ' items)</div>';
				html += '<div class="hearing-agenda" id="agenda-' + h.event_id + '">';
				h.agenda_items.forEach(function(item, i) {
					html += '<div class="agenda-item">';
					html += '<span class="matter-file">' + item.matter_file + '</span>';
					if (item.intro_link) html += ' <a href="' + item.intro_link + '" target="_blank" title="View on intro.nyc"><i class="bi bi-link-45deg"></i></a>';
					html += '<div class="text-muted small">' + item.matter_name + '</div>';
					html += '</div>';
				});
				html += '</div>';
			}

			html += '</div>';
		});

		$('#hearing-list').html(html);

		// Briefing link handlers
		$('.briefing-link').click(function(e) {
			e.preventDefault();
			var eventId = $(this).data('event-id');
			showBriefingModal(eventId);
		});
	}

	window.toggleAgenda = function(eventId) {
		$('#agenda-' + eventId).toggleClass('show');
		var toggle = $('[onclick="toggleAgenda(\'' + eventId + '\')"]');
		if ($('#agenda-' + eventId).hasClass('show')) {
			toggle.html('<i class="bi bi-chevron-up"></i> Hide Agenda');
		} else {
			var count = $('#agenda-' + eventId + ' .agenda-item').length;
			toggle.html('<i class="bi bi-chevron-down"></i> View Agenda (' + count + ' items)');
		}
	};

	function showBriefingModal(eventId) {
		var hearing = hearingsData.find(function(h) { return h.event_id == eventId; });
		if (!hearing) return;

		var year = hearing.date.slice(0, 4);

		// Show modal with loading state
		var modal = `
<div class="modal fade" id="briefingModal" tabindex="-1">
  <div class="modal-dialog modal-lg modal-dialog-scrollable">
    <div class="modal-content">
      <div class="modal-header" style="background: #162E51; color: #fff;">
        <h5 class="modal-title"><i class="bi bi-file-earmark-bar-graph"></i> Hearing Data Briefing</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body" id="briefing-body">
        <h5>${hearing.committee}</h5>
        <p class="text-muted">${hearing.date} at ${hearing.time || 'TBD'} · ${hearing.location || ''}</p>
        <hr>
        <div class="text-center py-4">
          <div class="spinner-border text-primary" role="status"></div>
          <p class="mt-2 text-muted">Cross-referencing hearing agenda with Databook data...</p>
          <p class="small text-muted">Checking contracts, budgets, capital projects, City Record notices, and jobs</p>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
      </div>
    </div>
  </div>
</div>`;

		$('#briefingModal').remove();
		$('body').append(modal);
		var bsModal = new bootstrap.Modal(document.getElementById('briefingModal'));
		bsModal.show();

		// Fetch briefing data
		$.ajax({
			url: apiBase + '/pipeline/hearing-briefing/' + eventId + '?year=' + year,
			success: function(data) {
				renderBriefing(data, hearing);
			},
			error: function(xhr) {
				var msg = xhr.responseJSON ? xhr.responseJSON.error : 'Unable to generate briefing';
				$('#briefing-body').html(`
					<h5>${hearing.committee}</h5>
					<p class="text-muted">${hearing.date}</p>
					<hr>
					<div class="alert alert-warning"><i class="bi bi-exclamation-triangle"></i> ${msg}</div>
				`);
			}
		});
	}

	function renderBriefing(data, hearing) {
		var html = '';
		html += '<h5>' + data.committee + '</h5>';
		html += '<p class="text-muted">' + data.date + ' at ' + (hearing.time || 'TBD') + ' · ' + (hearing.location || '') + '</p>';
		html += '<hr>';

		// Bills section
		if (data.bills && data.bills.length > 0) {
			html += '<h6><i class="bi bi-file-text"></i> Bills Under Consideration (' + data.bills.length + ')</h6>';
			html += '<div class="mb-3" style="background: #f8f9fa; padding: 12px; border-radius: 6px;">';
			data.bills.forEach(function(b) {
				html += '<div class="mb-1"><strong>' + b.matter_file + '</strong>';
				if (b.intro_link) html += ' <a href="' + b.intro_link + '" target="_blank" class="small"><i class="bi bi-link-45deg"></i>intro.nyc</a>';
				html += '<div class="text-muted small">' + b.matter_name + '</div></div>';
			});
			html += '</div>';
		}

		// Themes with data
		if (data.themes && data.themes.length > 0) {
			html += '<h6 class="mt-3"><i class="bi bi-diagram-3"></i> Related Databook Data (' + data.theme_count + ' themes matched)</h6>';

			data.themes.forEach(function(theme) {
				html += '<div class="card mb-3"><div class="card-header py-2" style="background: #e8edf3;"><strong>' + theme.label + '</strong></div>';
				html += '<div class="card-body py-2">';

				// Contracts
				if (theme.contracts && theme.contracts.length > 0) {
					html += '<div class="mb-2"><span class="badge bg-primary">Contracts</span>';
					html += '<table class="table table-sm table-borderless mb-0 small mt-1"><tbody>';
					theme.contracts.forEach(function(c) {
						var amt = c.amount ? '$' + c.amount.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ",") : 'N/A';
						html += '<tr><td>' + c.title + '</td><td class="text-muted">' + c.vendor + '</td><td class="text-end">' + amt + '</td></tr>';
					});
					html += '</tbody></table></div>';
				}

				// Budget
				if (theme.budget && theme.budget.length > 0) {
					html += '<div class="mb-2"><span class="badge bg-success">Budget</span>';
					theme.budget.forEach(function(b) {
						var total = '$' + (b.total / 1000000).toFixed(1) + 'M';
						html += '<div class="small mt-1">' + b.agency + ': <strong>' + total + '</strong> (FY' + (b.fy || '') + ')</div>';
					});
					html += '</div>';
				}

				// Capital projects
				if (theme.capital_projects && theme.capital_projects.length > 0) {
					html += '<div class="mb-2"><span class="badge bg-warning text-dark">Capital Projects</span>';
					theme.capital_projects.forEach(function(p) {
						var budget = p.budget ? ' — $' + (p.budget / 1000000).toFixed(1) + 'M' : '';
						html += '<div class="small mt-1"><a href="/p/' + p.project_id + '" target="_blank">' + p.project_id + '</a> ' + p.description + budget + '</div>';
					});
					html += '</div>';
				}

				// CROL
				if (theme.crol && theme.crol.length > 0) {
					html += '<div class="mb-2"><span class="badge bg-info">City Record Notices</span>';
					theme.crol.forEach(function(c) {
						html += '<div class="small mt-1">' + c.section + ': ' + c.title + '</div>';
					});
					html += '</div>';
				}

				// Jobs
				if (theme.open_jobs > 0) {
					html += '<div class="mb-1"><span class="badge bg-secondary">Open Jobs</span> <span class="small">' + theme.open_jobs + ' open positions</span></div>';
				}

				html += '</div></div>';
			});
		} else {
			html += '<div class="alert alert-info mt-3">No matching themes found for this hearing\'s agenda. The committee topic may not map to a specific agency in Databook yet.</div>';
		}

		$('#briefing-body').html(html);
	}

	// Event handlers
	$('#showPast').change(renderHearings);
	$('#committeeFilter').on('input', renderHearings);

	// Load data
	fetchHearings();
});
</script>
@endsection
