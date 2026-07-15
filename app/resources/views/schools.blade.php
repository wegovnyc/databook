@extends('layout')


@section('head')
	<meta name="description" content="A webpage for NYC schools" />
	<meta rel="canonical" href="{!! route('schools') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

	<script>

		var datatable = null
		var dataurl = '{!! $url !!}'
		var datasets = {!! json_encode(array_values($datasets)) !!}
		var tblStatsUrls = {!! json_encode($tblStatsUrls) !!}
		var dsstats_table = null



		function addrSearchKeyPress() {
			if(event.key === 'Enter') {
				addrSearch();
			}
		}
		
		function addrSearch() {
			var addr = $('#addrSearch').val()
			if (!addr || (addr.length < 6)) {
				addrSearchPopover('Please enter valid address')
				return
			}

			$.ajax({
				url: 'https://api.nyc.gov/geo/geoclient/v1/search.json',
				data: {input: addr},
				headers: {'Ocp-Apim-Subscription-Key': '{{ config('apis.geoclient_key') }}'},
				success: function (dd) {
					if (dd.status != 'OK') {
						addrSearchPopover('Not found, please try again')
						return
					}
					r = dd.results[0].response
					var addr = `${r.houseNumber} ${r.firstStreetNameNormalized}, ${r.uspsPreferredCityName}`.replace('  ', ' ').replace(' ,', '')
					var description = `
						<h4 style="font-size:18px;">${addr}</h4>
						<table><tbody>
							<tr><th scope="row">Community District</th>
								<td>
									<a href="/d/cd-${r.communityDistrict}-community-district-${r.communityDistrict}/city-council-discretionary">${r.communityDistrict}</a>
								</td>
							</tr>
							<tr><th scope="row">City Council District</th>
								<td>
									<a href="/d/cc-${r.cityCouncilDistrict.replace(/^0+/g, '')}-city-council-district-${r.cityCouncilDistrict.replace(/^0+/g, '')}/city-council-discretionary">${r.cityCouncilDistrict}</a>
								</td>
							</tr>
							<tr><th scope="row">School District</th>
								<td>
									<a href="/d/sd-${r.communitySchoolDistrict}-community-school-district-${r.communitySchoolDistrict}/schools">${r.communitySchoolDistrict}</a>
								</td>
							</tr>
							<tr><th scope="row">Zip Code</th><td>${r.zipCode}</td></tr>
							<tr><th scope="row">Election District</th><td>${r.electionDistrict}</td></tr>
							<tr><th scope="row">State Assembly District</th><td>${r.assemblyDistrict}</td></tr>
							<tr><th scope="row">State Senate District</th><td>${r.stateSenatorialDistrict}</td></tr>
							<tr><th scope="row">Congressional District</th><td>${r.congressionalDistrict}</td></tr>
							<tr><th scope="row">Police Precinct</th><td>${r.policePrecinct}</td></tr>
							<tr><th scope="row">Sanitation District</th><td>${r.sanitationDistrict}</td></tr>
							<tr><th scope="row">Fire Battilion</th><td>${r.fireBattalion}</td></tr>
							<tr><th scope="row">Health Center District</th><td>${r.healthCenterDistrict}</td></tr>
						</tbody></table>`

					map.fitBounds([
						[r.longitude - 0.002,r.latitude - 0.0005], // southwestern corner of the bounds
						[r.longitude + 0.002,r.latitude + 0.0035] // northeastern corner of the bounds
					], {
						padding: [50, 50],
						maxZoom: 15,
						duration: 1500,
						animate: true,
						essential: true,
					})

					if (popup)
						popup.remove()

					popup = new mapboxgl.Popup()
						.setLngLat([r.longitude,r.latitude])
						.setHTML(description)
						.addTo(map)

				}
			});
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


		$(document).ready(function() {

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
					@if ($details['detFlag'] ?? null)
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
				]

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
						$("div.toolbar .row").append('');

						@foreach ($details['filters'] as $i=>$v)
							@if ($v)
								setTimeout(function(){
									$('#filter-{{ $i }}').find('[value*="{!! $v !!}"]').prop('selected',true).trigger('change')
								}, 500 + 1000 * {{ $i }});
							@endif
						@endforeach
						setTimeout(function(){
							initPopovers();
						}, 1000);
					}
				@endif

				@if ($details['order'] ?? null)
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
				drawProjects('all');
			});

			$('#myTable tbody').on('click', 'td:not(.details-control)', function () {
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

			@if($sdStatsUrl ?? null)
				fapireq('{!! $sdStatsUrl !!}', function (resp) {
					$('#schools_no').text(commaThousands(resp.data[0].schools_no))
					$('#students_no').text(commaThousands(resp.data[0].students_no))
					$('#prj_no').text(commaThousands(resp.data[0].prj_no))
					$('#prj_budget').text(toFinShortK(resp.data[0].prj_budget))
					$('#prj_costs').text(toFinShortK(resp.data[0].prj_costs))
					$('#pcosts_per_student').text(toFinShortK(resp.data[0].pcosts_per_student))
				})
			@endif

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
					@foreach($tblStatsUrls as $tbl=>$statsUrl)
						loadTableStat(
							"{{ $tbl }}",
							"{!! $statsUrl !!}"
						);
					@endforeach
				}
			});


			// Initialize Map
			projectsMapInit();
			
			// Initialize District Switch
			setTimeout(function(){
					$('#sd-switch').click();
			}, 2500);

			$('.dropdown-menu').click(function (e) {
				e.stopPropagation();
			});

			// addr search autocomplete
			var autocomplete = new Bloodhound({
			  datumTokenizer: Bloodhound.tokenizers.whitespace,
			  queryTokenizer: Bloodhound.tokenizers.whitespace,
			  remote: {
				url: 'https://geosearch.planninglabs.nyc/v2/autocomplete?text=%QUERY',
				wildcard: '%QUERY',
				transform: function (resp) {
				  var rr = []
				  resp.features.forEach(function (f) {
					  rr.push(f['properties']['label'].replace('NY, ', ''))
				  })
				  return rr
				}
			  }
			});
			$('#addrSearch').typeahead(null, {
			  name: 'autocomplete',
			  limit: 16,
			  source: autocomplete
			});
			autocomplete.clearPrefetchCache();
			autocomplete.initialize(true);

		})


		function goSdOnClick(e) {
			var bbox = [
				[e.point.x, e.point.y],
				[e.point.x, e.point.y]
			];
			var features = map.queryRenderedFeatures(bbox, {
				layers: ['sdFHH']
			});

			var filter = features.reduce(
				function(memo, feature) {
					memo.push(feature.properties['nameCol']);
					return memo;
				},
				['in', 'nameCol']
			);

			window.open(`/d/sd-${filter[2]}-schools-district-${filter[2]}/schools`, '_self');
		}

		// Legacy toggleMap removed.
		// Legacy drawProjects updated:

		function drawProjects(pages) {	// 'all',     'current'
			// Always active now
			// var mapIsActive = !$('#map_container').attr('style')
			// if (!mapIsActive) return;

			var api = $('#myTable').dataTable().api();
			var modifier = {
				order:  'current',  // 'current', 'applied', 'index',  'original'
				page:   pages,      // 'all',     'current'
				search: 'applied',     // 'none',    'applied', 'removed'
			}
			var features = [];
			
			// Define color palette for school categories
			const categoryColors = {
				'Elementary': '#4e79a7',      // Blue
				'Junior High-Intermediate-Middle': '#f28e2b', // Orange
				'High school': '#e15759',     // Red
				'K-12 all grades': '#76b7b2', // Teal
				'K-8': '#59a14f',             // Green
				'Early Childhood': '#edc948', // Yellow
				'Secondary School': '#b07aa1',// Purple
				'Collaborative or Multi-graded': '#ff9da7', // Pink
				'Ungraded': '#9c755f'         // Brown
			};
			const defaultColor = '#bab0ac'; // Gray

			api.rows('', modifier).data().each(function (r, i) {
				if (r['GEO_JSON']) {
					try {
						r['GEO_JSON'] = r['GEO_JSON'].replaceAll('""', '"')
						geo_json = null
						geo_json = JSON.parse(r['GEO_JSON'])
						
						// Assign color based on Category
						// Check if Category exists in properties, otherwise fallback
						const category = geo_json.properties['CATEGORY']; 
						geo_json.properties['custom_color'] = categoryColors[category] || defaultColor;

						features.push(geo_json)
					} catch (error) {
						console.error(error);
					}
				}
			});
			projectsMapDrawFeatures(features);
		}


	</script>

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data">
					<h2>NYC Schools</h2>
					<p class="lead">We’ve created profiles for all NYC schools that combines data from over a dozen datasets from multiple city agencies.</p>
				</div>
			</div>


			<div id="stats_collapse" class="collapse show mt-2 mb-4">
				<div class="row justify-content-center my-2">
					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									# of Schools
									<h2 id="schools_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									# of Students
									<h2 id="students_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									# of Projects
									<h2 id="prj_no" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									Projects Budget
									<h2 id="prj_budget" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									Project Costs
									<h2 id="prj_costs" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

					<div class="col-md-2">
						<div class="card mb-2">
							<div class="card-body">
								<div class="card-text text-center">
									Project Cost per Student
									<h2 id="pcosts_per_student" class="prj_stat">&nbsp;</h2>
								</div>
							</div>
						</div>
					</div>

				</div>

			</div>


			<div class="row">
				<div id="map_container" class="col-12 mb-0 position-relative" style="min-height:540px!important;">
					<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;"></div>
					
					<!-- In-Map Toggle Button -->
					<button id="mapFilterToggle" class="map-filter-toggle-btn" type="button" onclick="toggleMapFilterPanel()">
						<i class="bi bi-funnel me-1"></i> Filters & Layers
					</button>
					
					<!-- In-Map Filter Panel -->
					<div id="mapFilterPanel" class="map-filter-panel" style="display: none;">
						<div class="map-filter-header">
							<h6 class="mb-0"><i class="bi bi-funnel me-2"></i>Filters & Layers</h6>
							<button type="button" class="btn-close btn-close-white btn-sm" onclick="toggleMapFilterPanel()"></button>
						</div>
						<div class="map-filter-body">
							<!-- Search Section -->
							<div class="mb-3">
								<div class="filter-section-title"><i class="bi bi-search me-1"></i> Search</div>
								<div class="input-group input-group-sm flex-nowrap mb-2">
									<span class="input-group-text"><i class="bi bi-geo-alt"></i></span>
									<input id="addrSearch" type="text" class="form-control" placeholder="Search by address..." onkeydown="addrSearchKeyPress(this)" autocomplete="off">
									<button class="btn btn-outline-light" type="button" id="addrSearchBtn" onclick="addrSearch();"><i class="bi bi-arrow-right"></i></button>
								</div>
								{{--
								<div class="input-group input-group-sm flex-nowrap">
									<span class="input-group-text"><i class="bi bi-hash"></i></span>
									<input id="idSearch" type="text" class="form-control" placeholder="Search by project ID..." onkeydown="idSearchKeyPress(this)" autocomplete="off">
									<button class="btn btn-outline-light" type="button" id="idSearchBtn" onclick="idSearch();"><i class="bi bi-arrow-right"></i></button>
								</div>
								--}}
							</div>
							
							<hr class="my-2">
							
							<!-- District Boundaries -->
							<div class="mb-2">
								<div class="filter-section-title"><i class="bi bi-map me-1"></i> District Boundaries</div>
								<div class="filter-options-list">
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="cd-switch"><label class="form-check-label small" for="cd-switch">Community Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="ed-switch"><label class="form-check-label small" for="ed-switch">Election Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="pp-switch"><label class="form-check-label small" for="pp-switch">Police Precincts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="dsny-switch"><label class="form-check-label small" for="dsny-switch">Sanitation Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="fb-switch"><label class="form-check-label small" for="fb-switch">Fire Battalion</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="sd-switch"><label class="form-check-label small" for="sd-switch">School Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="hc-switch"><label class="form-check-label small" for="hc-switch">Health Center Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="cc-switch"><label class="form-check-label small" for="cc-switch">City Council Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="nycongress-switch"><label class="form-check-label small" for="nycongress-switch">Congressional Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="sa-switch"><label class="form-check-label small" for="sa-switch">State Assembly Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="ss-switch"><label class="form-check-label small" for="ss-switch">State Senate Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="bid-switch"><label class="form-check-label small" for="bid-switch">Business Improvement Districts</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="nta-switch"><label class="form-check-label small" for="nta-switch">Neighborhood Tabulation Areas</label></div>
									<div class="form-check form-switch form-check-sm"><input type="checkbox" class="form-check-input" id="zipcode-switch"><label class="form-check-label small" for="zipcode-switch">Zip Codes</label></div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>


			<div class="row justify-content-center map_right">
				<div id="data_container" class="col-12">
					<div class="table-responsive" style="position:relative;">
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
			//console.log($(e.target).next("label")[0].innerHTML)
			$('#change_district').html($(e.target).next("label")[0].innerHTML);
		}
		$('#toggle_boundries').click( function (e) {
			$(this).next('.dropdown-menu').toggleClass('show');
		})

		$(".filter_icon").click(function() {
			//console.log($('.toolbar').is(':visible'))
			if(!$('.toolbar').is(':visible')) {
				$('.filter_icon').addClass('position_change');
			}else {
				$('.filter_icon').removeClass('position_change');
			}
			$(".toolbar").toggle();
		});
	</script>

@endsection
