@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => null])
@endsection

@section('content')
<div class="container my-4">
    <h1><i class="fas fa-cog me-2"></i>Admin Dashboard</h1>
    <p class="text-muted mb-4">Internal tools and data management</p>

    <div class="row g-4">
        <div class="col-md-4">
            <div class="card h-100 shadow-sm">
                <div class="card-body">
                    <h5 class="card-title"><i class="fas fa-database me-2 text-primary"></i>Database Tables</h5>
                    <p class="card-text">View all 70+ database tables with row counts, sizes, and source URLs.</p>
                    <a href="{{ route('admin.dataTables') }}" class="btn btn-primary">
                        <i class="fas fa-table me-1"></i> View Tables
                    </a>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card h-100 shadow-sm">
                <div class="card-body">
                    <h5 class="card-title"><i class="fas fa-history me-2 text-success"></i>Ingestion Log</h5>
                    <p class="card-text">Track data import history with timestamps and status.</p>
                    <a href="{{ route('admin.ingestionLog') }}" class="btn btn-success">
                        <i class="fas fa-list me-1"></i> View Log
                    </a>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card h-100 shadow-sm">
                <div class="card-body">
                    <h5 class="card-title"><i class="fas fa-heartbeat me-2 text-danger"></i>Data Health</h5>
                    <p class="card-text">Monitor dataset freshness, detect staleness, and track unmapped entities.</p>
                    <a href="{{ route('admin.dataHealth') }}" class="btn btn-danger">
                        <i class="fas fa-chart-line me-1"></i> View Health
                    </a>
                </div>
            </div>
        </div>
    </div>
</div>
@endsection
