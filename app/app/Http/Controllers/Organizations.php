<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\OrgsDatasets;
use App\Custom\ProjectsDatasets;
use App\Custom\UnDatasets;
use App\Custom\Breadcrumbs;
use App\Custom\CapProjectsBuilder;
use App\Custom\CapProjectsBuilder2024;
use App\Custom\DatabookAPI;
use App\Custom\Schema;
use Illuminate\Support\Str;


class Organizations extends Controller
{
	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function root()
	{
		try {
			$dates = DatabookAPI::req('/get/capitalprojects/dates');
			$date = ($dates && isset($dates[0]['PUB_DATE'])) ? $dates[0]['PUB_DATE'] : '2024-01-01';
		} catch (\Exception $e) {
			// If API call fails, use default date
			$date = '2024-01-01';
		}
		return view('root', [
			'breadcrumbs' => Breadcrumbs::root(),
			'tblStatsUrl' => DatabookAPI::url('/get/pstats-records_no/tblname'),
			'finStatUrls' => [
				'#projects_no' => DatabookAPI::url("/get/pstats-projects_no/{$date}"),
				'#orig_cost' => DatabookAPI::url("/get/pstats-orig_cost/{$date}"),
				'#curr_cost' => DatabookAPI::url("/get/pstats-curr_cost/{$date}"),
				'#over_budg_am' => DatabookAPI::url("/get/pstats-over_budg_am/{$date}"),
				'#long_no' => DatabookAPI::url("/get/pstats-long_no/{$date}"),
				'#over_budg_no' => DatabookAPI::url("/get/pstats-over_budg_no/{$date}"),
				'#late_start_no' => DatabookAPI::url("/get/pstats-late_start_no/{$date}"),
				'#late_end_no' => DatabookAPI::url("/get/pstats-late_end_no/{$date}"),
			],
			'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
			####### seo ########
			'pagetitle' => "NYC DataBook - Open Data Application for New York City Government Transparency",
			'articles' => (new \App\Services\PayloadService())->getLatestArticles(3, 'Databook'),
		]);
	}


	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function about()
	{
		$ds = new OrgsDatasets();
		return view('about', [
			#'breadcrumbs' => Breadcrumbs::about(),
			####### seo ########
			'pagetitle' => "About NYC Databook - Award-Winning Open Data NYC Government Transparency App",
			'datasets' => $ds->all_data_sources(DatabookAPI::req('/get/datasets/all')),
			'slist' => $ds->list,
			'allDS' => $ds->dd,
		]);
	}


	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function orgsChart($id = null)
	{
		// Citywide hierarchy is a static, curated tree; render it server-side as a
		// db-tree (replaces the jquery.orgchart plugin).
		$chartPath = public_path('data/orgChart.json');
		$chart = is_file($chartPath) ? json_decode(file_get_contents($chartPath), true) : null;
		return view('orgsChart', [
			'breadcrumbs' => Breadcrumbs::orgsChart(),
			'chart' => $chart,
			'defType' => $_GET['type'] ?? 'City Agency',
			'defTag' => $_GET['tag'] ?? null,
			'defSearch' => $_GET['search'] ?? null,
			'defId' => $id,
			####### seo ########
			'pagetitle' => "City Agency & Organizations - Open Data Driven Profiles by NYC Databook",
		]);
	}


	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function orgsDirectory()
	{
		return view('orgsDirectory', [
			'url' => DatabookAPI::url('/get/orgs/directory'),
			'breadcrumbs' => Breadcrumbs::orgs(),
			'defType' => $_GET['type'] ?? 'City Agency',
			'defTag' => $_GET['tag'] ?? null,
			'defSearch' => $_GET['search'] ?? null,
			'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
			####### seo ########
			'pagetitle' => "City Agency & Organizations - Open Data Driven Profiles by NYC Databook",
		]);
	}


	/**
	 * Show city agencies only.
	 *
	 * @return \Illuminate\View\View
	 */
	public function orgsAgencies()
	{
		return view('orgsAgencies', [
			'url' => DatabookAPI::url('/get/orgs/directory'),
			'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
			'pagetitle' => "NYC City Agencies - Data Driven Profiles by NYC Databook",
		]);
	}


	/**
	 * Show organizations list.
	 *
	 * @return \Illuminate\View\View
	 */
	public function orgsAll($req=null)
	{
		return view('orgsAll', [
			'url' => DatabookAPI::url('/get/orgs/all'),
			'breadcrumbs' => Breadcrumbs::orgsAll(),
			'defType' => $_GET['type'] ?? null,
			'defTag' => $_GET['tag'] ?? null,
			'defSearch' => $req ?? $_GET['search'] ?? null,
			####### seo ########
			'pagetitle' => "City Agency & Organizations - Open Data Driven Profiles by NYC Databook",
		]);
	}


