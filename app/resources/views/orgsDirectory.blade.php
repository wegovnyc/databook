@extends('layout')


@section('head')
	<meta name="description" content="Data-powered profiles of every NYC government agency." />
	<meta rel="canonical" href="{!! route('orgs') !!}" />
	<style>
		/* Organizations index — db-* design system. Page-specific glue only;
		   hero / stats / filter bar / cards / table all use shared component classes. */
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
				<h1>City agencies &amp; organizations</h1>
				<p>Every mayoral agency, public authority, and elected office — with the data sources behind each profile. Or view the <a href="/organizations/chart" style="color:var(--db-accent);">org chart</a>.</p>
			</div>
		</div>
	</div>
</div>

<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-5);">

		{{-- Summary stats — KEEP the .prj_stat count spans + ids (populated by globStatView) --}}
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
				<input type="text" id="peopleSearch" placeholder="Search organizations…" aria-label="Search organizations" @if($req ?? null ) value="{!! $req !!}" @endif>
			</div>
			<div class="db-field">
				<label for="filter-type">Type</label>
				<select id="filter-type"><option value="">All types</option></select>
			</div>
			<div class="db-field">
				<label for="filter-tags-wrap">Tag</label>
				<span id="filter-tags-wrap"></span>
			</div>
			<button id="peopleFormSubmitBtn" type="button" class="db-btn db-btn-primary db-btn-sm" onclick="peopleFormSubmit();">Search</button>
			<a href="{{ route('orgs') }}" class="db-btn db-btn-ghost db-btn-sm">Reset</a>
		</div>

		{{-- View toggle + count + export --}}
		<div class="d-flex align-items-center flex-wrap" style="gap: var(--db-space-2); margin-bottom: var(--db-space-2);">
			<span class="db-table-count"><strong id="orgs-result-count">…</strong> organizations</span>
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
							<th></th>
							<th></th>
							<th></th>
							<th></th>
							<th></th>
							<th></th>
							<th></th>
						</tr>
					</thead>
				</table>
			</div>
		</div>

		<div class="db-alert db-alert-info mt-4">
			<div class="db-alert-body">
				<i class="bi bi-info-circle"></i> The agencies listed here all appear in official New York City open data, cross referenced with the city’s <a href="https://www1.nyc.gov/nyc-resources/agencies.page" rel="nofollow">official agency directory</a>. If you notice inaccuracies, please <a href="https://wegovnyc.notion.site/Contact-Us-54b075fa86ec47ebae48dae1595afc2c" rel="nofollow">let us know</a>.
			</div>
		</div>

	</div>
