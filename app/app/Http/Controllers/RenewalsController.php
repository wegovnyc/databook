<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\RenewalsDatasets;
use App\Custom\RenewalStoryLoader;

class RenewalsController extends Controller
{
    public function queue(Request $request)
    {
        $rank = $request->input('rank', 'expiring');
        if (!array_key_exists($rank, RenewalsDatasets::VIEWS)) $rank = 'expiring';

        $filters = [
            'agency' => trim((string) $request->input('agency', '')),
            'window' => trim((string) $request->input('window', '')),
            'replaceable' => (bool) $request->input('replaceable', false),
        ];

        $result = RenewalsDatasets::queue($rank, $filters);

        return view('procurement.renewals', [
            'pagetitle' => "Renewal Review Queue - NYC Databook",
            'rank' => $rank,
            'filters' => $filters,
            'rows' => $result['rows'],
            'view' => $result['view'],
            'agencies' => $result['agencies'],
            'stats' => $result['stats'],
            'views' => RenewalsDatasets::VIEWS,
        ]);
    }

    public function story(Request $request, $contract)
    {
        $c = RenewalsDatasets::find($contract);
        if (!$c) abort(404, 'Contract not found');

        $story = RenewalStoryLoader::load($contract);
        if (!$story) abort(404, 'Story not published yet');

        return view('procurement.contract-story', [
            'pagetitle' => ($story['title'] ?? $c['purpose']) . " - NYC Databook",
            'contract' => $c,
            'story' => $story,
            'daysLeft' => RenewalsDatasets::daysLeft($c),
        ]);
    }
}
