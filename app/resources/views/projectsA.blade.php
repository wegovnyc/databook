@extends('layout')


@section('head')
	<meta name="description" content="A webpage for every NYC-funded infrastructure project" />
	<meta rel="canonical" href="{!! route('projects') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	
	<script>
		function details(r) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
			  @foreach ((array)$details['details'] as $h=>$f)
				'<tr><td>{{ $h }}:</td><td>' + {!! $f !!} + '</td></tr>' +
			  @endforeach
			'</table>';
		}
				
		var datatable = null
		var dataurltmpl = '{!! $url !!}'
		var dataurl = ''
		var datasets = {!! json_encode(array_values($datasets)) !!}
		var dsstats_table = null
		
		
		$(document).ready(function() {
			
			fapireq("{!! $dates_req_url !!}", function (resp) {
				var select = $('<select class="filter mt-1" style="width:100%;" id="filter-1" name="filter-1" aria-controls="myTable"><option value="" selected>- Publication Date -</option></select>')
					.appendTo($("#pub_date_filter"))
					.on('change', function () {
						var val = $(this).val()
						$('.loading').show()
						dataurl = dataurltmpl.replace('pubdate', val)
						datatable.ajax.load(function () {
							$('.loading').hide()
							loadFinStat()
						});
					});
				select.wrap('<div class="drop_dowm_select"></div>');
				resp['data'].forEach(function (d, j) {
					select.append(`<option value="${d['PUB_DATE']}" ${ j == 0 ? 'selected' : ''}>${toDashDate(d['PUB_DATE'])}</option>`)
				});
				
				loadFinStat();
				dataurl = dataurltmpl.replace('pubdate', resp['data'][0]['PUB_DATE']);
				
				datatable = $('#myTable').DataTable({
					ajax: function (url, cb) {
						fapireq(dataurl, cb);
					},
						
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
							@if (preg_match('~^function ~i', $f))
								type: 'html',
							@endif
							@if ($details['visible'][$i])
								visible: true
							@else
								visible: false
							@endif
							}
						@endforeach
						,
						{
							className: 'record',
							data:  null,
							defaultContent: null,
							visible: false,
							searchable: false
						}
					],
					createdRow: function(row, data, dataIndex) {
						if (data.GEO_JSON != '') {
							$(row).addClass('have_coords');
						}
					}

					@if ($details['filters'])
						,
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
							$("div.toolbar .row").append('<button id="map_button" class="btn map_btn col" style="margin:0 20px 0 10px; z-index: 10; max-width: 40px;" onclick="toggleMap();"><img src="/img/map_location.png" alt=""></button>');

							@foreach ($details['filters'] as $i=>$v)
								@if ($v)
									setTimeout(function(){
										$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
									}, 500 + 1000 * {{ $i }});
								@endif
							@endforeach
							setTimeout(function() {
									//datatable.draw();	// initiate projectsMapDrawFeatures
									//drawProjects('all');
									toggleMap();
								}, 500
							);
							setTimeout(function(){
								initPopovers();
							}, 1000);
						}
					@endif
					
					@if ($details['order'])
						,
						order: {!! json_encode($details['order']) !!}
					@endif
				});
				
				$('.btn_eyeicon').hide();
				
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
						initPopovers();
					}
				});

				$('#myTable_length label').html($('#myTable_length label').html().replace(' entries', ''));
				
				// if map is displayed updates and draws projects from GEO_JSON field
				datatable.on('draw', function () {
					drawProjects('current');
				});

				$('#myTable tbody').on('click', 'td:not(.details-control)', function () {
					var mapIsActive = !$('#map_container').attr('style')
					if (!mapIsActive) 
						return;
					var tr = $(this).closest('tr');
					var row = datatable.row(tr);
					r = row.data()
					if (r['GEO_JSON']) {
						var geo_json = JSON.parse(r['GEO_JSON'].replaceAll('""', '"'))
						var pr = geo_json.properties
						fitBounds([[pr.W, pr.S], [pr.E, pr.N]])
					}
				})
				
				// makes sortable html fields like 9.4 years late, $25,764 over
				$.fn.dataTable.ext.type.order['html-pre'] = function (data) {
					var d = data.replace(/>-</g, '>0<');
					d = d.replace(/<span class="(bad)"[^>]*>/g, '-');
					d = d.replace(/[,$]|years|late|<[^>]+>|earl\S+|%/g, '');
					d = d.replace(/NA|NaN|on time/g, '0');
					m = 1
					for (const[rg, tmpM] of [[/K$/g, 1000], [/M$/g, 1000000], [/B$/g, 1000000000]]) {
						if (d.match(rg)) {
							m = tmpM;
							d = d.replace(rg, '');
						}
					}
					d = d.match(/[-\d\.]+/g) ? parseFloat(d) * m : d;
					return d;
				};
				
			})

			
			dsstats_table = $('#dsStatsTable').DataTable({
				data: datasets,
				paging: false,
				columns: [
					{ title: "Name" },
					{ title: "Section" },
					{ title: "Description" },
					{ title: "Last Updated" },
					{ title: "Dataset Records" }
				],
				order: [],
				dom: 'rtp',
				initComplete: function () {
					@foreach($datasets as $tbl=>$ds)
						loadTableStat(
							"{{ $tbl }}", 
							"{!! str_replace('tblname', $tbl, $tblStatsUrl) !!}"
						);
					@endforeach
				}
			});
			

		});


		function toggleMap() {
			var isActive = !$('#map_container').attr('style')
			var cc = [{{ $details['hide_on_map_open'] }}];
			if (isActive) {
				$('#map_button').show()
				$('#data_container').attr('class', 'col')
				$('.toolbar ').show()
				$('#map_container').hide()
				$('#myTable').dataTable().api().columns(cc).every(function () {
					this.visible(true);
				});
			} else {
				$('#map_button').hide()
				$('#data_container').attr('class', 'col col-6')
				$('#map_container').show()
				projectsMapInit();
				$('#myTable').dataTable().api().columns(cc).every(function () {
					this.visible(false);
				});
				setTimeout(function() {
						drawProjects('all');
					}, 2500
				);
			}
			initPopovers();
		}
		
		function loadFinStat() {
			var uu = {!! json_encode($finStatUrls) !!}
			var pubdate = $('#filter-1 option:selected').val().replaceAll('-', '');
			for (let sel in uu) {
				//$.get(uu[sel].replace('pubdate', pubdate), function (resp) {
				fapireq(uu[sel].replace('pubdate', pubdate), function (resp) {
					var v = resp['data'][0]['res'] ?? '-'
					//console.log(['#orig_cost', '#curr_cost', '#over_budg_am'].includes(sel))
					if ((['#orig_cost', '#curr_cost', '#over_budg_am'].includes(sel)) && (v != '-')) {
						$(sel).text(toFinShortK(v, 1000))
						$(sel).attr('data-content', toFin(v, 1000))
					}						
					else 
						$(sel).text(v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","))
				})
			}
			setTimeout(function(){
				initPopovers();
			}, 1000);
		}

		function drawProjects(pages) {	// 'all',     'current'
			var mapIsActive = !$('#map_container').attr('style')
			if (!mapIsActive) 
				return;
			
			var api = $('#myTable').dataTable().api();
			var modifier = {
				order:  'current',  // 'current', 'applied', 'index',  'original'
				page:   pages,      // 'all',     'current'
				search: 'applied',     // 'none',    'applied', 'removed'
			}
			var features = [];
			api.rows('', modifier).data().each(function (r, i) {
				if (r['GEO_JSON']) {
					try {
						r['GEO_JSON'] = r['GEO_JSON'].replaceAll('""', '"')
						geo_json = null
						geo_json = JSON.parse(r['GEO_JSON'])
						geo_json.properties['AG_ID'] = r['wegov-org-id']
						features.push(geo_json)
					} catch (error) {
						console.error(error);
						console.log(r['GEO_JSON']);
						console.log(geo_json);
					}
				}
			});
			console.log(features.length)
			projectsMapDrawFeatures(features);
		}
		
		
		function loadTableStat(dsName, url) {
			dsstats_table = $('#dsStatsTable').DataTable();
			fapireq(url, function (resp) {
				if (resp['data'][0]['res']) {
					$('#stats_'+dsName).text(resp['data'][0]['res'])
					$('#total_records').text(Number($('#total_records').text()) + resp['data'][0]['res'])
					$('#total_datasets').text(Number($('#total_datasets').text()) + 1)
				} else {
					datasets.forEach(function (d, i) {
						if (d[4].indexOf('stats_'+dsName) != -1) {
							datasets.splice(i, 1)
							dsstats_table.row(i).remove()
							dsstats_table.draw();
						}
					})
				}
			})
		}

	</script>

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-9 organization_data">
					<h2>Capital Projects</h2>
					<p class="lead">Capital Projects are managed by city agencies and use city  funds to produce, improve and maintain city infrastructure and assets like roads, sewers, schools and sanitation trucks, and more.</p>
				</div>
				<div class="col-md-3 mt-2" id="org_summary">
					<table class="table-sm stats-table" width="100%">
					<thead>
						<tr>
						<th scope="col" width="50%" class="text-center px-0" data-content="See the project info published on specific dates.">Publication Date&nbsp;<small><i class="bi bi-question-circle-fill ml-1" style="top:-1px;position:relative;"></i></small></th>
						<th scope="col" width="50%" id="pub_date_filter"></th>
						</tr>
					</thead>
					<tbody>
						<tr>
							<td colspan=2 class="text-right px-0 pt-0 pb-3">
								<button class="type-label my-2 dropdown-toggle" data-bs-toggle="collapse" data-bs-target="#stats_collapse" aria-expanded="true" aria-controls="stats_collapse"><small>Show/Hide Stats</small></button>
							</td>
						</tr>
					</tbody>
					</table>
				</div>
			</div>


			<div id="stats_collapse" class="collapse show mt-2 mb-4">
				<div class="row justify-content-center my-2">
					<div class="col-md-3">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Number of Projects
									<h2 id="projects_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col-md-3">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Original Cost
									<h2 id="orig_cost" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col-md-3">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Current Cost
									<h2 id="curr_cost" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col-md-3">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Amount Over Budget
									<h2 id="over_budg_am" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
				</div>
					
				<div class="row justify-content-center mt-3 mb-4">
					<div class="col-md-3">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Running Long
									<h2 id="long_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col-md-3">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Over Budget
									<h2 id="over_budg_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col-md-3">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Starting Late
									<h2 id="late_start_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				
					<div class="col-md-3">
						<div class="card">
							<div class="card-body">
								<div class="card-text text-center">
									Ending Late
									<h2 id="late_end_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>
				</div>
				
			</div>
					

			<div class="row justify-content-center map_right">
				@if ($map ?? null)
					<div id="map_container" class="col-6" style="display:none;">
						<button id="map_button_alt" class="btn btn-outline map_btn" style="margin:0 20px 20px 10px; z-index: 10; max-width: 40px; float:right;" onclick="toggleMap();"><img src="/img/map_location.png" alt=""></button>
						<!-- toggles -->
						<div class="select_district" id="toggles" style="left:0px;">
							<img src="/img/eyes.png" alt="">
							<ul class="inner_district">
								<li class="dropdown">
									<a class="dropdown-toggle" id="toggle_boundries" role="button" aria-haspopup="true" aria-expanded="true">Show District Boundaries</a>
									<div class="dropdown-menu" style="width:100%;padding:0px 0px 0px 10px;">
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="cd-switch">
											<label class="custom-control-label" for="cd-switch">Community Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="ed-switch">
											<label class="custom-control-label" for="ed-switch">Election Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="pp-switch">
											<label class="custom-control-label" for="pp-switch">Police Precincts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="dsny-switch">
											<label class="custom-control-label" for="dsny-switch">Sanitation Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="fb-switch">
											<label class="custom-control-label" for="fb-switch">Fire Battilion<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="sd-switch">
											<label class="custom-control-label" for="sd-switch">School Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="hc-switch">
											<label class="custom-control-label" for="hc-switch">Health Center Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="cc-switch">
											<label class="custom-control-label" for="cc-switch">City Council Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="nycongress-switch">
											<label class="custom-control-label" for="nycongress-switch">Congressional Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="sa-switch">
											<label class="custom-control-label" for="sa-switch">State Assembly Dist...<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="ss-switch">
											<label class="custom-control-label" for="ss-switch">State Senate Districts<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="bid-switch">
											<label class="custom-control-label" for="bid-switch">Business Improvem...<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="nta-switch">
											<label class="custom-control-label" for="nta-switch">Neighborhood Tab...<hr class="border-sample"></label>
										</div>
										<div class="custom-control custom-switch">
											<input type="checkbox" class="custom-control-input" id="zipcode-switch">
											<label class="custom-control-label" for="zipcode-switch">Zip Code<hr class="border-sample"></label>
										</div>
									</div>
								</li>
							</ul>
						</div>
						<!-- /toggles -->
						<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;border:4px solid #112F4E; position:relative; min-height:800px;"></div>
						<p class="mt-4 mx-4">
							<i class="bi-geo-alt" style="font-weight: 600; font-size: 1.25rem;"></i>&nbsp;&nbsp;Our map uses data from <a href="https://data.cityofnewyork.us/City-Government/Capital-Projects-Database-CPDB-Projects-Polygons-/9jkp-n57r/" target="_blank">Capital&nbsp;Projects Database (CPDB) - Projects (Polygons)</a>, <a href="https://data.cityofnewyork.us/City-Government/Capital-Projects-Database-CPDB-Projects-Points-/h2ic-zdws/" target="_blank">Capital&nbsp;Projects Database (CPDB) - Projects (Points)</a> datasets.
						</p>
						<div id="help_us" class="" style="width:100%;min-height:260px;border:1px solid #112F4E; margin-top:20px; padding: 32px;">
							<h4>Help us locate projects</h4>
							<p>NYC’s government doesn’t publish the locations of capital projects (!?), so volunteers are using the information they do publish to determine where the projects are actually located.</p>
							<p><a href="https://www.notion.so/wegovnyc/Volunteer-d751814ef6374dd9b9d10c989bcfa141" class="learn_more" target="_blank" rel="nofollow">Join Us</a></p>
						</div>
					</div>
				@endif
				
				<div id="data_container" class="col float-left">
					<div class="table-responsive">
						<div class="filter_icon">
							<i class="bi bi-funnel-fill"></i>
						</div>
						<table id="myTable" class="display table-striped table-hover" style="width:100%;">
							<thead>
								<tr>
									@if ($details['detFlag'])
										<th></th>
									@endif
									@foreach ($details['hdrs'] as $name)
										<th>{{ $name }}</th>
									@endforeach
									<th></th>
								</tr>
							</thead>
						</table>
					</div>
				</div>
			</div>
		</div>
		
		<div class="container">
				<div class="row my-4">
					<div id="data_container_accordion" class="col-12 accordion">
					
						<div class="accordion social_media" id="accordionThree">
							<div>
								<div id="headingThree">
									<button class="social_btn" type="button" data-bs-toggle="collapse" data-bs-target="#collapseThree" aria-expanded="false" aria-controls="collapseThree">
										We’re using normalized data from <span id="total_datasets"></span> datasets containing <span id="total_records"></span> records. Click here to learn more.
									</button>
								</div>
								<div id="collapseThree" class="collapse hide" aria-labelledby="headingOne" data-parent="#accordionThree">
									<div class="card-text table-responsive">
										<table id="dsStatsTable" class="display table-hover table-borderless" style="width:100%;">
										</table>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
		</div>
		
	</div>
	
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