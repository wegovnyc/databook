@extends('layout')


@section('head')
	<meta name="description" content="Databook combines dozens of open datasets to help people better understand New York City’s government." />
	<meta rel="canonical" href="{!! route('root') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => null])
@endsection


@section('content')
<!-- Hero (db-* design system) — centered intro, shown once per device (first visit),
     dismissible. Hidden by default; an inline script reveals it for first-timers. -->
<div class="db-hero" id="dbHero" style="display:none;">
	<button type="button" class="db-hero-close" id="dbHeroClose" aria-label="Dismiss intro">&times;</button>
	<div class="inner_container">
		<div class="db-hero-inner is-centered">
			<div class="db-hero-copy">
				<h1>Understand how New York City government works.</h1>
				<p>Databook combines dozens of official open datasets — agencies, people, jobs, capital projects, procurement, and more — into one searchable picture of the city.</p>
				<form class="db-hero-search" action="{{ route('search') }}" method="get" role="search" style="margin: var(--db-space-3) auto 0; max-width: 520px;">
					<i class="bi bi-search"></i>
					<input type="search" name="q" placeholder="Search organizations, people, contracts…" aria-label="Search Databook">
				</form>
			</div>
		</div>
	</div>
</div>
<script>
(function () {
	var hero = document.getElementById('dbHero');
	if (!hero) return;
	var SEEN = 'db_hero_seen';
	var seen;
	try { seen = localStorage.getItem(SEEN); } catch (e) { seen = null; }
	if (!seen) {
		hero.style.display = '';                       // first visit on this device → show once
		try { localStorage.setItem(SEEN, '1'); } catch (e) {}
	}
	var close = document.getElementById('dbHeroClose');
	if (close) close.addEventListener('click', function () {
		hero.style.display = 'none';
		try { localStorage.setItem(SEEN, '1'); } catch (e) {}
	});
})();
</script>

