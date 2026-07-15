<?php

namespace App\Http\Controllers;

use App\Custom\DatabookAPI;

/**
 * Admin controller for internal management views.
 */
class Admin extends Controller
{
    /**
     * Display the admin dashboard with links to all admin pages.
     *
     * @return \Illuminate\View\View
     */
    public function index()
    {
        return view('admin.index', [
            'pagetitle' => 'Admin Dashboard | Databook.nyc',
        ]);
    }

    /**
     * Display the ingestion log from the Databook API.
     *
     * @return \Illuminate\View\View
     */
    public function ingestionLog()
    {
        $logs = DatabookAPI::req('/ingestion-log?limit=100');
        
        return view('admin.ingestion_log', [
            'logs' => $logs ?? [],
            'pagetitle' => 'Ingestion Log | Admin',
        ]);
    }

    /**
     * Display database table statistics as an interactive DataTable.
     *
     * @return \Illuminate\View\View
     */
    public function dataTables()
    {
        $stats = DatabookAPI::reqOCE('/table-stats');
        
        return view('admin.datatables', [
            'tables' => $stats['rows'] ?? [],
            'total_tables' => $stats['total_tables'] ?? 0,
            'pagetitle' => 'Database Tables | Admin',
        ]);
    }

    /**
     * Display the data health dashboard showing dataset freshness and unmapped entities.
     *
     * Why: Provides admins a single view to monitor data pipeline health,
     * identify stale datasets, and track unmapped entities needing manual mapping.
     *
     * @return \Illuminate\View\View
     */
    public function dataHealth()
    {
        $health = DatabookAPI::reqOCE('/pipeline/health');

        return view('admin.data_health', [
            'summary' => $health['summary'] ?? [],
            'datasets' => $health['datasets'] ?? [],
            'pagetitle' => 'Data Health | Admin',
        ]);
    }
}
