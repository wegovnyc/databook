@extends('layout')


@section('head')
	<meta name="description" content="News and events from all of NYC's government agencies via the City Record" />
	<meta rel="canonical" href="{!! route('notices') !!}" />
    <!-- Plotly.js -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        .chart-container {
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
    </style>
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
{{--
	<script>
	
		
		$(document).ready(function() {
			loadStat();
		});
		function loadStat() {
			var uu = {!! json_encode($statUrls) !!}
			for (let sel in uu) {
				//$.get(uu[sel], function (resp) {
				fapireq(uu[sel], function (resp) {
					var v = resp['data'][0]['res'] ?? '-'
					$(sel).text(v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","))
				})
			}
		}
	</script>
--}}

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-11 organization_data">
					<div class="db-eyebrow">Notices</div>
					<h1 class="main_hdr">Notices</h1>
					<p>Notices are official government publications that serve as authoritative legal records of government actions. NYC government published them in “The City Record” with versions in print, and online as a <a href="https://www1.nyc.gov/site/dcas/about/city-record.page" target="_blank">PDF</a>, a <a href="https://a856-cityrecord.nyc.gov/" target="_blank">website</a> and <a href="https://data.cityofnewyork.us/City-Government/City-Record-Online/dg92-zbpx/data" target="_blank">open data</a>. Databook.NYC uses the open data version, which is updated daily.</p>
				</div>
				<div class="col-md-1 mt-2" id="org_summary">
				</div>
			</div>


			</div>
			
			<div class="row justify-content-center">
				<div class="col-md-6 organization_data">
					<h4 class="mb-3  p-0">News&nbsp;<a title="Copy News RSS feed link" onclick="copyLinkM(this, 'noticesRSSNews');"><i class="bi bi-rss share_icon_container" data-bs-toggle="popover" data-content="News RSS feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer; top:-3px;"></i></a></h4>
					<textarea id="noticesRSSNews" class="details">{!! route('noticesRSSNews') !!}</textarea>
	
					@foreach (array_slice($news ?? [], 0, 10) as $n)
					  <div class="db-card is-hoverable mb-1">
					    <a href="https://a856-cityrecord.nyc.gov/RequestDetail/{{ $n['RequestID'] }}" class="hoveronly" target="_blank">
						  <div class="card-body py-2">
							<div class="d-flex justify-content-between mb-1">
								<div><span class="db-badge db-badge-navy">{{ $n['SectionName'] }}</span></div>
								<small class="text-muted">{{ $n['StartDate'] }}</small>
							</div>
							<h5 class="card-title mb-1">{{ $n['TypeOfNoticeDescription'] }}</h5>
							<p class="card-text mb-1 small">{{ $n['ShortTitle'] }}</p>
							@if ($n['wegov-org-name'])
							  <p class="card-text mb-0 small text-muted">{{ $n['wegov-org-name'] }}</p>
							@endif
						  </div>
					    </a>
					  </div>
					@endforeach
					<div class="row justify-content-center">
						<div class="col-md-12 text-center">
							<a type="button" class="db-btn db-btn-outline" href="{{ route('noticesSection', ['section' => 'all']) }}">See All News</a>
						</div>
					</div>
					
				</div>
				
				<div class="col-md-6 organization_data">
					<h4 class="mb-3  p-0">Events&nbsp;<a title="Copy Events iCal feed link" onclick="copyLinkM(this, 'noticesIcalEvents');"><i class="bi bi-calendar-event share_icon_container" data-bs-toggle="popover" data-content="Events iCal feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer; top:-3px;"></i></a></h4>
					<textarea id="noticesIcalEvents" class="details">{!! route('noticesIcalEvents') !!}</textarea>
					@foreach ($events ?? [] as $e)
					  <div class="db-card is-hoverable mb-1">
					    <a href="https://a856-cityrecord.nyc.gov/RequestDetail/{{ $e['RequestID'] }}" class="hoveronly" target="_blank">
						  <div class="card-body py-2">
							<div class="d-flex justify-content-between mb-1">
								<div><span class="db-badge db-badge-navy">{{ $e['SectionName'] }}</span></div>
								<small class="text-muted">{{ $e['EventDate'] }}</small>
							</div>
							<h5 class="card-title mb-1">{{ $e['TypeOfNoticeDescription'] }}</h5>
							<p class="card-text mb-1 small">{{ $e['ShortTitle'] }}</p>
							@if ($e['wegov-org-name'])
							  <p class="card-text mb-0 small text-muted">{{ $e['wegov-org-name'] }}</p>
							@endif
						  </div>
					    </a>
					  </div>
					@endforeach
					<div class="row justify-content-center">
						<div class="col-md-12 text-center">
							<a type="button" class="db-btn db-btn-outline" href="{{ route('noticesSection', ['section' => 'events']) }}">See All Events</a>
						</div>
					</div>
				</div>
			</div>
			
			
			<div class="row justify-content-center mb-4">
				<div class="col-12">
					<div class="chart-container">
						<div id="noticesChart"></div>
					</div>
				</div>
			</div>
			
				
{{--
			<div class="row justify-content-center py-1">
				<div class="col-md-12 organization_data">
					<h4 class="mb-2 p-0">Auctions</h4>
					<p class="p-0">Get great deals and help the city raise funds by bidding on items New York City agencies put up for sale.</p>
				</div>
				@foreach (array_slice($auctions ?? [], 0, 3) as $a)
				  <div class="col-md-4 organization_data">
					  @php
						$img = json_decode(str_replace('""', '"', $a['Featured Image']), true);
						$img = $a['Featured Img Url'] ?? $img[0]['thumbnails']['large']['url'] ?? $img[0]['url'] ?? null;
					  @endphp
					<div class="card">
						<a href="{!! $a['URL'] !!}" target="_blank" class="hoveronly">
							@if ($img)
								<div style="height: 250px; overflow: hidden; display: block; margin: 20px; text-align: center;    background: #f0f0f0;">
									<img src="{{ $img }}" alt="{{ $a['Title'] }}" style="max-width: 100%; max-height: 100%;width:auto; margin: 0 auto;">
								</div>
							@endif
							<div class="card-body pt-0 text-center">
								<h6 class="card-title mb-2" style="color:#000;font-weight:bold">{{ $a['Title'] }}</h6>
								<p class="card-text mb-0" style="color:#000;">Time Left: {{ $a['Time Left'] }}<br/>Current Price: {{ $a['Current Price'] }}</p>
							</div>
						</a>
					</div>
				  </div>
				@endforeach
			</div>
			<div class="row justify-content-center">
				<div class="col-md-12 text-center">
					<p>* Bid is updated daily so the current price we display may no longer be accurate.</p>
					<a type="button" class="outline_btn mb-3" href="{{ route('auctions') }}">See All Auctions</a>
				</div>
			</div>
--}}
		</div>

		@if($dataset)
		<div class="col-md-12">
			<div class="bottom_lastupdate">
		@if ($dataset)
				<p class="lead"><img src="/img/info.png" alt=""> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank">{{ $dataset['Name'] ?? '' }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ $crolLastUpdated ?? explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span></p>
			</div>
		</div>
		@endif
		@endif
	</div>
	
