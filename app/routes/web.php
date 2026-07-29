<?php
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Http;
use Illuminate\Http\Request;
use App\Http\Controllers\Organizations;
use App\Http\Controllers\Districts;
use App\Http\Controllers\Projects;
use App\Http\Controllers\Titles;
use App\Http\Controllers\Notices;
use App\Http\Controllers\Auctions;
use App\Http\Controllers\People;
use App\Http\Controllers\ProcurementController;
use App\Custom\DatabookAPI;

// Local API proxy for bypassing CORS in development
Route::get('/api/{path}', function ($path) {
    if (env('APP_ENV') === 'local') {
        $url = env('FAPI_ENTRY') . "/{$path}?" . http_build_query(request()->query());
        $apiKey = env('FAPI_KEY');
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            "Authorization: Bearer {$apiKey}"
        ]);
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

        if ($httpCode >= 200 && $httpCode < 300) {
            return response($response)->header('Content-Type', 'application/json');
        }
    }
    return abort(404);
})->where('path', '.*')->name('apiProxy');

Route::get('/', [Organizations::class, 'root'])->name('root');
Route::get('/new-home', [Organizations::class, 'root'])->name('newHome');

Route::get('/about', function () { return view('about.project'); })->name('about');
Route::get('/about/data', [\App\Http\Controllers\Admin::class, 'dataHealth'])->name('about.data');
Route::get('/about/tables', [\App\Http\Controllers\Admin::class, 'dataTables'])->name('about.tables');
Route::get('/about/log', [\App\Http\Controllers\Admin::class, 'ingestionLog'])->name('about.log');

Route::get('/styleguide', function () {
    return view('styleguide', ['pagetitle' => 'Styleguide - Databook.nyc']);
});
Route::get('/styleguide/components', function () {
    return view('components-demo', ['pagetitle' => 'Blade components - Databook.nyc']);
});
Route::get('/mcp', function () {
    return view('mcp', ['pagetitle' => 'MCP Server - Databook.nyc']);
})->name('mcp');

Route::get('/blog', [\App\Http\Controllers\Articles::class, 'index'])->name('blog');
Route::get('/articles/{slug}', [\App\Http\Controllers\Articles::class, 'show'])->name('article');
Route::get('/organizations', function (\Illuminate\Http\Request $r) {
    $qs = $r->getQueryString();
    return redirect('/organizations/agencies' . ($qs ? '?'.$qs : ''));
})->name('orgs');
Route::get('/organizations/agencies', [Organizations::class, 'orgsAgencies'])->name('orgsAgencies');
Route::get('/organizations/directory', function () { return redirect(route('orgs')); });
Route::get('/organizations/chart', [Organizations::class, 'orgsChart'])->name('orgsChart');
Route::get('/organizations/chart/{id}', [Organizations::class, 'orgsChart'])->name('orgsChartFocus');
Route::get('/organizations/all', [Organizations::class, 'orgsAll'])->name('orgsAll');
Route::get('/organizations/all/{req}', [Organizations::class, 'orgsAll'])->name('orgsAllReq');

Route::get('/organization/{id}', [Organizations::class, 'orgAbout'])->name('orgProfileDepr');
Route::get('/o/{id}-{orgslug}', [Organizations::class, 'orgAbout'])->name('orgProfile');
Route::get('/o/{id}-{orgslug}/projects', [Organizations::class, 'orgProjectSection'])->name('orgProjectSection');
Route::get('/organizations/{id}/events.ics', [Organizations::class, 'ical'])->name('orgIcalEvents');
Route::get('/organizations/{id}/news.rss', [Organizations::class, 'rss'])->name('orgRSSNews');
Route::get('/o/{id}-{orgslug}/notices/{subsection}', function ($id, $orgslug, $subsection) {
    return redirect(route('orgSection', ['id' => $id, 'orgslug' => $orgslug, 'section' => $subsection]));
})->name('orgNoticeSection');
Route::get('/o/{id}-{orgslug}/{section}', [Organizations::class, 'orgSection'])->name('orgSection');
Route::get('/o/{id}-{orgslug}/p/{prjId}-{prjslug}', function ($id, $prjId, $prjslug) {
    return redirect(route('project', ['prjId' => $prjId, 'prjslug' => $prjslug]));
})->name('orgProject');
Route::get('/p/{prjId}_{prjslug}', [Organizations::class, 'project'])->name('project');
// Support ID-only URLs without slug (e.g., /p/PW193ELV)
Route::get('/p/{prjId}', [Organizations::class, 'project'])->name('project-id-only')
    ->where('prjId', '[A-Za-z0-9\-]+');