	/**
	 * Show organization profile - section about.
	 *
	 * @param  int  $id
	 * @return \Illuminate\View\View
	 */
	/**
	 * Fetch an org profile, distinguishing a transient API outage from a genuine
	 * not-found. DatabookAPI::req() returns `false` when the API is unreachable
	 * (e.g. mid-deploy restart) and `[]` when the API is up but the org doesn't
	 * exist. On a transient failure we retry once, then return a 503 (retryable,
	 * auto-refreshing) instead of a hard, cacheable 404. Returns the org row, or
	 * null when the org genuinely isn't found (caller aborts 404).
	 */
	protected function fetchOrg($id)
	{
		$rows = DatabookAPI::req("/get/orgs/profile/{$id}");
		if ($rows === false) {
			usleep(500000); // ride out a micro-blip before giving up
			$rows = DatabookAPI::req("/get/orgs/profile/{$id}");
		}
		if ($rows === false) {
			abort(response()->view('errors.service-unavailable', [], 503, ['Retry-After' => '5']));
		}
		return $rows[0] ?? null;
	}

	public function orgAbout($id, $orgslug = '')
	{
		$org = $this->fetchOrg($id);
		if (!$org)
			return abort(404);
		if (preg_match('~Union|Bargaining Unit~si', $org['type']))
			return redirect(route('orgSection', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-'), 'section' => 'civil-service-titles']));

		$ds = new OrgsDatasets();
		#$details = $ds->getAbout('jobs');
		$details = $ds->get('jobs-about');
		$positionDetails = $ds->get('positions');
		return view('organization', [
			'id' => $id,
			'org' => $org,
			'slist' => $ds->list,
			'menu' => $ds->menu,
			'activeDropDown' => '',
			'icons' => $ds->socicons,
			'allDS' => $ds->dd,
			'details' => $details,
			'url' => ($details['fapireq'] ?? null)
				? DatabookAPI::url(sprintf($details['fapireq'], $id))
				: DatabookAPI::url("/get/orgs/section/{$id}/{$details['table']}"),
			'positionDataUrl' => DatabookAPI::url("/get/orgs/stats-civillist-aggregated/{$id}"),
			'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
			'tableStatUrls' => [
				'reg' => DatabookAPI::url("/get/orgs/stats-reg/{$id}/tablename"),
				'notices' => DatabookAPI::url("/get/orgs/stats-notices/{$id}/sectionTitle"),
				'noticesEvents' => DatabookAPI::url("/get/orgs/stats-events/{$id}"),
			],
			'finStatUrls' => [
				'headcount' => DatabookAPI::url("/get/orgs/stats-headcount/{$id}"),
				'pastheadcount' => DatabookAPI::url("/get/orgs/stats-pastheadcount/{$id}"),
				'as' => DatabookAPI::url("/get/orgs/stats-as/{$id}"),
				'ac' => DatabookAPI::url("/get/orgs/stats-ac/{$id}"),
				'prj' => DatabookAPI::url("/get/orgs/stats-prj/{$id}"),
			],
			'finStatYear' => 2025,
			'breadcrumbs' => Breadcrumbs::org($id, $org['name']),
			'newsUrl' => DatabookAPI::url("/get/orgs/frontnews/{$id}"),
			'eventsUrl' => DatabookAPI::url("/get/orgs/frontevents/{$id}"),
			'procurementSummaryUrl' => DatabookAPI::url("/oce/agency/summary?name=" . rawurlencode($org['name'])),
			'procurementProfileUrl' => '/procurement/agency/' . rawurlencode($org['name']),
			'datasets' => $ds->data_sources(DatabookAPI::req('/get/datasets/all'), $id, $org['name']),

			####### seo ########
			'schema' => Schema::org($org),
			'pagetitle' => "{$org['name']} | WeGovNYC Databook",
			'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', $org['description']),
			'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]),
		]);
	}


	/**
	 * Show organization profile section.
	 *
	 * @param  int  	$id
	 * @param  string  	$section
	 * @return \Illuminate\View\View
	 */
	public function orgSection($id, $orgslug = null, $section = null)
	{
		$org = $this->fetchOrg($id);
		// Check if org exists before accessing its properties
		if (!$org) {
			return abort(404);
		}
		
		// Handle procurement sections specially
		if (str_starts_with($section, 'procurement-')) {
			return $this->orgProcurementSection($id, $org, $section);
		}
		
		$ds = preg_match('~Union|Bargaining Unit~si', $org['type'])
			? new UnDatasets()
			: new OrgsDatasets();
		$details = $ds->get($section);
		return $org && $details
			? view('orgsection', [
				'id' => $id,
				'org' => $org,
				'section' => $section,
				'slist' => $ds->list,
				'menu' => $ds->menu,
				'activeDropDown' => $ds->menuActiveDD($section),
				'icons' => $ds->socicons,
				'url' => ($details['fapireq'] ?? null)
					? DatabookAPI::url(sprintf($details['fapireq'], $id))
					: DatabookAPI::url("/get/orgs/section/{$id}/{$details['table']}"),
				'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
				'breadcrumbs' => Breadcrumbs::orgSect($org['id'], $org['name'], $section, $ds->list[$section]),
				'details' => $details,
				'map' => $details['map'] ?? null,
				####### seo ########
				#'schema' => Schema::org($org),
				'pagetitle' => "{$org['name']} | WeGovNYC Databook",
				'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', $org['description']),
				'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]),


				'salaryStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-civillist_salaries_by_year"),
				'employeesStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-civillist_entries_by_year"),
				'positionsStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-positionschedule_positions_by_agency"),

			])
			: abort(404);
	}


