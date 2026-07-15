@extends('layout')

@section('head')
	<meta name="description" content="Profiles of all NYC city agencies with data-driven insights." />
	<meta rel="canonical" href="{!! route('orgsAgencies') !!}" />
	<style>
		/* Organizations index — db-* design system. Page-specific glue only. */
		#orgsCards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--db-space-2); }
		.org-card-head { display: flex; align-items: flex-start; gap: var(--db-space-15); }
		.org-card-icon { flex: 0 0 auto; width: 44px; height: 44px; border-radius: var(--db-radius-sm); background: var(--db-gray-100); color: var(--db-primary); display: flex; align-items: center; justify-content: center; font-size: 22px; overflow: hidden; }
		.org-card-icon img { max-width: 100%; max-height: 100%; }
		.org-card-name { font-size: var(--db-text-md); font-weight: var(--db-weight-bold); line-height: var(--db-leading-snug); margin: 0; color: var(--db-primary); }
		.org-card-code { font-family: var(--db-font-mono); font-size: var(--db-text-xs); color: var(--db-text-muted); margin-top: 2px; }
		.org-card-desc { font-size: var(--db-text-sm); color: var(--db-text-muted); margin: var(--db-space-15) 0 0; line-height: var(--db-leading-snug); }
		.org-card-foot { display: flex; gap: var(--db-space-2); margin-top: var(--db-space-15); padding-top: var(--db-space-15); border-top: 1px solid var(--db-border); flex-wrap: wrap; }
		.org-card-foot .stat-label { font-size: var(--db-text-2xs); text-transform: uppercase; letter-spacing: var(--db-tracking-caps); color: var(--db-text-muted); }
		.org-card-foot .stat-val { font-weight: var(--db-weight-bold); }
		.org-card-foot .stat-val.is-navy { color: var(--db-primary); }
		.db-card.is-hoverable a.org-card-link { color: inherit; text-decoration: none; display: block; }
		#viewToggle { margin-left: auto; }
	</style>
@endsection

@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

{{-- Navy hero band --}}
<div class="db-hero">
	<div class="inner_container">
		<div class="container db-hero-inner">
			<div class="db-hero-copy">
				<div class="db-eyebrow" style="color:var(--db-accent);">Organizations</div>
				<h1>NYC City Agencies</h1>
				<p>Profiles of all NYC city agencies, built from open data sources. Or view the <a href="/organizations/chart" style="color:var(--db-accent);">org chart</a>.</p>
			</div>
		</div>
	</div>
</div>