@endsection


@section('scripts')
	<script>
		function changeToggle (e) {
			console.log($(e.target).next("label")[0].innerHTML)
			$('#change_district').html($(e.target).next("label")[0].innerHTML);
		}
		
		$('.clickable').click(function(e) {
			var url = $(this).attr('onclick_url');
			console.log(e, url)
			window.location.href = url;
			e.stopPropagation();
		})
		
		$('#toggle_boundries').click( function (e) {
			$(this).next('.dropdown-menu').toggleClass('show');
		})

		$(".filter_icon").click(function() {
			console.log($('.toolbar').is(':visible'))
			if(!$('.toolbar').is(':visible')) {
				$('.filter_icon').addClass('position_change');
			}else {
				$('.filter_icon').removeClass('position_change');
			}
			$(".toolbar").toggle();
		});
		
	    $(document).ready(function() {
			globStatView({!! json_encode($globStats) !!})
			
			// Notices Chart (Stacked Line)
			var stats = {!! json_encode($stats) !!};
            if (stats && stats.length > 0) {
                // 1. Get unique sections
                var sections = [...new Set(stats.map(i => i['SectionName']))];
                
                // 2. Generate last 30 days array (0 to 30)
                // User wants X axis = "number of days ago". 
                // Let's create an array [30, 29, ..., 0]
                var daysAgo = Array.from({length: 31}, (_, i) => 30 - i);
                
                // Helper to get date string for X days ago to match backend data
                function getDateString(daysAgo) {
                    var d = new Date();
                    d.setDate(d.getDate() - daysAgo);
					// Use local YYYY-MM-DD to match backend and avoid UTC offsets
					var year = d.getFullYear();
					var month = String(d.getMonth() + 1).padStart(2, '0');
					var day = String(d.getDate()).padStart(2, '0');
					return year + '-' + month + '-' + day;
                }
                
                // 3. Build Traces
                var traces = [];
                sections.forEach(function(section) {
                    var sectionData = stats.filter(i => i['SectionName'] === section);
                    var yValues = daysAgo.map(d => {
                         // Find matching record for this date
                         // Note: Backend StartDate format needs to match. 
                         // Assuming Backend returns 'YYYY-MM-DD'.
                         // We iterate days ago [30..0]. 
                         // For each day, we calculate the date string, and look for it in sectionData.
                         var dateStr = getDateString(d);
                         var record = sectionData.find(r => r['StartDate'] === dateStr);
                         return record ? parseInt(record['count']) : 0;
                    });

                    traces.push({
                        x: daysAgo, 
                        y: yValues,
                        name: section,
                        type: 'scatter',
                        mode: 'lines',
                        stackgroup: 'one'
                    });
                });

                Plotly.newPlot('noticesChart', traces, {
                    title: 'Notices by Type (Last 30 Days)',
                    xaxis: {title: 'Days Ago', automargin: true, autorange: 'reversed'}, // Reverse so 30 is left, 0 is right? Or standard: 0 left?
                    // "x axis being the number of days ago a notice ... was published"
                    // Usually time series: Left (Past) -> Right (Present).
                    // So Left=30 days ago, Right=0 days ago.
                    // If X is "Days Ago", values are 30, 29, ... 0.
                    // Plotly plots X numerically. 0, 1, ... 30.
                    // If we want Left=Past(30), Right=Present(0), we should set X axis to be reversed if X is "Days Ago".
                    // Or we plot X=[30, 29...0] and let Plotly handle it. Plotly usually puts smaller numbers left.
                    // If X=30 (Left), X=0 (Right), then X-axis needs to be reversed (range: [30, 0]).
                    
                    yaxis: {title: 'Number of Notices'},
                    margin: {t: 40, r: 20, l: 40, b: 40},
                    legend: {orientation: 'h', y: -0.2}
                }, {responsive: true});
            }
		})
	</script>
@endsection