// Support dash-separated URLs (redirect to underscore version)
Route::get('/p/{prjId}-{prjslug}', function ($prjId, $prjslug) {
    return redirect(route('project', ['prjId' => $prjId, 'prjslug' => $prjslug]), 301);
});
// Legacy capital-archive project URLs → redirect to /p/
Route::get('/capital-archive/p/{prjId}_{prjslug}', function ($prjId, $prjslug) {
    return redirect(route('project', ['prjId' => $prjId, 'prjslug' => $prjslug]), 301);
});

#Route::get('/sitemap.xml', [Organizations::class, 'sitemap'])->name('sitemap');

Route::get('/orgChartsXHR/{id}/{section}', [Organizations::class, 'orgChartsXHR'])->name('orgChartsXHR');



Route::get('/districts', [Districts::class, 'main'])->name('districts');
Route::get('/districts/{type}', [Districts::class, 'main'])->where('type', '^(cd|cc|nta|sd)$')->name('districtsPresetType');
Route::get('/d/{type}-{id}-{dslug}', function ($type, $id, $dslug) {
    return redirect(route('districtsPreset', ['type' => $type, 'id' => $id, 'dslug' => $dslug, 'section' => 'projects']));
})->where('type', '^(cd|cc|nta|sd)$');
Route::get('/d/{type}-{id}-{dslug}/{section}', [Districts::class, 'main'])->where('type', '^(cd|cc|nta|sd)$')->name('districtsPreset');
Route::get('/districtXHR/{type}/{id}/projects', [Districts::class, 'projectSectionXHR'])->name('distProjectSection');
Route::get('/districtXHR/{type}/{id}/{section}', [Districts::class, 'sectionXHR'])->name('distSection');


Route::get('/schools', [Districts::class, 'schools'])->name('schools');
Route::get('/s/{code}-{slug}', function ($code, $slug) {
    return redirect(route('schoolSection', ['code' => $code, 'slug' => $slug, 'section' => 'enrollment']));
})->name('school');
Route::get('/s/{code}-{slug}/{section}', [Districts::class, 'schoolSection'])->name('schoolSection');
Route::get('/schoolsXHR/geojson', [Districts::class, 'schoolsGeoJson'])->name('schoolsGeoJson');



// Legacy capital-archive URLs → redirect to /projects/ equivalents
Route::get('/capital-archive', function () { return redirect(route('capital'), 301); });
Route::get('/capital-archive/projects', function () { return redirect(route('projects'), 301); });
Route::get('/capital-archive/project-types/{tslug?}', function ($tslug = null) { return $tslug ? redirect(route('prjType', ['tslug' => $tslug]), 301) : redirect(route('prjTypes'), 301); });
Route::get('/capital-archive/categories/{cslug?}', function ($cslug = null) { return $cslug ? redirect(route('prjStratCategory', ['cslug' => $cslug]), 301) : redirect(route('prjCategories'), 301); });
Route::get('/capital-archive/budget-lines/{blcode?}', function ($blcode = null) { return $blcode ? redirect(route('budgetLine', ['blcode' => $blcode]), 301) : redirect(route('budgetLines'), 301); });
Route::get('/capital-archive/commitments', function () { return redirect(route('prjCommitments'), 301); });

Route::get('/capital/minor-projects', [Projects::class, 'mProjects'])->name('mProjects');
Route::get('/capital/minor-projects/{maprojid}', [Projects::class, 'mProject'])->name('mProject');


Route::get('/projects', [Projects::class, 'projects'])->name('projects');
Route::get('/projects/capital', [Projects::class, 'main'])->name('capital');
Route::get('/projects/types', [Projects::class, 'prjTypes_a'])->name('prjTypes');
Route::get('/projects/types/{tslug}', [Projects::class, 'prjType_a'])->name('prjType');
Route::get('/projects/categories', [Projects::class, 'categories_a'])->name('prjCategories');
Route::get('/projects/categories/{cslug?}', [Projects::class, 'category_a'])->name('prjStratCategory');
Route::get('/projects/budget-lines', [Projects::class, 'budgetLines_a'])->name('budgetLines');
Route::get('/projects/budget-lines/{blcode}', [Projects::class, 'budgetLine_a'])->name('budgetLine');
Route::get('/projects/commitments', [Projects::class, 'commitments_a'])->name('prjCommitments');

