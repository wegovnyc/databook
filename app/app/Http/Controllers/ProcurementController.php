<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Custom\DatabookAPI;

use App\Custom\Breadcrumbs;

class ProcurementController extends Controller
{
    public function index(Request $request)
    {
        // OCE Parquet queries can take 30-90s; nginx fastcgi_read_timeout must be >= this
        $stats = DatabookAPI::reqOCE('/oce/dashboard/stats', 90);
        
        // Graceful fallback if API times out or fails
        if (!$stats || !is_array($stats)) {
            $stats = [
                'contracts' => 0, 'vendors' => 0, 'solicitations' => 0,
                'agencies' => 0, 'spending' => 0, 'awarded' => 0,
                'charts' => ['time' => ['labels' => [], 'values' => []],
                             'agencies' => ['labels' => [], 'values' => []],
                             'vendors' => ['labels' => [], 'values' => []],
                             'industries' => ['labels' => [], 'values' => []],
                             'methods' => ['labels' => [], 'values' => []]],
            ];
        }
        
        // Capital mini-dashboard aggregates — precomputed homepage stats (NYC
        // Capital Projects Database), the same source /projects/capital uses. Fast
        // (cached); falls back to the bundled globStats.json if the API is down.
        $globStats = DatabookAPI::reqOCE('/pipeline/globstats', 15);
        if (!$globStats || !is_array($globStats)) {
            $fallback = public_path('data/globStats.json');
            $globStats = file_exists($fallback) ? (json_decode(file_get_contents($fallback), true) ?: []) : [];
        }

        // Actual capital spending (Checkbook 'Capital Contracts' payments) by fiscal
        // year — last 10 complete FYs — for the capital spending chart. Cached +
        // pre-warmed on the API side; empty-safe if unavailable.
        $capitalSpend = DatabookAPI::reqOCE('/oce/spending/capital-by-year', 30);
        if (!$capitalSpend || !is_array($capitalSpend)) {
            $capitalSpend = ['labels' => [], 'values' => []];
        }

        return view('procurement.index', [
            'pagetitle' => "Procurement Dashboard - Databook",
            'stats' => $stats,
            'globStats' => $globStats,
            'capitalSpend' => $capitalSpend,
        ]);
    }

    public function vendors(Request $request)
    {
        $page = $request->input('page', 1);
        $q = $request->input('q', '');
        // Default to highest total-awarded first so the landing surfaces real
        // contracting vendors, not the many $0 registered suppliers.
        $sort = $request->input('sort', 'amount');
        $order = $request->input('order', 'desc');
        $category = $request->input('category', '');
        $mwbe = $request->input('mwbe', '');
        
        // Pass empty strings to clear filters if not set
        $data = DatabookAPI::reqOCE("/oce/vendors?page={$page}&q=" . urlencode($q) . "&sort={$sort}&order={$order}&category=" . urlencode($category) . "&mwbe=" . urlencode($mwbe), 30);
        $data = $data ?: ['data' => [], 'total' => 0, 'page' => 1, 'pages' => 1, 'categories' => [], 'mwbe_options' => []];
        
        return view('procurement.vendors', [
            'pagetitle' => "Vendors - Procurement",
            'data' => $data,
            'q' => $q,
            'sort' => $sort,
            'order' => $order,
            'category' => $category,
            'mwbe' => $mwbe,
        ]);
    }

    public function vendorProfile($id)
    {
        $data = DatabookAPI::reqOCE("/oce/vendor/{$id}", 30);
        
        if (!$data || !isset($data['vendor'])) {
            abort(404, 'Vendor not found');
        }
        
        return view('procurement.vendor_profile', [
            'pagetitle' => ($data['vendor']['name'] ?? 'Vendor') . " - Procurement",
            'vendor' => $data['vendor'],
            'contracts' => $data['contracts'] ?? [],
            'spend' => $data['spend'] ?? null,   // Checkbook actuals across this vendor's contracts
            'sbs' => $data['sbs'] ?? null,       // SBS certified-business profile (null when unmatched)
            'passport' => $data['passport'] ?? null, // PASSPort sub-tables: ownership, MOCS ratings, entity record
            'doingBusiness' => $data['doing_business'] ?? null, // MOCS Doing Business Database (LL34)
            'dos' => $data['dos'] ?? null,        // NY DOS legal-entity record (null when unmatched)
            'relatedNotices' => $data['related_notices'] ?? [],
            'nycha' => $data['nycha'] ?? null,
            // Track B: orgs in the civic register that ARE this vendor. A list,
            // because several register rows can legitimately share one vendor —
            // United Federation of Teachers is the union plus two bargaining units.
            'civicOrgs' => $data['civic_orgs'] ?? [],
            'breadcrumbs' => Breadcrumbs::procurementVendor($id, $data['vendor']['name'] ?? 'Vendor')
        ]);
    }

