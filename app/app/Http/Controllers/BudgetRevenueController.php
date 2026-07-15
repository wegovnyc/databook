<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\DatabookAPI;

/**
 * Budget & Revenue domains (CheckbookNYC parity). Data comes from the DuckDB-over-
 * Parquet endpoints in api/routers/budget_revenue.py. Both pages degrade gracefully:
 * the API returns available:false (empty shape) until the Parquet is ingested, and
 * the views render a "not yet available" state.
 */
class BudgetRevenueController extends Controller
{
    public function budget(Request $request)
    {
        $fy = $request->input('fiscal_year');
        $summary = DatabookAPI::reqOCE('/oce/budget/summary', 60)
            ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => []];
        $agenciesUrl = '/oce/budget/agencies' . ($fy ? "?fiscal_year={$fy}" : '');
        $agencies = DatabookAPI::reqOCE($agenciesUrl, 60)
            ?: ['available' => false, 'data' => [], 'total' => 0];

        return view('procurement.budget', [
            'pagetitle' => 'Budget - Procurement - Databook',
            'summary' => $summary,
            'agencies' => $agencies,
        ]);
    }

    public function revenue(Request $request)
    {
        $fy = $request->input('fiscal_year');
        $summary = DatabookAPI::reqOCE('/oce/revenue/summary', 60)
            ?: ['available' => false, 'latest_year' => null, 'totals' => [], 'by_year' => [], 'by_category' => []];
        $agenciesUrl = '/oce/revenue/agencies' . ($fy ? "?fiscal_year={$fy}" : '');
        $agencies = DatabookAPI::reqOCE($agenciesUrl, 60)
            ?: ['available' => false, 'data' => [], 'total' => 0];

        return view('procurement.revenue', [
            'pagetitle' => 'Revenue - Procurement - Databook',
            'summary' => $summary,
            'agencies' => $agencies,
        ]);
    }
}
