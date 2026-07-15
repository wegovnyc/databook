@extends('layout')

@section('head')
	@if($noindex ?? null)
		<meta name="robots" content="noindex,nofollow">
	@else
		<meta name="description" content="{{ $snippet ?? '' }}" />
		<meta rel="canonical" href="{!! $canonicalUrl ?? '' !!}" />
	@endif

@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
{{-- District-type switcher lives in the submenu now (sub/menubar districts config).
     These buttons are kept (hidden) ONLY as JS plumbing: orgSectionMapInit() inits the
     map by clicking #{type}-button, and changeToggle2() tracks state via .btn.active.
     Do not remove — removing them breaks initial map load + type switching. --}}
<div class="d-none" id="button-addon3" aria-hidden="true">
	<button class="btn" id="cd-button" type="button" onclick="changeToggle2('cd');">Community Districts</button>
	<button class="btn" id="cc-button" type="button" onclick="changeToggle2('cc');">City Council Districts</button>
	<button class="btn" id="nta-button" type="button" onclick="changeToggle2('nta');">Neighborhood (NTA)</button>
	<button class="btn" id="sd-button" type="button" onclick="changeToggle2('sd');">School Districts</button>
	<span trg=""></span>
</div>

<div class="inner_container">
	{{-- Full-bleed map stage; all overlay chrome is absolutely positioned inside it. --}}
	{{-- float:none/width:100% override the legacy `#map_container{float:right}` rule, which
	     collapsed this to 0 width once the old .row/.col-12 flex wrapper was removed. --}}
	<div id="map_container" class="db-map-stage" style="position:relative; float:none; width:100%; height:min(70vh, 720px); min-height:480px;">
		<div class="map-loading" style="display:none; position:absolute; top:0; left:0; right:0; bottom:0; background:rgba(255,255,255,0.8); z-index:1000; align-items:center; justify-content:center;">
			<div style="text-align:center;">
				<div class="spinner-border text-primary" role="status" style="width:3rem; height:3rem;"></div>
				<div class="mt-2 text-muted">Loading map data...</div>
			</div>
		</div>
		<div id="map" class="map" style="width:100%;height:100%;"></div>

		{{-- Address search, top-left --}}
		<div class="db-map-search" style="top: var(--db-space-2); left: var(--db-space-2);">
			<i class="bi bi-search"></i>
			<input id="addrSearch" type="text" placeholder="Search an address…" aria-label="Enter address to find districts" aria-describedby="searchBtn">
			<button class="db-map-search-go" id="searchBtn" type="button" onclick="addrSearch();" data-bs-toggle="popover" data-content="" data-placement="bottom" data-trigger="manual" aria-label="Search address"><i class="bi bi-arrow-right"></i></button>
		</div>

		{{-- "Show District Boundaries" overlay control, top-right --}}
		<div class="db-map-control" id="boundaries-control" style="top: var(--db-space-2); right: var(--db-space-2);">
			<button type="button" class="db-btn db-btn-outline db-btn-sm" id="boundaries-toggle" aria-haspopup="true" aria-expanded="false" style="background:#fff;">
				<i class="bi bi-bounding-box-circles"></i> Show District Boundaries <i class="bi bi-chevron-down db-caret"></i>
			</button>
			<div class="db-map-control-menu" id="boundaries_controls">
				<p class="db-map-control-label">Overlay boundaries</p>
				@php
					$boundaryLayers = [
						'cd' => 'Community Districts',
						'ed' => 'Election Districts',
						'pp' => 'Police Precincts',
						'dsny' => 'Sanitation Districts',
						'fb' => 'Fire Battalions',
						'sd' => 'School Districts',
						'hc' => 'Health Center Districts',
						'cc' => 'City Council Districts',
						'nycongress' => 'Congressional Districts',
						'sa' => 'State Assembly Districts',
						'ss' => 'State Senate Districts',
						'bid' => 'Business Improvement Districts',
						'nta' => 'Neighborhood Tabulation Areas',
						'zipcode' => 'Zip Code',
					];
				@endphp
				@foreach ($boundaryLayers as $code => $label)
					<label class="db-map-control-row" for="{{ $code }}-switch">
						<input type="checkbox" id="{{ $code }}-switch">
						<span>{{ $label }}</span>
						<hr class="border-sample db-map-swatch">
					</label>
				@endforeach
			</div>
		</div>
	</div>

	<div class="container">
		<div class="row justify-content-center">
			<div id="section_content" class="col-12 mb-4 p-0 district_section">
				{!! $subview ?? '' !!}
			</div>
		</div>
	</div>