    public function agencies(Request $request)
    {
        $page = $request->input('page', 1);
        $q = $request->input('q', '');
        $sort = $request->input('sort', 'amount');
        $order = $request->input('order', 'desc');
        
        $data = DatabookAPI::reqOCE("/oce/agencies?page={$page}&q=" . urlencode($q) . "&sort={$sort}&order={$order}&limit=50", 30);
        $data = $data ?: ['data' => [], 'total' => 0, 'page' => 1, 'pages' => 1];
        
        return view('procurement.agencies', [
            'pagetitle' => "Agencies - Procurement",
            'data' => $data ?? [],
            'q' => $q,
            'sort' => $sort,
            'order' => $order,
        ]);
    }

    public function contracts(Request $request)
    {
        [$sort, $order] = array_pad(explode('-', $request->input('sort', 'amount-desc'), 2), 2, 'desc');
        if (!in_array($sort, ['amount', 'date', 'vendor', 'agency'], true)) { $sort = 'amount'; }
        $order = $order === 'asc' ? 'asc' : 'desc';

        $filters = [
            'q'                => trim($request->input('q', '')),
            'agency'           => $request->input('agency', ''),
            'status'           => $request->input('status', ''),
            'method'           => $request->input('method', ''),
            'industry'         => $request->input('industry', ''),
            'expense_category' => $request->input('expense_category', ''),
            'min_amount'       => $request->input('min_amount', ''),
            'max_amount'       => $request->input('max_amount', ''),
        ];
        $active = array_filter($filters, fn($v) => $v !== '' && $v !== null);

        $query = http_build_query($active + [
            'page' => (int) $request->input('page', 1), 'sort' => $sort, 'order' => $order,
        ]);
        $data = DatabookAPI::reqOCE("/oce/contracts?{$query}", 30)
            ?: ['data' => [], 'total' => 0, 'page' => 1, 'pages' => 1];
        $filterOptions = DatabookAPI::reqOCE("/oce/filter-options", 10);

        $apiBase = rtrim(config('apis.fapi_public_entry', 'https://api.databook.nyc'), '/');
        $exportUrl = $apiBase . "/oce/contracts/export?" . http_build_query($active + ['sort' => $sort, 'order' => $order]);

        return view('procurement.contracts', [
            'pagetitle'     => "Contracts - Procurement",
            'data'          => $data,
            'filters'       => $filters,
            'sortKey'       => "{$sort}-{$order}",
            'filterOptions' => $filterOptions['contracts'] ?? [],
            'exportUrl'     => $exportUrl,
        ]);
    }

    public function solicitations(Request $request)
    {
        $page = $request->input('page', 1);
        $q = $request->input('q', '');
        $status = $request->input('status', '');
        $method = $request->input('method', '');
        $industry = $request->input('industry', '');
        
        $queryParams = http_build_query([
            'page' => $page,
            'q' => $q,
            'status' => $status,
            'method' => $method,
            'industry' => $industry
        ]);
        
        $data = DatabookAPI::reqOCE("/oce/solicitations?{$queryParams}", 30);
        $data = $data ?: ['data' => [], 'total' => 0, 'page' => 1, 'pages' => 1];
        $filterOptions = DatabookAPI::reqOCE("/oce/filter-options", 10);
        
        return view('procurement.solicitations', [
            'pagetitle' => "Solicitations - Procurement",
            'data' => $data,
            'q' => $q,
            'status' => $status,
            'method' => $method,
            'industry' => $industry,
            'filterOptions' => $filterOptions['solicitations'] ?? [],
        ]);
    }

