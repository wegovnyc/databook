<?php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\TitlesDatasets;
use App\Custom\Breadcrumbs;
use App\Custom\DatabookAPI;


class Titles extends Controller
{

    /**
     * Show districts main view.
     *
     * @return \Illuminate\View\View
     */
    public function main()
    {
        $ds = new TitlesDatasets();
        
        // Define paths: check shared volume first, then local fallback
        $sharedPath = '/var/shared/dashboard_data.json';
        $localPath = base_path('../dashboard_data.json');
        
        if (file_exists($sharedPath)) {
            $jsonPath = $sharedPath;
        } else {
            $jsonPath = $localPath;
        }

        $data = file_exists($jsonPath) ? json_decode(file_get_contents($jsonPath), true) : null;

        return view('titles', [
                    'breadcrumbs' => Breadcrumbs::titles(),
                    'slist' => $ds->list,
                    'url' => DatabookAPI::url("/get/titles"),
                    'defSearch' => $_GET['search'] ?? null,
                    'defUnion' => $_GET['union'] ?? '',
                    'data' => $data,
                   ####### seo ########
                    'pagetitle' => 'Civil Service Titles - Open Data Driven Profiles by NYC Databook',
                ]);
    }
	
    /**
     * Show district section.
     *
     * @return \Illuminate\View\View
     */
    public function stats()
    {
        $jsonPath = base_path('../dashboard_data.json');
        if (!file_exists($jsonPath)) {
            abort(404, 'Stats data not found. Please run the generation script.');
        }
        $json = file_get_contents($jsonPath);
        $data = json_decode($json, true);
        
        return view('title_stats', [
            'data' => $data,
            'sect' => 'titles',
            'title' => 'Civil Service Title Statistics',
            'breadcrumbs' => array_merge(Breadcrumbs::titles(), [[route('titleStats'), 'Statistics']]),
            'pagetitle' => 'Civil Service Title Statistics - Databook NYC',
        ]);
    }

    public function section($id, $slug, $section)
    {
		$ds = new TitlesDatasets();
		$titles = DatabookAPI::req("/get/titles/{$id}");
		$details = $ds->get($section);
		return $titles && ($details || $section == 'description' || $section == 'exams')
			? view($section == 'description' ? 'titledescsection' : ($section == 'exams' ? 'titleexams' : 'titlesection'), [
					'id' => $id,
					'section' => $section,
					'titles' => $titles,
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'breadcrumbs' => Breadcrumbs::titleSect($titles[0]['Title Code'], $titles[0]['Title Description'], $section, $ds->list[$section]),
					'url' => $details ? DatabookAPI::url("/get/titles/{$id}/{$details['table']}") : null,
					'dataset' => $details ? (DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null) : null,
					'salaryStatsUrl' => DatabookAPI::url("/get/titles/{$id}/stats-civillist_salaries_by_year"),
					#'employeesStatsUrl' => DatabookAPI::url("/get/titles/{$id}/stats-civillist_entries_by_year"),
					'positionsStatsUrl' => DatabookAPI::url("/get/titles/{$id}/stats-positionschedule_positions_by_agency"),
					'details' => $details,
				   ####### seo ########
					'pagetitle' => "{$titles[0]['Title Description']} - NYC Databook Profile",
					'snippet' => "Civil Services Title of New York City. {$titles[0]['Title Description']}",
				])
			: abort(404);
        }
    
    public function sectionShort($id, $section)
    {
        return $this->section($id, null, $section);
    }
}
