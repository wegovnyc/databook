<?php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\Breadcrumbs;
use App\Custom\DatabookAPI;


class People extends Controller
{

    /**
     * Show districts main view.
     *
     * @return \Illuminate\View\View
     */
    public function main()
    {
        return view('people', [
					'breadcrumbs' => Breadcrumbs::people(),
					'url' => DatabookAPI::url("/get/titles/positionschedule_positions"),
				   ####### seo ########
					'pagetitle' => 'People - People Profiles by NYC Databook',
					'snippet' => '',
				]);
    }
	
    /**
     * Show district section.
     *
     * @return \Illuminate\View\View
     */
    public function search($req, $tbl)
    {
		return view('peoplesearchresults', [
					'breadcrumbs' => Breadcrumbs::people(),
					'url' => DatabookAPI::url("/search/people/{$req}/{$tbl}"),
					'req' => urldecode($req),
					'tbl' => $tbl,
				   ####### seo ########
					'pagetitle' => 'People - People Profiles by NYC Databook',
					'snippet' => '',
				]);
    }

    /**
     * Show district section.
     *
     * @return \Illuminate\View\View
     */
    public function person($id, $slug)
    {
		$person = DatabookAPI::req("/get/people/{$id}?name=" . urlencode($slug))[0] ?? [];
		if (!$person) {
			return abort(404);
		}
		$prefix = preg_replace('~\d~', '', $id);
		$map = ['cl' => 'civillist', 'cla' => 'civillistactive', 'gb' => 'nycgreenbook', 'pr' => 'payrolldata'];
		if (!array_key_exists($prefix, $map)) {
			// Fallback or abort if ID format is invalid
			return abort(404);
		}
		$tbl = $map[$prefix];
		$uid = preg_replace('~[a-z]~si', '', $id);
		$name = ['civillistactive' => implode(' ', [$person['First Name'] ?? '', $person['MI'] ?? '', $person['Last Name'] ?? '']),
				 'civillist' => $person['EMPLOYEE NAME'] ?? '',
				 'nycgreenbook' => implode(' ', [$person['First Name'] ?? '', $person['Middle Initial'] ?? '', $person['Last Name'] ?? '']),
				 'payrolldata' => implode(' ', [$person['First Name'] ?? '', $person['Mid Init'] ?? '', $person['Last Name'] ?? '']),
				][$tbl];
		$req = urlencode($name);
		$ds = DatabookAPI::req('/get/datasets/profile/' . rawurlencode([
				'civillist' => 'Civil List',
				'civillistactive' => 'Civil Service List (Active)',
				'nycgreenbook' => 'Greenbook',
				'payrolldata' => 'Citywide Payroll Data (Fiscal Year)',
			][$tbl]))[0] ?? null;
		return view('person', [
					'breadcrumbs' => Breadcrumbs::person($id, $slug, preg_replace('~\s+~', ' ', $name)),
					'url' => DatabookAPI::url("/search/people/{$req}/all"),
					'person' => $person,
					'dataset' => $ds,
					'tbl' => $tbl,
					'id' => $id,
					'slug' => $slug,
					'uid' => $uid,
					'name' => $name,
					'req' => $req,
				   ####### seo ########
					'pagetitle' => 'People - People Profiles by NYC Databook',
					'snippet' => '',
				]);
    }
}