    public function contractProfile($id)
    {
        $data = DatabookAPI::reqOCE("/oce/contract/{$id}", 30);
        
        if (!$data || !isset($data['contract'])) {
            abort(404, 'Contract not found');
        }
        
        return view('procurement.contract_profile', [
            'pagetitle' => ($data['contract']['contract_id'] ?? 'Contract') . " - Procurement",
            'contract' => $data['contract'],
            'vendor' => $data['vendor'] ?? null,
            'solicitation' => $data['solicitation'] ?? null,
            'relatedNotices' => $data['related_notices'] ?? [],
            'spendTimeline' => $data['spend_timeline'] ?? ['labels' => [], 'values' => []],
            'spendVendors' => $data['spend_vendors'] ?? [],
            'evaluations' => $data['evaluations'] ?? [],           // MOCS agency ratings for this contract
            'evaluationsAsOf' => $data['evaluations_as_of'] ?? '',
            'breadcrumbs' => Breadcrumbs::procurementContract($id, $data['contract']['contract_id'] ?? 'Contract')
        ]);
    }

    public function solicitationProfile($epin)
    {
        $data = DatabookAPI::reqOCE("/oce/solicitation/{$epin}", 30);
        
        if (!$data || !isset($data['solicitation'])) {
            abort(404, 'Solicitation not found');
        }
        
        return view('procurement.solicitation_profile', [
            'pagetitle' => ($data['solicitation']['epin'] ?? 'Solicitation') . " - Procurement",
            'solicitation' => $data['solicitation'],
            'contracts' => $data['contracts'] ?? [],
            'relatedNotices' => $data['related_notices'] ?? [],
            'stats' => $data['stats'] ?? [],
            'breadcrumbs' => Breadcrumbs::procurementSolicitation($epin, $data['solicitation']['procurement_name'] ?? 'Solicitation')
        ]);
    }

    public function digitalReform(Request $request)
    {
        return view('procurement.digital-reform', array_merge(
            ['pagetitle' => "Digital Services - NYC Databook"],
            $this->digitalReformViewData($request)
        ));
    }

    /**
     * Dedicated page for the Renewal Review Queue (contracts expiring before 2030).
     */
    public function digitalReformExpiring(Request $request)
    {
        return view('procurement.digital-reform-expiring', array_merge(
            ['pagetitle' => "Expiring Digital Service Contracts - NYC Databook"],
            $this->digitalReformViewData($request)
        ));
    }