	/**
	 * Show organization procurement section (Highlights, Contracts, Solicitations, Vendors).
	 *
	 * @param  int  	$id
	 * @param  array  	$org
	 * @param  string  	$section
	 * @return \Illuminate\View\View
	 */
	protected function orgProcurementSection($id, $org, $section)
	{
		$ds = new OrgsDatasets();
		
		// Map section to subsection name
		$subsectionMap = [
			'procurement-highlights' => 'highlights',
			'procurement-contracts' => 'contracts',
			'procurement-solicitations' => 'solicitations',
			'procurement-vendors' => 'vendors',
			'procurement-transactions' => 'transactions',
		];
		
		$subsection = $subsectionMap[$section] ?? 'highlights';

		// NYCHA is a separate public authority — its procurement lives in the
		// dedicated /oce/nycha/* domains (Checkbook `_NYCHA` feeds), NOT the City
		// contracts/solicitations/spending tables that the shared agency_body reads
		// (which is why the standard tab is empty for it). Render the NYCHA hub body
		// (explanatory flag + the four domain cards) instead.
		$isNycha = (string) ($org['id'] ?? '') === '170020034'
			|| stripos($org['name'] ?? '', 'housing authority') !== false;
		if ($isNycha) {
			$orgslug = Str::slug($org['name'], '-');
			// Shared org-profile chrome for every NYCHA procurement page (org header
			// + on-page NYCHA tabs). The tabs/cards build orgSection URLs from these.
			$chrome = [
				'id' => $id,
				'org' => $org,
				'section' => $section,
				'subsection' => $subsection,
				'orgslug' => $orgslug,
				'slist' => $ds->list,
				'menu' => $ds->menu,
				'activeDropDown' => 'Procurement',
				'icons' => $ds->socicons,
				'breadcrumbs' => Breadcrumbs::orgSect($org['id'], $org['name'], $section, $ds->list[$section] ?? 'Procurement'),
				'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => $orgslug]),
			];
			$fy = request()->input('fiscal_year');
			$q  = $fy ? "?fiscal_year={$fy}" : '';
			$qc = $fy ? "&fiscal_year={$fy}" : '';
			switch ($section) {
				case 'procurement-nycha-budget':
					$bq = trim((string) request()->input('q', ''));
					$bsort = request()->input('sort', 'modified');
					$border = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$bpage = max(1, (int) request()->input('page', 1));
					$brecUrl = '/oce/nycha/budget/records?limit=25&page=' . $bpage
						. '&sort=' . urlencode($bsort) . '&order=' . $border
						. ($fy ? '&fiscal_year=' . $fy : '') . ($bq !== '' ? '&q=' . urlencode($bq) : '');
					return view('procurement.nycha_budget', $chrome + [
						'pagetitle' => "{$org['name']} — Expense Budget | WeGovNYC Databook",
						'snippet' => "NYCHA expense budget — adopted, modified, committed, and actual spending.",
						'summary' => DatabookAPI::reqOCE('/oce/nycha/budget/summary', 60) ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => []],
						'units'   => DatabookAPI::reqOCE('/oce/nycha/budget/units' . $q, 60) ?: ['available' => false, 'data' => [], 'total' => 0],
						'records' => DatabookAPI::reqOCE($brecUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'recFilters' => ['q' => $bq, 'fiscal_year' => $fy, 'sort' => $bsort, 'order' => $border],
					]);
				case 'procurement-nycha-revenue':
					$vq = trim((string) request()->input('q', ''));
					$vsort = request()->input('sort', 'recognized');
					$vorder = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$vpage = max(1, (int) request()->input('page', 1));
					$vrecUrl = '/oce/nycha/revenue/records?limit=25&page=' . $vpage
						. '&sort=' . urlencode($vsort) . '&order=' . $vorder
						. ($fy ? '&fiscal_year=' . $fy : '') . ($vq !== '' ? '&q=' . urlencode($vq) : '');
					return view('procurement.nycha_revenue', $chrome + [
						'pagetitle' => "{$org['name']} — Revenue | WeGovNYC Databook",
						'snippet' => "NYCHA revenue — adopted, modified, and recognized by funding source.",
						'summary' => DatabookAPI::reqOCE('/oce/nycha/revenue/summary', 60) ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => [], 'by_funding_source' => []],
						'sources' => DatabookAPI::reqOCE('/oce/nycha/revenue/sources' . $q, 60) ?: ['available' => false, 'data' => [], 'total' => 0],
						'records' => DatabookAPI::reqOCE($vrecUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'recFilters' => ['q' => $vq, 'fiscal_year' => $fy, 'sort' => $vsort, 'order' => $vorder],
					]);
				case 'procurement-nycha-contracts':
					// Record explorer: search/filter/sort/paginate individual contracts.
					$cq    = trim((string) request()->input('q', ''));
					$csort = request()->input('sort', 'current');
					$corder = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$cpage = max(1, (int) request()->input('page', 1));
					$clim  = 25;
					$cUrl  = '/oce/nycha/contracts?limit=' . $clim
						. '&page=' . $cpage . '&sort=' . urlencode($csort) . '&order=' . $corder
						. ($cq !== '' ? '&q=' . urlencode($cq) : '') . $qc;
					return view('procurement.nycha_contracts', $chrome + [
						'pagetitle' => "{$org['name']} — Contracts | WeGovNYC Databook",
						'snippet' => "NYCHA contracts — original, current, and invoiced value by vendor.",
						'summary' => DatabookAPI::reqOCE('/oce/nycha/contracts/summary', 60) ?: ['available' => false, 'totals' => [], 'by_year' => [], 'top_vendors' => []],
						'contracts' => DatabookAPI::reqOCE($cUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'filters' => ['q' => $cq, 'fiscal_year' => $fy, 'sort' => $csort, 'order' => $corder],
					]);
				case 'procurement-nycha-spending':
					$ssum = DatabookAPI::reqOCE('/oce/nycha/spending/summary', 60) ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => [], 'by_funding_source' => [], 'section_8' => [], 'top_vendors' => []];
					// Payment (record) explorer: FY-scoped (default latest) so each query
					// prunes to one partition instead of the full 22.56M-row lake.
					$sFy   = $fy ?: ($ssum['latest_year'] ?? null);
					$sq    = trim((string) request()->input('q', ''));
					$scat  = (string) request()->input('spending_category', '');
					$ss8   = (string) request()->input('section_8', '');
					$ssort = request()->input('sort', 'amount');
					$sorder = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$spage = max(1, (int) request()->input('page', 1));
					$recUrl = '/oce/nycha/spending/records?limit=25&page=' . $spage
						. '&sort=' . urlencode($ssort) . '&order=' . $sorder
						. ($sFy ? '&fiscal_year=' . $sFy : '')
						. ($sq !== '' ? '&q=' . urlencode($sq) : '')
						. ($scat !== '' ? '&spending_category=' . urlencode($scat) : '')
						. (in_array($ss8, ['Y', 'N'], true) ? '&section_8=' . $ss8 : '');
					return view('procurement.nycha_spending', $chrome + [
						'pagetitle' => "{$org['name']} — Spending | WeGovNYC Databook",
						'snippet' => "NYCHA spending — every payment by category, funding source, and development.",
						'summary' => $ssum,
						'developments' => DatabookAPI::reqOCE('/oce/nycha/spending/by-development?sort=spending&limit=50' . ($sFy ? '&fiscal_year=' . $sFy : ''), 60) ?: ['available' => false, 'data' => [], 'total' => 0],
						'records' => DatabookAPI::reqOCE($recUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'recFilters' => ['q' => $sq, 'fiscal_year' => $sFy, 'spending_category' => $scat, 'section_8' => $ss8, 'sort' => $ssort, 'order' => $sorder],
					]);
				case 'procurement-nycha-contract':
					// Individual NYCHA contract profile (detail + actual payments).
					$cpId = trim((string) request()->input('id', ''));
					if ($cpId === '') {
						return redirect(route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-contracts']));
					}
					$cp = DatabookAPI::reqOCE('/oce/nycha/contract?id=' . urlencode($cpId), 60);
					if (!$cp || empty($cp['available'])) {
						abort(404, 'NYCHA contract not found');
					}
					return view('procurement.nycha_contract_profile', $chrome + [
						'pagetitle' => "{$cpId} — NYCHA Contract | WeGovNYC Databook",
						'snippet' => "NYCHA contract {$cpId} — value, vendor, and actual payments (Checkbook NYC).",
						'cp' => $cp,
						'cid' => $cpId,
					]);
				case 'procurement-nycha-vendors':
					// Directory of every NYCHA vendor. Matched vendors link to the
					// City vendor profile; unmatched get a NYCHA-native profile.
					$nvq = trim((string) request()->input('q', ''));
					$nvsort = request()->input('sort', 'spending');
					$nvorder = request()->input('order', 'desc') === 'asc' ? 'asc' : 'desc';
					$nvpage = max(1, (int) request()->input('page', 1));
					$nvUrl = '/oce/nycha/vendors?limit=25&page=' . $nvpage
						. '&sort=' . urlencode($nvsort) . '&order=' . $nvorder
						. ($nvq !== '' ? '&q=' . urlencode($nvq) : '');
					return view('procurement.nycha_vendors', $chrome + [
						'pagetitle' => "{$org['name']} — Vendors | WeGovNYC Databook",
						'snippet' => "NYCHA vendors — contract and payment activity, linked to City vendor profiles where matched.",
						'vendors' => DatabookAPI::reqOCE($nvUrl, 60) ?: ['available' => false, 'data' => [], 'total' => 0, 'page' => 1, 'pages' => 1],
						'filters' => ['q' => $nvq, 'sort' => $nvsort, 'order' => $nvorder],
					]);
				case 'procurement-nycha-vendor':
					// NYCHA-native vendor profile (for vendors with no PASSPort record).
					$vpName = trim((string) request()->input('name', ''));
					if ($vpName === '') {
						return redirect(route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => 'procurement-nycha-vendors']));
					}
					$vp = DatabookAPI::reqOCE('/oce/nycha/vendor?name=' . urlencode($vpName), 60);
					// Crosswalked vendors have a richer City profile (which now shows
					// NYCHA activity) — send them there instead of the NYCHA-native page.
					if ($vp && !empty($vp['vendor_id'])) {
						return redirect(route('procurement.vendor', ['id' => $vp['vendor_id']]));
					}
					return view('procurement.nycha_vendor_profile', $chrome + [
						'pagetitle' => "{$vpName} — NYCHA Vendor | WeGovNYC Databook",
						'snippet' => "NYCHA vendor {$vpName} — contracts and spending (Checkbook NYC).",
						'vp' => $vp ?: ['available' => false, 'contract_list' => [], 'contracts' => null, 'spending' => null],
						'vname' => $vpName,
					]);
				default: // procurement-highlights (and any other procurement-* for NYCHA) → finances overview
					$councilStat = DatabookAPI::req('/get/orgs/stats-reg/' . $id . '/nyccouncildiscretionaryfunding');
					return view('org_procurement_section', $chrome + [
						'isNycha' => true,
						'pagetitle' => "{$org['name']} Finances & Procurement | WeGovNYC Databook",
						'snippet' => "NYCHA finances & procurement — budget, revenue, contracts, spending (Checkbook NYC), and Council discretionary funding.",
						'budget'    => DatabookAPI::reqOCE('/oce/nycha/budget/summary', 30)    ?: ['available' => false, 'totals' => []],
						'revenue'   => DatabookAPI::reqOCE('/oce/nycha/revenue/summary', 30)   ?: ['available' => false, 'totals' => []],
						'contracts' => DatabookAPI::reqOCE('/oce/nycha/contracts/summary', 30) ?: ['available' => false, 'totals' => []],
						'spending'  => DatabookAPI::reqOCE('/oce/nycha/spending/summary', 30)  ?: ['available' => false, 'totals' => []],
						'councilCount' => (int) ($councilStat[0]['count'] ?? 0),
					]);
			}
		}

		// Fetch procurement data from OCE API (cached 24h — data refreshes daily)
		$cacheKey = "org_procurement_" . md5($org['name']);
		$data = \Illuminate\Support\Facades\Cache::remember($cacheKey, 86400, function () use ($org) {
			return DatabookAPI::reqOCE("/oce/agency/procurement?name=" . urlencode($org['name']), 60);
		});
		
		if (!$data || !isset($data['agency'])) {
			// If no procurement data, show empty state
			$data = [
				'agency' => ['name' => $org['name']],
				'stats' => [],
				'monthly_activity' => [],
				'yearly_spending' => [],
				'contracts' => [],
				'solicitations' => [],
				'vendors' => [],
			];
		}
		
		// Transactions are loaded client-side (lazy AJAX) in the view to avoid a slow
		// blocking OCE fetch that could exceed the request timeout (504). The Checkbook
		// query for large agencies is expensive; fetching it in the browser keeps the
		// page responsive. See org_procurement_section.blade.php (transactions subsection).
		$transactions = [];
		
		return view('org_procurement_section', [
			'id' => $id,
			'org' => $org,
			'section' => $section,
			'subsection' => $subsection,
			'slist' => $ds->list,
			'menu' => $ds->menu,
			'activeDropDown' => 'Procurement',
			'icons' => $ds->socicons,
			'breadcrumbs' => Breadcrumbs::orgSect($org['id'], $org['name'], $section, $ds->list[$section] ?? 'Procurement'),
			
			// Procurement data
			'agency' => $data['agency'],
			'stats' => $data['stats'] ?? [],
			'monthly_activity' => $data['monthly_activity'] ?? [],
			'yearly_spending' => $data['yearly_spending'] ?? [],
			'contracts' => $data['contracts'] ?? [],
			'solicitations' => $data['solicitations'] ?? [],
			'vendors' => $data['vendors'] ?? [],
			'transactions' => $transactions,
			
			####### seo ########
			'pagetitle' => "{$org['name']} Procurement | WeGovNYC Databook",
			'snippet' => "Procurement data for {$org['name']} including contracts, solicitations, and vendors.",
			'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]),
		]);
	}




