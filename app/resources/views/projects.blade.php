@extends('layout')


@section('head')
	<meta name="description" content="A webpage for every NYC-funded infrastructure project" />
	<meta rel="canonical" href="{!! route('projects') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')

	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data pb-1">
					<div class="db-eyebrow">Projects</div>
					<h2>Capital Projects</h2>
					<p class="lead">Capital Projects are managed by city agencies and use city  funds to produce, improve and maintain city infrastructure and assets like roads, sewers, schools and sanitation trucks, and more.</p>
				</div>
			</div>


			<div id="stats_collapse" class="collapse show mt-0 mb-3">
				<div class="db-stat-grid">
					<div class="db-stat"><div class="db-stat-label">Number of Projects</div><div class="db-stat-value prj_stat gs_thousandscomma" id="projects_no">&nbsp;</div></div>
					<div class="db-stat"><div class="db-stat-label">Original Cost</div><div class="db-stat-value prj_stat gs_finshort" data-multiplier="1000" id="orig_cost">&nbsp;</div></div>
					<div class="db-stat"><div class="db-stat-label">Current Cost</div><div class="db-stat-value prj_stat gs_finshort" data-multiplier="1000" id="curr_cost">&nbsp;</div></div>
					<div class="db-stat is-accent"><div class="db-stat-label">Amount Over Budget</div><div class="db-stat-value prj_stat gs_finshort" data-multiplier="1000" id="over_budg_am">&nbsp;</div></div>
				</div>
			</div>
					

			

		<div class="row">
				<div id="map_container" class="col-12 mb-0 position-relative" style="min-height:540px!important;">
					<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;"></div>

					<!-- Map-scoped loading overlay (not the full-page .loading) -->
					<div id="mapLoadingOverlay" style="display:none; position:absolute; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.55); z-index:400; align-items:center; justify-content:center; flex-direction:column; border-radius:8px;">
						<div style="width:40px; height:40px; border:3px solid rgba(255,255,255,0.3); border-top-color:#fff; border-radius:50%; animation:mapSpin 0.8s linear infinite;"></div>
						<div style="color:#fff; margin-top:12px; font-size:14px; font-weight:500;">Loading 5,000+ capital projects&hellip;</div>
					</div>
					<style>@keyframes mapSpin { to { transform: rotate(360deg); } }</style>

					
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
								<div class="input-group input-group-sm flex-nowrap">
									<span class="input-group-text"><i class="bi bi-hash"></i></span>
									<input id="idSearch" type="text" class="form-control" placeholder="Search by project ID..." onkeydown="idSearchKeyPress(this)" autocomplete="off">
									<button class="btn btn-outline-light" type="button" id="idSearchBtn" onclick="idSearch();"><i class="bi bi-arrow-right"></i></button>
								</div>
							</div>
							
							<hr class="my-2">
							
							<!-- Agency Filter -->
							<div class="mb-3">
								<div class="filter-section-title"><i class="bi bi-building me-1"></i> Managing Agency</div>
								<div id="agcyflt_controls" class="filter-options-list"></div>
							</div>
							<!-- Project Type Filter -->
							<div class="mb-3">
								<div class="filter-section-title"><i class="bi bi-folder me-1"></i> Project Type</div>
								<div id="typeflt_controls" class="filter-options-list"></div>
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
			</div>

		</div>
		
		<div class="container">
			<div class="inner_container">
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
										<table id="dsStatsTable" class="db-table display table-hover table-borderless" style="width:100%;">
										</table>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
		
	</div>
	
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<script src="https://typeahead.js.org/releases/latest/typeahead.bundle.js"></script>
	
	<script>
		var globfilter = []
		var idSearchData = []
		
		function getBounds(coords, bounds) {		// recursively walks over multilevel object calculating leaves-points coords
			if (typeof coords[0][0] == 'object')
				return coords.reduce(function (bounds, subcoords) {
						return getBounds(subcoords, bounds)
					},
					bounds
				)
			else {
				return coords.reduce(function (bounds, coord) {
							return bounds.extend(coord);
						}, (typeof bounds == 'undefined') ? new mapboxgl.LngLatBounds(coords[0], coords[0]) : bounds
					);
			}
		}

		function addrSearchPopover(msg) {
			$('#searchBtn').attr('data-content', msg)
			$('#searchBtn').popover('show')
			setTimeout(function(){
				$('#searchBtn').popover('hide')
			}, 2000);
		}

		function mapPopup(e) {
			var obj = e.features[0].properties;
			//console.log('mapPopup', obj);
			var description = `<table><tbody>
				<tr><th scope="row">Name</th><td><a href="/p/${obj.PRJ_ID}_${slug(obj.NAME)}">${obj.NAME}</a></td></tr>
				<tr><th scope="row">Current Phase</th><td>${obj.CURRENT_PHASE}</td></tr>
				<tr><th scope="row">Agency</th><td><a href="/o/${obj.AGENCY_ID}-${slug(obj.AGENCY)}/projects">${obj.AGENCY}</a></td></tr>
 				<tr><th scope="row">Category</th><td>${obj.CATEGORY}</td></tr>
				<tr><th scope="row" class="pr-2">Planned Cost</th><td data-content="${toFin(obj.PLANNEDCOST.replaceAll(',', ''), 1)}">${toFinShortK(obj.PLANNEDCOST.replaceAll(',', ''), 1)}</td></tr>
				<tr><th scope="row">Start</th><td>${obj.START_ORIG}</td></tr>
				<tr><th scope="row">End</th><td>${obj.END_CURR}</td></tr>
			</tbody></table>`;

			
			// Some features have missing/zero W/S/E/N bounds. fitBounds() on those
			// produces an invalid box → the map zooms out to [0,0] and renders gray.
			// Guard: only fit when all four bounds are finite & non-zero, else just
			// recenter gently on the clicked point.
			var W = parseFloat(obj.W), S = parseFloat(obj.S), E = parseFloat(obj.E), N = parseFloat(obj.N);
			if ([W, S, E, N].every(Number.isFinite) && (W || S || E || N)) {
				map.fitBounds([
					[W, S],
					[E, N]
				], {
					padding: [50, 50],
					maxZoom: 18,
					duration: 1000,
					animate: true,
					essential: true,
				});
			} else {
				map.easeTo({
					center: e.lngLat,
					zoom: Math.max(map.getZoom(), 14),
					duration: 1000,
					essential: true,
				});
			}

			if (popup)
				popup.remove();

			popup = new mapboxgl.Popup()
				.setLngLat(e.lngLat)
				.setHTML(description)
				.addTo(map);
			initPopovers();
			//e.stopPropagation();
		}


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
									<a id="cd-agency" style="display:none;" target="_blank"><i class="bi bi-link-45deg"></i></a>
									<a id="cd-url" style="display:none;" target="_blank"><i class="bi bi-box-arrow-up-right"></i></a>
								</td>
							</tr>
							<tr><th scope="row">City Council District</th>
								<td>
									<a href="/d/cc-${r.cityCouncilDistrict.replace(/^0+/g, '')}-city-council-district-${r.cityCouncilDistrict.replace(/^0+/g, '')}/city-council-discretionary">${r.cityCouncilDistrict}</a>
									<a id="cc-agency" style="display:none;" target="_blank"><i class="bi bi-link-45deg"></i></a>
									<a id="cc-url" style="display:none;" target="_blank"><i class="bi bi-box-arrow-up-right"></i></a>
								</td>
							</tr>
							{{--<tr><th scope="row">Neighborhood (NTA)</th><td><a href="/d/nta-${r.nta}-${r.nta}/city-council-discretionary">${r.nta}</a></td></tr>--}}
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

		function idSearchKeyPress() {
			if(event.key === 'Enter') {
				idSearch();
			}
		}

		function idSearch() {
			var name = $('#idSearch').val()
			const rr = /^(.*?)\s*\(([-\w\d]{4,})\)$/g.exec(name)
			url = `/p/${rr[2]}_${slug(rr[1])}`
			//console.log(name, rr)
			window.location.href = url
		}

		$(document).ready(function() {
			projectsMapInit();
			setTimeout(function(){
					$('#cd-switch').click();
				}, 2500);
			showObjects('{!! $url !!}');
			
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


		function showObjects(url) {
			$('#mapLoadingOverlay').css('display', 'flex');
			const cc = {'Other': '#53777a', 'Completed': '#f5ae33', 'Pending': '#bcbcbc', 'Pre-Design': '#ff7c7c', 'Close-out': '#f2c45a', 'Construction': '#36c726', 'Construction Procurement': '#beedb9', 'Design': '#78c0a8'}
			console.log('Fetching URL:', url);
			fapireq(url, function (jj) {
				console.log('Data received:', jj);
				var features = []
				var tt = []
				var aa = []
				console.log('Starting loop');
				
				// Handle errors or missing data gracefully
				if (jj.error || !jj.data || !Array.isArray(jj.data)) {
					console.error('API Error or missing data:', jj.error || 'Invalid format');
					$('#mapLoadingOverlay').hide();
					return;
				}

				try {
					jj.data.forEach(function (j) {
						if (j['GEO_JSON']) {
						try {
							j['GEO_JSON'] = j['GEO_JSON'].replaceAll('""', '"')
							geo_json = JSON.parse(j['GEO_JSON'])
							if (!geo_json.properties) geo_json.properties = {};
							geo_json.properties['CURRENT_PHASE'] = j['CURRENT_PHASE']
							geo_json.properties['AGENCY'] = j['wegov-org-name']
							geo_json.properties['AGENCY_ID'] = j['wegov-org-id']
							geo_json.properties['AG_ID'] = j['wegov-org-id']
							geo_json.properties['PRJ_TYPE'] = j['wegov-prjtype-name']
							geo_json.properties['custom_color'] = (j['wegov-prj-color'] && cc[j['wegov-prj-color']]) || geo_json.properties['custom_color'] || '#53777a'
							
							// Add bounds
							if (j['lat'] && j['lng']) {
								geo_json.properties['W'] = parseFloat(j['lng'])
								geo_json.properties['E'] = parseFloat(j['lng'])
								geo_json.properties['N'] = parseFloat(j['lat'])
								geo_json.properties['S'] = parseFloat(j['lat'])
							}

							// Ensure coordinates are numbers
							if (geo_json.geometry && geo_json.geometry.coordinates) {
								if (geo_json.geometry.type === 'Point') {
									geo_json.geometry.coordinates = geo_json.geometry.coordinates.map(parseFloat);
								} else if (geo_json.geometry.type === 'MultiPoint' || geo_json.geometry.type === 'LineString') {
									geo_json.geometry.coordinates = geo_json.geometry.coordinates.map(c => c.map(parseFloat));
								} else if (geo_json.geometry.type === 'Polygon' || geo_json.geometry.type === 'MultiLineString') {
									geo_json.geometry.coordinates = geo_json.geometry.coordinates.map(r => r.map(c => c.map(parseFloat)));
								} else if (geo_json.geometry.type === 'MultiPolygon') {
									geo_json.geometry.coordinates = geo_json.geometry.coordinates.map(p => p.map(r => r.map(c => c.map(parseFloat))));
								}
							}

							features = features.concat(gen_multi_geo(geo_json))
						} catch (error) {
							console.log('Errror', j['GEO_JSON']);
							console.error('JSON Parse Error:', error);
						}
						if (j['wegov-prjtype-name'] && typeof j['wegov-prjtype-name'] === 'string' && j['wegov-prjtype-name'].trim())
							tt.push(j['wegov-prjtype-name'])
						if (j['wegov-org-name'] && typeof j['wegov-org-name'] === 'string' && j['wegov-org-name'].trim())
							aa.push(j['wegov-org-name'])
					}
					idSearchData.push(`${j['description']} (${j['projectid']})`)
				})
				console.log('Loop finished');
				tt = [...new Set(tt)]
				aa = [...new Set(aa)]
				idSearchData = [...new Set(idSearchData)]
				console.log('Loop finished');

				tt.sort().forEach(function (d, j) {
					$('#typeflt_controls').append('<button class="dropdown-item" type="button">'+d+'</button>')
				});
				$('#typeflt_controls button').click(function () {fltClick('type', $(this));});
				
				aa.sort().forEach(function (d, j) {
					$('#agcyflt_controls').append('<button class="dropdown-item" type="button">'+d+'</button>')
				});
				$('#agcyflt_controls button').click(function () {fltClick('agcy', $(this));});
				console.log('Features count:', features.length);
				if (features.length > 0) console.log('First feature:', features[0]);
				projectsMapDrawFeatures(features, false);


				// Name search autocomplete
				var idSearch = new Bloodhound({
				  datumTokenizer: Bloodhound.tokenizers.whitespace,
				  queryTokenizer: Bloodhound.tokenizers.whitespace,
				  local: idSearchData
				});

				$('#idSearch').typeahead(null, {
				  name: 'idSearchAutocomplete',
				  limit: 16,
				  source: idSearch
				});

				idSearch.clearPrefetchCache();
				idSearch.initialize(true);

				} catch (processingError) {
					console.error('Error processing projects data:', processingError);
				} finally {
					$('#mapLoadingOverlay').hide();
				}

			});
		}

		function fltClick(flttype, el) {
			var flt = null
			var set_active = null
			if (el.hasClass('active')) {
				flt = ['has', 'PRJ_TYPE']
				set_active = false
			} else if (flttype == 'type') {
				flt = ['in', 'PRJ_TYPE', el.text()]
				set_active = true
			} else {
				flt = ['in', 'AGENCY', el.text()]
				set_active = true
			}
			// set bounds
				var features = map.querySourceFeatures('route', {
					sourceLayer: 'markers',
					filter: flt
				})
				console.log(features)
				features = getUniqueFeatures(features, 'PRJ_ID')
				console.log(features)
				const bounds = features.reduce((bounds, el) => {
					bounds[0][0] = Math.min(bounds[0][0], el.properties.W - 0.01);
					bounds[0][1] = Math.min(bounds[0][1], el.properties.S - 0.01);
					bounds[1][0] = Math.max(bounds[1][0], el.properties.E + 0.01);
					bounds[1][1] = Math.max(bounds[1][1], el.properties.N + 0.01);
					return bounds;
				}, [[360, 180], [-360, -180]]);
			//
			map.setFilter('markers', ['all', flt, ['==', '$type', 'Point']])
			map.setFilter('streets', ['all', flt, ['==', '$type', 'LineString']])
			map.setFilter('areas', ['all', flt, ['==', '$type', 'Polygon']])
			$('#agcyflt_controls button, #typeflt_controls button').removeClass('active')
			if (set_active)
				el.addClass('active')
			$('#agcyflt_toggle').dropdown('hide')
			$('#typeflt_toggle').dropdown('hide')
			map.fitBounds(bounds, {
				padding: [50, 50],
				maxZoom: 18,
				duration: 1000,
				animate: true,
				essential: true,
			});
		}

	
		function gen_multi_geo(geo_json) {
			var rr = []
			const idx = {'MultiPoint': 'Point', 'MultiLineString': 'LineString', 'MultiPolygon': 'Polygon'}
			
			if (Object.keys(idx).includes(geo_json.geometry.type)) {
				var newtype = idx[geo_json.geometry.type]
				geo_json.geometry.coordinates.forEach((el)=>{
					rr.push(Object.assign({}, geo_json, {geometry: {type: newtype, coordinates: el}}))
				})
			} else {
				rr.push(geo_json)
			}
			return rr
		}


		function getUniqueFeatures(features, comparatorProperty) {
			const uniqueIds = new Set();
			const uniqueFeatures = [];
			for (const feature of features) {
				const id = feature.properties[comparatorProperty];
				if (!uniqueIds.has(id)) {
					uniqueIds.add(id);
					uniqueFeatures.push(feature);
				}
			}
			return uniqueFeatures;
		}

	</script>


	<script>
				
		var datatable = null
		var dataurl = '{!! $url !!}'
		var datasets = {!! json_encode(array_values($datasets)) !!}
		var dsstats_table = null
		
		
		$(document).ready(function() {
			const globStats = {!! json_encode($globStats) !!};
			globStatView(globStats);
			
			var tbl = $('#most_expensive_list_ tbody');
		globStats['most_expensive_list'].forEach(function (row) {
			$(`<tr><td style="white-space:nowrap; text-overflow:ellipsis; max-width:0; overflow:hidden; width:100%;"><a href="/p/${row['PROJECT_ID']}_${slug(row['PROJECT_DESCR'])}">${row['PROJECT_DESCR']}</a> </td><td>${toFinShortK(parseFloat(row['BUDG_CURR']), 1)}</td></tr>`).appendTo(tbl);
		})
		
		tbl = $('#longest_running_list_ tbody');
		globStats['longest_running_list'].forEach(function (row) {
			$(`<tr><td style="white-space:nowrap; text-overflow:ellipsis; max-width:0; overflow:hidden; width:100%;"><a href="/p/${row['PROJECT_ID']}_${slug(row['PROJECT_DESCR'])}">${row['PROJECT_DESCR']}</a> </td><td style="white-space:nowrap;">${parseFloat(row['DURATION_CURR']).toFixed(1)} yrs</td></tr>`).appendTo(tbl);
		})

		tbl = $('#most_over_budget_list_ tbody');
		globStats['most_over_budget_list'].forEach(function (row) {
			$(`<tr><td style="white-space:nowrap; text-overflow:ellipsis; max-width:0; overflow:hidden; width:100%;"><a href="/p/${row['PROJECT_ID']}_${slug(row['PROJECT_DESCR'])}">${row['PROJECT_DESCR']}</a> </td><td style="white-space:nowrap;">${toFinShortK(parseFloat(row['BUDG_DIFF']), 1)} over</td></tr>`).appendTo(tbl);
		})

			tbl = $('#latest_list_ tbody');
			globStats['latest_list'].forEach(function (row) {
				$(`<tr><td style="white-space:nowrap; text-overflow:ellipsis; max-width:0; overflow:hidden; width:100%;"><a href="/p/${row['PROJECT_ID']}_${slug(row['PROJECT_DESCR'])}">${row['PROJECT_DESCR']}</a> </td><td style="white-space:nowrap;">${parseFloat(row['END_DIFF']).toFixed(1)} yrs late</td></tr>`).appendTo(tbl);
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
				if (r['GEO_JSON'] != null) {
					try {
						r['GEO_JSON'] = r['GEO_JSON'].replaceAll('""', '"')
						geo_json = null
						geo_json = JSON.parse(r['GEO_JSON'])
						geo_json.properties['AG_ID'] = r['wegov-org-id']
						geo_json.properties['CURRENT_PHASE'] = r['CURRENT_PHASE']
						features.push(geo_json)
					} catch (error) {
						console.log(r['GEO_JSON']);
						console.log(geo_json);
						console.error(error);
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


		function changeToggle (e) {
			console.log($(e.target).next("label")[0].innerHTML)
			$('#change_district').html($(e.target).next("label")[0].innerHTML);
		}
		$('#toggle_boundries').click( function (e) {
			$(this).next('.dropdown-menu').toggleClass('show');
		})
	</script>

@endsection