    /**
     * Shared loader for both Digital Services pages: reads all filter params,
     * calls the combined API (cached 24h), and returns the full view-data array.
     * The two pages each render the slice they need.
     */
    private function digitalReformViewData(Request $request)
    {
        $vendorPage = $request->input('vendor_page', 1);
        $vendorSort = $request->input('vendor_sort', 'amount');
        $vendorOrder = $request->input('vendor_order', 'desc');
        $vendorQ = trim((string) $request->input('vendor_q', ''));

        $contractPage = $request->input('contract_page', 1);
        $contractSort = $request->input('contract_sort', 'date');
        $contractOrder = $request->input('contract_order', 'desc');
        $contractQ = trim((string) $request->input('contract_q', ''));
        $contractMethod = trim((string) $request->input('contract_method', ''));

        $expiringPage = $request->input('expiring_page', 1);
        $expiringSort = $request->input('expiring_sort', 'date');
        $expiringOrder = $request->input('expiring_order', 'asc');
        $expiringYear = trim((string) $request->input('expiring_year', ''));
        $expiringAgency = trim((string) $request->input('expiring_agency', ''));
        $expiringMethod = trim((string) $request->input('expiring_method', ''));
        $expiringMin = (float) $request->input('expiring_min', 0);
        $expiringFlag = trim((string) $request->input('expiring_flag', ''));
        $expiringCategory = trim((string) $request->input('expiring_category', ''));
        $expiringLicense = trim((string) $request->input('expiring_license', ''));
        $expiringBuildbuy = trim((string) $request->input('expiring_buildbuy', ''));
        $expiringShowNonTech = trim((string) $request->input('expiring_shownontech', ''));

        // Single combined API call with Laravel file cache (24h). Cache key + the
        // forwarded query string both include every filter so results stay correct.
        $qs = http_build_query([
            'vendor_page' => $vendorPage, 'vendor_sort' => $vendorSort, 'vendor_order' => $vendorOrder,
            'vendor_q' => $vendorQ,
            'contract_page' => $contractPage, 'contract_sort' => $contractSort, 'contract_order' => $contractOrder,
            'contract_q' => $contractQ, 'contract_method' => $contractMethod,
            'expiring_page' => $expiringPage, 'expiring_sort' => $expiringSort, 'expiring_order' => $expiringOrder,
            'expiring_year' => $expiringYear, 'expiring_agency' => $expiringAgency,
            'expiring_method' => $expiringMethod, 'expiring_min' => $expiringMin, 'expiring_flag' => $expiringFlag,
            'expiring_category' => $expiringCategory, 'expiring_license' => $expiringLicense,
            'expiring_buildbuy' => $expiringBuildbuy, 'expiring_shownontech' => $expiringShowNonTech,
        ]);
        $cacheKey = 'digital_reform_' . md5($qs);
        $allData = \Illuminate\Support\Facades\Cache::remember($cacheKey, 86400, function () use ($qs) {
            return DatabookAPI::reqOCE("/oce/digital-reform/all?{$qs}", 30);
        });

        $stats = $allData['stats'] ?? [];
        $charts = $allData['charts'] ?? [];
        $vendors = $allData['vendors'] ?? [];
        $contracts = $allData['contracts'] ?? [];
        $expiring = $allData['expiring'] ?? [];
        $contractOptions = $allData['contract_options'] ?? ['methods' => []];

        return [
            'stats' => $stats,
            'charts' => $charts,
            'vendors' => $vendors,
            'contracts' => $contracts,
            'expiring' => $expiring,
            'contractOptions' => $contractOptions,
            'vendorPage' => $vendorPage,
            'vendorSort' => $vendorSort,
            'vendorOrder' => $vendorOrder,
            'vendorQ' => $vendorQ,
            'contractPage' => $contractPage,
            'contractSort' => $contractSort,
            'contractOrder' => $contractOrder,
            'contractQ' => $contractQ,
            'contractMethod' => $contractMethod,
            'expiringPage' => $expiringPage,
            'expiringSort' => $expiringSort,
            'expiringOrder' => $expiringOrder,
            'expiringYear' => $expiringYear,
            'expiringAgency' => $expiringAgency,
            'expiringMethod' => $expiringMethod,
            'expiringMin' => $expiringMin,
            'expiringFlag' => $expiringFlag,
            'expiringCategory' => $expiringCategory,
            'expiringLicense' => $expiringLicense,
            'expiringBuildbuy' => $expiringBuildbuy,
            'expiringShowNonTech' => $expiringShowNonTech,
        ];
    }

    public function orgProcurement(Request $request, $name = null)
    {
        $agencyName = $name ?? $request->input('name');
        if (!$agencyName) {
            abort(400, 'Agency name required');
        }
        
        $data = DatabookAPI::reqOCE("/oce/agency/procurement?name=" . urlencode($agencyName), 30);

        if (!$data || !isset($data['agency'])) {
            abort(404, 'Agency not found');
        }

        // Agency-profile unification: when this agency resolves to an org record,
        // send users to the single canonical profile (org profile's procurement
        // section) instead of this standalone page. Unmatched agencies (org_id
        // null) fall through and render the standalone page as the fallback.
        // 302 (not 301) during rollout so the crosswalk stays tunable without
        // poisoning browser caches.
        $orgId = $data['agency']['org_id'] ?? null;
        if ($orgId) {
            return redirect()->route('orgSection', [
                'id'      => $orgId,
                'orgslug' => \Illuminate\Support\Str::slug($data['agency']['name'] ?? $agencyName, '-'),
                'section' => 'procurement-highlights',
            ], 302);
        }

        return view('procurement.org_procurement', [
            'pagetitle' => ($data['agency']['name'] ?? 'Agency') . " Procurement - Databook",
            'agency' => $data['agency'],
            'stats' => $data['stats'] ?? [],
            'monthly_activity' => $data['monthly_activity'] ?? [],
            'yearly_spending' => $data['yearly_spending'] ?? [],
            'contracts' => $data['contracts'] ?? [],
            'solicitations' => $data['solicitations'] ?? [],
            'vendors' => $data['vendors'] ?? [],
            'breadcrumbs' => Breadcrumbs::procurementAgency($data['agency']['name'] ?? $agencyName)
        ]);
    }

