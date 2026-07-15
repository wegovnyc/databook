@extends('layout')


@section('head')
	<meta name="description" content="The roles, positions and pay of NYC's civil servants" />
	<meta rel="canonical" href="{!! route('titles') !!}" />
    <!-- Plotly.js -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        /* Titles index — db-* design system. Page-specific glue only;
           stats/cards/table/badges use shared component classes. */
        .titles-popular-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--db-space-2); }
        .titles-pop-card-title { font-size: var(--db-text-md); font-weight: var(--db-weight-bold); line-height: var(--db-leading-snug); margin: 0 0 2px; }
        .titles-pop-card-title a { color: var(--db-primary); }
        .titles-pop-code { font-family: var(--db-font-mono); font-size: var(--db-text-xs); color: var(--db-text-muted); }
        .titles-pop-salary { font-weight: var(--db-weight-bold); color: var(--db-primary); font-variant-numeric: tabular-nums; margin-top: var(--db-space-15); }
        .titles-pop-positions { font-size: var(--db-text-sm); color: var(--db-text-muted); }
        .chart-container {
            background: var(--db-bg);
            border: 1px solid var(--db-border);
            padding: var(--db-space-2);
            border-radius: var(--db-radius);
            margin-bottom: var(--db-space-3);
        }
    </style>
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'titles'])
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<script>
		var table = null
        var data = @json($data);

		function copyShareLink() {
			const url = $('#details-permalink').text()
			const params = new URLSearchParams({
			  search: $('input[type="search"]').val()
			});
			$('#details-permalink').text(`${url}?${params.toString()}`)
			copyLink()
			$('#details-permalink').text(url)
		}
		
		function loadShareLink() {
			const params = {!! $_GET ? json_encode($_GET) : '""' !!}
			if (params && params['q']) {
                table.search(params['q']).draw();
			}
		}

		$(document).ready(function() {
            // Plotly Charts
            if (data.charts) {
                // Chart 1: Timeline
                if (data.charts.timeline) {
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
                }

                // Chart 2: Buckets
                if (data.charts.buckets) {
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
                }
            }

            // Chart 3: Top Titles (Horizontal)
            if (data.top_lists && data.top_lists.total) {
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
                    margin: {t: 40, r: 20, l: 200, b: 40} 
                }, {responsive: true});
            }

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

            // Oldest Titles Table
            $('#oldestTitlesTable').DataTable({
                "order": [[ 2, "asc" ]], // Sort by Effective Date (index 2) ASC
                "pageLength": 10, // Default to 10 entries
                "language": {
                    "search": "Search Titles:"
                }
            });

            // No Desc Table
             $('#noDescTable').DataTable({
                "order": [[ 2, "desc" ]],
                "pageLength": 10,
                "language": {
                    "search": "Search Titles:"
                }
            });

			table = $('#titles-table').DataTable( {
				pageLength: 10,
				deferRender: true,
				order: [[2, 'desc']], // Sort by Scheduled Positions (index 2)
				dom: "<'db-table-toolbar'<'db-table-count'i><'db-spacer'>f>" + "rt" + "<'db-table-footer'lp>",
				language: { search: '', searchPlaceholder: 'Search titles…' },
				columnDefs: [{ className: 'db-num', targets: [2, 3, 5, 6] }],
				data: data && data.lists ? data.lists.master_list : [],
				columns: [
					{data: function (r) { return `<a href="/t/${r["Title Code"]}">${r["Title Code"]}</a>` }},
					{data: 'Title Description'},
					{
                        data: 'Scheduled Positions',
                        render: $.fn.dataTable.render.number(',', '.', 0)
                    },
					{
                        data: 'Agencies',
                        render: $.fn.dataTable.render.number(',', '.', 0)
                    },
					{data: 'Full Description'},
					{
                        data: 'Minimum Salary',
                        render: $.fn.dataTable.render.number(',', '.', 0, '$')
                    },
					{
                        data: 'Maximum Salary',
                        render: $.fn.dataTable.render.number(',', '.', 0, '$')
                    }
                ],
				@if ($defSearch)
					search: {
						'search': '{{ $defSearch }}'
					},
				@endif	
			});
		});
	</script>
{{-- Navy hero band (family-wide "Briefing" treatment) --}}
<div class="db-hero">
	<div class="inner_container">
		<div class="container db-hero-inner">
			<div class="db-hero-copy">
				<div class="db-eyebrow" style="color:var(--db-accent);">Jobs &amp; Exams</div>
				<h1>Civil Service Titles</h1>
				<p>NYC's government workforce is composed of people who hold "civil service titles" — the official descriptions of the work city employees perform. Each title links individuals to job positions, salary ranges, org charts and related exams.</p>
			</div>
		</div>
	</div>
