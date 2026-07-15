<?php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\CROLDatasets;
use App\Custom\Breadcrumbs;
use App\Custom\DatabookAPI;


class Notices extends Controller
{
    /**
     * Show notices main view.
     *
     * @return \Illuminate\View\View
     */
    public function main()
    {
		$ds = new CROLDatasets();
		$details = $ds->get('events');
		
		// Get actual CROL last updated date from ingestion log
		$crolLastUpdated = null;
		$lastUpdatedResult = DatabookAPI::req('/get/notices/lastupdated');
		if (!empty($lastUpdatedResult[0]['last_updated'])) {
			$crolLastUpdated = date('m/d/Y', strtotime($lastUpdatedResult[0]['last_updated']));
		}
		
        return view('notices', [
					'breadcrumbs' => Breadcrumbs::notices(),
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'details' => $details,
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
					'crolLastUpdated' => $crolLastUpdated,
					'news' => DatabookAPI::req('/get/notices/frontnews') ?: [],
					'events' => DatabookAPI::req('/get/notices/frontevents') ?: [],
					'auctions' => DatabookAPI::req('/get/frontauctions') ?: [],
					'stats' => DatabookAPI::req('/get/notices/last30daysstats') ?: [],
					/*
					'statUrls' => [
						'#publichearings1' => DatabookAPI::url('/get/notices/stats/publichearings/1'),
						'#publichearings7' => DatabookAPI::url('/get/notices/stats/publichearings/7'),
						'#publichearings30' => DatabookAPI::url('/get/notices/stats/publichearings/30'),

						'#contractawards1' => DatabookAPI::url('/get/notices/stats/contractawards/1'),
						'#contractawards7' => DatabookAPI::url('/get/notices/stats/contractawards/7'),
						'#contractawards30' => DatabookAPI::url('/get/notices/stats/contractawards/30'),
						
						'#specialmaterials1' => DatabookAPI::url('/get/notices/stats/specialmaterials/1'),
						'#specialmaterials7' => DatabookAPI::url('/get/notices/stats/specialmaterials/7'),
						'#specialmaterials30' => DatabookAPI::url('/get/notices/stats/specialmaterials/30'),

						'#agencyrules1' => DatabookAPI::url('/get/notices/stats/agencyrules/1'),
						'#agencyrules7' => DatabookAPI::url('/get/notices/stats/agencyrules/7'),
						'#agencyrules30' => DatabookAPI::url('/get/notices/stats/agencyrules/30'),

						'#propertydisposition1' => DatabookAPI::url('/get/notices/stats/propertydisposition/1'),
						'#propertydisposition7' => DatabookAPI::url('/get/notices/stats/propertydisposition/7'),
						'#propertydisposition30' => DatabookAPI::url('/get/notices/stats/propertydisposition/30'),

						'#courtnotices1' => DatabookAPI::url('/get/notices/stats/courtnotices/1'),
						'#courtnotices7' => DatabookAPI::url('/get/notices/stats/courtnotices/7'),
						'#courtnotices30' => DatabookAPI::url('/get/notices/stats/courtnotices/30'),

						'#procurement1' => DatabookAPI::url('/get/notices/stats/procurement/1'),
						'#procurement7' => DatabookAPI::url('/get/notices/stats/procurement/7'),
						'#procurement30' => DatabookAPI::url('/get/notices/stats/procurement/30'),

						'#changeofpersonnel1' => DatabookAPI::url('/get/notices/stats/changeofpersonnel/1'),
						'#changeofpersonnel7' => DatabookAPI::url('/get/notices/stats/changeofpersonnel/7'),
						'#changeofpersonnel30' => DatabookAPI::url('/get/notices/stats/changeofpersonnel/30'),
					],
					*/
					'globStats' => DatabookAPI::reqOCE('/pipeline/globstats') ?: json_decode(file_get_contents(public_path('data/globStats.json')), true),
				   ####### seo ########
					'pagetitle' => 'NYC Government News and Hearings - Open Data City Record Online by NYC Databook',
				]);
    }
	
    /**
     * Show notice section.
     *
     * @return \Illuminate\View\View
     */
    public function section($section)
    {
		$ds = new CROLDatasets();
		$details = $ds->get($section);
		
		// Get actual CROL last updated date from ingestion log
		$crolLastUpdated = null;
		$lastUpdatedResult = DatabookAPI::req('/get/notices/lastupdated');
		if (!empty($lastUpdatedResult[0]['last_updated'])) {
			$crolLastUpdated = date('m/d/Y', strtotime($lastUpdatedResult[0]['last_updated']));
		}
		
		return $details
			? view('noticessection', [
					'section' => $section,
					'slist' => $ds->list,
					'menu' => $ds->menu,
					'breadcrumbs' => Breadcrumbs::noticesSect($section, $ds->list[$section]),
					'url' => DatabookAPI::url(str_replace('-', '', "/get/notices/{$section}/pubdate")),
					'dates_req_url' => DatabookAPI::url('/get/notices/years'),
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode($details['fullname']))[0] ?? null,
					'crolLastUpdated' => $crolLastUpdated,
					'details' => $details,
				   ####### seo ########
					'pagetitle' => 'NYC Government News and Hearings - Open Data City Record Online by NYC Databook',
				])
			: abort(404);
    }
	
    /**
     * Return events ical feed.
     *
     * @return \Illuminate\View\View
     */
    public function ical()
    {
		return response()->view('icalevents', [
					'data' => DatabookAPI::req('/get/notices/icalevents'),
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('City Record Online (CROL)'))[0] ?? null,
				])
				->header('Content-type', 'text/calendar')
			;
    }
	
    /**
     * Return news rss feed.
     *
     * @return \Illuminate\View\View
     */
    public function rss()
    {
		return response()->view('rss', [
					'data' => DatabookAPI::req('/get/notices/rssnews'),
					'dataset' => DatabookAPI::req('/get/datasets/profile/' . rawurlencode('City Record Online (CROL)'))[0] ?? null,
				])
				->header('Content-type', 'text/xml; charset=utf-8')
			;
    }
}