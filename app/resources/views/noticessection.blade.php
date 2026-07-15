@extends('layout')


@section('head')
	<meta name="description" content="News and events from all of NYC's government agencies via the City Record" />
	<meta rel="canonical" href="{!! route('notices') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	<div class="inner_container">
		<div id="pos-header" class="org-header">
			<div class="row mx-2">
				<div class="col-md-9 org_detailheader">
					<div class="db-eyebrow">Notices</div>
					<h1 class="main_hdr db-profile-title">{{ $slist[$section] }}
						@if ($section == 'events')
							&nbsp;<a title="Copy Events iCal feed link" onclick="copyLinkM(this, 'events-ical-link');"><i class="bi bi-calendar-event share_icon_container" data-bs-toggle="popover" data-content="Events iCal feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer; top:-3px;"></i></a>
							<textarea id="events-ical-link" class="details">{!! route('noticesIcalEvents') !!}</textarea>
						@endif
						@if ($section == 'news')
							&nbsp;<a title="Copy News RSS feed link" onclick="copyLinkM(this, 'news-rss-link');"><i class="bi bi-rss share_icon_container" data-bs-toggle="popover" data-content="News RSS feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer; top:-3px;"></i></a>
							<textarea id="news-rss-link" class="details">{!! route('noticesRSSNews') !!}</textarea>
						@endif
					</h1>
					<p>{!! $details['description'] !!}</p>
				</div>
				<div class="col-md-3 mt-2" id="org_summary">
					<table class="table-sm stats-table" width="100%">
					<thead>
						<tr>
						<th scope="col" width="50%" class="text-center px-0" data-content="See the project info published on specific dates.">Year&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
						<th scope="col" width="50%" id="pub_date_filter"></th>
						</tr>
					</thead>
					</table>
				</div>
			</div>
		</div>

		<div class="db-tabs-wrap is-scroll org_headermenu mb-4">
			<nav class="db-tabs submenu_org" aria-label="Notices sections">
				@foreach ($menu as $h=>$sect)
					@if (is_string($sect))
						<a class="db-tab @if ($section == $sect) is-active @endif" href="{{ route('noticesSection', ['section' => $sect]) }}">{{ $slist[$sect] }}</a>
					@else
						<div class="db-tab-dd">
							<button type="button" class="db-tab @if (($activeDropDown ?? '') == $h) is-active @endif" data-dd aria-haspopup="true" aria-expanded="false" aria-controls="noticedd-{{ $loop->index }}">
								{{ $h }} <i class="bi bi-chevron-down db-caret"></i>
							</button>
							<div class="db-tab-menu" id="noticedd-{{ $loop->index }}" role="menu">
								@foreach ($sect as $subsect)
									<a role="menuitem" href="{{ route('noticesSection', ['section' => $subsect]) }}">{{ $slist[$subsect] }}</a>
								@endforeach
							</div>
						</div>
					@endif
				@endforeach
			</nav>
		</div>
	</div>



	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

	<script>
		function details(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  @foreach ((array)$details['details'] as $h=>$f)
				(d["{{ $f }}"] ? '<tr><td>{{ $h }}:</td><td>'+d["{{ $f }}"]+'</td></tr>' : '') +
			  @endforeach
			'</table>';
		}
		var datatable = null
		var dataurl = '{!! $url !!}'
		var year = null
		
		$(document).ready(function() {
			/* custom pub_date filter on top-right */
			//$.get("{!! $dates_req_url !!}", function (resp) {
			fapireq("{!! $dates_req_url !!}", function (resp) {
				var select = $('<select class="filter mt-1" style="width:100%;" id="filter-1" name="filter-1" aria-controls="myTable"><option value="" selected>- Publication Date -</option></select>')
					.appendTo($("#pub_date_filter"))
					.on('change', function () {
						year = $(this).val()
						$('.loading').show()
						//datatable.ajax.url(dataurl.replace('pubdate', val)).load(function () {
						datatable.ajax.reload(function () {
							$('.loading').hide()
						});
					});
				select.wrap('<div class="drop_dowm_select"></div>');
				resp['data'].forEach(function (d, j) {
					select.append(`<option value="${d['yy']}" ${ j == 0 ? 'selected' : ''}>${d['yy']}</option>`)
				});

				year = resp['data'][0]['yy']
				
				datatable = $('#myTable').DataTable({
					ajax: function (url, cb) {
						fapireq(dataurl.replace('pubdate', year), cb);
					},
						
					/*	
					ajax: {
						url: dataurl.replace('pubdate', resp['data'][0]['yy']),
						dataSrc: 'rows'
					},
					*/
					buttons: [{
						extend: 'colvis',
						className: 'btn_eyeicon',
						columnText: function ( dt, idx, title ) {
							return (idx+1)+': '+(title ? title : 'details');
						}
					}],
					deferRender: true,
					dom: '<"toolbar container-flex"<"row">>Blfrtip',
					columns: [
						@if ($details['detFlag'])
							{
								"className": 'details-control',
								"orderable": false,
								"data":  null,
								"defaultContent": ''
							},
						@endif
						@foreach ($details['flds'] as $i=>$f)
							@if ($i > 0)
								,
							@endif
							{
							data: {!! $f !!},
							@if ($details['visible'][$i])
								visible: true
							@else
								visible: false
							@endif
							}
						@endforeach
					],

					@if ($details['filters'])
						initComplete: function () {
							this.api().columns([{{ $details['fltsCols'] }}]).every(function (c,a,i) {
								var delim = {!! json_encode($details['fltDelim']) !!};
								var column = this;
								var select = $('<select class="filter" id="filter-' + column[0][0] + '" name="filter-' + column[0][0] + '" aria-controls="myTable"><option value="" selected>- ' + $(column.header()).text() + ' -</option></select>')
									.appendTo($("div.toolbar .row"))
									.on('change', function () {
										var val = $(this).val()
										column
											.search(val ? val : '', false, false)
											.draw();
									});
								select.wrap('<div class="drop_dowm_select col"></div>');
								$('div.toolbar').insertAfter('#myTable_filter');

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

							@if ($details['script'] ?? null)
								{!! $details['script'] !!}
							@endif
						}
					@endif
				});

				$('a.toggle-vis').on('click', function (e) {
					e.preventDefault();
					var column = datatable.column($(this).attr('data-column'));
					column.visible(!column.visible());
				});

				$('#myTable tbody').on('click', 'td.details-control', function () {
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

				$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));
			});
		});
	</script>
	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center map_right">
				<div id="data_container" class="col-12">
					<div class="table-responsive">
						<div class="filter_icon">
							<i class="bi bi-funnel-fill"></i>
						</div>
						<table id="myTable" class="db-table display table-striped table-hover" style="width:100%;">
							<thead>
								<tr>
									@if ($details['detFlag'])
										<th></th>
									@endif
									@foreach ($details['hdrs'] as $name)
										<th>{{ $name }}</th>
									@endforeach
								</tr>
							</thead>
						</table>
					</div>
				</div>
			</div>
		</div>

		@if (($dataset['Public Note'] ?? null))
			<div class="col-md-12">
				<h4 class="note_bottom">{{ nl2br($dataset['Public Note']) }}</h4>
			</div>
		@endif
		<div class="col-md-12">
			<div class="bottom_lastupdate">
		@if ($dataset)
				<p class="lead"><img src="/img/info.png"> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank">{{ $dataset['Name'] ?? '' }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ $crolLastUpdated ?? explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span></p>
			</div>
		</div>
	</div>
		@endif
	
	<script>
		function changeToggle (e) {
			console.log($(e.target).next("label")[0].innerHTML)
			$('#change_district').html($(e.target).next("label")[0].innerHTML);
		}
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
	</script>

@endsection