</div>

<div class="inner_container">
	<div class="container" style="padding-top: var(--db-space-4); padding-bottom: var(--db-space-5);">

    @if($data)
    {{-- Summary stats --}}
    <div class="db-stat-grid" style="margin-bottom: var(--db-space-4);">
        <div class="db-stat is-accent">
            <div class="db-stat-label">Unique Title Codes</div>
            <div class="db-stat-value">{!! number_format($data['metrics']['total_rows']) !!}</div>
            <div class="db-stat-sub">classified</div>
        </div>
        <div class="db-stat">
            <div class="db-stat-label">Titles with Positions</div>
            <div class="db-stat-value">{!! number_format($data['metrics']['cnt_titles_pos']) !!}</div>
            <div class="db-stat-sub">&gt;0 scheduled</div>
        </div>
        <div class="db-stat">
            <div class="db-stat-label">Scheduled Positions</div>
            <div class="db-stat-value">{!! number_format($data['metrics']['total_positions']) !!}</div>
            <div class="db-stat-sub">citywide</div>
        </div>
        <div class="db-stat">
            <div class="db-stat-label">Individual Positions</div>
            <div class="db-stat-value">{!! number_format($data['metrics']['individual_positions']) !!}</div>
            <div class="db-stat-sub">filled</div>
        </div>
    </div>

    {{-- Popular titles --}}
    <div style="margin-bottom: var(--db-space-5);">
        <div class="db-eyebrow">Most positions</div>
        <h2 style="margin: 0 0 var(--db-space-2);">Popular titles</h2>
        <div class="titles-popular-grid">
            @foreach($data['top_lists']['agencies'] as $row)
            <div class="db-card is-hoverable">
                <div class="db-card-body">
                    <h3 class="titles-pop-card-title" title="{!! $row['Title Description'] !!}">
                        <a href="{!! route('title', ['id' => $row['Title Code']]) !!}">{!! $row['Title Description'] !!}</a>
                    </h3>
                    <div class="titles-pop-code">{!! $row['Title Code'] !!}</div>
                    <div class="titles-pop-salary">${{ number_format($row['Minimum Salary']) }}–${{ number_format($row['Maximum Salary']) }}</div>
                    <div class="titles-pop-positions">{!! number_format($row['Total Positions using this Title']) !!} positions</div>
                </div>
            </div>
            @endforeach
        </div>
    </div>
    @endif

	{{-- Directory --}}
    <div>
        <div class="db-eyebrow">Directory</div>
        <h2 style="margin: 0 0 var(--db-space-2);">All titles</h2>
        <div class="db-table-wrap">
            <div class="table-responsive">
                <table id="titles-table" class="db-table db-table-striped display table-hover" style="width:100%">
                    <thead>
                        <tr>
							<th>Title Code</th>
							<th>Title Description</th>
							<th>Scheduled Positions</th>
							<th>Agencies</th>
							<th>Full Description</th>
							<th>Minimum Salary</th>
							<th>Maximum Salary</th>
                        </tr>
                    </thead>
                </table>
            </div>
        </div>
    </div>
    @if($data)
    <div class="mt-5">
        <div class="db-eyebrow">Analysis</div>
        <h2 style="margin: 0 0 var(--db-space-2);">Title analysis</h2>

        <div class="row mb-5">
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

        <div class="db-stat-grid" style="margin-bottom: var(--db-space-4);">
            <div class="db-stat">
                <div class="db-stat-label">Age of Oldest Title</div>
                <div class="db-stat-value">{!! number_format($data['metrics']['oldest_title_age'], 1) !!} yrs</div>
                <div class="db-stat-sub">{!! $data['metrics']['oldest_title_name'] !!}</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Average Title Age</div>
                <div class="db-stat-value">{!! number_format($data['metrics']['avg_age'], 1) !!} yrs</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Median Title Age</div>
                <div class="db-stat-value">{!! number_format($data['metrics']['median_age'], 1) !!} yrs</div>
            </div>
        </div>

        <div class="row">
            <div class="col-12">
                <div class="chart-container">
                    <div id="timelineChart"></div>
                </div>
            </div>
        </div>

        <div class="db-eyebrow" style="margin-top: var(--db-space-3);">Coverage</div>
        <h3 style="margin: 0 0 var(--db-space-2);">Titles &amp; descriptions</h3>
        <div class="db-stat-grid" style="margin-bottom: var(--db-space-4);">
            <div class="db-stat">
                <div class="db-stat-label">Titles with Scheduled Positions</div>
                <div class="db-stat-value">{!! number_format($data['metrics']['pct_titles_pos'], 1) !!}%</div>
                <div class="db-stat-sub">{!! number_format($data['metrics']['cnt_titles_pos']) !!} titles</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Titles with Full Descriptions</div>
                <div class="db-stat-value">{!! number_format($data['metrics']['cnt_full_desc']) !!}</div>
                <div class="db-stat-sub">{!! number_format($data['metrics']['pct_full_desc'], 1) !!}%</div>
            </div>
            <div class="db-stat">
                <div class="db-stat-label">Positions w/ Described Titles</div>
                <div class="db-stat-value">{!! number_format($data['metrics']['cnt_positions_full_desc']) !!}</div>
                <div class="db-stat-sub">{!! number_format($data['metrics']['pct_positions_full_desc'], 1) !!}%</div>
            </div>
        </div>

        <div class="row mb-5">
            <!-- Left Column: Titles Missing Descriptions -->
            <div class="col-md-6">
                 <h4>Titles Missing Descriptions</h4>

                 <div class="db-table-wrap">
                    <div class="table-responsive">
                    <table id="noDescTable" class="db-table db-table-striped display table-hover" style="width:100%">
                        <thead>
                            <tr>
                                <th>Code</th>
                                <th>Title Description</th>
                                <th class="db-num">Pos.</th> <!-- Shortened header -->
                            </tr>
                        </thead>
                        <tbody>
                            @foreach($data['lists']['no_desc'] as $row)
                            <tr>
                                <td><a href="{!! route('title', ['id' => $row['Title Code']]) !!}">{!! $row['Title Code'] !!}</a></td>
                                <td>{!! $row['Title Description'] !!}</td>
                                <td class="db-num" data-order="{!! $row['Total Positions using this Title'] !!}">{!! number_format($row['Total Positions using this Title']) !!}</td>
                            </tr>
                            @endforeach
                        </tbody>
                    </table>
                    </div>
                </div>
            </div>

            <!-- Right Column: Oldest Titles -->
            <div class="col-md-6">
                <h4>Oldest Titles</h4>

                <div class="db-table-wrap">
                    <div class="table-responsive">
                    <table id="oldestTitlesTable" class="db-table db-table-striped display table-hover" style="width:100%">
                        <thead>
                            <tr>
                                <th>Code</th>
                                <th>Title Description</th>
                                <th>Effective Date</th>
                                <th class="db-num">Pos.</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach($data['top_lists']['oldest'] as $row)
                            <tr>
                                <td><a href="{!! route('title', ['id' => $row['Title Code']]) !!}">{!! $row['Title Code'] !!}</a></td>
                                <td>{!! $row['Title Description'] !!}</td>
                                <td data-order="{!! date('Ymd', strtotime($row['Effective Date'])) !!}">{!! $row['Effective Date'] !!}</td>
                                <td class="db-num" data-order="{!! $row['Total Positions using this Title'] !!}">{!! number_format($row['Total Positions using this Title']) !!}</td>
                            </tr>
                            @endforeach
                        </tbody>
                    </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- Agency Pie Chart -->
        <div class="row mb-5">
            <div class="col-12">
                <div class="chart-container">
                    <div id="agencyPieChart" style="height: 600px;"></div>
                </div>
            </div>
        </div>

        <div class="db-alert db-alert-info mt-4">
            <div class="db-alert-body">
                <i class="bi bi-info-circle"></i> This data comes from <a href="https://data.cityofnewyork.us/City-Government/NYC-Civil-Service-Titles/nzjr-3966" target="_blank" rel="nofollow">NYC Civil Service Titles</a>. <span style="color: var(--db-text-muted);"><i>Last updated {{ date('m/d/Y', strtotime('-1 day')) }}</i></span>
            </div>
        </div>
        </div>
    </div>
    @endif
	</div><!-- container -->
</div><!-- inner_container -->
@endsection
