@extends('layout')


@section('head')
	<meta name="description" content="{{ $snippet }}" />
	<meta rel="canonical" href="{!! $canonicalUrl !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	@include('sub.orgheader', ['active' => 'about'])

	@php
		$w = ($org['twitter'] ?? null) || ($org['facebook'] ?? null) ? 4 : 6;
		$dw = 12 - $w;
	@endphp

	<div class="inner_container">	
		<div class="container py-2">
			<div class="row mb-5">
				<div class="col-md-{{ $dw }}">
					@if ($org['description'] == '')
						<h1 class="display-4">...</h1>
					@else
						<p class="lead mt-4">
							{!! nl2br($org['description']) !!}
						</p>
					@endif
					@if ($org['url'])
						<div class="mt-3">
							<a href="{!! $org['url'] !!}" class="db-btn db-btn-primary no-underline" target="_blank" rel="nofollow">
								<i class="bi bi-box-arrow-up-right"></i> Official source
							</a>
						</div>
					@endif

					@php
						// Greenbook-derived leadership + address (see api/enrich_agency.py).
						// Address prefers the WeGov seed, falls back to the derived value.
						// NOTE: precompute badge label/title in PHP — Blade won't compile an
						// @if glued to a preceding word char (e.g. "derived@if(...)").
						$headName    = trim($org['derived_head_name'] ?? '');
						$headTitle   = trim($org['derived_head_title'] ?? '');
						$headTierB   = ($org['derived_head_confidence'] ?? '') === 'B';
						$seedAddr    = trim($org['main_address'] ?? '');
						$addr        = $seedAddr !== '' ? $seedAddr : trim($org['derived_address'] ?? '');
						$addrDerived = $seedAddr === '' && trim($org['derived_address'] ?? '') !== '';
						$headBadge   = 'derived' . ($headTierB ? ' · verify' : '');
						$headBadgeTip = 'Derived from the NYC Greenbook' . ($headTierB ? ' — director-tier match, verify' : '');
					@endphp
					@if ($headName !== '' || $addr !== '')
						<div class="mt-4">
							@if ($headName !== '')
								<div class="mb-1">
									<i class="bi bi-person-badge text-muted"></i>
									<span class="fw-semibold">{{ $headName }}</span>@if($headTitle !== '')<span class="text-muted">, {{ $headTitle }}</span>@endif
									<span class="db-badge db-badge-neutral" style="font-size: .62em; vertical-align: middle;" title="{{ $headBadgeTip }}">{{ $headBadge }}</span>
								</div>
							@endif
							@if ($addr !== '')
								<div>
									<i class="bi bi-geo-alt text-muted"></i>
									<span>{{ $addr }}</span>
									@if($addrDerived)
										<span class="db-badge db-badge-neutral" style="font-size: .62em; vertical-align: middle;" title="Derived from the NYC Greenbook (no address in the WeGov seed)">derived</span>
									@endif
								</div>
							@endif
						</div>
					@endif

				</div>
				<div class="col-md-{{ $w }} mt-3" id="org_summary">
					<div class="db-card organization_summary">
						<div class="db-card-body">
							<div class="card-text">
								<table class="db-table stats-table" width="100%">
								<thead>
									<tr>
									<th scope="col">Summary</th>
									<th scope="col">
										<select style="width:100%;" class="filter" onchange="loadStats();" id="fin_stat_select">
											<option value="">Year</option>
											@for($i=date('Y') - 1; $i>=date('Y') - 3; $i--)
											{{--<option value="{{ $i }}" @if($i == date('Y') - 1) selected @endif>{{ $i }}</option>--}}
												<option value="{{ $i }}" @if($i == 2022) selected @endif>{{ $i }}</option>
											@endfor
										</select>
									</th>
									</tr>
								</thead>
								<tbody>
									<tr>
										<td scope="row">Headcount</td>
										<td id="summary_headcount" class="pl-3"></td>
									</tr>
									<tr>
										<td scope="row">Actual Spending</td>
										<td id="summary_as" class="pl-3"></td>
									</tr>
									<tr>
										<td scope="row">Additional Cost</td>
										<td id="summary_ac" class="pl-3"></td>
									</tr>
								</tbody>
								</table>
							</div>
						</div>
					</div>
				</div>
			</div>
			<div class="row mb-5">
				<div class="col-md-{{ $dw }}">
					<div class="notice_org">
						<h2 class="card-title mb-4">Job Opportunities</h2>
					</div>
					<div id="data_container" class="col float-left mb-4">
						<div class="table-responsive" style="overflow-x:visible;">
							<div class="filter_icon">
								<i class="bi bi-funnel-fill"></i>
							</div>
							<table id="jobTable" class="db-table display table-striped table-hover" style="width:100%;">
								<thead>
									<tr>
										{{-- @if ($details['detFlag'])
											<th></th>
										@endif --}}
										@foreach ($details['hdrs'] as $name)
											<th>{{ $name }}</th>
										@endforeach
									</tr>
								</thead>
							</table>
						</div>
					</div>
					<div class="text-center">
						<a href="{{ route('orgSection', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-'), 'section' => 'jobs']) }}"  class="db-btn db-btn-outline db-btn-sm no-underline" target="_blank">All Jobs</a>
					</div>
				</div>
				<div class="col-md-{{ $w }}">
					<div class="notice_org">
						<h2 class="card-title mb-4">Positions</h2>
					</div>
					<div class="col row px-0" id="spending_by_title">
						<div height="200" width="285" style="overflow: visible; display: inline-block; vertical-align: top;">
							<canvas id="titleSpendingChart" height="200" width="285" style="width:100%; height:200px;"></canvas>
						</div>
						<div height="200" width="400" style="overflow: visible; display: inline-block; vertical-align: top; max-width:480px;">
							<ul id="spending_by_title_legend" class="pie_legend">
							</ul>
						</div>
					</div>
					<div class="text-center">
						<a href="{{ route('orgSection', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-'), 'section' => 'positions']) }}" class="db-btn db-btn-outline db-btn-sm no-underline" target="_blank">All Positions</a>
					</div>
				</div>
			</div>
			<div class="row mb-4">
				@if(($org['twitter'] ?? null) || ($org['facebook'] ?? null))
					<div class="col-md-{{ $w }}" id="org_socials">
						<div class="notice_org">
							<h2 class="card-title mb-4">Social Media</h2>
							@if(($org['twitter'] ?? null) && ($org['facebook'] ?? null))
								<style>
									#org_socials .card-text  {overflow: auto;height: 545px; margin-bottom: 10px;}
									#org_socials .card-text iframe  {overflow: auto;height: 535px !important;border: 1px solid #e1e0e0 !important;}
								</style>
							@else
								<style>
									#org_socials .card-text  {overflow: auto;height: 600px;}
									#org_socials .card-text iframe  {overflow: auto;height: 590px !important;border: 1px solid #e1e0e0 !important;}
								</style>
							@endif


							<div class="accordion social_media" id="socAccordion">
							@if($org['twitter'] ?? null)
								<div>
									<div id="socHeadingOne">
										<button class="social_btn collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#socCollapseTwo" aria-expanded="false" aria-controls="socCollapseTwo">
											Twitter
										</button>
									</div>
									<div id="socCollapseOne" class="collapse show" aria-labelledby="socHeadingOne" data-parent="#socAccordion">
										<div class="card-text" id="tw_content">
											<a class="twitter-timeline" data-height="740" href="{{ $org['twitter'] }}">&nbsp;</a> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
										</div>
									</div>
								</div>
							@endif
							@if($org['facebook'] ?? null)
								<div>
									<div id="socHeadingTwo">
										<button class="social_btn" type="button" data-bs-toggle="collapse" data-bs-target="#socCollapseOne" aria-expanded="true" aria-controls="socCollapseOne">
											Facebook
										</button>
									</div>
									<div id="socCollapseTwo" class="collapse" aria-labelledby="socHeadingTwo" data-parent="#socAccordion">
										<div class="card-text" id="fb_content">
											<aside class="widget--facebook--container">
												<div class="widget-facebook">
													<iframe id="facebook_iframe" class="facebook_iframe"></iframe>
												</div>
											</aside>
											<style type="text/css">
												.widget--facebook--container {
													padding: 0px;
												}
												.widget-facebook .facebook_iframe {
													border: none;
												}
											</style>
											<script type="text/javascript">
												function setupFBframe(frame) {
													var container = frame.parentNode;

													var facebooklink = "{{ $org['facebook'] }}";

													var containerWidth = container.offsetWidth;
													var containerHeight = container.offsetHeight;

													var src =
													"https://www.facebook.com/plugins/page.php" +
													"?href="+facebooklink+
													"&tabs=timeline" +
													"&width=" +
													containerWidth +
													"&height=" +
													containerHeight +
													"&small_header=true" +
													"&adapt_container_width=true" +
													"&hide_cover=false" +
													"&hide_cta=true" +
													"&show_facepile=true" +
													"&appId";

													frame.width = containerWidth;
													frame.height = containerHeight;
													frame.src = src;
												}

												/* begin Document Ready                                             
												############################################ */

												document.addEventListener('DOMContentLoaded', function() {
													var facebookIframe = document.querySelector('#facebook_iframe');
													setupFBframe(facebookIframe);
													
													/* begin Window Resize                                            
													############################################ */
													
													// Why resizeThrottler? See more : https://developer.mozilla.org/ru/docs/Web/Events/resize
													(function() {
													window.addEventListener("resize", resizeThrottler, false);

													var resizeTimeout;

													function resizeThrottler() {
														if (!resizeTimeout) {
														resizeTimeout = setTimeout(function() {
															resizeTimeout = null;
															actualResizeHandler();
														}, 66);
														}
													}

													function actualResizeHandler() {
														document.querySelector('#facebook_iframe').removeAttribute('src');
														setupFBframe(facebookIframe);
													}
													})();
													/* end Window Resize
													############################################ */
												});
											</script>
										</div>
									</div>
								</div>
							@endif
							</div>
							
						</div>
					</div>
				@endif


				<div class="col-md-{{ $w }}" id="org_news">
					<div class="notice_org">
						<h2 class="card-title mb-4">
							Notices
						</h2>
						<div class="accordion social_media" id="newsAccordion">
							<div>
								<div id="newsHeadingOne">
									<button class="social_btn" type="button" data-bs-toggle="collapse" data-bs-target="#newsCollapseOne" aria-expanded="true" aria-controls="newsCollapseOne">
										Event Notices&nbsp;<a title="Copy Agency Events iCal feed link" onclick="copyLinkM(this);"><i class="bi bi-calendar-event share_icon_container" data-bs-toggle="popover" data-content="Agency Events iCal feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer; top:-2px;"></i></a>
									</button>
								</div>
								<div id="newsCollapseOne" class="collapse show" aria-labelledby="newsHeadingOne" data-parent="#newsAccordion">
									<div class="card-text" id="events">
										<img src="/ical/images/ajax-loader.gif" class="my-5 ml-5" />
										<div class="card-text" style="display:none;">
											<div id="calendar">
											</div>
											<img id="loading-calendar" src="/ical/images/ajax-loader.gif"/>
										</div>
										<div class="text-center col-md-12" style="display:none;">
											<a class="outline_btn" href="{{ route('orgSection', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-'), 'section' => 'events']) }}">See More Events</a>
										</div>
									</div>
								</div>
							</div>
							<div>
								<div id="newsHeadingTwo">
									<button class="social_btn collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#newsCollapseTwo" aria-expanded="false" aria-controls="newsCollapseTwo">
										Other Notices&nbsp;<a title="Copy Agency News RSS feed link" onclick="copyLinkM(this, 'orgRSSNews');"><i class="bi bi-rss share_icon_container" data-bs-toggle="popover" data-content="Agency News RSS feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer; top:-2px;"></i></a>
									</button>
								</div>
								<div id="newsCollapseTwo" class="collapse" aria-labelledby="newsHeadingTwo" data-parent="#newsAccordion">
									<div class="card-text" id="notices">
										<img src="/ical/images/ajax-loader.gif" class="my-5 ml-5" />
										
										<div class="card-text" style="display:none;">
										</div>
										<div class="text-center col-md-12" style="display:none;">
											<a class="outline_btn" href="{{ route('orgSection', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-'), 'section' => 'notices']) }}">See More News</a>
										</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>


				<div class="col-md-{{ $w }}" id="org_charts">
					<div class="notice_org">
						<h2 class="card-title mb-4">Trends</h2>
						<h5 class="mt-0 mb-0" style="margin-top:32px!important; font-size:16px;"><b>Employees</b></h5>
						<canvas id="chart_headcount" height="190" style="width:100%; height:190px; display:none;"></canvas>
						<h5 class="mt-3 mb-0" style="font-size:16px;"><b>Spending</b></h5>
						<canvas id="chart_as" height="190" style="width:100%; height:190px; display:none;"></canvas>
						<h5 class="mt-3 mb-0" style="font-size:16px;"><b>Capital Projects</b></h5>
						<canvas id="chart_prj" height="195" style="width:100%; height:195px; display:none;"></canvas>
					</div>
				</div>
				
			</div>
			
			<div class="row mb-4">

				<div id="data_container_accordion" class="col-12 accordion">
				
					<div class="accordion social_media" id="accordionThree">
						<div>
							<div id="headingThree">
								<button class="social_btn" type="button" data-bs-toggle="collapse" data-bs-target="#collapseThree" aria-expanded="true" aria-controls="collapseThree">
									This agency’s profile has <span id="total_records"></span> records from <span id="total_datasets"></span> datasets. Click here to learn more.
								</button>
							</div>
							<div id="collapseThree" class="collapse hide" aria-labelledby="socHeadingOne" data-parent="#accordionThree">
								<div class="card-text table-responsive">
									<table id="myTable" class="db-table display table-hover table-borderless" style="width:100%;">
									</table>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
	
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/rowgroup/1.1.4/js/dataTables.rowGroup.min.js"></script>
	
	<!-- calendar -->
	
	<!-- Moment -->
	<script src="//cdnjs.cloudflare.com/ajax/libs/moment.js/2.12.0/moment.min.js"></script>
	<script src="/ical/js/moment-timezone-with-data.min.js"></script>
	<!-- Fullcalendar -->
	<!--<script src="https://cdnjs.cloudflare.com/ajax/libs/fullcalendar/3.8.2/fullcalendar.js"></script>-->
	<script src="/ical/js/fullcalendar.js"></script>
	<script src="https://cdnjs.cloudflare.com/ajax/libs/fullcalendar/3.8.2/locale-all.js"></script>
	<link href="https://cdnjs.cloudflare.com/ajax/libs/fullcalendar/3.8.2/fullcalendar.min.css" rel="stylesheet" type="text/css">
	<link href="https://cdnjs.cloudflare.com/ajax/libs/fullcalendar/3.8.2/fullcalendar.print.min.css" rel="stylesheet" type="text/css" media="print">
	<!-- qtip2 -->
	<script src="//cdn.jsdelivr.net/qtip2/3.0.3/jquery.qtip.min.js"></script>
	<link href="//cdn.jsdelivr.net/qtip2/3.0.3/jquery.qtip.min.css" rel="stylesheet" type="text/css">
	<!-- PNotify & Animate-->
	<script src="/ical/js/pnotify.min.js"></script>
	<link href="/ical/css/pnotify.min.css" rel="stylesheet" type="text/css">
	<link href="/ical/css/animate.css" rel="stylesheet" type="text/css">
	<!-- Mozilla-comm/ical -->
	<script src="/ical/js/ical.js"></script>
	<!-- icalendar2fullcalendar -->
	<script src="/ical/js/ical_events.js"></script>
	<script src="/ical/js/ical_fullcalendar.js"></script>
	<!-- app  -->
	<script src="/ical/js/app.js"></script>
	<link href="/ical/css/app.css" rel="stylesheet" type="text/css">
	<link rel="canonical" href="https://getbootstrap.com/docs/4.6/components/modal/">
	<!-- /calendar -->
	
	<!-- /Chart.js -->
	<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.8.0/chart.min.js" integrity="sha512-sW/w8s4RWTdFFSduOTGtk4isV1+190E/GghVffMA9XczdJ2MDzSzLEubKAs5h0wzgSJOQTRYyaz73L3d6RtJSg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script>if(window.DBChart&&window.Chart)DBChart.apply(window.Chart);</script>
	<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.0.0"></script>

	<style>
		#jobTable_filter.dataTables_filter label{display: flex;align-items: center;}
	</style>

	<script>
		$(document).ready(function() {
			
			datatable = $('#jobTable').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $url !!}", cb);
			    },
				"lengthChange": false,
				pageLength : 5,
				order: [[6, 'desc']],			
				buttons: [{
                    extend: 'colvis',
                    "className": 'btn_eyeicon',
                    columnText: function ( dt, idx, title ) {
                        return (idx+1)+': '+(title ? title : 'details');
                    }
                }],
				deferRender: true,
				dom: '<"toolbar container-flex"<"row">>Blfrtip',
				columns: [
                    
                    @foreach ($details['flds'] as $i=>$f)
                        {
							data: {!! $f !!},
							@if ($details['visible'][$i])
								visible: true
							@else
								visible: false
							@endif
                        },
                    @endforeach
					{data: null, visible: false}
                ],

				@if (($details['filters'] ?? null) || ($details['pubdate_filter'] ?? null))
					initComplete: function () {
						@if ($details['filters'])
							this.api().columns([{{ $details['fltsCols'] }}]).every(function (c,a,i) {
								var delim = {!! json_encode($details['fltDelim']) !!};
								var column = this;
								var select = $('<select class="filter" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="jobTable"><option value="" selected>- ' + $(column.header()).text() + ' -</option></select>')
									.appendTo($("div.toolbar .row"))
									.on('change', function () {
										var val = $(this).val()
										column
											.search(val ? val : '', false, false)
											.draw();
									});
								select.wrap('<div class="drop_dowm_select col"></div>');
								$('div.toolbar').insertAfter('#jobTable_filter');

								var tt = []
								dd = column.data()

								column.data().each(function (d, j) {
									d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
									if (c in delim && typeof d == 'string') {
										d.split(delim[c]).forEach(function (v, k) {
											tt.push(v)
										})
									}
									else
										tt.push(d)
								})
								tt = [...new Set(tt)]

								tt.sort().forEach(function (d, j) {
									select.append('<option value="'+d+'">'+d+'</option>')
								});
							});

							@foreach ($details['filters'] as $i=>$v)
								@if ($v)
									setTimeout(function(){
										$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
									}, 500 + 1000 * {{ $i }});
								@endif
							@endforeach
						@endif
						
						@if ($details['pubdate_filter'] ?? null)
							this.api().columns([{{ array_keys($details['pubdate_filter'])[0] }}]).every(function (c,a,i) {
								var column = this;
								var select = $('<select class="filter" style="width:100%;" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="jobTable"></select>')
									.appendTo($("#pub_date_filter"))
									.on('change', function () {
										var val = $(this).val()
										column
											.search(val ? val : '', false, false)
											.draw();
										pubDateFilterChange();
									});
								select.wrap('<div class="drop_dowm_select"></div>');

								var tt = []
								dd = column.data()

								column.data().each(function (d, j) {
									d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
									tt.push(d)
								})
								tt = [...new Set(tt)]

								//tt.sort().forEach(function (d, j) {
								sortUsDatesList(tt).forEach(function (d, j) {
									select.append('<option value="'+d+'">'+d+'</option>')
								});
							});
							
							setTimeout(function(){
									$('#filter-{{ array_keys($details["pubdate_filter"])[0] }}').find('{{ array_values($details["pubdate_filter"])[0] }}').prop('selected',true).trigger('change')
								}, 100);
						@endif
						

						@if ($details['script'] ?? null)
							{!! $details['script'] !!}
						@endif
					}
				@endif
			});
			// @if ($details['detFlag'])
            //             {
            //                 "className": 'details-control',
            //                 "orderable": false,
            //                 "data":  null,
            //                 "defaultContent": ''
            //             },
            //         @endif

			$('#filter-1').find('[value*="20190619"]').prop('selected',true).trigger('change');

			$('a.toggle-vis').on('click', function (e) {
				e.preventDefault();
				var column = datatable.column($(this).attr('data-column'));
				column.visible(!column.visible());
			});

			$('#jobTable tbody').on('click', 'td.details-control', function () {
				var tr = $(this).closest('tr');
				var row = datatable.row(tr);

				if (row.child.isShown()) {
					row.child.hide();
					tr.removeClass('shown');
                    tr.next('tr').removeClass('child-row');
				}
				else {
					row.child(details(row.data())).show();
					tr.addClass('shown');
                    tr.next('tr').addClass('child-row');
				}
			});

			// $('#jobTable_length label').html($('#jobTable_length label').html().replace(' entries', ''));
			
			setTimeout(function(){
				initPopovers();
			}, 1000);
		});
	</script>
	
	<script>
		function pubDateFilterChange() {}

		function pie_labels_off() {
			$('.pie_legend li').removeClass('pie_label_h')
		}

		function pie_label_on(i, sel) {
			pie_labels_off()
			$(`${sel} .pie_legend li[idx=${i}]`).addClass('pie_label_h')
		}

		function pie_sectors_off(chart) {
			chart.setActiveElements([{datasetIndex: 1, index: 0}])
			chart.update()
		}

		function pie_sector_on(chart, i) {
			pie_sectors_off(chart)
			var dd = [{datasetIndex: 0, index: parseInt(i)}]
			res = chart.setActiveElements(dd);
			chart.update()
		}

		var config5 = {
		  type: 'pie',
		  data: {
			  labels: [],
			  datasets: [{
				label: 'spending_by_title',
				data: [],
				fill: false,
				backgroundColor: (window.DBChart ? DBChart.palette.concat(DBChart.palette, DBChart.palette) : ['#162e51']),
				borderColor: 'rgba(0, 0, 0, 0.2)',
				hoverBorderColor: 'rgba(0, 0, 0, 0.7)',
				borderWidth: 1,
				hoverOffset: 3,
				datalabels: {
				  color: 'rgba(0, 0, 0, 0.8)',
				  align: 'center',
				  anchor: 'end',
				  //display: 'auto',
				  clip: false,
				  font: {
					  size: 12,
				  }
				}
			  }]
			},
			options: {
				layout: {
					autoPadding: true,
					padding: 5,
				},
				responsive: false,
				radius: '96%',
				showAllTooltips: true,
				onHover: function(evt, elements, chart) {
					if (elements.length) {
						pie_label_on(elements[0].index, '#spending_by_title')
					} else {
						pie_labels_off()
					}
				},
				plugins: {
				  legend: {
					display: false,
				  },
				  tooltip: {
					enabled: false,
				  }

				},
			}
		}


		$(document).ready(function() {

			var canvas5 = document.getElementById("titleSpendingChart");
			window.chart5 = new Chart(canvas5, config5)

			// $.ajax({
			// 	url: '{{ $positionDataUrl }}',
			// 	success: function(response) {
			// 		console.log(response)
			// 	},
			// 	error: function(error) {
			// 		console.log(error)
			// 	}
			// })
			

			setTimeout(function(){
				graphsUpdate()
			}, 1000);
			// datatable.on('draw.dt', function () {
			// 	setTimeout(function(){
			// 		graphsUpdate()
			// 	}, 1000);
			// })

		})


		function graphsUpdate() {
			// const vv = datatable.rows('', {search: 'applied'}).data()
			fapireq('{!! $positionDataUrl !!}', function (data) {
				const vv = data.data;
				var tmprr = {'by_titlecode': {}};

				if (vv.length > 0 && vv[0]['title'] !== undefined) {
					vv.forEach(function(b) {
						tmprr['by_titlecode'][b['title']] = parseFloat(b['sum']);
					});
				} else {
					tmprr = vv.reduce( function (a, b) {
						s = parseInt(b['ANNUAL RATE'])
						a['by_titlecode'][b['TITLE CODE NAME']] =
							(a['by_titlecode'][b['TITLE CODE NAME']] ?? null)
								? a['by_titlecode'][b['TITLE CODE NAME']] + s
								: s
						return a
					}, {'by_titlecode': {}})
				}
	
				var rr = {}
				for (var k in tmprr) {
					let sortable = []
					for (var f in tmprr[k]) {
						sortable.push([f, tmprr[k][f]]);
					}
					rr[k] = sortable.sort((a,b) => b[1] - a[1])
				}
	
				pieUpd(window.chart5, config5, '#spending_by_title', rr['by_titlecode'])
			});

		}


		function pieUpd(chart, conf, sel, dd) {
			$(sel + ' canvas').attr('width', 280)
			var s = 0
			if (dd.length == 0) {
				$(sel + ' .pie_legend').replaceWith('<p class="my-4 mx-3">No Positions to Display</p>')
				return
			}
			conf.data.labels = []
			conf.data.datasets[0].data = []
			$(sel + ' .pie_legend').html('')
			dd.forEach(function (d, i, vv) {
				conf.data.labels.push(d[0])
				conf.data.datasets[0].data.push(d[1])
				s += d[1]
			})
			conf.data.labels.forEach(function (l, i, ll) {
				if (i <= 11) {
					var perc = (conf.data.datasets[0].data[i] / s * 100).toFixed(1)
					$(`<li idx="${i}" class="cut-text"><i class="bi bi-square-fill" style="color: ${conf.data.datasets[0].backgroundColor[i]};"></i>&nbsp;&nbsp;${l}: ${toFin(conf.data.datasets[0].data[i])} (${perc} %)</li>`).appendTo(sel + ' .pie_legend')
				}
			})
			if (conf.data.labels.length > 11) {
				$('<li>...</li>').appendTo(sel + ' .pie_legend')
			}
			chart.update()

			$(sel + ' .pie_legend li').mouseover(function (evt) {
				var i = $(this).attr('idx')
				pie_sectors_off(chart)
				pie_sector_on(chart, i)
			}).mouseout(function (evt) {
				var i = $(this).attr('idx')
				pie_sectors_off(chart)
			})

		}
	</script>



	<script>
		var datasets = {!! json_encode($datasets) !!}
		var datatable = null


		var config1 = {
			type: 'line',
			data: {
				labels: [],
				datasets: [{
					label: 'Headcount',
					data: [],
					fill: false,
					borderColor: (window.DBChart ? DBChart.navy : '#1f5673'),
					borderWidth: 2,
					pointBackgroundColor: 'transparent',
					pointBorderColor: '#CCCCCC',
					pointBorderWidth: 3,
					pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
					pointHoverBorderWidth: 6,
					tension: 0.1,
					datalabels: {display: false},
				}]
			},
			options: {
				responsive: false,
			  elements: { 
				point: {
				  radius: 4,
				  hitRadius: 3,
				  hoverRadius: 3
				} 
			  },
			  plugins: {
				  legend: {
					display: true,
					position: 'top',
					align: 'end',
					labels: {boxHeight: 2},
					usePointStyle: true,
				  },
				  tooltip: {
					backgroundColor: 'rgba(255, 255, 255, 0.9)',
					сolor: 'black',
					displayColors: false,
					bodyFontSize: 14,
					callbacks: {
					  label: function(tooltipItems, data) { 
						return tooltipItems.formattedValue;
					  },
					  title: function(tooltipItems, data) { 
						return '';
					  },
					  labelTextColor: function(context) {
						return '#444';
					  }
					}
				  },
			  },
			  scales: {
				x: {
				  display: true,
				  grid: {display: false},
				},
				y: {
				  display: true,
				  position: 'left',
				  grid: {display: false},
				  beginAtZero: false,
				  ticks: {
					callback: function(value, index, ticks) {
						return Chart.Ticks.formatters.numeric.apply(this, [value, index, ticks]);
					}
				  }
				}
			  }
			},
		};

		var config2 = {
			type: 'line',
			data: {
				labels: [],
				datasets: [{
					label: 'Actual Spending',
					data: [],
					fill: false,
					borderColor: (window.DBChart ? DBChart.accent : '#759FBC'),
					borderWidth: 2,
					pointBackgroundColor: 'transparent',
					pointBorderColor: '#CCCCCC',
					pointBorderWidth: 3,
					pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
					pointHoverBorderWidth: 6,
					tension: 0.1,
					datalabels: {display: false},
				}]
			},
			options: {
				responsive: false,
			  elements: { 
				point: {
				  radius: 4,
				  hitRadius: 3,
				  hoverRadius: 3
				} 
			  },
			  plugins: {
				  legend: {
					display: true,
					position: 'top',
					align: 'end',
					labels: {boxHeight: 2},
					usePointStyle: true,
				  },
				  tooltip: {
					backgroundColor: 'rgba(255, 255, 255, 0.9)',
					сolor: 'black',
					displayColors: false,
					bodyFontSize: 14,
					callbacks: {
					  label: function(tooltipItems, data) { 
						return '$' + tooltipItems.formattedValue;
					  },
					  title: function(tooltipItems, data) { 
						return '';
					  },
					  labelTextColor: function(context) {
						return '#444';
					  }
					}
				  },
			  },
			  scales: {
				x: {
				  display: true,
				  grid: {display: false},
				},
				y: {
				  display: true,
				  position: 'left',
				  grid: {display: false},
				  beginAtZero: false,
				  ticks: {
					callback: function(value, index, ticks) {
						return '$' + Chart.Ticks.formatters.numeric.apply(this, [value, index, ticks]);
					}
				  }
				}
			  }
			},
		};

		var config3 = {
			type: 'line',
			data: {
				labels: [],
				datasets: [{
						label: 'Current Budget',
						data: [],
						fill: false,
						borderColor: (window.DBChart ? DBChart.navy : '#90C3C8'),
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
					},
					{
						label: 'Amount Over Budget',
						data: [],
						fill: false,
						borderColor: (window.DBChart ? DBChart.accent : '#B9B8D3'),
						borderWidth: 2,
						pointBackgroundColor: 'transparent',
						pointBorderColor: '#CCCCCC',
						pointBorderWidth: 3,
						pointHoverBorderColor: 'rgba(0, 0, 0, 0.8)',
						pointHoverBorderWidth: 6,
						tension: 0.1,
						datalabels: {display: false},
					}
				]
			},
			options: {
				responsive: false,
			  elements: { 
				point: {
				  radius: 4,
				  hitRadius: 3,
				  hoverRadius: 3
				} 
			  },
			  plugins: {
				  legend: {
					display: true,
					position: 'top',
					align: 'end',
					labels: {boxHeight: 2},
					usePointStyle: true,
				  },
				  tooltip: {
					backgroundColor: 'rgba(255, 255, 255, 0.9)',
					сolor: 'black',
					displayColors: false,
					bodyFontSize: 14,
					callbacks: {
					  label: function(tooltipItems, data) { 
						return '$' + tooltipItems.formattedValue;
					  },
					  title: function(tooltipItems, data) { 
						return '';
					  },
					  labelTextColor: function(context) {
						return '#444';
					  }
					}
				  },
			  },
			  scales: {
				x: {
				  display: true,
				  grid: {display: false},
				},
				y: {
				  display: true,
				  position: 'left',
				  //grid: {display: true},
				  beginAtZero: true,
				  ticks: {
					callback: function(value, index, ticks) {
						return '$' + Chart.Ticks.formatters.numeric.apply(this, [value, index, ticks]);
					}
				  },
				  grid: {
					color: 'rgba(0, 0, 0, 0)',
					lineWidth: 1,
					display: true,
					drawBorder: true,
					zeroLineColor: 'rgba(0, 0, 0, 0.5)',
					zeroLineWidth: 1,
				  },
				},
			  }
			},
		};


		function loadTableStat(dsName, url) {
			var datatable = $('#myTable').DataTable();
			fapireq(url, function (resp) {
				if (resp['data'][0]['count']) {
					$('#stats_'+dsName).text(resp['data'][0]['count'])
					$('#total_records').text(Number($('#total_records').text()) + resp['data'][0]['count'])
					$('#total_datasets').text(Number($('#total_datasets').text()) + 1)
				} else {
					datasets.forEach(function (d, i) {
						if (d[5].indexOf('stats_'+dsName) != -1) {
							datasets.splice(i, 1)
							datatable.row(i).remove()
                            datatable.draw();
						}
					})
				}
			})

		}
		
		var cachedStats = {}
		function loadStats() {
			var uu = {!! json_encode($finStatUrls) !!}
			var year = $('#fin_stat_select option:selected').val()
			for (let k in uu) {
				if (cachedStats[k] ?? null) {
					drawStats(k, year, cachedStats[k])
				} else {
					fapireq(uu[k], function (resp) {
						cachedStats[k] = resp['data']
						drawStats(k, year, cachedStats[k])
						if (k == 'headcount')
							drawHeadcountChart(cachedStats[k])
						if (k == 'as')
							drawSpendingsChart(cachedStats[k])
						if (k == 'prj')
							drawPrjstatChart(cachedStats[k])
					})
				}
			}
		}
		
		function drawStats(k, y, data) {
			var v = '-'
			for (let i in data) {
				//console.log(k, i, data, data[i], data[i]['v'])
				if (data[i]['year'] == y) {					
					v = data[i]['v']
					currency = k == 'headcount' ? '' : '$'
					v = v != '-' ? currency + intWithCommas(v) : v
				}
				
			}
			$('#summary_'+k).text(v)
		}

		function drawHeadcountChart(data) {
			$('#chart_headcount').show();
			var canvas1 = document.getElementById("chart_headcount");
			window.chart1 = new Chart(canvas1, config1);
			for (let i in data) {
				window.chart1.data.labels.push(data[i]['year'])
				window.chart1.data.datasets[0].data.push(data[i]['v'])
			}
			window.chart1.update()
		}

		function drawSpendingsChart(data) {
			$('#chart_as').show();
			var canvas2 = document.getElementById("chart_as");
			window.chart2 = new Chart(canvas2, config2);
			for (let i in data) {
				window.chart2.data.labels.push(data[i]['year'])
				window.chart2.data.datasets[0].data.push(data[i]['v'])
			}
			window.chart2.update()
		}
		
		function drawPrjstatChart(data) {
			$('#chart_prj').show();
			var canvas3 = document.getElementById("chart_prj");
			window.chart3 = new Chart(canvas3, config3);
			for (let i in data) {
				window.chart3.data.labels.push(toUsDateNowrap(data[i]['pub_date']))
				window.chart3.data.datasets[0].data.push(data[i]['budg_curr'])
				window.chart3.data.datasets[1].data.push(data[i]['budg_diff'])
			}
			window.chart3.update()
		}
		
	</script>
	
			
	<script>
	
		$(document).ready(function () {
			loadStats();
			
			// Load procurement stats
			fapireq('{!! $procurementSummaryUrl !!}', function(data) {
				if (data) {
					$('#procurement_contracts').text(data.contracts_count ? data.contracts_count.toLocaleString() : '0');
					$('#procurement_awarded').text(data.total_awarded ? '$' + (data.total_awarded / 1000000).toFixed(1) + 'M' : '$0');
					$('#procurement_active').text(data.active_contracts ? data.active_contracts.toLocaleString() : '0');
					$('#procurement_solicitations').text(data.solicitations_count ? data.solicitations_count.toLocaleString() : '0');
				}
			});
			

			datatable = $('#myTable').DataTable({
				data: datasets,
				paging: false,
				columns: [
					{ title: "Name" },
					{ title: "Label" },
					{ title: "Description" },
					{ 
						title: "Section", 
						visible: false 
					},
					{ title: "Last Updated" },
					{ title: "Agency Records" }
				],
				order: [],
				rowGroup: { dataSrc: 3 },
				dom: 'rtp',
				initComplete: function () {
					@foreach(array_keys($slist) as $i=>$dsName)	
						@if($i > 0)
							loadTableStat(
								"{{ str_replace('/', '_', $dsName) }}", 
								@if ($dsName == 'notices/events')
									"{!! $tableStatUrls['noticesEvents'] !!}"
								@elseif ($allDS[$dsName]['sectionTitle'] ?? null)
									"{!! str_replace('sectionTitle', $allDS[$dsName]['sectionTitle'], $tableStatUrls['notices']) !!}"
								@else
									"{!! str_replace('tablename', $allDS[$dsName]['table'], $tableStatUrls['reg']) !!}"
								@endif
							);
						@endif
					@endforeach
				}
			});
			
			set_calendar("{!! route('orgIcalEvents', ['id' => $id]) !!}");

			fapireq('{!! $newsUrl !!}', function (data) {
				$('#notices img').remove()
				if ('data' in data && data.data.length) {
					data.data.forEach( function (n, i, arr) {
						var html = `
								  <div class="card mb-1">
									<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${n['RequestID']}" class="hoveronly" target="_blank" rel="nofollow">
									  <div class="card-body py-2">
										<h5 class="card-title mb-0">${n['TypeOfNoticeDescription']} <small>${n['StartDate']}</small></h5>
										<p class="mb-0">${n['ShortTitle']}</p>
										${ n['wegov-org-name'] ? '<span class="badge bg-primary" >' + n['SectionName'] + '</span>' : '' }
									  </div>
									</a>
								  </div>
								`
						$(html).appendTo('#notices .card-text')
					})
					$('#notices div').show()
				} else
					$('<div class="text-center col-md-12 mt-5">No upcoming notices</div>').appendTo('#notices')
			})

			fapireq('{!! $eventsUrl !!}', function (data) {
				$('#events img').remove()
				if ('data' in data && data.data.length) {
					$('#events div').show()
				} else
					$('<div class="text-center col-md-12 mt-5">No upcoming events</div>').appendTo('#events')
			});
		})
	</script>
	<script type="application/ld+json">{!! json_encode($schema) !!}</script>
	

	
@endsection