    /**
     * Spending dashboard — stat tiles, Top-5 ranked cards, and charts.
     */
    public function transactions(Request $request)
    {
        // The dashboard's heavy widgets (totals, Top-N, charts, sub-vendor, M/WBE)
        // are lazy-loaded client-side from the API so a cold/slow Parquet scan never
        // blocks the page render. Controller just passes the fiscal year.
        $fy = (int) $request->input('fiscal_year', 2026);

        return view('procurement.transactions', [
            'pagetitle' => "Spending - Procurement",
            'fiscal_year' => $fy,
        ]);
    }

    /**
     * Transaction explorer — faceted filters, expandable results table, pagination.
     */
    public function transactionsSearch(Request $request)
    {
        // Sort select encodes column + direction as "col-dir" (e.g. "amount-desc").
        [$sort, $order] = array_pad(explode('-', $request->input('sort', 'amount-desc'), 2), 2, 'desc');
        $allowedSort = ['amount', 'date', 'agency', 'vendor'];
        if (!in_array($sort, $allowedSort, true)) { $sort = 'amount'; }
        $order = $order === 'asc' ? 'asc' : 'desc';

        $filters = [
            'q'                 => trim($request->input('q', '')),
            'fiscal_year'       => $request->input('fiscal_year', 2026),
            'agency'            => $request->input('agency', ''),
            'expense_category'  => $request->input('expense_category', ''),
            'spending_category' => $request->input('spending_category', ''),
            'industry'          => $request->input('industry', ''),
            'sub_vendor'        => $request->input('sub_vendor', ''),
            'mwbe_category'     => $request->input('mwbe_category', ''),
            'woman_owned'       => $request->input('woman_owned', ''),
            'emerging'          => $request->input('emerging', ''),
            'min_amount'        => $request->input('min_amount', ''),
            'max_amount'        => $request->input('max_amount', ''),
            'date_from'         => $request->input('date_from', ''),
            'date_to'           => $request->input('date_to', ''),
        ];
        $active = array_filter($filters, fn($v) => $v !== '' && $v !== null);

        $query = http_build_query($active + [
            'page'  => (int) $request->input('page', 1),
            'sort'  => $sort,
            'order' => $order,
        ]);
        $data = DatabookAPI::reqOCE("/oce/transactions?{$query}", 30)
            ?: ['data' => [], 'total' => 0, 'total_amount' => 0, 'page' => 1, 'pages' => 1, 'fiscal_years' => []];

        $fy = (int) $filters['fiscal_year'];
        // Contextual facets: pass every active filter so each dimension narrows to the rest.
        $facets = DatabookAPI::reqOCE("/oce/transactions/facets?" . http_build_query($active), 300)
            ?: ['agency' => [], 'expense_category' => [], 'industry' => [], 'spending_category' => []];

        // CSV export streams from the public API directly (browser download), current filters minus paging.
        $apiBase = rtrim(config('apis.fapi_public_entry', 'https://api.databook.nyc'), '/');
        $exportUrl = $apiBase . "/oce/transactions/export?" . http_build_query($active + ['sort' => $sort, 'order' => $order]);

        return view('procurement.transactions_search', [
            'pagetitle'  => "Transactions - Spending",
            'data'       => $data,
            'facets'     => $facets,
            'filters'    => $filters,
            'sortKey'    => "{$sort}-{$order}",
            'exportUrl'  => $exportUrl,
        ]);
    }

    /**
     * Display the data sources page documenting all OCE datasets.
     */
    public function dataSources()
    {
        return view('procurement.data_sources', [
            'pagetitle' => "Data Sources - Procurement",
        ]);
    }
}

