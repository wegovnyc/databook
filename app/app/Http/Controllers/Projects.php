<?php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Str;
use App\Custom\OrgsDatasets;
use App\Custom\ProjectsDatasets;
use App\Custom\Breadcrumbs;
use App\Custom\DatabookAPI;


class Projects extends Controller
{
    /**
     * Show capital projects main page.
     *
     * @return \Illuminate\View\View
     */
    public function main()
    {
		$ds = new ProjectsDatasets();
		$dates = DatabookAPI::req('/get/capitalprojects/dates');
		$date = ($dates && isset($dates[0]['PUB_DATE'])) ? $dates[0]['PUB_DATE'] : '2024-01-01';
        return view('capital', [
					'breadcrumbs' => Breadcrumbs::capital_a(),
					'datasets' => $ds->stats_data_sources(DatabookAPI::req('/get/datasets/all')),
					'tblStatsUrl' => DatabookAPI::url('/get/pstats-records_no/tblname'),
					'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
					/*
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
					*/
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => true,
				]);
    }		


    /**
     * Show capital projects archive page.
     *
     * @return \Illuminate\View\View
     */
    public function main_a()
    {
		$ds = new ProjectsDatasets();
		$dates = DatabookAPI::req('/get/capitalprojects/dates');
		$date = ($dates && isset($dates[0]['PUB_DATE'])) ? $dates[0]['PUB_DATE'] : '2024-01-01';
        return view('capitalA', [
					'breadcrumbs' => Breadcrumbs::capital_a(),
					'datasets' => $ds->stats_data_sources(DatabookAPI::req('/get/datasets/all')),
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
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => true,
				]);
    }		


