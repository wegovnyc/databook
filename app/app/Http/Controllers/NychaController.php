<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

/**
 * NYCHA (NYC Housing Authority) procurement.
 *
 * NYCHA procurement now lives on the canonical org profile (id 170020034),
 * mirroring the /procurement/agency/{name} → org-profile unification. These
 * legacy /procurement/nycha* routes 302-redirect into the org profile's
 * procurement section (rendered by Organizations::orgProcurementSection, which
 * pulls the DuckDB-over-Parquet endpoints in api/routers/nycha.py). Preserving
 * the routes keeps old links / bookmarks working.
 */
class NychaController extends Controller
{
    /** Canonical NYCHA org profile identifiers. */
    private const ORG_ID   = 170020034;
    private const ORG_SLUG = 'nyc-housing-authority';

    /** Redirect helper preserving ?fiscal_year= (301 would be cached; use 302). */
    private function toOrg(string $section, Request $request)
    {
        return redirect(route('orgSection', [
            'id' => self::ORG_ID,
            'orgslug' => self::ORG_SLUG,
            'section' => $section,
        ]) . ($request->query('fiscal_year') ? '?fiscal_year=' . $request->query('fiscal_year') : ''));
    }

    public function index(Request $request)     { return $this->toOrg('procurement-highlights', $request); }
    public function budget(Request $request)    { return $this->toOrg('procurement-nycha-budget', $request); }
    public function revenue(Request $request)   { return $this->toOrg('procurement-nycha-revenue', $request); }
    public function contracts(Request $request) { return $this->toOrg('procurement-nycha-contracts', $request); }
    public function spending(Request $request)  { return $this->toOrg('procurement-nycha-spending', $request); }
}