	/**
	 * Show organization notice subsection.
	 *
	 * @param  int  	$id
	 * @param  string  	$subsection
	 * @return \Illuminate\View\View
	 */
	public function orgNoticesSection($id, $subsection)
	{
		return $this->orgSection($id, "notices/{$subsection}");
	}


	/**
	 * Show organization capital projects section.
	 *
	 * @param  int  	$id
	 * @return \Illuminate\View\View
	 */
	public function orgProjectSection($id, $orgslug = '')
	{
		$section = 'projects';
		$org = $this->fetchOrg($id);
		$ds = new OrgsDatasets();
		$details = $ds->get($section);
		return $org && $details
			? view('orgprojectsection', [
				'id' => $id,
				'org' => $org,
				'section' => $section,
				'slist' => $ds->list,
				'menu' => $ds->menu,
				'activeDropDown' => $ds->menuActiveDD($section),
				'icons' => $ds->socicons,
				'url' => DatabookAPI::url("/get/orgs/section/{$id}/{$details['table']}"),
				'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
				'breadcrumbs' => Breadcrumbs::orgSect($org['id'], $org['name'], $section, $ds->list[$section]),
				'details' => $details,
				'map' => true,
				'finStatUrls' => [
					'#projects_no' => DatabookAPI::url("/get/orgs/pstats-projects_no/{$id}/pubdate"),
					'#orig_cost' => DatabookAPI::url("/get/orgs/pstats-orig_cost/{$id}/pubdate"),
					'#curr_cost' => DatabookAPI::url("/get/orgs/pstats-curr_cost/{$id}/pubdate"),
					'#over_budg_am' => DatabookAPI::url("/get/orgs/pstats-over_budg_am/{$id}/pubdate"),
					'#long_no' => DatabookAPI::url("/get/orgs/pstats-long_no/{$id}/pubdate"),
					'#over_budg_no' => DatabookAPI::url("/get/orgs/pstats-over_budg_no/{$id}/pubdate"),
					'#late_start_no' => DatabookAPI::url("/get/orgs/pstats-late_start_no/{$id}/pubdate"),
					'#late_end_no' => DatabookAPI::url("/get/orgs/pstats-late_end_no/{$id}/pubdate"),
				],
				####### seo ########
				#'schema' => Schema::org($org),
				'pagetitle' => "{$org['name']} | WeGovNYC Databook",
				'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', $org['description']),
				'canonicalUrl' => route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]),
			])
			: abort(404);
	}


	/**
	 * Show capital project.
	 *
	 * @param  string  	$prjId
	 * @return \Illuminate\View\View
	 */
	public function project($prjId, $prjslug = '')
	{
		$section = 'projects';
		$ds = new OrgsDatasets();
		$pds = new ProjectsDatasets();
		$details = $ds->get($section);
		$prj = DatabookAPI::req("/get/capitalprojects/core/{$prjId}");		#241
		if (!$prj || !isset($prj[0])) {
			return abort(404);
		}
		// A core row tagged _source='list' is a list-only project (present in
		// capitalprojectslist but absent from the commitment-plan dollars dataset).
		// Render the reduced 'pureproject' page; the full page needs dollarscomp.
		if (($prj[0]['_source'] ?? null) !== 'list') {
			$data = CapProjectsBuilder2024::build($prj[0]);
			if (0)
			{
				echo '<pre>';
				print_r($data);
				return;
			}
			
			$id = $data['id'];
			$org = $this->fetchOrg($id);
			return $org && $details
				? view('orgproject', [
					'id' => $id,
					'prjId' => $prjId,
					'pagetitle' => "{$data['name']} | {$prjId}",
					'org' => $org,
					'section' => $section,
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'activeDropDown' => $ds->menuActiveDD($section),
					'icons' => $ds->socicons,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
					'breadcrumbs' => Breadcrumbs::orgPrj($org['id'], $org['name'], $section, $ds->list[$section], $prjId, $data['name']),
					'urls' => [
						'commitments' => DatabookAPI::url("/get/capitalprojects/commitments/{$prjId}"),
						'budgetandspend' => DatabookAPI::url("/get/capitalprojects/budgetandspend/{$prjId}"),
						'budgetspendhistory' => DatabookAPI::url("/get/capitalprojects/budgetspendhistory/{$prjId}"),
						'schedulehistory' => DatabookAPI::url("/get/capitalprojects/schedulehistory/" . ($prj[0]['magencyacro'] ?? $prj[0]['MANAGING_AGCY_CD'] ?? '')),
						'budgetsandschedule' => DatabookAPI::url("/get/capitalprojects/budgetsandschedule/{$prjId}"),
					],
					#'coreUrl' => DatabookAPI::url("/get/capitalprojects/core/{$prjId}"),
					'data' => $data,
					'map' => true,
					'datasets' => $pds->stats_data_sources(
						DatabookAPI::req('/get/datasets/all'),
						['capitalprojectsdollarscomp', 'capitalprojectsmilestones', 'capitalprojectslist', 'capitalprojectscommitments']
					),
					'tblStatsUrl' => DatabookAPI::url("/get/pstats-records_no-byprj/tblname/{$prjId}"),
					####### seo ########
					'schema' => Schema::project($prj[0], $org),
					'pagetitle' => "{$prj[0]['PROJECT_DESCR']} | WeGovNYC Databook Capital Projects",
					'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', "{$prj[0]['PROJECT_ID']} - {$prj[0]['PROJECT_DESCR']}"),
					'canonicalUrl' => route('project', ['prjId' => $prj[0]['PROJECT_ID'], 'prjslug' => Str::slug($prj[0]['PROJECT_DESCR'], '-')]),
				])
				: abort(404);
		} else {
			$orgId = $prj[0]['wegov-org-id'] ?? null;
			$org = $orgId ? ($this->fetchOrg($orgId)) : null;
			return $org
				? view('pureproject', [
					'id' => $orgId,
					'prjId' => $prjId,
					'pagetitle' => "{$prj[0]['description']} | {$prjId}",
					'org' => $org,
					'section' => $section,
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'activeDropDown' => $ds->menuActiveDD($section),
					'icons' => $ds->socicons,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
					#'coreUrl' => DatabookAPI::url("/get/capitalprojects/core/{$prjId}"),
					'prj' => $prj,
					'commUrl' => DatabookAPI::url("/get/capitalprojects/commitments/{$prjId}"),
					'breadcrumbs' => Breadcrumbs::purePrj($prjId, $prj[0]['description']),
					'map' => true,
					####### seo ########
					#'schema' => Schema::project($prj[0], $org),
					'pagetitle' => "{$prj[0]['description']} | WeGovNYC Databook Capital Projects",
					'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', "{$prjId}"),
					'canonicalUrl' => route('project', ['prjId' => $prjId, 'prjslug' => Str::slug($prj[0]['description'], '-')]),
				])
				: abort(404);
		}
	}


	/**
	 * Show capital project.
	 *
	 * @param  string  	$prjId
	 * @return \Illuminate\View\View
	 */
	public function project_a($prjId, $prjslug = '')
	{
		$section = 'projects';
		$ds = new OrgsDatasets();
		$pds = new ProjectsDatasets();
		$details = $ds->get($section);
		$prj = DatabookAPI::req("/get/capitalprojects/profile/{$prjId}");
		if ($prj) {
			$data = CapProjectsBuilder::build(
				$prj,
				DatabookAPI::req("/get/capitalprojects/milestones/{$prjId}")
			);
			$id = $data['id'];
			$org = $this->fetchOrg($id);
			#var_dump($data['items']);
			return $org && $details
				? view('orgprojectA', [
					'id' => $id,
					'prjId' => $prjId,
					'pagetitle' => "{$data['name']} | {$prjId}",
					'org' => $org,
					'section' => $section,
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'activeDropDown' => $ds->menuActiveDD($section),
					'icons' => $ds->socicons,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
					'coreUrl' => DatabookAPI::url("/get/capitalprojects/core/{$prjId}"),
					'commUrl' => DatabookAPI::url("/get/capitalprojects/commitments/{$prjId}"),
					'breadcrumbs' => Breadcrumbs::orgPrj($org['id'], $org['name'], $section, $ds->list[$section], $prjId, $data['name']),
					'data' => $data,
					'map' => true,
					#'defaultPubDate' => '20221012',
					'datasets' => $pds->stats_data_sources(
						DatabookAPI::req('/get/datasets/all'),
						['capitalprojectsdollarscomp', 'capitalprojectsmilestones', 'capitalprojectslist', 'capitalprojectscommitments']
					),
					'tblStatsUrl' => DatabookAPI::url("/get/pstats-records_no-byprj/tblname/{$prjId}"),
					####### seo ########
					'schema' => Schema::project_a($prj[0], $org),
					'pagetitle' => "{$prj[0]['PROJECT_DESCR']} | WeGovNYC Databook Capital Projects",
					'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', "{$prj[0]['PROJECT_ID']} - {$prj[0]['SCOPE_TEXT']}"),
					'canonicalUrl' => route('project', ['prjId' => $prj[0]['PROJECT_ID'], 'prjslug' => Str::slug($prj[0]['PROJECT_DESCR'], '-')]),
				])
				: abort(404);
		} else {
			$prj = DatabookAPI::req("/get/capitalprojects/core/{$prjId}");
			$org = $this->fetchOrg($prj[0]['wegov-org-id']);
			return $prj && $org
				? view('pureproject', [
					'id' => $prj[0]['wegov-org-id'],
					'prjId' => $prjId,
					'pagetitle' => "{$prj[0]['description']} | {$prjId}",
					'org' => $org,
					'section' => $section,
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'activeDropDown' => $ds->menuActiveDD($section),
					'icons' => $ds->socicons,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
					#'coreUrl' => DatabookAPI::url("/get/capitalprojects/core/{$prjId}"),
					'prj' => $prj,
					'commUrl' => DatabookAPI::url("/get/capitalprojects/commitments/{$prjId}"),
					'breadcrumbs' => Breadcrumbs::purePrj($prjId, $prj[0]['description']),
					'map' => true,
					####### seo ########
					#'schema' => Schema::project($prj[0], $org),
					'pagetitle' => "{$prj[0]['description']} | WeGovNYC Databook Capital Projects",
					'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', "{$prjId}"),
					'canonicalUrl' => route('project', ['prjId' => $prjId, 'prjslug' => Str::slug($prj[0]['description'], '-')]),
				])
				: abort(404);
		}
	}


	/**
	 * Show dataset charts.
	 *
	 * @param  string  	$id
	 * @param  string  	$chartName
	 * @return \Illuminate\View\View
	 */
	public function orgChartsXHR($id, $section)
	{
		return view("orgCharts.{$section}", [
			'id' => $id,
			'section' => $section,

			'salaryStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-civillist_salaries_by_year"),
			'employeesStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-civillist_entries_by_year"),
			'positionsStatsUrl' => DatabookAPI::url("/get/titles/51810/stats-positionschedule_positions_by_agency"),
		]);
	}


	/**
	 * Show events ical feed.
	 *
	 * @return \Illuminate\View\View
	 */
	public function ical($id)
	{
		$data = DatabookAPI::req("/get/orgs/icalevents/{$id}");
		if (!$data) {
			return response('BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//WeGovNYC//Databook//EN
END:VCALENDAR', 200)
				->header('Content-type', 'text/calendar');
		}
		return response()->view('icalevents', [
			'data' => $data,
			'agencyName' => $data[0]['wegov-org-name'],
			'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('City Record Online (CROL)'))[0] ?? null,
		])
			->header('Content-type', 'text/calendar');
	}


	/**
	 * Return news rss feed.
	 *
	 * @return \Illuminate\View\View
	 */
	public function rss($id)
	{
		$data = DatabookAPI::req("/get/orgs/rssnews/{$id}");
		if (!$data) {
			return response('<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
 <title>WeGovNYC Databook</title>
 <description>No news found</description>
</channel>
</rss>', 200)
				->header('Content-type', 'text/xml; charset=utf-8');
		}
		return response()->view('rss', [
			'data' => $data,
			'agencyName' => $data[0]['wegov-org-name'],
			'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('City Record Online (CROL)'))[0] ?? null,
		])
			->header('Content-type', 'text/xml; charset=utf-8');
	}


	/**
	 * Return sitemap.xml.
	 *
	 * @return \Illuminate\View\View
	 */
	public function sitemap()
	{
		$dd = [];
		#orgs
		$dd[] = [route('root'), 0.6, 'monthly'];
		$dd[] = [route('about'), 0.6, 'monthly'];
		$dd[] = [route('orgs'), 0.6, 'monthly'];
		foreach (DatabookAPI::req('/get/orgs/directory') as $org)
			$dd[] = [route('orgProfile', [$org['id'], Str::slug($org['name'], '-')]), 1, 'weekly'];
		#districts
		$dd[] = [route('districts'), 0.6, 'monthly'];
		foreach (['cc', 'cd', 'nta'] as $type) {
			$fn = public_path("data/{$type}.geojson");
			$title = ['cc' => 'City Council District ', 'cd' => 'Community District ', 'nta' => ''][$type];
			$geojson = json_decode(file_get_contents($fn), true);
			$f = $type == 'nta' ? 'nameAlt' : 'nameCol';
			foreach ($geojson['features'] as $d) {
				$id = $d['properties'][$f];
				$name = $title . $id;
				$dd[] = [route('districtsPreset', ['type' => $type, 'id' => $id, 'dslug' => Str::slug($name, '-'), 'section' => 'projects']), 1, 'weekly'];
			}
		}
		#projects
		$dd[] = [route('projects'), 0.6, 'monthly'];
		$dates = DatabookAPI::req('/get/capitalprojects/dates');
		#print_r($dates);
		foreach (DatabookAPI::req('/get/capitalprojects/all/' . $dates[0]['PUB_DATE']) as $prj)
			if (!strstr($prj['PROJECT_ID'], '&'))
				$dd[] = [route('project', ['prjId' => $prj['PROJECT_ID'], 'prjslug' => Str::slug($prj['PROJECT_DESCR'], '-')]), 1, 'weekly'];
		#titles
		$dd[] = [route('titles'), 0.6, 'monthly'];
		#notices 
		$dd[] = [route('notices'), 0.6, 'monthly'];
		#auctions
		$dd[] = [route('auctions'), 0.6, 'monthly'];

		return response()->view('sitemap', [
			'entries' => $dd,
		])
			->header('Content-type', 'text/xml; charset=utf-8');
	}
}