    /**
     * Show capital projects main view.
     *
     * @return \Illuminate\View\View
     */
    public function projects()
    {
		$ds = new ProjectsDatasets();
		$details = $ds->get('main');
        return view('projects', [
					'breadcrumbs' => Breadcrumbs::projects(),
					'url' => DatabookAPI::url('/get/capitalprojects/projectsnew'),
					'details' => $details,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
					'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
					/*
					'finStatUrls' => [
						'#projects_no' => DatabookAPI::url("/get/pstats-projects_no/pubdate"),
						'#orig_cost' => DatabookAPI::url("/get/pstats-orig_cost/pubdate"),
						'#curr_cost' => DatabookAPI::url("/get/pstats-curr_cost/pubdate"),
						'#over_budg_am' => DatabookAPI::url("/get/pstats-over_budg_am/pubdate"),
						'#long_no' => DatabookAPI::url("/get/pstats-long_no/pubdate"),
						'#over_budg_no' => DatabookAPI::url("/get/pstats-over_budg_no/pubdate"),
						'#late_start_no' => DatabookAPI::url("/get/pstats-late_start_no/pubdate"),
						'#late_end_no' => DatabookAPI::url("/get/pstats-late_end_no/pubdate"),
					],
					*/
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'), 
							['capitalprojectslist', 'capitalprojectscommitments', 'capprojectsbudgetsandschedule', 'capprojectsbudgetandspend', 'capprojectsbudgetspendhistory', 'capprojectsschedulehistory']
						),
					'tblStatsUrl' => DatabookAPI::url('/get/pstats-records_no/tblname'),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => true,
				]);
    }		


    /**
     * Show capital projectcts archive view.
     *
     * @return \Illuminate\View\View
     */
    public function projects_a()
    {
		$ds = new ProjectsDatasets();
		$details = $ds->get('main-a');
        return view('projectsA', [
					'breadcrumbs' => Breadcrumbs::projects_a(),
					'url' => DatabookAPI::url('/get/capitalprojects/all/pubdate'),
					'dates_req_url' => DatabookAPI::url('/get/capitalprojects/dates'),
					'details' => $details,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
					'finStatUrls' => [
						'#projects_no' => DatabookAPI::url("/get/pstats-projects_no/pubdate"),
						'#orig_cost' => DatabookAPI::url("/get/pstats-orig_cost/pubdate"),
						'#curr_cost' => DatabookAPI::url("/get/pstats-curr_cost/pubdate"),
						'#over_budg_am' => DatabookAPI::url("/get/pstats-over_budg_am/pubdate"),
						'#long_no' => DatabookAPI::url("/get/pstats-long_no/pubdate"),
						'#over_budg_no' => DatabookAPI::url("/get/pstats-over_budg_no/pubdate"),
						'#late_start_no' => DatabookAPI::url("/get/pstats-late_start_no/pubdate"),
						'#late_end_no' => DatabookAPI::url("/get/pstats-late_end_no/pubdate"),
					],
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'), 
							['capitalprojectsdollarscomp', 'capitalprojectsmilestones', 'capitalprojectslist', 'capitalprojectscommitments']
						),
					'tblStatsUrl' => DatabookAPI::url('/get/pstats-records_no/tblname'),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => true,
				]);
    }		


    /**
     * Show project types directory main view.
     *
     * @return \Illuminate\View\View
     */
    public function prjTypes_a()
    {
		$dd = DatabookAPI::req('/get/capitalprojects/taxonomy/all');
		$ds = new ProjectsDatasets();
		if (!$dd || !is_array($dd)) {
			$dd = [];
		}
		foreach ($dd as $i=>$d)
	{
		if (!$d['ptype_name'])
			unset($dd[$i]);
		else
			$dd[$i] = array_merge($d, ['link' => route('prjType', ['tslug'=> Str::slug($d['ptype_name'])])]);
	}
    return view('prjTypesA', [
					'breadcrumbs' => Breadcrumbs::prjTypes_a(),
					'data' => $dd,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Ten-Year Capital Strategy'))[0] ?? null,
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							['capitalprojectsdollarscomp', 'capitalbudget', 'capitalcommitmentplan', 'capitalstrategy']
						),
					'tblStatsUrl' => DatabookAPI::url('/get/pstats-records_no/tblname'),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					#'map' => true,
				]);
    }		


    /**
     * Show project type page main view.
     *
     * @return \Illuminate\View\View
     */
    public function prjType_a($tslug)
    {
		$ds = new ProjectsDatasets();
		$data = DatabookAPI::req('/get/pstats-categories_by_type/' . $tslug);
		if (!$data || !is_array($data) || empty($data)) {
			return abort(404);
		}
		foreach ($data as $i=>$d)
			$data[$i]['category-slug'] = Str::slug($d['category']);
        return view('prjTypeA', [
					'breadcrumbs' => Breadcrumbs::prjType_a($data[0]['prjtypename']),
					'data' => $data,
					'budg_lines_url' => DatabookAPI::url('/get/budglines_by_prjtype/' . $tslug),
					'prj_commitments_url' => DatabookAPI::url('/get/commitments_by_prjtype/' . $tslug),
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							['capitalstrategy', 'capitalbudget', 'capitalcommitmentplan']
						),
					'tblStatsUrl' => DatabookAPI::url("/get/pstats-records_no-by_prjtype/tblname/{$tslug}"),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
				]);
    }		


    /**
     * Show project categories directory main view.
     *
     * @return \Illuminate\View\View
     */
    public function categories_a()
    {
		$data = DatabookAPI::req("/get/pstats-categories/all");
		if (isset($data['rows'])) {
			$data = $data['rows'];
		}

		if (!$data || !is_array($data)) {
			$data = [];
		}
		foreach ($data as $i=>$d)
			$data[$i]['category-slug'] = Str::slug($d['category']);
        return view('categoriesA', [
					'breadcrumbs' => Breadcrumbs::categories_a(),
					'data' => $data,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Ten-Year Capital Strategy'))[0] ?? null,
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					#'map' => true,
				]);
    }		


    /**
     * Show project strategy category page main view.
     *
     * @return \Illuminate\View\View
     */
    public function category_a($cslug)
    {
		$data = DatabookAPI::req("/get/capitalprojects/stratcategory/{$cslug}");
		if (!$data)
			return abort(404);
		$ds = new ProjectsDatasets();
		$details = $ds->get('main');
		$prjTypes = [];
		foreach ($data as $d)
			if ($d['Project Type Description'])
				$prjTypes[$d['Project Type Description']] = route('prjType', ['tslug'=> Str::slug($d['Project Type Description'])]);
        return view('categoryA', [
					'breadcrumbs' => Breadcrumbs::category_a($data[0]['Ten-Year Plan Category']),
					'prjsUrl' => DatabookAPI::url("/get/capitalprojects/by_category/{$cslug}"),
					#'dates_req_url' => DatabookAPI::url('/get/capitalprojects/dates'),
					'data' => $data,
					'details' => $details,
					'prjTypes' => $prjTypes,
					'finStatSelectors' => ['#projects_no', '#orig_cost', '#curr_cost', '#over_budg_am', '#long_no', '#over_budg_no', '#late_start_no', '#late_end_no'],
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							['capitalstrategy', 'capitalprojectsdollarscomp']
						),
					'tblStatsUrl' => DatabookAPI::url("/get/pstats-records_no-by_category/tblname/{$cslug}"),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => true,
					'cslug' => $cslug,
				]);
    }		


    /**
     * Show project categories directory main view.
     *
     * @return \Illuminate\View\View
     */
    public function budgetLines_a()
    {
		$data = DatabookAPI::req('/get/pstats-categories/recent');
		if (!$data || !is_array($data)) {
			$data = [];
		}
		foreach ($data as $i=>$d)
			$data[$i]['category-slug'] = Str::slug($d['category']);
        return view('budgetLinesA', [
					'breadcrumbs' => Breadcrumbs::budgetLines_a(),
					'data' => $data,
					'dataUrl' => DatabookAPI::url('/get/capitalbudget/bydate/recent'),
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Capital Budget'))[0] ?? null,
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					#'map' => true,
				]);
    }		


    /**
     * Show project budget line page main view.
     *
     * @return \Illuminate\View\View
     */
    public function budgetLine_a($blcode, $blslug=null)
    {
		$enc = rawurlencode($blcode);
		$data = DatabookAPI::req("/get/capitalbudget/{$enc}");
		if (!$data)
			return abort(404);
		// Ensure wegov-prjtype-name exists (fallback data from capitalcommitmentplan may lack it)
		foreach ($data as &$row) {
			if (!isset($row['wegov-prjtype-name']) && isset($row['Project Type Description']))
				$row['wegov-prjtype-name'] = $row['Project Type Description'];
		}
		unset($row);
		$ds = new ProjectsDatasets();
		$details = $ds->get('main');
        return view('budgetLineA', [
					'breadcrumbs' => Breadcrumbs::budgetLine_a($data[0]['Budget Line'], $data[0]['Budget Line Title']),
					'prjsUrl' => DatabookAPI::url("/get/capitalprojects/by_budgetline/{$enc}"),
					'capCommUrl' => DatabookAPI::url("/get/capitalcommitments/stats_by_budgetline/{$enc}"),
					'commUrl' => DatabookAPI::url("/get/commitments/by_budgetline/{$enc}"),
					'data' => $data,
					'details' => $details,
					'finStatSelectors' => ['#projects_no', '#orig_cost', '#curr_cost', '#over_budg_am', '#long_no', '#over_budg_no', '#late_start_no', '#late_end_no'],
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							['capitalbudget', 'capitalcommitmentplan', 'capitalprojectscommitments', 'capitalprojectsdollarscomp']
						),
					'tblStatsUrl' => DatabookAPI::url("/get/pstats-records_no-by_budgetline/tblname/{$enc}"),
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => true,				
				]);
    }		


    /**
     * Show projects commitments directory main view.
     *
     * @return \Illuminate\View\View
     */
    	public function commitments_a()
	{
		$data = DatabookAPI::req('/get/capitalcommitmentplan/all');
        return view('prjCommitmentsA', [
					'breadcrumbs' => Breadcrumbs::prjCommitments_a(),
					'data' => $data,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Capital Commitment Plan'))[0] ?? null,
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					#'map' => true,
				]);
    }		




    /**
     * Show minor capital projects main view.
     *
     * @return \Illuminate\View\View
     */
    public function mProjects()
    {
        $data = DatabookAPI::req('/get/mcapitalprojects/all');
        if (!is_array($data) || isset($data['detail'])) {
            $data = [];
        }
        return view('mProjects', [
					'breadcrumbs' => Breadcrumbs::mProjects(),
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Capital Projects Database (CPDB) - Projects'))[0] ?? null,
					'data' => $data,
				   ####### seo ########
					'pagetitle' => 'NYC Capital Projects - Open Data Driven Profiles by NYC Databook',
					'map' => false,
				]);
    }		

	
    /**
     * Show minor capital project.
     *
     * @param  string  	$prjId
     * @return \Illuminate\View\View
     */
    public function mProject($maprojid)
    {
		$section = 'projects';
		$prj = DatabookAPI::req("/get/capitalprojects/mcore/{$maprojid}");
		if (!$prj || !isset($prj[0])) {
			return abort(404);
		}
		//print_r($prj);
		//die();
		$org = DatabookAPI::req("/get/orgs/profile/{$prj[0]['wegov-org-id']}")[0] ?? null;
		$ds = new OrgsDatasets();
		$details = $ds->get($section);
		return $prj
			? view('mProject', [
					'id' => $prj[0]['wegov-org-id'],
					'prjId' => $maprojid,
					'pagetitle' => "{$prj[0]['description']} | {$maprojid}",
					'org' => $org,
					'section' => $section,
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'activeDropDown' => $ds->menuActiveDD($section),
					'icons' => $ds->socicons,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('Capital Projects Database (CPDB) - Projects'))[0] ?? null,
					//'url' => DatabookAPI::url("/get/capitalprojects/mcore/{$maprojid}"),
					'prj' => $prj[0],
					'commUrl' => DatabookAPI::url("/get/capitalprojects/commitments/{$prj[0]['projectid']}"),
					'breadcrumbs' => Breadcrumbs::mProject($maprojid, $prj[0]['description']),
					'map' => true,
				   ####### seo ########
					#'schema' => Schema::project($prj[0], $org),
					'pagetitle' => "{$prj[0]['description']} | WeGovNYC Databook Capital Projects",
					'snippet' => preg_replace('~\s*[\r\n]+\s*~', ' ', "{$maprojid}"),
					'canonicalUrl' => route('mProject', ['maprojid' => $maprojid]),
				])
			: abort(404);
    }


}