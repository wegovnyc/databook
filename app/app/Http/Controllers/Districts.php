<?php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\DistDatasets;
use App\Custom\SchoolDatasets;
use App\Custom\Breadcrumbs;
use App\Custom\DatabookAPI;
use App\Custom\Schema;
use App\Custom\SchoolsBuilder;
use Illuminate\Support\Str;


class Districts extends Controller
{
    /**
     * Show districts main view.
     *
     * @return \Illuminate\View\View
     */
    public function main($type=null, $id=null, $dslug=null, $section=null)
    {
		$ds = new DistDatasets();
		if ($type && $id)
		{
			if ($type == 'cd') {
				$res = DatabookAPI::req('/get/orgs/bycd/' . $id);
				$org = ($res && isset($res[0])) ? $res[0] : [];
			} elseif ($type == 'cc') {
				$res = DatabookAPI::req('/get/orgs/byccd/' . $id);
				$org = ($res && isset($res[0])) ? $res[0] : [];
			}
			else
				$org = null;
			$schema = Schema::districtFromFile($type, $id, $org);
			$schema['name'] = $schema['name'] ?? '';
		}
        return view('districts', [
					'type' => $type ?? 'cd',
					'id' => $id ?? null,
					'section' => $section ?? 'nyccouncildiscretionaryfunding',
					'breadcrumbs' => Breadcrumbs::districts(),
					'menu' => $ds->menu,
					'slist' => $ds->list,
					'map' => ['cc' => 'inherit', 'cd' => 'inherit', 'nta' => 'inherit', 'sd' => 'inherit'],
					'prjUrl' => DatabookAPI::url('/get/capitalprojects/geojson'),
					'schoolsUrl' => route('schoolsGeoJson'),
					'cdAgencyUrl' => DatabookAPI::url('/get/orgs/bycd/@@@'),
					'ccAgencyUrl' => DatabookAPI::url('/get/orgs/byccd/@@@'),
				] + (($type && $id) 
			   ####### seo ########
					? [
						'schema' => $schema,
						'pagetitle' => "{$schema['name']} | WeGovNYC Databook",
						'snippet' => "NYC Open Data about neighborhood, city council and community districts - {$schema['name']}.",
						'canonicalUrl' => $schema['url'] ?? '',
						'subview' => str_replace('<h1></h1>', "<h1>{$schema['name']}</h1>", 
							($section == 'projects') 
								? $this->projectSectionXHR($type, $id) 
								: $this->sectionXHR($type, $id, $section)
						),
					  ] 
					: [
						'pagetitle' => 'District Open Data by NYC Databook - Neighborhood, city council and community district data',
						#'snippet' => 'NYC Open Data about neighborhood, city council and community districts',
						#'canonicalUrl' => route('districts'),
						'noindex' => true
					  ]
				));
    }