</div>
	<script src="https://typeahead.js.org/releases/latest/typeahead.bundle.js"></script>
	<script>

		var globfilter = []
		var defSection = '{{ $section ?? '' }}'
		var defId = '{{ $id ?? '' }}'
		var menu = {!! json_encode($menu) !!}

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

		function mapAction(filter, type, sect, reloadSection=true) {
			$('.map-loading').show()
			if (sect == 'inherit')
				if ($('.dsmenu.is-active').length) {
					sect = $('.dsmenu.is-active').attr('id').replace('dsmenu-', '')
				} else {
					//sect = '{{ array_keys($slist)[0] }}'
					sect = menu[type][0]
				}
			globfilter = filter

			$.get(`/districtXHR/${type}/${filter[2]}/${sect}`, function (html) {
				if (reloadSection) {
					$('#section_content').html(html)
				}

				window.setTimeout(function (){
					var features = map.querySourceFeatures(type, {
						filter: filter
					});
					//console.log(filter, features, features.length)
					if (features.length) {
						var title = features[0].properties['nameCol']
						var center = getBounds(features[0].geometry.coordinates).getCenter()
						tt = {'cc': 'City Council District ', 'cd': 'Community District ', 'nta': '', 'sd': 'School District '}
						$('#section_content h1').html(tt[type]+title)
						$('#details-permalink').text($('#details-permalink').text().replace('dslug', slug(tt[type]+title)))
						$('.map-loading').hide()
						window.setTimeout(function (){
							map.flyTo({
								center: center,
								speed: 0.4
							});
							}, 1000
						)
					} else {
						$('.map-loading').hide()
					}
				}, 1000);
			})
		}


		function addrSearchPopover(msg) {
			$('#searchBtn').attr('data-content', msg)
			$('#searchBtn').popover('show')
			setTimeout(function(){
				$('#searchBtn').popover('hide')
			}, 2000);
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
						maxZoom: 18,
						duration: 1000,
						animate: true,
						essential: true,
					})

					if (popup)
						popup.remove()

					popup = new mapboxgl.Popup()
						.setLngLat([r.longitude,r.latitude])
						.setHTML(description)
						.addTo(map)

					fapireq('{!! $cdAgencyUrl !!}'.replace('%40%40%40', r.communityDistrict.replace(/^0+/g, '')), function (cd) {
						$('#cd-agency').attr('href', '/organization/' + cd['data'][0]['id'])
						$('#cd-agency').show()
						if (cd['data'][0]['url']) {
							$('#cd-url').attr('href', cd['data'][0]['url'])
							$('#cd-url').show()
						}
					})
					fapireq('{!! $ccAgencyUrl !!}'.replace('%40%40%40', r.cityCouncilDistrict.replace(/^0+/g, '')), function (cc) {
						$('#cc-agency').attr('href', '/organization/' + cc['data'][0]['id'])
						if (cc['data'][0]['url']) {
							$('#cc-url').attr('href', cc['data'][0]['url'])
							$('#cc-url').show()
						}
					})
				}
			});
		}

		$(document).ready(function() {
			orgSectionMapInit({!! json_encode($map) !!}, {!! $type ? "'{$type}'" : "''" !!});

			/*
			map.on('load', function() {
				showObjects('{!! $prjUrl !!}');
			})
			*/

			$('.dropdown-menu').click(function (e) {
				e.stopPropagation();
			});

			// "Show District Boundaries" overlay control (.db-map-control) — open/close,
			// aria sync, outside-click close. Replaces the old Bootstrap dropdown.
			var boundariesControl = document.getElementById('boundaries-control');
			var boundariesToggle = document.getElementById('boundaries-toggle');
			if (boundariesControl && boundariesToggle) {
				boundariesToggle.addEventListener('click', function (e) {
					e.stopPropagation();
					var open = boundariesControl.classList.toggle('is-open');
					boundariesToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
				});
				document.addEventListener('click', function (e) {
					if (!e.target.closest || !e.target.closest('#boundaries-control')) {
						boundariesControl.classList.remove('is-open');
						boundariesToggle.setAttribute('aria-expanded', 'false');
					}
				});
			}

		})


		function showObjects(url) {
			fapireq(url, function (jj) {
				//console.log(jj)
				var features = []
				jj.data.forEach(function (j) {
					try {
						geo_json = JSON.parse(j['GEO_JSON'].replaceAll('""', '"').replaceAll('\\"', '"'))
						geo_json.properties['AG_ID'] = j['wegov-org-id']
						features.push(geo_json)
					} catch (error) {
						console.error(error);
					}
				})
				projectsMapDrawFeatures(features, false);
				$('.map-loading').hide()
			});
		}


		function changeToggle2 (type) {
			var prev_type = ($('.btn.active').attr('id')) ? $('.btn.active').attr('id').replace('-button', '') : null;
			if ((type == 'sd' && prev_type != 'sd') || (type != 'sd' && (prev_type == 'sd' || prev_type == null)))	 {
				$('.map-loading').show()
			}
			if ((type == 'sd' && prev_type != 'sd' && prev_type != null) || (type != 'sd' && prev_type == 'sd'))	 {
				defId = null
				defSection = null
				$('#section_content').html('')
			}

			['cd', 'cc', 'nta', 'sd'].forEach(function(i) {
				if (i == type) {
					map.setLayoutProperty(type + 'FL', 'visibility', 'visible');
					map.setLayoutProperty(type + 'FS', 'visibility', 'visible');
					map.setLayoutProperty(type + 'FH', 'visibility', 'visible');
					map.setLayoutProperty(type + 'FHH', 'visibility', 'visible');
				} else {
					map.setLayoutProperty(i + 'FL', 'visibility', 'none');
					map.setLayoutProperty(i + 'FS', 'visibility', 'none');
					map.setLayoutProperty(i + 'FH', 'visibility', 'none');
					map.setLayoutProperty(i + 'FHH', 'visibility', 'none');
				}
			})
			$('#button-addon3 span').attr('trg', type);

			var id = defId
			defId = null

			var section = defSection ? defSection : 'inherit'
			defSection = null

			if (id) {
				var tmpfilter = ['in', filtFields[type], id]
				mapAction(tmpfilter, type, section, false);
				map.setFilter(type+'FH', tmpfilter);
				//html = $('html').innerHTML()
				//title = '{{ $pagetitle }}';
				//window.history.pushState({'html': html, 'pageTitle': title}, '', '{{ route('districts') }}');
				//window.history.pushState(null, '', '{{ route('districts') }}');
			}

			$('#button-addon3 button').removeClass('active');
			$(`#${type}-button`).addClass('active');

			if (type == 'sd' && prev_type != 'sd') {
				showObjects('{!! $schoolsUrl !!}')
			} else if (type != 'sd' && (prev_type == 'sd' || prev_type == null)) {
				showObjects('{!! $prjUrl !!}');
			}

		}

		$('#toggle_boundries').click( function (e) {
			$(this).next('.dropdown-menu').toggleClass('show');
		})


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


	</script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	<script type="application/ld+json">{!! json_encode($schema ?? []) !!}</script>
@endsection