// Backward compatibility redirects
Route::get('/capital', function () { return redirect(route('capital')); });
Route::get('/capital/projects', function () { return redirect(route('projects')); });
Route::get('/capital/project-types/{tslug?}', function ($tslug = null) { return $tslug ? redirect(route('prjType', ['tslug' => $tslug])) : redirect(route('prjTypes')); });
Route::get('/capital/categories/{cslug?}', function ($cslug = null) { return $cslug ? redirect(route('prjStratCategory', ['cslug' => $cslug])) : redirect(route('prjCategories')); });
Route::get('/capital/budget-lines/{blcode?}', function ($blcode = null) { return $blcode ? redirect(route('budgetLine', ['blcode' => $blcode])) : redirect(route('budgetLines')); });
Route::get('/capital/commitments', function () { return redirect(route('prjCommitments')); });



Route::get('/jobs-exams', function () {
    return view('jobs_exams', [
        'pagetitle' => 'Civil Service Exams - Databook.nyc',
        'breadcrumbs' => [[route('titles'), 'Titles'], [null, 'Exams']],
    ]);
})->name('jobsExams');

Route::get('/jobs', function () {
    return view('jobs', [
        'pagetitle' => 'NYC Jobs - Databook.nyc',
        'breadcrumbs' => [[null, 'NYC Jobs']],
        'jobsUrl' => \App\Custom\DatabookAPI::url('/get/jobs/all'),
    ]);
})->name('jobs');


Route::get('/jobs-dashboard', function () {
    $sharedPath = '/var/shared/dashboard_data.json';
    $localPath = base_path('../dashboard_data.json');
    $jsonPath = file_exists($sharedPath) ? $sharedPath : $localPath;
    $data = file_exists($jsonPath) ? json_decode(file_get_contents($jsonPath), true) : null;
    return view('titles_overview', [
        'pagetitle' => 'NYC Jobs Dashboard - Databook.nyc',
        'breadcrumbs' => [[null, 'Jobs Dashboard']],
        'data' => $data,
        'jobsUrl' => \App\Custom\DatabookAPI::url('/get/jobs/all'),
    ]);
})->name('jobsDashboard');

Route::get('/titles-overview', function () {
    return redirect('/jobs-dashboard', 301);
})->name('titlesOverview');

Route::get('/titles', [Titles::class, 'main'])->name('titles');
Route::get('/title-stats', [Titles::class, 'stats'])->name('titleStats');

// Legacy Routes (Long URL)
Route::get('/t/{id}-{tslug}', function ($id, $tslug) {
    return redirect(route('titleSectionLong', ['id' => $id, 'tslug' => $tslug, 'section' => 'positions']));
})->name('titleLong');
Route::get('/t/{id}-{tslug}/{section}', [Titles::class, 'section'])->name('titleSectionLong');

// New Routes (Short URL)
Route::get('/t/{id}', function ($id) {
    return redirect(route('titleSection', ['id' => $id, 'section' => 'positions']));
})->name('title');
Route::get('/t/{id}/{section}', [Titles::class, 'sectionShort'])->name('titleSection');


Route::get('/notices', [Notices::class, 'main'])->name('notices');
Route::get('/notices/events.ics', [Notices::class, 'ical'])->name('noticesIcalEvents');
Route::get('/notices/news.rss', [Notices::class, 'rss'])->name('noticesRSSNews');
Route::get('/notices/{section}', [Notices::class, 'section'])->name('noticesSection');


Route::get('/auctions', [Auctions::class, 'main'])->name('auctions');

Route::get('/council', function () {
    return view('council', ['pagetitle' => 'City Council Hearings - Databook.nyc']);
})->name('council');


// Global search — server-rendered results page. Federates entity types via the
// API's /get/search (one round-trip); see api/routers/search.py.
Route::get('/search', function (\Illuminate\Http\Request $request) {
	$q = trim((string) $request->query('q', ''));
	$data = ['query' => $q, 'total' => 0, 'groups' => []];
	if (mb_strlen($q) >= 2) {
		// reqOCE returns the full decoded JSON; req() would strip to ['rows'] only.
		$res = \App\Custom\DatabookAPI::reqOCE('/get/search?q=' . rawurlencode($q), 8);
		if (is_array($res) && isset($res['groups'])) {
			$data = $res;
		}
	}
	return view('search', [
		'q' => $q,
		'data' => $data,
		'pagetitle' => ($q !== '' ? "Search: {$q}" : 'Search') . ' — NYC Databook',
		'noindex' => true,
	]);
})->name('search');