    /**
     * Show district section.
     *
     * @return \Illuminate\View\View
     */
    public function sectionXHR($type, $id, $section)
    {
		$ds = new DistDatasets();
		$details = $ds->get($section, $type);
		return $details
			? view('distsection', [
					'type' => $type,
					'id' => $id,
					'section' => $section,
					'slist' => $ds->list,
					'menu' => $ds->menu($type),
					'activeDropDown' => $ds->menuActiveDD($type, $section),
					'url' => DatabookAPI::url("/get/districts/{$type}/{$id}/{$details['table']}?sort={$details['sort'][0]},{$details['sort'][1]}&f={$details['map'][$type]}"),
					'sdStatsUrl' => ($type == 'sd')
						? DatabookAPI::url("/get/schools/sdstats/{$id}")
						: null,
					'dataset' => ($d = DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))) && isset($d[0]) ? $d[0] : null,
					'member' => (($type == 'cc') and ($id <> 'undefined')) ? (($m = DatabookAPI::req("/get/districts/ccmember/{$id}")) && isset($m[0]) ? $m[0] : []) : [],
					'details' => $details,
					'linkedAgencyUrl' => 
						$type == 'cd'
							? DatabookAPI::url("/get/orgs/bycd/{$id}")
							: '',
					'altName' => $type == 'cd' ? $ds->cdAltName[$id] ?? null : null,
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							$id, $type,
							(($type == 'sd') 
								? ['scademostats', 'schoollocations', 'scacapitalprojectschedules', 'demographics']
								: ['nyccouncildiscretionaryfunding', 'capitalprojectsdollarscomp', 'budgetrequestsregister', 'facilitydb'])
							+ (($type == 'cc') ? [5 => 'ccmembers'] : [])
							+ (($type == 'cd') ? [5 => 'nyccommunityboards'] : [])
						),
					'tblStatsUrl' => DatabookAPI::url("/get/districts/pstats-records_no/{$type}/{$id}/tblname"),
				])
			: abort(404);
    }


    /**
     * Show organization capital projects section.
     *
     * @param  int  	$id
     * @return \Illuminate\View\View
     */
    public function projectSectionXHR($type, $id)
    {
		$section = 'projects';
		$ds = new DistDatasets();
		$details = $ds->get($section, $type);
		return $details
			? view('distprojectsection', [
					'type' => $type,
					'id' => $id,
					'section' => $section,
					'slist' => $ds->list,
					'menu' => $ds->menu($type),
					'activeDropDown' => $ds->menuActiveDD($type, $section),
					'url' => DatabookAPI::url("/get/districts/{$type}/{$id}/capitalprojects"),
					'dataset' => ($d = DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))) && isset($d[0]) ? $d[0] : null,
					'details' => $details,
					'finStatUrls' => [
						'#projects_no' => DatabookAPI::url("/get/districts/pstats-projects_no/{$type}/{$id}/pubdate"),
						'#orig_cost' => DatabookAPI::url("/get/districts/pstats-orig_cost/{$type}/{$id}/pubdate"),
						'#curr_cost' => DatabookAPI::url("/get/districts/pstats-curr_cost/{$type}/{$id}/pubdate"),
						'#over_budg_am' => DatabookAPI::url("/get/districts/pstats-over_budg_am/{$type}/{$id}/pubdate"),
						'#long_no' => DatabookAPI::url("/get/districts/pstats-long_no/{$type}/{$id}/pubdate"),
						'#over_budg_no' => DatabookAPI::url("/get/districts/pstats-over_budg_no/{$type}/{$id}/pubdate"),
						'#late_start_no' => DatabookAPI::url("/get/districts/pstats-late_start_no/{$type}/{$id}/pubdate"),
						'#late_end_no' => DatabookAPI::url("/get/districts/pstats-late_end_no/{$type}/{$id}/pubdate"),
					],
					'linkedAgencyUrl' => [
						'nta' => '',
						'cd' => DatabookAPI::url("/get/orgs/bycd/{$id}"),
						'cc' => DatabookAPI::url("/get/orgs/bycc/{$id}"),
					][$type],
					'altName' => $type == 'cd' ? $ds->cdAltName[$id] ?? null : null,
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							$id, $type,
							(($type == 'sd') 
								? ['scademostats', 'schoollocations', 'scacapitalprojectschedules']
								: ['nyccouncildiscretionaryfunding', 'capitalprojectsdollarscomp', 'budgetrequestsregister', 'facilitydb'])
							+ (($type == 'cc') ? [5 => 'ccmembers'] : [])
							+ (($type == 'cd') ? [5 => 'nyccommunityboards'] : [])
						),
					'tblStatsUrl' => DatabookAPI::url("/get/districts/pstats-records_no/{$type}/{$id}/tblname"),
				])
			: abort(404);
    }
	
	
    /**
     * Show schools main view.
     *
     * @return \Illuminate\View\View
     */
    public function schools()
    {
		#$ds = new DistDatasets();
		$ds = new SchoolDatasets();
		$details = $ds->get('schools');
		$sampleSchool = DatabookAPI::req('/get/schools/K001')[0] ?? [];
        return view('schools', [
					'breadcrumbs' => Breadcrumbs::schools(),
					'map' => ['cc' => 'inherit', 'cd' => 'inherit', 'nta' => 'inherit', 'sd' => 'inherit'],
					'url' => route('schoolsGeoJson'),
					'sdStatsUrl' => DatabookAPI::url('/get/schools/sdstats/all'),
					'details' => $details,
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							$sampleSchool
						)['tbl'],
					'tblStatsUrls' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							$sampleSchool,
							true
						)['urls'],
				] 
				/*
				+ 
			   ####### seo ########
					[
						'schema' => $schema,
						'pagetitle' => "{$schema['name']} | WeGovNYC Databook",
						'snippet' => "NYC Open Data about neighborhood, city council and community districts - {$schema['name']}.",
						'canonicalUrl' => $schema['url'] ?? '',
						'subview' => str_replace('<h1></h1>', "<h1>{$schema['name']}</h1>", $this->section($type, $id, $section)),
					]
				*/
				);
    }




    /**
     * Show school profile.
     *
     * @return \Illuminate\View\View
     */
    public function schoolSection($code, $slug, $section)
    {
		$school = DatabookAPI::req('/get/schools/' . $code)[0] ?? [];
		//print_r($school);
		$ds = new SchoolDatasets();
		$details = $ds->get($section);
		return ($school && $details)
			? view('schoolSection', [
					'code' => $code,
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'activeDropDown' => $ds->menuActiveDD('sd', $section),
					//'url' => DatabookAPI::url("/get/schoolsection/{$details['table']}?sort={$details['sort'][0]},{$details['sort'][1]}"),
					'url' => DatabookAPI::url("/get/schools/section/{$school[$details['DBNkey']]}/{$details['table']}"),
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
					'details' => $details,
					'school' => $school,
					'section' => $section,
					'slug' => $slug,
					'breadcrumbs' => Breadcrumbs::schoolSect(
										$school['Geographical_District_code'],
										"School District {$school['Geographical_District_code']}",
										$code,
										$school['location_name'],
										$section,
										$ds->list[$section]
									),								// schoolSect($distId, $distName, $code, $schoolName, $sect, $sectN)
					'datasets' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							$school
						)['tbl'],
					'schoolStatsUrl' => DatabookAPI::url("/get/schools/schoolStats/{$code}"),
					'tblStatsUrls' => $ds->stats_data_sources(
							DatabookAPI::req('/get/datasets/all'),
							$school
						)['urls'],
					'map' => true,
				])
			: abort(404);
    }


    /**
     * Show school profile.
     *
     * @return \Illuminate\View\View
     */
    public function schoolsGeoJson()
    {
		// /get/schools/all takes ~7s — use reqOCE with 15s timeout instead of
		// the default DatabookAPI::req which times out at 5s and returns false.
		$raw = DatabookAPI::reqOCE('/get/schools/all', 15) ?? [];
		$schools = isset($raw['rows']) && is_array($raw['rows']) ? $raw['rows'] : [];
		return response(json_encode(SchoolsBuilder::schoolsWithGeoJson($schools)), 200)
                  ->header('Content-Type', 'application/json');
    }
	
}