</div>

	<script>
		var table = null

		// Type → badge color + icon for cards
		function orgTypeBadge(type) {
			var map = {'City Agency':'navy','City Fund':'success','Community Board':'info','Economic Development Organization':'info','Elected Office':'success','State Agency':'info',
				// OTI's vocabulary, adopted 2026-07-30 — without these, every
				// retyped agency falls through to the neutral badge.
				'Mayoral Agency':'navy','Mayoral Office':'navy','Division':'navy',
				'Advisory or Regulatory Organization':'info','Pension Fund':'success',
				'Public Benefit or Development Organization':'info',
				'State Government Agency':'info','Nonprofit Organization':'neutral'};
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

		function copyShareLink()
		{
			const url = $('#details-permalink').text()
			const params = new URLSearchParams({
			  search: $('input[type="search"]').val(),
			  type: $('#filter-4').val(),
			  tag: $('#filter-tags').val()
			});
			$('#details-permalink').text(`${url}?${params.toString()}`)
			copyLink()
			$('#details-permalink').text(url)
		}

		function loadShareLink()
		{
			const params = {!! $_GET ? json_encode($_GET) : '""' !!}
			if (params) {
				if (params['q']) {
					table({
					  'search': {
						'search': params['q']
					  }
					})
				}
				if (params['type']) {
					$('#filter-4').val(params['type'])
					$('#filter-4').trigger('change')
				}
				if (params['tag']) {
					$('#filter-tags').val(params['tag'])
					$('#filter-tags').trigger('change')
				}
			}
		}

		// Render the cards grid from the currently-filtered DataTable rows
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
			$('#orgsCards').html(html || '<div class="db-empty"><div class="db-empty-title">No organizations found</div><div class="db-empty-text">Try widening your filters or clearing the search.</div></div>');
			$('#orgs-result-count').text(rows.length);
		}

		$(document).ready(function() {
			table = $('#orgsTable').DataTable( {
				pageLength: 12,
				deferRender: true,
				order: [[2, 'asc']],
				ordering: false,
				dom: '<"toolbar">frtip',
				ajax: function (url, cb) {
					fapireq("{!! $url !!}", cb);
			    },

				columns: [
                    {data: 'id'},
                    {data: function (r) {
                        return r['logo']
                            ? JSON.parse(unescape(r['logo']))[0]['url']
                            : '';
                    }},
                    {data: 'name'},
                    {data: 'tags'},
                    {data: 'type'},
                    {data: function (r) {
                        return r['description'].substr(0,100)+
                        (r['description'].length > 100 ? '...' : '')
                    }},
                    {
                        className: 'record',
                        data:  null,
                        defaultContent: null,
                        searchable: false
                    }
                ],
				@if ($defSearch)
					search: {
						'search': '{{ $defSearch }}'
				    },
				@endif

				initComplete: function () {
					this.api().columns([4]).every(function () {						// Type
						var column = this;

						setTimeout(function(){
							var val = $.fn.dataTable.util.escapeRegex(
								'{!! $defType !!}'
							);
							column
								.search(val ? '^'+val+'$' : '', true, false)
								.draw();
						}, 700);
					});



					this.api().columns([3]).every(function () {						// tags
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

						rg = /"([^"]+)"/g;
						column.data().each(function (d, j) {
							while ((t = rg.exec(d)) !== null) {
								tt.push(t[1])
							}
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							select.append( '<option value="'+d+'">'+d+'</option>' )
						});
						@if ($defTag)
						  setTimeout(function(){
							select.val('{!! $defTag !!}')
							select.trigger('change')
						  }, 1000);
						@endif
					});

					// Populate the visible Type select (cosmetic db-* filter) and drive column 4 search
					this.api().columns([4]).every(function () {
						var column = this;
						var tt = [];
						column.data().each(function (d) { if (d) tt.push(d); });
						tt = [...new Set(tt)].sort();
						var $sel = $('#filter-type');
						tt.forEach(function (d) { $sel.append('<option value="'+d+'">'+d+'</option>'); });
						$sel.val('{!! $defType !!}');
						$sel.on('change', function () {
							var val = $.fn.dataTable.util.escapeRegex($(this).val());
							column.search(val ? '^'+val+'$' : '', true, false).draw();
						});
					});

					// share button
					$('<span class="share_icon_container" data-bs-toggle="popover" data-content="Link copied to clipboard" placement="left" trigger="manual" style="top: 0;font-size: 22px;"><textarea id="details-permalink" class="details">{!! preg_replace('~\?.*~', '', route("orgs")) !!}</textarea><span id="details-addr"></span><a title="Share direct link" onclick="copyShareLink();"><i class="bi bi-share"></i></a></span>').appendTo($('div.toolbar'));

					loadShareLink()
				}
			});

			table.on('preDraw', function () {
                $('#orgsTable tbody').hide();
                return true
            });

			table.on('draw', function () {
                var api = $('#orgsTable').dataTable().api();
                var modifier = {
                    order:  'current',  // 'current', 'applied', 'index',  'original'
                    page:   'current',      // 'all',     'current'
                    search: 'applied',     // 'none',    'applied', 'removed'
                }
                var td = $('<td></td>')
                var div = $('<div></div>')

                api.cells('.record', modifier).data().each(function (r, i) {

                    div = $('<div class="card-body"></div>')

                    if (r['logo_file'])
                        div.append(`<div class="inner_logoimg"><div class="inside_org_logo"><img src="/img/logo/${r['logo_file']}"></div></div>`)

                    if (r['name'])
                        div.append(`<h6>${r['name']}</h6>`)

                    var descr = r['description'].substr(0,100)+(r['description'].length > 100 ? '...' : '')
                    div.append(`<p class="card-text">${descr}</p>`)

                    if (r['tags']) {
                        var tags = ''
                        JSON.parse(unescape(r['tags'])).forEach(function (d, j) {
                            tags = tags+'<span class="tag-label" onclick="tagFlt(event, \''+d+'\');">'+d+'</span>'
                        })
                        div.append(`<a title="Tags"><i class="bi-tags" style="color:black;"></i></a> ${tags}`)
                    }

                    td.append($(`<div class="col-md-3"><a href="/organization/${r['id']}"><div class="card  w-33"><div class="card-body">${div.html()}</div></div></a></div>`))
                });
                $('#orgsTable tbody').html('<tr><td colspan="7"><div class="row">'+td.html()+'</div></td></tr>')
                $('#orgsTable tbody').show();

                // Keep the db-* cards grid in sync with the table's current filtered data
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
		});
	</script>

@endsection



@section('scripts')
	<script>
		$(document).ready(function() {
			globStatView({!! json_encode($globStats) !!})

			setTimeout(function(){
				initPopovers();
			}, 700);

			$('#peopleSearch').on('keyup', function () {
				var v = $('#peopleSearch').val();
				if (table) table.search(v).draw();
			})
		})

		function peopleFormSubmit() {
			var v = $('#peopleSearch').val();
			if (table) table.search(v).draw();
		}
	</script>
@endsection
