@extends('layout')

@section('head')
	<meta name="description" content="Statistics for NYC Civil Service Titles" />
	<title>Civil Service Title Statistics | Databook</title>
    <!-- Plotly.js -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        .stat-card {
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
            margin-bottom: 20px;
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        .chart-container {
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        .section-title {
            margin-top: 40px;
            margin-bottom: 20px;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
    </style>
@endsection

@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
<div class="inner_container">
<div class="container">
    <div class="row" style="margin-top: 20px;">
        <div class="col-12">
            <h1>Civil Service Title Statistics</h1>
            <p class="lead">An analysis of the city's civil service title system. To see a directory of all Titles visit <a href="https://databook.nyc/titles">databook.nyc/titles</a></p>
        </div>
    </div>

    <!-- Section 1: Top Summary Cards -->
    <div class="row" style="margin-bottom: 30px;">
        <div class="col">
            <div class="db-stat">
                <div class="db-stat-value">{!! number_format($data['metrics']['total_rows']) !!}</div>
                <div class="db-stat-label">Unique Title Codes</div>
            </div>
        </div>
        <div class="col">
            <div class="db-stat">
                <div class="db-stat-value">{!! number_format($data['metrics']['cnt_titles_pos']) !!}</div>
                <div class="db-stat-label">Titles with >0 Scheduled Positions</div>
            </div>
        </div>
        <div class="col">
            <div class="db-stat">
                <div class="db-stat-value">{!! number_format($data['metrics']['total_positions']) !!}</div>
                <div class="db-stat-label">Scheduled Positions</div>
            </div>
        </div>
        <div class="col">
            <div class="db-stat">
                <div class="db-stat-value">{!! number_format($data['metrics']['unique_positions']) !!}</div>
                <div class="db-stat-label">Unique Positions</div>
            </div>
        </div>
    </div>

    <!-- Section 2: Titles in Other Datasets -->
    <h3 class="section-title">Titles in Other Datasets</h3>
    <div class="row">
        <div class="col-md-6">
            <div class="db-stat">
                <div class="db-stat-value">{!! number_format($data['metrics']['cnt_civil_active']) !!}</div>
                <div class="db-stat-label">Civil List Active Check</div>
                <div style="font-size: 0.9em; color: #888;">({!! number_format($data['metrics']['pct_civil_active'], 1) !!}%)</div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="db-stat">
                <div class="db-stat-value">{!! number_format($data['metrics']['cnt_civil']) !!}</div>
                <div class="db-stat-label">Civil List Check</div>
                <div style="font-size: 0.9em; color: #888;">({!! number_format($data['metrics']['pct_civil'], 1) !!}%)</div>
            </div>
        </div>
    </div>

    <!-- Section 3: Titles and Descriptions -->
    <h3 class="section-title" style="margin-top: 20px;">Titles and Descriptions</h3>
    <div class="row">
        <div class="col-md-4">
            <div class="db-stat">
                <div class="db-stat-value">{!! number_format($data['metrics']['cnt_full_desc']) !!}</div>
                <div class="db-stat-label">Titles with Full Descriptions</div>
                <div style="font-size: 0.9em; color: #888;">({!! number_format($data['metrics']['pct_full_desc'], 4) !!}%)</div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="db-stat">
                <div class="db-stat-value">{!! number_format($data['metrics']['cnt_unique_full_desc']) !!}</div>
                <div class="db-stat-label">Unique Positions with Titles with Descriptions</div>
                <div style="font-size: 0.9em; color: #888;">({!! number_format($data['metrics']['pct_unique_full_desc'], 4) !!}%)</div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="db-stat">
                <div class="db-stat-value">{!! number_format($data['metrics']['cnt_positions_full_desc']) !!}</div>
                <div class="db-stat-label">Scheduled Positions with Titles with Descriptions</div>
                <div style="font-size: 0.9em; color: #888;">({!! number_format($data['metrics']['pct_positions_full_desc'], 4) !!}%)</div>
            </div>
        </div>
    </div>

    <!-- Charts -->
    <h2 class="section-title">Visualizations</h2>
    
    <div class="row">
        <div class="col-12">
            <div class="chart-container">
                <div id="timelineChart"></div>
            </div>
        </div>
    </div>

    <div class="row">
        <div class="col-md-6">
            <div class="chart-container">
                <div id="bucketChart"></div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="chart-container">
                <div id="topTitlesChart"></div>
            </div>
        </div>
    </div>

    <!-- New Row for Agency Pie Chart -->
    <div class="row">
        <div class="col-12">
            <div class="chart-container">
                <div id="agencyPieChart" style="height: 600px;"></div>
            </div>
        </div>
    </div>



    <!-- Section 4: Titles Missing Descriptions -->
    <h2 class="section-title" style="margin-top: 40px;">Titles Missing Descriptions</h2>
    <div class="row">
        <div class="col-12">
            <p>Listing of all {!! count($data['lists']['no_desc']) !!} titles that do not have a full description, sorted by scheduled positions.</p>
            <table id="noDescTable" class="db-table table table-striped table-bordered" style="width:100%">
                <thead>
                    <tr>
                        <th>Code</th>
                        <th>Title Description</th>
                        <th class="text-right">Scheduled Positions</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($data['lists']['no_desc'] as $row)
                    <tr>
                        <td><a href="{!! route('title', ['id' => $row['Title Code']]) !!}">{!! $row['Title Code'] !!}</a></td>
                        <td>{!! $row['Title Description'] !!}</td>
                        <td class="text-right" data-order="{!! $row['Total Positions using this Title'] !!}">{!! number_format($row['Total Positions using this Title']) !!}</td>
                    </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
    </div>

</div>
</div>

<script>
    var data = @json($data);

    // Chart 1: Timeline
    Plotly.newPlot('timelineChart', [{
        x: data.charts.timeline.years,
        y: data.charts.timeline.counts,
        type: 'bar'
    }], {
        title: 'Titles by Effective Date Year',
        xaxis: {title: 'Year'},
        yaxis: {title: 'Number of Titles'},
        margin: {t: 40, r: 20, l: 60, b: 40}
    }, {responsive: true});

    // Chart 2: Buckets
    Plotly.newPlot('bucketChart', [{
        x: data.charts.buckets.labels,
        y: data.charts.buckets.values,
        type: 'bar'
    }], {
        title: 'Distribution of Positions per Title',
        xaxis: {
            title: 'Position Count Bucket',
            type: 'category',
            categoryorder: 'array',
            categoryarray: data.charts.buckets.labels
        },
        yaxis: {title: 'Number of Titles'},
        margin: {t: 40, r: 20, l: 60, b: 40}
    }, {responsive: true});

    // Chart 3: Top Titles (Horizontal)
    // Reverse order so largest is at top
    var topTitles = data.top_lists.total.slice().reverse(); 
    Plotly.newPlot('topTitlesChart', [{
        x: topTitles.map(i => i['Total Positions using this Title']),
        y: topTitles.map(i => i['Title Description']), 
        type: 'bar',
        orientation: 'h'
    }], {
        title: 'Top 10 Titles by Total Positions',
        xaxis: {title: 'Total Positions'},
        yaxis: {
            automargin: true,
            title: ''
        },
        margin: {t: 40, r: 20, l: 200, b: 40} // Increased left margin as fallback
    }, {responsive: true});

    // Chart 4: Agency No Description Pie
    var agencyData = data.charts.agency_no_desc;
    if (agencyData && agencyData.length > 0) {
        // limit to top 15 and group 'others'
        var topAgency = agencyData.slice(0, 15);
        var others = agencyData.slice(15);
        
        var labels = topAgency.map(i => i['Agency Name']);
        var values = topAgency.map(i => i['Scheduled Positions']);
        
        if (others.length > 0) {
            var otherSum = others.reduce((acc, curr) => acc + curr['Scheduled Positions'], 0);
            labels.push('All Others (' + others.length + ' Agencies)');
            values.push(otherSum);
        }

        Plotly.newPlot('agencyPieChart', [{
            labels: labels,
            values: values,
            type: 'pie',
            textinfo: 'label+percent',
            insidetextorientation: 'radial'
        }], {
            title: 'Scheduled Positions with Titles Missing Descriptions by Agency',
            margin: {t: 50, r: 20, l: 20, b: 20}
        }, {responsive: true});
    }

    // DataTable Initialization
    $(document).ready(function() {
        $('#noDescTable').DataTable({
            "order": [[ 2, "desc" ]],
            "pageLength": 100,
            "language": {
                "search": "Search Titles:"
            }
        });
    });

</script>
@endsection
