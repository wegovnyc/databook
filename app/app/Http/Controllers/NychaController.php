<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\DatabookAPI;

/**
 * NYCHA (NYC Housing Authority) Budget & Revenue domains (CheckbookNYC `_NYCHA`
 * feeds). Data from the DuckDB-over-Parquet endpoints in api/routers/nycha.py.
 * Both pages degrade gracefully: the API returns available:false (empty shape)
 * until the Parquet is ingested, and the views render a "not yet available" state.
 *
 * NYCHA has NO `agency` dimension — the breakdowns are by responsibility_center
 * (developments + functional units) for budget and by funding_source for revenue.
 */
class NychaController extends Controller
{
    /**
     * NYCHA landing page — a hub summarizing all four NYCHA financial domains
     * (budget, revenue, contracts, spending) with headline figures and links to
     * each subsection. Each summary endpoint is independently graceful
     * (available:false until its Parquet exists), so a card degrades on its own
     * without breaking the page.
     */
    public function index(Request $request)
    {
        $budget = DatabookAPI::reqOCE('/oce/nycha/budget/summary', 30)
            ?: ['available' => false, 'totals' => []];
        $revenue = DatabookAPI::reqOCE('/oce/nycha/revenue/summary', 30)
            ?: ['available' => false, 'totals' => []];
        $contracts = DatabookAPI::reqOCE('/oce/nycha/contracts/summary', 30)
            ?: ['available' => false, 'totals' => []];
        $spending = DatabookAPI::reqOCE('/oce/nycha/spending/summary', 30)
            ?: ['available' => false, 'totals' => []];

        return view('procurement.nycha_home', [
            'pagetitle' => 'NYCHA - Procurement - Databook',
            'budget' => $budget,
            'revenue' => $revenue,
            'contracts' => $contracts,
            'spending' => $spending,
        ]);
    }

    public function budget(Request $request)
    {
        $fy = $request->input('fiscal_year');
        $summary = DatabookAPI::reqOCE('/oce/nycha/budget/summary', 60)
            ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => [], 'by_funding_source' => []];
        $unitsUrl = '/oce/nycha/budget/units' . ($fy ? "?fiscal_year={$fy}" : '');
        $units = DatabookAPI::reqOCE($unitsUrl, 60)
            ?: ['available' => false, 'data' => [], 'total' => 0];

        return view('procurement.nycha_budget', [
            'pagetitle' => 'NYCHA Budget - Procurement - Databook',
            'summary' => $summary,
            'units' => $units,
        ]);
    }

    public function revenue(Request $request)
    {
        $fy = $request->input('fiscal_year');
        $summary = DatabookAPI::reqOCE('/oce/nycha/revenue/summary', 60)
            ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => [], 'by_funding_source' => []];
        $sourcesUrl = '/oce/nycha/revenue/sources' . ($fy ? "?fiscal_year={$fy}" : '');
        $sources = DatabookAPI::reqOCE($sourcesUrl, 60)
            ?: ['available' => false, 'data' => [], 'total' => 0];

        return view('procurement.nycha_revenue', [
            'pagetitle' => 'NYCHA Revenue - Procurement - Databook',
            'summary' => $summary,
            'sources' => $sources,
        ]);
    }

    public function contracts(Request $request)
    {
        $fy = $request->input('fiscal_year');
        $summary = DatabookAPI::reqOCE('/oce/nycha/contracts/summary', 60)
            ?: ['available' => false, 'totals' => [], 'by_year' => [], 'top_vendors' => []];
        $listUrl = '/oce/nycha/contracts?sort=current&limit=50' . ($fy ? "&fiscal_year={$fy}" : '');
        $contracts = DatabookAPI::reqOCE($listUrl, 60)
            ?: ['available' => false, 'data' => [], 'total' => 0];

        return view('procurement.nycha_contracts', [
            'pagetitle' => 'NYCHA Contracts - Procurement - Databook',
            'summary' => $summary,
            'contracts' => $contracts,
        ]);
    }

    public function spending(Request $request)
    {
        $fy = $request->input('fiscal_year');
        $summary = DatabookAPI::reqOCE('/oce/nycha/spending/summary', 60)
            ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [],
                'by_category' => [], 'by_funding_source' => [], 'section_8' => [], 'top_vendors' => []];
        $devUrl = '/oce/nycha/spending/by-development?sort=spending&limit=50' . ($fy ? "&fiscal_year={$fy}" : '');
        $developments = DatabookAPI::reqOCE($devUrl, 60)
            ?: ['available' => false, 'data' => [], 'total' => 0];

        return view('procurement.nycha_spending', [
            'pagetitle' => 'NYCHA Spending - Procurement - Databook',
            'summary' => $summary,
            'developments' => $developments,
        ]);
    }
}