// Navbar typeahead — JSON proxy to the API's lightweight suggest endpoint.
// Proxied (not browser→API direct) so the bearer key stays server-side.
Route::get('/search/suggest', function (\Illuminate\Http\Request $request) {
	$q = trim((string) $request->query('q', ''));
	$out = ['query' => $q, 'suggestions' => []];
	if (mb_strlen($q) >= 2) {
		$res = \App\Custom\DatabookAPI::reqOCE('/get/search/suggest?q=' . rawurlencode($q), 3);
		if (is_array($res) && isset($res['suggestions'])) {
			$out = $res;
		}
	}
	return response()->json($out)
		->header('Cache-Control', 'private, max-age=30');
})->name('search.suggest');

Route::get('/people', [People::class, 'main'])->name('people');
Route::get('/people/search/{req}', function ($req) {
	return redirect(route('peopleSearchTbl', ['req' => $req, 'tbl' => 'all']));
})->name('peopleSearch');
Route::get('/people/search/{req}/{tbl}', [People::class, 'search'])->name('peopleSearchTbl');
Route::get('/people/{id}-{slug}', [People::class, 'person'])->name('peoplePerson');


# Procurement
Route::get('/procurement', 'ProcurementController@index')->name('procurement.index');
Route::get('/procurement/vendors', 'ProcurementController@vendors')->name('procurement.vendors');
Route::get('/procurement/vendor/{id}', 'ProcurementController@vendorProfile')->name('procurement.vendor');
Route::get('/procurement/agencies', 'ProcurementController@agencies')->name('procurement.agencies');
Route::get('/procurement/contracts', 'ProcurementController@contracts')->name('procurement.contracts');
Route::get('/procurement/contract/{id}', 'ProcurementController@contractProfile')->name('procurement.contract');
Route::get('/procurement/solicitations', 'ProcurementController@solicitations')->name('procurement.solicitations');
Route::get('/procurement/solicitation/{epin}', 'ProcurementController@solicitationProfile')->name('procurement.solicitation');
Route::get('/procurement/agency/{name}', 'ProcurementController@orgProcurement')->where('name', '.*')->name('agency.procurement');
Route::get('/research/digital-reform', 'ProcurementController@digitalReform')->name('research.digital-reform');
Route::get('/research/digital-reform/expiring', 'ProcurementController@digitalReformExpiring')->name('research.digital-reform.expiring');
Route::get('/procurement/transactions', 'ProcurementController@transactions')->name('procurement.transactions');
Route::get('/procurement/transactions/search', 'ProcurementController@transactionsSearch')->name('procurement.transactions.search');
Route::get('/procurement/budget', 'BudgetRevenueController@budget')->name('procurement.budget');
Route::get('/procurement/revenue', 'BudgetRevenueController@revenue')->name('procurement.revenue');
Route::get('/procurement/payroll', 'BudgetRevenueController@payroll')->name('procurement.payroll');
Route::get('/procurement/nycha', 'NychaController@index')->name('procurement.nycha');
Route::get('/procurement/nycha/budget', 'NychaController@budget')->name('procurement.nycha.budget');
Route::get('/procurement/nycha/revenue', 'NychaController@revenue')->name('procurement.nycha.revenue');
Route::get('/procurement/nycha/contracts', 'NychaController@contracts')->name('procurement.nycha.contracts');
Route::get('/procurement/nycha/spending', 'NychaController@spending')->name('procurement.nycha.spending');
Route::get('/procurement/data-sources', 'ProcurementController@dataSources')->name('procurement.datasources');

# Legacy OCE blog redirects
Route::get('/blog/the-missing-pieces-bridging-nyc-procurement-data-with-ocds', fn() =>
    redirect('/articles/the-missing-pieces-bridging-nyc-procurement-data-with-ocds', 301));
Route::get('/blog/all-in-a-days-work-building-the-open-contracting-explorer', fn() =>
    redirect('/articles/all-in-a-days-work-building-the-open-contracting-explorer', 301));