<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-5);">

		{{-- Summary stats — .prj_stat count spans + ids (populated by globStatView) --}}
		<div class="db-stat-grid" style="margin-bottom: var(--db-space-4);">
			<div class="db-stat is-accent">
				<div class="db-stat-label"><i class="bi bi-building"></i> City Agencies</div>
				<div class="db-stat-value"><span id="agencies_no" class="prj_stat">&nbsp;</span></div>
			</div>
			<div class="db-stat">
				<div class="db-stat-label"><i class="bi bi-diagram-3"></i> All Organizations</div>
				<div class="db-stat-value"><span id="orgs_no" class="prj_stat">&nbsp;</span></div>
			</div>
			<div class="db-stat">
				<div class="db-stat-label"><i class="bi bi-database"></i> Profile Data Sources</div>
				<div class="db-stat-value"><span id="orgs_datasets_no" class="prj_stat">&nbsp;</span></div>
			</div>
		</div>

		{{-- Filter bar --}}
		<div class="db-filter-bar mb-3">
			<div class="db-search">
				<i class="bi bi-search"></i>
				<input type="search" id="orgsSearch" placeholder="Search agencies…" aria-label="Search agencies">
			</div>
			<div class="db-field">
				<label for="filter-tags-wrap">Tag</label>
				<span id="filter-tags-wrap"></span>
			</div>
			<a href="{{ route('orgsAgencies') }}" class="db-btn db-btn-ghost db-btn-sm">Reset</a>
		</div>

		{{-- View toggle + count --}}
		<div class="d-flex align-items-center flex-wrap" style="gap: var(--db-space-2); margin-bottom: var(--db-space-2);">
			<span class="db-table-count"><strong id="orgs-result-count">…</strong> agencies</span>
			<div class="db-filter-pills" id="viewToggle">
				<button class="db-filter-pill is-active" data-view="cards"><i class="bi bi-grid-3x3-gap"></i> Cards</button>
				<button class="db-filter-pill" data-view="table"><i class="bi bi-table"></i> Table</button>
			</div>
		</div>

		{{-- Cards view (default) — built client-side from the SAME DataTable data --}}
		<div id="orgsCards"></div>

		{{-- Table view — the existing #orgsTable DataTable, skinned db-table --}}
		<div class="db-table-wrap" id="orgsTableWrap" style="display:none;">
			<div class="table-responsive">
				<table id="orgsTable" class="db-table db-table-striped display" style="width:100%;">
					<thead>
						<tr>
							<th>Organization</th>
							<th>Type</th>
							<th>Tags</th>
							<th></th>
						</tr>
					</thead>
				</table>
			</div>
		</div>

	</div>
</div>

	<script>
		var table = null

		function orgTypeBadge(type) {
			var map = {'City Agency':'navy','City Fund':'success','Community Board':'info','Economic Development Organization':'info','Elected Office':'success','State Agency':'info'};
			return map[type] || 'neutral';
		}
		function orgTypeIcon(type) {
			if (type === 'Elected Office') return 'bi-person-badge';
			if (type === 'City Fund' || (type || '').indexOf('Authority') >= 0) return 'bi-bank';
			return 'bi-building';
		}

		function tagFlt(e, tag) {
			$('#filter-tags').val(tag)
			$('#filter-tags').trigger('change')
			e.preventDefault()
		}

		function renderOrgCards() {
			if (!table) return;
			var rows = table.rows({search: 'applied'}).data();
			var html = '';
			rows.each(function (r) {
				var type = r['type'] || '';
				var badge = orgTypeBadge(type);
				var icon = orgTypeIcon(type);
				var logo = r['logo_file'] ? '<img src="/img/logo/' + r['logo_file'] + '">' : '<i class="bi ' + icon + '"></i>';
				var descr = (r['description'] || '');
				descr = descr.substr(0,90) + (descr.length > 90 ? '…' : '');
				var website = '';
				if (r['url']) {
					var u = r['url'].replace(/^https?:\/\//,'').replace(/\/$/,'');
					website = '<div><div class="stat-label">Website</div><div class="stat-val is-navy">' + u + '</div></div>';
				}
				html += '<div class="db-card is-hoverable">' +
					'<a class="org-card-link" href="/organization/' + r['id'] + '">' +
						'<div class="db-card-body">' +
							'<div class="org-card-head">' +
								'<div class="org-card-icon">' + logo + '</div>' +
								'<div>' +
									'<h3 class="org-card-name">' + (r['name'] || 'Unknown') + '</h3>' +
									'<div class="org-card-code">#' + r['id'] + '</div>' +
								'</div>' +
							'</div>' +
							'<div style="margin-top:var(--db-space-1)"><span class="db-badge db-badge-' + badge + '">' + (type || 'Organization') + '</span></div>' +
							(descr ? '<p class="org-card-desc">' + descr + '</p>' : '') +
							(website ? '<div class="org-card-foot">' + website + '</div>' : '') +
						'</div>' +
					'</a>' +
				'</div>';
			});
			$('#orgsCards').html(html || '<div class="db-empty"><div class="db-empty-title">No agencies found</div><div class="db-empty-text">Try widening your filters or clearing the search.</div></div>');
			$('#orgs-result-count').text(rows.length);
		}

		$(document).ready(function() {
			table = $('#orgsTable').DataTable( {
				pageLength: 12,
				deferRender: true,
				order: [[0, 'asc']],
				dom: '<"toolbar">frtip',
				ajax: function (url, cb) {
					fapireq("{!! $url !!}", cb);
			    },

				columns: [
                    // 0: Organization (name link)
                    {data: function (r) {
                        return '<a href="/organization/' + r['id'] + '">' + (r['name'] || 'Unknown') + '</a>'
                    }},
                    // 1: Type (db-badge) — searched by the City-Agency default + Type filter
                    {data: function (r) {
                        var type = r['type'] || '';
                        return '<span class="db-badge db-badge-' + orgTypeBadge(type) + '">' + (type || 'Organization') + '</span>'
                    }},
                    // 2: Tags (chips) — searched by the Tags filter
                    {data: function (r) {
                        if (!r['tags']) return '';
                        var rr = '';
                        JSON.parse(unescape(r['tags'])).forEach(function (d) {
                            rr += '<span class="tag-label" onclick="tagFlt(event, \'' + d + '\');">' + d + '</span>'
                        })
                        return rr
                    }},
                    // 3: Profile (button)
                    {
                        data: function (r) {
                            return '<a class="db-btn db-btn-outline db-btn-sm" href="/organization/' + r['id'] + '">Profile</a>'
                        },
                        orderable: false,
                        searchable: false
                    }
                ],

				initComplete: function () {
					// Filter to City Agency type only — Type is now column index 1
					this.api().columns([1]).every(function () {
						var column = this;
						setTimeout(function(){
							column
								.search('^City Agency$', true, false)
								.draw();
						}, 700);
					});

					// Tags filter — Tags is now column index 2
					this.api().columns([2]).every(function () {
						var column = this;
						var select = $('<select class="filter-top" id="filter-tags"><option value="">All tags</option></select>')
							.appendTo($('#filter-tags-wrap'))
							.on('change', function () {
								var val = $(this).val()
								column
									.search(val ? val : '', false, false)
									.draw();
							});

						var tt = []
						rg = />([^<]+)</g;
						column.data().each(function (d, j) {
							while ((t = rg.exec(d)) !== null) {
								tt.push(t[1])
							}
						})
						tt = [...new Set(tt)]
						tt.sort().forEach(function (d, j) {
							select.append( '<option value="'+d+'">'+d+'</option>' )
						});
					});
				}
			});

			// Re-render the cards grid on each draw so search/filters stay in sync;
			// the TABLE renders normal columnar rows (no card-in-tbody override).
			table.on('draw', function () {
                renderOrgCards();
            });

			// View toggle: Cards (default) vs Table
			$('#viewToggle .db-filter-pill').on('click', function () {
				var v = $(this).data('view');
				if (!v) return;
				$('#viewToggle .db-filter-pill').removeClass('is-active');
				$(this).addClass('is-active');
				if (v === 'table') {
					$('#orgsCards').hide();
					$('#orgsTableWrap').show();
				} else if (v === 'cards') {
					$('#orgsTableWrap').hide();
					$('#orgsCards').show();
				}
			});

			// Search filters both views
			$('#orgsSearch').on('keyup', function () {
				if (table) table.search($(this).val()).draw();
			});
		});
	</script>

@endsection

@section('scripts')
	<script>
		$(document).ready(function() {
			globStatView({!! json_encode($globStats) !!})
		})
	</script>
@endsection
