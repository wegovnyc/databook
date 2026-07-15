<?php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\AuctionsDatasets;
use App\Custom\Breadcrumbs;
use App\Custom\DatabookAPI;


class Auctions extends Controller
{
    /**
     * Show auctions main view.
     *
     * @return \Illuminate\View\View
     */
    public function main()
    {
		$ds = new AuctionsDatasets();
		$details = $ds->get('auctions');
        return $details
			? view('auctions', [
					'url' => DatabookAPI::url($details['fapireq']),
					'breadcrumbs' => Breadcrumbs::auctions(),
					'details' => $details,
				   ####### seo ########
					'pagetitle' => "NYC Government Auctions - List of NYC Government Auctions by NYC Databook",
				])
			: abort(404);
    }
}