<div class="inner_container">
	<!-- Morning Briefing Dashboard -->
	<style>
		.briefing-header {
			display: flex; align-items: center; justify-content: space-between;
			padding: 12px 0 8px; border-bottom: 2px solid #162E51;
		}
		.briefing-header h2 { margin: 0; font-weight: 800; color: #162E51; font-size: 22px; }
		.briefing-header .briefing-date { color: #6c757d; font-size: 14px; font-weight: 500; }
		.briefing-tabs {
			display: flex; gap: 4px; padding: 8px 0; border-bottom: 1px solid #e9ecef;
		}
		.briefing-tab {
			padding: 4px 12px; font-size: 12px; font-weight: 600; border: 1px solid #dee2e6;
			border-radius: 14px; cursor: pointer; background: #fff; color: #495057;
			transition: all 0.15s; white-space: nowrap;
		}
		.briefing-tab:hover { background: #f0f7ff; border-color: #4299e1; }
		.briefing-tab.active { background: #162E51; color: #fff; border-color: #162E51; }
		.briefing-tab .tab-count {
			display: inline-block; background: rgba(255,255,255,0.2); padding: 0 5px;
			border-radius: 8px; font-size: 10px; margin-left: 4px;
		}
		.briefing-tab.active .tab-count { background: rgba(255,255,255,0.3); }
		.briefing-tab:not(.active) .tab-count { background: #e9ecef; }
		.briefing-panels { margin-top: 8px; }
		.briefing-cards {
			display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
			margin-bottom: 12px;
		}
		.briefing-ticker {
			columns: 2; column-gap: 20px;
			max-height: 380px; overflow-y: auto;
		}
		/* Ticker rows */
		.ticker-section { margin-bottom: 6px; break-inside: avoid; }
		.ticker-section-header {
			font-size: 11px; font-weight: 700; text-transform: uppercase;
			letter-spacing: 0.8px; padding: 4px 0; color: #162E51;
			border-bottom: 1px solid #e9ecef; margin-bottom: 2px;
			display: flex; align-items: center; gap: 6px;
		}
		.ticker-section-header .sec-dot {
			width: 8px; height: 8px; border-radius: 50%; display: inline-block;
		}
		.ticker-row {
			display: flex; align-items: baseline; padding: 3px 0; font-size: 13px;
			border-bottom: 1px solid #f8f9fa; cursor: pointer; transition: background 0.1s;
			gap: 8px;
		}
		.ticker-row:hover { background: #f0f7ff; }
		.ticker-badge {
			font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px;
			white-space: nowrap; flex-shrink: 0;
		}
		.ticker-title { flex: 1; color: #212529; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
		.ticker-agency { color: #6c757d; font-size: 11px; flex-shrink: 0; white-space: nowrap; }
		.ticker-time { color: #adb5bd; font-size: 11px; flex-shrink: 0; white-space: nowrap; }
		/* Card items */
		.briefing-card {
			border: 1px solid #e9ecef; border-radius: 6px; padding: 10px 12px;
			transition: border-color 0.15s, box-shadow 0.15s;
			cursor: pointer; display: flex; flex-direction: column;
		}
		.briefing-card:hover { border-color: #4299e1; box-shadow: 0 1px 4px rgba(66,153,225,0.12); }
		.briefing-card .card-top {
			display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
		}
		.briefing-card .card-title {
			font-size: 13px; font-weight: 600; color: #212529; margin: 0;
			line-height: 1.3;
		}
		.briefing-card .card-context {
			font-size: 12px; color: #6c757d; margin: 2px 0 0; line-height: 1.3;
		}
		.briefing-card .card-meta {
			display: flex; justify-content: space-between; align-items: center;
			margin-top: 4px; font-size: 11px; color: #adb5bd;
		}
		/* Badge colors by section */
		.badge-hearing { background: #dbeafe; color: #1e40af; }
		.badge-rules { background: #ede9fe; color: #6b21a8; }
		.badge-contracts { background: #ffedd5; color: #c2410c; }
		.badge-solicitations { background: #fef9c3; color: #a16207; }
		.badge-capital { background: #dcfce7; color: #166534; }
		.badge-jobs { background: #ccfbf1; color: #0f766e; }
		.badge-personnel { background: #f3f4f6; color: #4b5563; }
		.badge-schools { background: #fce7f3; color: #9d174d; }
		.badge-vendors { background: #ede9fe; color: #7c3aed; }
		/* Scrollbar */
		.briefing-ticker::-webkit-scrollbar, .briefing-cards::-webkit-scrollbar { width: 4px; }
		.briefing-ticker::-webkit-scrollbar-thumb, .briefing-cards::-webkit-scrollbar-thumb {
			background: #cbd5e1; border-radius: 2px;
		}
		/* Responsive */
		@media (max-width: 768px) {
			.briefing-cards { grid-template-columns: 1fr; }
			.briefing-ticker { columns: 1; max-height: 300px; }
		}
		/* Time window headers */
		.time-window { margin-bottom: 16px; }
		.time-window-header {
			display: flex; align-items: center; justify-content: space-between;
			padding: 6px 10px; background: #f1f5f9; border-radius: 4px;
			margin-bottom: 6px;
		}
		.time-window-label { font-size: 14px; font-weight: 700; color: #162E51; }
		.time-window-count { font-size: 12px; color: #6c757d; font-weight: 500; }
		/* Collapsible extended windows */
		.time-window-header.collapsible {
			cursor: pointer; background: #e2e8f0;
			transition: background 0.15s;
		}
		.time-window-header.collapsible:hover { background: #cbd5e1; }
		.time-window-header.collapsible .toggle-icon { display: inline-block; transition: transform 0.2s; }
		.time-window-header.collapsible.open .toggle-icon { transform: rotate(90deg); }
		.time-window-body { display: none; }
		.time-window-body.open { display: block; }
		/* View toggle */
		.briefing-toggle {
			display: flex; gap: 4px; margin-bottom: 10px;
		}
		.briefing-toggle .toggle-btn {
			padding: 5px 14px; font-size: 12px; font-weight: 600;
			border: 1px solid #cbd5e1; border-radius: 6px;
			background: #fff; color: #64748b; cursor: pointer;
			transition: all 0.15s;
		}
		.briefing-toggle .toggle-btn:hover { background: #f1f5f9; }
		.briefing-toggle .toggle-btn.active {
			background: #162E51; color: #fff; border-color: #162E51;
		}
		/* Today highlight */
		.ticker-row.ticker-today {
			background: #eff6ff; border-left: 3px solid #3b82f6;
		}
	</style>

    <div class="homeround_content">

		<div class="briefing-header">
			<h2>🏙️ City Briefing</h2>
			<span class="briefing-date" id="briefingDate"></span>
		</div>
		<div class="briefing-panels">
			<div class="briefing-toggle">
				<button class="toggle-btn active" data-view="section">📂 Group by Section</button>
				<button class="toggle-btn" data-view="time">📅 Group by Date</button>
			</div>
			<!-- Cards hidden for now -->
			<div class="briefing-cards" id="cardFeed" style="display:none;"></div>
			<div id="tickerFeed"></div>
		</div>
	
		<style>
			.home-card {
				border: 1px solid var(--db-border);
				border-radius: var(--db-radius);
				padding: var(--db-space-2);
				height: 100%;
				transition: border-color var(--db-transition), background-color var(--db-transition), box-shadow var(--db-transition);
				text-decoration: none;
				color: inherit;
				display: block;
			}
			.home-card:hover {
				border-color: var(--db-border-strong);
				background-color: var(--db-navy-050);
				box-shadow: var(--db-shadow-md);
				text-decoration: none;
				color: inherit;
			}
			/* Blog article cards hover */
			.col-md-4 .card { transition: border-color var(--db-transition), box-shadow var(--db-transition); }
			.col-md-4 a:hover .card {
				border-color: var(--db-border-strong) !important;
				box-shadow: var(--db-shadow-md) !important;
			}
		</style>

		<!-- Our Data -->
		<div class="briefing-header" style="margin-top: 20px;">
			<h2>📊 Our Data</h2>
			<a href="{{ route('about.data') }}" style="font-size: 13px; font-weight: 600; color: var(--db-link); text-decoration: none;">Learn more →</a>
		</div>
		<p class="text-muted" style="margin: 8px 0 12px; font-size: 14px;">All our data comes from official, public NYC government sources. We're currently processing <strong id="total_datasets_no" class="prj_stat gs_thousandscomma">&nbsp;</strong> datasets with <strong id="total_records_no" class="prj_stat gs_thousandscomma">&nbsp;</strong> records that were last updated <strong id="latest_update" class="prj_stat">&nbsp;</strong>.</p>
		<div class="row">
			<!-- Notices -->
			<div class="col-md-3 mb-3">
				<a href="{{ route('notices') }}" class="home-card">
					<div class="d-flex align-items-center mb-2">
						<img src="/img/request.png" style="width: 36px; height: 36px; margin-right: 10px;">
						<h5 style="margin: 0; font-weight: 700;">Notices</h5>
					</div>
					<p class="text-muted small mb-2">City Record agency news</p>
					<div class="row text-center mb-0">
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Today</div>
							<strong id="notices_all_1" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">7 Days</div>
							<strong id="notices_all_7" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">30 Days</div>
							<strong id="notices_all_30" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
					</div>
				</a>
			</div>

			<!-- Organizations -->
			<div class="col-md-3 mb-3">
				<a href="{{ route('orgs') }}" class="home-card">
					<div class="d-flex align-items-center mb-2">
						<img src="/img/people.png" style="width: 36px; height: 36px; margin-right: 10px;">
						<h5 style="margin: 0; font-weight: 700;">Organizations</h5>
					</div>
					<p class="text-muted small mb-2">City agencies & groups</p>
					<div class="row text-center mb-0">
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Agencies</div>
							<strong id="agencies_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">All Orgs</div>
							<strong id="orgs_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Sources</div>
							<strong id="orgs_datasets_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
					</div>
				</a>
			</div>

			<!-- People -->
			<div class="col-md-3 mb-3">
				<a href="{{ route('people') }}" class="home-card">
					<div class="d-flex align-items-center mb-2">
						<img src="/img/profile.png" style="width: 36px; height: 36px; margin-right: 10px;">
						<h5 style="margin: 0; font-weight: 700;">People</h5>
					</div>
					<p class="text-muted small mb-2">NYC government profiles</p>
					<div class="row text-center mb-0">
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Salaries</div>
							<strong id="salary" class="prj_stat gs_finshort">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Employees</div>
							<strong id="employees_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Contacts</div>
							<strong id="contacts_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
					</div>
				</a>
			</div>

			<!-- Titles -->
			<div class="col-md-3 mb-3">
				<a href="{{ route('titles') }}" class="home-card">
					<div class="d-flex align-items-center mb-2">
						<img src="/img/jobs.png" style="width: 36px; height: 36px; margin-right: 10px;">
						<h5 style="margin: 0; font-weight: 700;">Titles</h5>
					</div>
					<p class="text-muted small mb-2">Civil service title profiles</p>
					<div class="row text-center mb-0">
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Titles</div>
							<strong id="titles_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Positions</div>
							<strong id="positions_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Jobs</div>
							<strong id="jobs_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
					</div>
				</a>
			</div>

			<!-- Capital Program -->
			<div class="col-md-3 mb-3">
				<a href="{{ route('capital') }}" class="home-card">
					<div class="d-flex align-items-center mb-2">
						<img src="/img/projects.png" style="width: 36px; height: 36px; margin-right: 10px;">
						<h5 style="margin: 0; font-weight: 700;">Projects</h5>
					</div>
					<p class="text-muted small mb-2">Capital budget & commitments</p>
					<div class="row text-center mb-0">
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Projects</div>
							<strong id="projects_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Orig. Cost</div>
							<strong id="orig_cost" class="prj_stat gs_finshort" data-multiplier="1000">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Curr. Cost</div>
							<strong id="curr_cost" class="prj_stat gs_finshort" data-multiplier="1000">&nbsp;</strong>
						</div>
					</div>
				</a>
			</div>

			<!-- Schools -->
			<div class="col-md-3 mb-3">
				<a href="{{ route('schools') }}" class="home-card">
					<div class="d-flex align-items-center mb-2">
						<img src="/img/services.png" style="width: 36px; height: 36px; margin-right: 10px;">
						<h5 style="margin: 0; font-weight: 700;">Schools</h5>
					</div>
					<p class="text-muted small mb-2">K-12 school & building profiles</p>
					<div class="row text-center mb-0">
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Schools</div>
							<strong id="schools_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Students</div>
							<strong id="students_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Projects</div>
							<strong id="prj_no" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
					</div>
				</a>
			</div>

			<!-- Districts -->
			<div class="col-md-3 mb-3">
				<a href="{{ route('districts') }}" class="home-card">
					<div class="d-flex align-items-center mb-2">
						<img src="/img/indicators.png" style="width: 36px; height: 36px; margin-right: 10px;">
						<h5 style="margin: 0; font-weight: 700;">Districts</h5>
					</div>
					<p class="text-muted small mb-2">Neighborhood & council data</p>
					<div class="row text-center mb-0">
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Community</div>
							<strong id="dist_cd" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Council</div>
							<strong id="dist_cc" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Hoods</div>
							<strong id="dist_nta" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
					</div>
				</a>
			</div>

			<!-- Procurement -->
			<div class="col-md-3 mb-3">
				<a href="{{ route('procurement.index') }}" class="home-card">
					<div class="d-flex align-items-center mb-2">
						<img src="/img/request.png" style="width: 36px; height: 36px; margin-right: 10px;">
						<h5 style="margin: 0; font-weight: 700;">Procurement</h5>
					</div>
					<p class="text-muted small mb-2">Contracts, vendors & bids</p>
					<div class="row text-center mb-0">
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Contracts</div>
							<strong id="procurement_contracts" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Vendors</div>
							<strong id="procurement_vendors" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
						<div class="col-4">
							<div style="font-size: 11px; color: #6c757d; text-transform: uppercase;">Solicitations</div>
							<strong id="procurement_solicitations" class="prj_stat gs_thousandscomma">&nbsp;</strong>
						</div>
					</div>
				</a>
			</div>
		</div>

	{{--
		<h1 class="my-4">More Apps</h1>
        <div class="row mb-5">
            <div class="col-md-6">
				<div class="circle_img">
					<img src="/img/jobs.png">
				</div>
				<div class="content_area">
					<h4>Auctions</h4>
					<p>A list of items being sold by the city.</p>
					<a class="btn_org_home_sm2" href="{{ route('auctions') }}" role="button" target="_blank">View Auctions</a>
				</div>
            </div>
            <div class="col-md-6">
				<div class="circle_img">
					<img src="/img/profile.png">
				</div>
				<div class="content_area">
					<h4>Participate</h4>
					<p>Tell us what you think on our engagement platform.</p>
					<a class="btn_org_home_sm2" href="https://participate.wegov.nyc/assemblies/wegovga" role="button" target="_blank" rel="nofollow">Join Us</a>
				</div>
            </div>
        </div>
	--}}

    @if(isset($articles) && count($articles) > 0)
	<div class="briefing-header" style="margin-top: 20px;">
		<h2>📰 The Latest from WeGovNYC</h2>
		<a href="{{ route('blog') }}" style="font-size: 13px; font-weight: 600; color: var(--db-link); text-decoration: none;">More Posts →</a>
	</div>
    <div class="row mb-5" style="margin-top: 12px;">
        @foreach($articles as $article)
        <div class="col-md-4 d-flex align-items-stretch">
            <a href="{{ route('article', ['slug' => $article['slug']]) }}" class="w-100" style="text-decoration: none; color: inherit; display: block;">
            <div class="card w-100 shadow-sm border-0" style="border-radius: 4px; overflow: hidden; transition: border-color 0.2s, box-shadow 0.2s; border: 1px solid transparent; height: 100%;">
                @if(isset($article['image']['url']))
                    <div style="height: 200px; background-image: url('{{ $article['image']['url'] }}'); background-size: cover; background-position: center;"></div>
                @endif
                <div class="card-body d-flex flex-column">
                    <div class="mb-2">
                        <span class="badge bg-light text-dark border" style="font-weight: 500;">{{ $article['category'] ?? 'Update' }}</span>
                        <small class="text-muted ms-2">{{ date('M d, Y', strtotime($article['originalPublishDate'] ?? $article['publishedAt'])) }}</small>
                    </div>
                    <h5 class="card-title fw-bold text-dark">{{ $article['title'] }}</h5>
                    <p class="card-text text-muted small flex-grow-1">
                        {{ \Illuminate\Support\Str::limit(strip_tags($article['description'] ?? $article['content'] ?? ''), 120) }}
                    </p>
                </div>
            </div>
            </a>
        </div>
        @endforeach
    </div>
    @endif
	
		<div class="briefing-header" style="margin-top: 20px;">
			<h2>ℹ️ About</h2>
		</div>

		<!-- Work with Us + About WeGovNYC — side by side cards -->
		<div class="row mb-4">
			<div class="col-md-6 mb-3">
				<div class="db-card" style="padding: 24px; height: 100%;">
					<h4 style="margin-bottom: 8px;">Work with Us</h4>
					<p class="text-muted">We create information products and experiences for elected officials, journalists, educators, city agencies and others.</p>
					<a href="https://wegovnyc.notion.site/Contact-Us-54b075fa86ec47ebae48dae1595afc2c" target="_blank" rel="nofollow" class="btn_org_home_sm2">Contact Us</a>
				</div>
			</div>
			<div class="col-md-6 mb-3">
				<div class="db-card" style="padding: 24px; height: 100%;">
					<h4 style="margin-bottom: 8px;">About WeGov.NYC</h4>
					<p class="text-muted">Databook is a project of the WeGov.NYC initiative, funded by Sarapis, a 501(c)(3) nonprofit.</p>
					<a href="https://wegov.nyc" target="_blank" class="btn_org_home_sm2">About WeGov.NYC</a>
				</div>
			</div>
		</div>
    </div>
</div>


@endsection

@section('scripts')
	<script>
		$(document).ready(function() {
			var uu = {!! json_encode($finStatUrls) !!}
			/*
			for (let sel in uu) {
				fapireq(uu[sel], function (resp) {
					var v = resp['data'][0]['res'] ?? '-'
					//console.log(['#orig_cost', '#curr_cost', '#over_budg_am'].includes(sel))
					if ((['#orig_cost', '#curr_cost', '#over_budg_am'].includes(sel)) && (v != '-')) {
						$(sel).text(toFinShortK(v, 1000))
						$(sel).attr('data-content', toFin(v, 1000))
					}
					else
						$(sel).text(v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","))
				})
			}
			*/
			globStatView({!! json_encode($globStats) !!})

			// Override stale static stats with live data from the API
			fetch('{{ \App\Custom\DatabookAPI::url("/pipeline/dataset-counts") }}')
				.then(function(r) { return r.ok ? r.json() : Promise.reject('API error'); })
				.then(function(d) {
					if (d.total_datasets_no) $('#total_datasets_no').text(commaThousands(d.total_datasets_no));
					if (d.total_records_no) $('#total_records_no').text(commaThousands(d.total_records_no));
					if (d.latest_update) {
						var dt = new Date(d.latest_update);
						$('#latest_update').text(dt.toLocaleString('en-US', {
							year:'numeric', month:'numeric', day:'numeric',
							hour:'numeric', minute:'numeric', timeZone:'America/New_York'
						}));
					}
				})
				.catch(function(e) { console.log('[stats] Live counts unavailable:', e); });
			
			setTimeout(function(){
				initPopovers();
			}, 700);

			// ── Morning Briefing ──────────────────────────────────────
			var SECTIONS = {
				hearing:       { label: 'Public Hearing',     dot: '#1e40af', badge: 'badge-hearing' },
				rules:         { label: 'Rules & Regulations', dot: '#6b21a8', badge: 'badge-rules' },
				contracts:     { label: 'Contracts',           dot: '#c2410c', badge: 'badge-contracts' },
				solicitations: { label: 'Solicitations',       dot: '#a16207', badge: 'badge-solicitations' },
				capital:       { label: 'Capital Projects',    dot: '#166534', badge: 'badge-capital' },
				jobs:          { label: 'Jobs',                dot: '#0f766e', badge: 'badge-jobs' },
				personnel:     { label: 'Personnel',           dot: '#4b5563', badge: 'badge-personnel' },
				schools:       { label: 'Schools',             dot: '#9d174d', badge: 'badge-schools' },
				vendors:       { label: 'New Vendors',         dot: '#7c3aed', badge: 'badge-vendors' }
			};

			// Helper: date offsets
			function dOff(n) { var d = new Date(); d.setDate(d.getDate()+n); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
			var TODAY = dOff(0), YESTERDAY = dOff(-1), TOMORROW = dOff(1);

			// Mock items — realistic NYC data
			var MOCK = [
				// ── Public Hearings ──
				{s:'hearing', title:'Speed Camera Program Renewal — Public Comment Session', agency:'DOT', date:TODAY, time:'10:00 AM', loc:'22 Reade St, Hearing Room 2A', url:'/notices'},
				{s:'hearing', title:'Proposed Zoning Amendment — Gowanus Rezoning Phase 2', agency:'DCP', date:TODAY, time:'2:00 PM', loc:'120 Broadway, 31st Floor', url:'/notices'},
				{s:'hearing', title:'Water Rate Increase Proposal — FY2027', agency:'DEP', date:TOMORROW, time:'10:00 AM', loc:'59-17 Junction Blvd, Flushing', url:'/notices'},
				{s:'hearing', title:'NYCHA RAD Conversion — Red Hook Houses', agency:'NYCHA', date:dOff(3), time:'6:00 PM', loc:'Red Hook Community Center', url:'/notices'},
				{s:'hearing', title:'Street Vendor Permit Cap — Council Oversight', agency:'Council', date:dOff(5), time:'1:00 PM', loc:'250 Broadway, Committee Room', url:'/notices'},

				// ── Rules & Regulations ──
				{s:'rules', title:'Adopted: Updated Sidewalk Café Permit Requirements', agency:'DCA', date:TODAY, context:'Effective immediately. Requires ADA-compliant seating plans.', url:'/notices'},
				{s:'rules', title:'Proposed: Commercial Waste Zone Rate Changes', agency:'DSNY', date:TODAY, context:'Open for comment until Mar 19. Affects 30,000+ businesses.', url:'/notices'},
				{s:'rules', title:'Adopted: Building Energy Grade Posting Rules', agency:'DOB', date:YESTERDAY, context:'LL97 compliance. All buildings >25,000 sqft must post by May 1.', url:'/notices'},
				{s:'rules', title:'Proposed: AI Hiring Tool Audit Requirements', agency:'DCWP', date:dOff(2), context:'Comment period: 30 days. Applies to automated employment decisions.', url:'/notices'},
				{s:'rules', title:'Adopted: E-Bike Battery Safety Standards', agency:'FDNY', date:dOff(-3), context:'UL 2271 certification required for all commercial e-bike batteries.', url:'/notices'},

				// ── Contracts ──
				{s:'contracts', title:'$4.2M Waste Collection Fleet Upgrade — Registration Complete', agency:'DSNY', date:TODAY, context:'Vendor: Mack Trucks. Contract #CT-23891.', amount:'$4.2M', url:'/procurement/contracts'},
				{s:'contracts', title:'$18.7M IT Modernization — Systems Integration', agency:'DoITT', date:TODAY, context:'Vendor: Deloitte. 3-year term. Replaces legacy HR system.', amount:'$18.7M', url:'/procurement/contracts'},
				{s:'contracts', title:'$890K Street Light LED Conversion — Phase 3', agency:'DOT', date:YESTERDAY, context:'Vendor: Musco Lighting. Covers 12,000 fixtures in Queens.', amount:'$890K', url:'/procurement/contracts'},
				{s:'contracts', title:'$2.1M Emergency Shelter Staffing — Extension', agency:'DHS', date:YESTERDAY, context:'Vendor: BRC. 6-month extension through Sep 2026.', amount:'$2.1M', url:'/procurement/contracts'},
				{s:'contracts', title:'$56M Ferry Service Operations — Expiring Mar 15', agency:'EDC', date:dOff(4), context:'NYC Ferry operator Hornblower. Renewal pending.', amount:'$56M', url:'/procurement/contracts'},
				{s:'contracts', title:'$320K Legal Services — Immigrant Affairs', agency:'MOIA', date:dOff(-4), context:'Vendor: Legal Aid Society. ActionNYC program.', amount:'$320K', url:'/procurement/contracts'},

				// ── Solicitations ──
				{s:'solicitations', title:'RFP: Citywide Broadband Equity Study', agency:'DoITT', date:TODAY, context:'Due Mar 28. Budget: $2-5M. Focus on NYCHA developments.', url:'/procurement/solicitations'},
				{s:'solicitations', title:'RFP: Affordable Housing Marketing Agent', agency:'HPD', date:TOMORROW, context:'Due Apr 4. Lottery marketing for 15 developments.', url:'/procurement/solicitations'},
				{s:'solicitations', title:'IFB: Park Bench Replacement — Prospect Park', agency:'DPR', date:dOff(-2), context:'Due Mar 18. 200 benches. Bid #IFB-20260305.', url:'/procurement/solicitations'},
				{s:'solicitations', title:'RFP: Youth Summer Employment Outreach', agency:'DYCD', date:dOff(3), context:'Due Apr 1. Target: 100K placements. Budget: $800K.', url:'/procurement/solicitations'},
				{s:'solicitations', title:'RFEI: EV Charging Infrastructure — Municipal Fleet', agency:'DCAS', date:dOff(-5), context:'Due Mar 25. 500+ Level 2 chargers across 50 sites.', url:'/procurement/solicitations'},

				// ── Capital Projects ──
				{s:'capital', title:'BQE Triple Cantilever — Design Phase Complete', agency:'DOT', date:TODAY, context:'$1.8B project. Construction procurement begins Q2 2026.', amount:'$1.8B', url:'/capital/projects'},
				{s:'capital', title:'Rikers Island Closure — Borough Jail Construction 40% Complete', agency:'DDC', date:YESTERDAY, context:'Bronx site on schedule. $2.7B of $8.7B program spent.', amount:'$8.7B', url:'/capital/projects'},
				{s:'capital', title:'East Side Coastal Resiliency — Seawall Section B Poured', agency:'DDC', date:dOff(-2), context:'$1.45B project protecting Lower East Side. On schedule.', amount:'$1.45B', url:'/capital/projects'},
				{s:'capital', title:'Kensington Library Renovation — Permit Approved', agency:'DDC', date:dOff(2), context:'$12M renovation. Construction start Jun 2026.', amount:'$12M', url:'/capital/projects'},
				{s:'capital', title:'Jamaica Water Pollution Control Plant Upgrade', agency:'DEP', date:dOff(-6), context:'$440M. Biological nutrient removal. 60% complete.', amount:'$440M', url:'/capital/projects'},

				// ── Jobs ──
				{s:'jobs', title:'City Planner — Gowanus Rezoning Implementation', agency:'DCP', date:TODAY, context:'Salary: $72K-$95K. Exam #: Open competitive.', url:'/titles'},
				{s:'jobs', title:'Senior Data Analyst — Mayor\'s Office of Data Analytics', agency:'MODA', date:TODAY, context:'Salary: $85K-$110K. Python, SQL required.', url:'/titles'},
				{s:'jobs', title:'Emergency Medical Specialist — Level 2', agency:'FDNY', date:YESTERDAY, context:'Salary: $42K-$68K. EMT cert required. 50 positions.', url:'/titles'},
				{s:'jobs', title:'Bridge Painter — Dept. of Transportation', agency:'DOT', date:dOff(-2), context:'Salary: $58K-$72K. Civil service exam #6048.', url:'/titles'},
				{s:'jobs', title:'Social Worker — Homeless Services', agency:'DHS', date:dOff(1), context:'Salary: $62K-$78K. LMSW required. 25 openings.', url:'/titles'},
				{s:'jobs', title:'Cybersecurity Analyst — DoITT', agency:'DoITT', date:dOff(-4), context:'Salary: $90K-$120K. CISSP preferred.', url:'/titles'},

				// ── Personnel Changes ──
				{s:'personnel', title:'Commissioner Appointment — Dept. of Buildings', agency:'DOB', date:TODAY, context:'New commissioner effective Mar 10.', url:'/notices'},
				{s:'personnel', title:'Deputy Commissioner Resignation — Parks & Recreation', agency:'DPR', date:YESTERDAY, context:'Effective Mar 14. Interim appointment pending.', url:'/notices'},
				{s:'personnel', title:'Chief Technology Officer — Mayor\'s Office', agency:'OTI', date:dOff(-3), context:'New CTO from private sector. Start date Mar 17.', url:'/notices'},

				// ── Schools ──
				{s:'schools', title:'PS 89 Liberty School — HVAC Modernization Complete', agency:'SCA', date:TODAY, context:'$3.2M project. Serves 650 students in FiDi.', amount:'$3.2M', url:'/schools'},
				{s:'schools', title:'New 600-Seat School — Hunters Point, Queens', agency:'SCA', date:dOff(-1), context:'Construction 75% complete. Opening Sep 2026.', url:'/schools'},
				{s:'schools', title:'IS 230 Jackson Heights — Accessibility Retrofit', agency:'SCA', date:dOff(3), context:'$8.5M. Elevator, ramps, ADA bathrooms.', amount:'$8.5M', url:'/schools'},
				{s:'schools', title:'Citywide Lead Paint Abatement — Phase 4 Complete', agency:'SCA', date:dOff(-5), context:'47 schools remediated. $22M invested in FY26.', amount:'$22M', url:'/schools'}
			];

			// Classify items into time windows
			function getWindow(dateStr) {
				if (dateStr === TODAY) return 'today';
				if (dateStr === YESTERDAY) return 'yesterday';
				if (dateStr === TOMORROW) return 'tomorrow';
				var d = new Date(dateStr + 'T12:00:00'), now = new Date(TODAY + 'T12:00:00');
				var diff = (d - now) / 86400000;
				if (diff >= -7 && diff < 0) return 'last7';
				if (diff > 0 && diff <= 7) return 'next7';
				return null;
			}

			// Set date header
			var opts = {weekday:'long', year:'numeric', month:'long', day:'numeric'};
			$('#briefingDate').text(new Date().toLocaleDateString('en-US', opts));

			// Count per window
			var counts = {today:0, yesterday:0, tomorrow:0, last7:0, next7:0};
			MOCK.forEach(function(m) {
				var w = getWindow(m.date);
				// today/yesterday/tomorrow also count in 7-day windows
				if (w === 'today' || w === 'yesterday' || w === 'last7') counts.last7++;
				if (w === 'today' || w === 'tomorrow' || w === 'next7') counts.next7++;
				if (w === 'today') counts.today++;
				if (w === 'yesterday') counts.yesterday++;
				if (w === 'tomorrow') counts.tomorrow++;
			});
			Object.keys(counts).forEach(function(k) {
				$('#count-' + k).text(counts[k]);
			});

			// Render a single time window's ticker
			function renderTickerSection(items) {
				var grouped = {};
				items.forEach(function(m) {
					if (!grouped[m.s]) grouped[m.s] = [];
					grouped[m.s].push(m);
				});

				var html = '';
				var sectionOrder = ['hearing','rules','contracts','solicitations','capital','jobs','personnel','schools','vendors'];
				sectionOrder.forEach(function(sec) {
					if (!grouped[sec]) return;
					var si = SECTIONS[sec];
					html += '<div class="ticker-section">';
					html += '<div class="ticker-section-header"><span class="sec-dot" style="background:'+si.dot+'"></span>'+si.label+' ('+grouped[sec].length+')</div>';
					grouped[sec].forEach(function(m) {
						var timeLabel = (m.time || '').replace(/^\d{1,2}\/\d{1,2}\/\d{4}\s+/, '').replace(/:00(\s*(AM|PM))/i, '$1');
						if (!timeLabel) {
							var d = new Date(m.date+'T12:00:00');
							timeLabel = d.toLocaleDateString('en-US',{month:'short',day:'numeric'});
						}
						var isExternal = m.url.indexOf('http') === 0;
						html += '<div class="ticker-row" onclick="'+(isExternal ? "window.open('"+m.url+"','_blank')" : "window.location.href='"+m.url+"'")+'">';
						html += '<span class="ticker-badge '+si.badge+'">'+si.label.split(' ')[0]+'</span>';
						html += '<span class="ticker-title">'+m.title+'</span>';
						html += '<span class="ticker-agency">'+m.agency+'</span>';
						html += '<span class="ticker-time">'+timeLabel+'</span>';
						html += '</div>';
					});
					html += '</div>';
				});
				return html;
			}

			// Render all time windows stacked
			function renderAllWindows() {
				// Always-open sections in desired order
				var openWindows = [
					{key: 'today', label: 'Today', icon: '☀️'},
					{key: 'tomorrow', label: 'Tomorrow', icon: '📅'},
					{key: 'next7', label: 'Next 7 Days', icon: '⏩'},
					{key: 'yesterday', label: 'Yesterday', icon: '⏮️'}
				];

				var fullHtml = '';
				openWindows.forEach(function(win) {
					var items = MOCK.filter(function(m) {
						return getWindow(m.date) === win.key;
					});
					if (items.length === 0) return;

					fullHtml += '<div class="time-window">';
					fullHtml += '<div class="time-window-header">';
					fullHtml += '<span class="time-window-label">'+win.icon+' '+win.label+'</span>';
					fullHtml += '<span class="time-window-count">'+items.length+' items</span>';
					fullHtml += '</div>';
					fullHtml += '<div class="briefing-ticker">';
					fullHtml += renderTickerSection(items);
					fullHtml += '</div>';
					fullHtml += '</div>';
				});

				// Last 7 Days — collapsible, closed by default
				var last7Items = MOCK.filter(function(m) {
					return getWindow(m.date) === 'last7';
				});
				if (last7Items.length > 0) {
					fullHtml += '<div class="time-window">';
					fullHtml += '<div class="time-window-header collapsible" data-target="ext-last7">';
					fullHtml += '<span class="time-window-label"><span class="toggle-icon">▶</span> ⏪ Last 7 Days</span>';
					fullHtml += '<span class="time-window-count">'+last7Items.length+' more items</span>';
					fullHtml += '</div>';
					fullHtml += '<div class="time-window-body briefing-ticker" id="ext-last7">';
					fullHtml += renderTickerSection(last7Items);
					fullHtml += '</div>';
					fullHtml += '</div>';
				}

				$('#tickerFeed').html(fullHtml);

				// Toggle handler for collapsible sections
				$('.time-window-header.collapsible').on('click', function() {
					var target = $('#' + $(this).data('target'));
					$(this).toggleClass('open');
					target.toggleClass('open');
				});
			}

			// Group by Section view — all items grouped by section type
			function renderBySection() {
				var allItems = MOCK.filter(function(m) { return getWindow(m.date) !== null; });
				var grouped = {};
				allItems.forEach(function(m) {
					if (!grouped[m.s]) grouped[m.s] = [];
					grouped[m.s].push(m);
				});

				var sectionOrder = ['hearing','rules','contracts','solicitations','capital','jobs','personnel','schools','vendors'];
				var fullHtml = '';
				sectionOrder.forEach(function(sec) {
					if (!grouped[sec] || grouped[sec].length === 0) return;
					// Sort items within each section by date, earliest first
					grouped[sec].sort(function(a, b) { return (a.date || '').localeCompare(b.date || ''); });
					var si = SECTIONS[sec];
					fullHtml += '<div class="time-window">';
					fullHtml += '<div class="time-window-header">';
					fullHtml += '<span class="time-window-label"><span class="sec-dot" style="background:'+si.dot+';display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px"></span>'+si.label+'</span>';
					fullHtml += '<span class="time-window-count">'+grouped[sec].length+' items</span>';
					fullHtml += '</div>';
					fullHtml += '<div class="briefing-ticker">';
					grouped[sec].forEach(function(m) {
						var d = new Date(m.date+'T12:00:00');
						var dateLabel = d.toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'});
						var isExternal = m.url.indexOf('http') === 0;
						var todayCls = (m.date === TODAY) ? ' ticker-today' : '';
						fullHtml += '<div class="ticker-row'+todayCls+'" onclick="'+(isExternal ? "window.open('"+m.url+"','_blank')" : "window.location.href='"+m.url+"'")+'"><span class="ticker-badge '+si.badge+'">'+dateLabel+'</span><span class="ticker-title">'+m.title+'</span><span class="ticker-agency">'+m.agency+'</span>';
						if (m.amount) fullHtml += '<span class="ticker-time">'+m.amount+'</span>';
						fullHtml += '</div>';
					});
					fullHtml += '</div></div>';
				});
				$('#tickerFeed').html(fullHtml);
			}

			// Active view tracker
			var currentView = 'section';
			function renderCurrentView() {
				if (currentView === 'section') renderBySection();
				else renderAllWindows();
			}

			// Toggle handler
			$('.briefing-toggle .toggle-btn').on('click', function() {
				$('.briefing-toggle .toggle-btn').removeClass('active');
				$(this).addClass('active');
				currentView = $(this).data('view');
				renderCurrentView();
			});

			// Try live API first, fallback to mock data
			var BRIEFING_DATA = MOCK; // default to mock
			fetch('{{ \App\Custom\DatabookAPI::url("/pipeline/briefing") }}')
				.then(function(r) { return r.ok ? r.json() : Promise.reject('API error'); })
				.then(function(data) {
					if (data && data.length > 0) {
						MOCK = data;
						console.log('[briefing] Loaded ' + data.length + ' live items');
					} else {
						console.log('[briefing] API returned empty, using mock data');
					}
					renderCurrentView();
				})
				.catch(function(err) {
					console.log('[briefing] API unavailable, using mock data:', err);
					renderCurrentView();
				});
		})
	</script>

@endsection
