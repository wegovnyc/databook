@extends('layout')


@section('head')
	<meta name="description" content="{{ $snippet }}" />
	<meta rel="canonical" href="{!! $canonicalUrl !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	@if($org ?? [])
		@include('sub.orgheader', ['active' => $section])
	@endif
	<div class="inner_container">
		<div class="container">
			<div class="row justify-content-center">
				<div class="col-md-12 organization_data">
					<p>This dataset contains capital commitment plan data by project type, budget line and source of funds. The dollar values are in thousands. The dataset is updated three times per year in Preliminary, Executive and Adopted Budget to match commitment numbers in the Capital Commitment Plan publication.</p>
					<h1>{{ $prj['description'] }} <small>({{ $prj['projectid'] }})</small></h1>
				</div>
			</div>
			
			<div class="row justify-content-center">

				<div id="capproject_profile" class="col-md-8 col-sm-12">

					<div class="table-responsive mb-4">
						<table width="100%" class="mb-5 mt-0" id="project_data">
							<thead>
								<tr>
									<th scope="row">Total City Planned Commitment</th>
									<td id="totalplannedcommit"></td>
								</tr>
								<tr>
									<th scope="row">Min Date</th>
									<td id="mindate">{{ $prj['mindate'] }}</td>
								</tr>
								<tr>
									<th scope="row">Max Date</th>
									<td id="maxdate">{{ $prj['maxdate'] }}</td>
								</tr>
								<tr>
									<th scope="row">Agency</th>
									@if($prj['wegov-org-name'])
										<td><a href="{{ route('orgProfileDepr', ['id' => $prj['wegov-org-id']]) }}" id="wegov-org-name">{{ $prj['wegov-org-name'] }}</a></td>
									@else
										<td>-</td>
									@endif
								</tr>
								<tr>
									<th scope="row">City Nonexempt</th>
									<td id="ccnonexempt"></td>
								</tr>
								<tr>
									<th scope="row">State Cost</th>
									<td id="nccstate"></td>
								</tr>
								<tr>
									<th scope="row">Total Noncity Planned</th>
									<td id="totalnoncityplannedcommit"></td>
								</tr>
								<tr>
									<th scope="row">Type Category</th>
									<td id="typecategory">{{ $prj['typecategory'] }}</td>
								</tr>
								<tr>
									<th scope="row">Version</th>
									<td id="ccpversion">{{ $prj['ccpversion'] }}</td>
								</tr>
							</thead>
							<tbody>
							</tbody>
						</table>
					</div>

					<div class="table-responsive my-4 mb-5">
						<h4>Commitments</h4>
						<table width="100%" class="mb-3 mt-0" id="commitments">
							<thead>
								<tr>
									<th scope="col"></th>
									<th scope="col">Description</th>
									<th scope="col">Plan Commitment Date</th>
									<th scope="col">Commitment Description</th>
									<th scope="col">Commitment Type</th>
									<th scope="col">Total Planned Commit</th>
								</tr>
							</thead>
							<tbody>
							</tbody>
						</table>
					</div>

					<div class="my-5">
{{-- 
						<div id="disqus_thread"></div>
						<script>
							/**
							*  RECOMMENDED CONFIGURATION VARIABLES: EDIT AND UNCOMMENT THE SECTION BELOW TO INSERT DYNAMIC VALUES FROM YOUR PLATFORM OR CMS.
							*  LEARN WHY DEFINING THESE VARIABLES IS IMPORTANT: https://disqus.com/admin/universalcode/#configuration-variables    */
							
							var disqus_config = function () {
							this.page.url = '{!! $canonicalUrl !!}';  // Replace PAGE_URL with your page's canonical URL variable
							this.page.identifier = '{{ $prjId }}'; // Replace PAGE_IDENTIFIER with your page's unique identifier variable
							};
							
							(function() { // DON'T EDIT BELOW THIS LINE
							var d = document, s = d.createElement('script');
							s.src = 'https://databook-wegov-nyc.disqus.com/embed.js';
							s.setAttribute('data-timestamp', +new Date());
							(d.head || d.body).appendChild(s);
							})();
						</script>
						<noscript>Please enable JavaScript to view the <a href="https://disqus.com/?ref_noscript" rel="nofollow">comments powered by Disqus.</a></noscript>				
 --}}
					</div>
				</div>

				<div class="col-md-4 col-sm-12 p-0">
					<div id="map_container" style="float:none;">
						<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;border:2px solid #112F4E;"></div>
					</div>
					<p class="suggest_button mt-4"><a href="https://airtable.com/shrWWa3rNJFGSFObd?prefill_project_id={{ $prjId }}" class="learn_more" target="_blank" rel="nofollow">Suggest a Change</a></p>
				</div>

			</div>
		</div>

		<div class="col-md-12">
			<div class="bottom_lastupdate">
		@if ($dataset)
				<p class="lead"><img src="/img/info.png" alt=""> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a><span class="float-right" style="font-weight: 300;"><i>Last updated {{ explode(' ', $dataset['Last Updated'] ?? '')[0] }}</i></span></p>
			</div>
		</div>
	</div>
		@endif
<style>
	#map_container #map {height: 800px !important;}
</style>
@endsection



@section('scripts')

	<script>
		/*
		function details(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
				(d["maprojid"] 		? '<tr><td>maprojid:</td><td>'+d["maprojid"]+'</td></tr>' : '') +
				(d["ccnonexempt"] 	? '<tr><td>ccnonexempt:</td><td>'+d["ccnonexempt"]+'</td></tr>' : '') +
				(d["ccexempt"] 		? '<tr><td>ccexempt:</td><td>'+d["ccexempt"]+'</td></tr>' : '') +
				(d["nccstate"] 		? '<tr><td>nccstate:</td><td>'+d["nccstate"]+'</td></tr>' : '') +
				(d["nccfederal"] 	? '<tr><td>nccfederal:</td><td>'+d["nccfederal"]+'</td></tr>' : '') +
				(d["nccother"] 		? '<tr><td>nccother:</td><td>'+d["nccother"]+'</td></tr>' : '') +
				(d["totalnoncityplannedcommit"] ? '<tr><td>totalnoncityplannedcommit:</td><td>'+d["totalnoncityplannedcommit"]+'</td></tr>' : '') +
				(d["totalplannedcommit"] ? '<tr><td>totalplannedcommit:</td><td>'+d["totalplannedcommit"]+'</td></tr>' : '') +
				(d["totalspend"] 	? '<tr><td>totalspend:</td><td>'+d["totalspend"]+'</td></tr>' : '') +
				(d["typecategory"] 	? '<tr><td>typecategory:</td><td>'+d["typecategory"]+'</td></tr>' : '') +
				(d["ccpversion"] 	? '<tr><td>ccpversion:</td><td>'+d["ccpversion"]+'</td></tr>' : '') +
			'</table>';
		}
		*/

		function commDetails(d) {
			return '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
				(d["maprojid"] 		? '<tr><td>Full Project ID:</td><td>'+d["maprojid"]+'</td></tr>' : '') +
				(d["typc"] 			? '<tr><td>Type Code:</td><td>'+d["typc"]+'</td></tr>' : '') +
				(d["typcname"] 		? '<tr><td>Type Code Name:</td><td>'+d["typcname"]+'</td></tr>' : '') +
				(d["ccnonexempt"] 	? '<tr><td>City Nonexempt:</td><td>'+toFin(d["ccnonexempt"])+'</td></tr>' : '') +
				(d["ccexempt"] 		? '<tr><td>City Exempt:</td><td>'+toFin(d["ccexempt"])+'</td></tr>' : '') +
				(d["totalcityplannedcommit"] ? '<tr><td>Total City Planned:</td><td>'+toFin(d["totalcityplannedcommit"])+'</td></tr>' : '') +
				(d["nccstate"] 		? '<tr><td>State Cost:</td><td>'+d["nccstate"]+'</td></tr>' : '') +
				(d["nccfederal"] 	? '<tr><td>Federal Cost:</td><td>'+d["nccfederal"]+'</td></tr>' : '') +
				(d["nccother"] 		? '<tr><td>Other Cost:</td><td>'+d["nccother"]+'</td></tr>' : '') +
				(d["totalnoncityplannedcommit"] ? '<tr><td>Total Noncity Planned:</td><td>'+d["totalnoncityplannedcommit"]+'</td></tr>' : '') +
				(d["sagencyname"] 	? '<tr><td>Agency Name:</td><td>'+d["sagencyname"]+'</td></tr>' : '') +
				(d["ccpversion"] 	? '<tr><td>Version:</td><td>'+d["ccpversion"]+'</td></tr>' : '') +
			'</table>';
		}

		//var datatable = null
		var data = {!! json_encode($prj) !!}
		var commTable = null

		$(document).ready(function() {
			/*
			datatable = $('#project_data').DataTable({
				data: {!! json_encode($prj) !!},
				deferRender: true,
				dom: 'rt',
				columns: [
					{
						"className": 'details-control',
						"orderable": false,
						"data":  null,
						"defaultContent": ''
					},
					{data: 'maprojid'},
					{data: 'totalcityplannedcommit'},
					{data: 'maxdate'},
					{data: 'mindate'},
					{data: 'wegov-org-name'},
                ],

			});
			
			*/
			
			var ff = ['totalplannedcommit', 'ccnonexempt', 'nccstate', 'totalnoncityplannedcommit']
			ff.forEach(function (f, i) {
				$(`#${f}`).text(data[f] ? toFin(data[f]) : '-')
			})
									
			
			
			@if ($prj['GEO_JSON'] ?? null)
				const feature = {!! $prj['GEO_JSON'] !!}
				var bounds = [[feature.properties.W, feature.properties.S], [feature.properties.E, feature.properties.N]]
				var features = []
				if (feature.geometry.type != 'MultiPolygon') 
					features = [feature]
				else {
					feature.geometry.coordinates.forEach(function (c) {
						var subgj = JSON.parse(JSON.stringify(feature))
						subgj.geometry.type = 'Polygon'
						subgj.geometry.coordinates = c
						features.push(subgj)
					})
				}
			
				mapboxgl.accessToken = 'pk.REPLACE_WITH_YOUR_MAPBOX_TOKEN';

				map = new mapboxgl.Map({
					container: 'map',
					style: 'mapbox://styles/mapbox/light-v10',
					center: [-73.99255747855759,40.58992167435116],
					zoom: 10
				});
				map.addControl(new mapboxgl.NavigationControl());

				map.on('load', function () {
					map.addSource('route', {
							"type": "geojson",
							"data": {
								"type": "FeatureCollection",
								"features": features
							}
						});

					map.addLayer({
						'id': 'streets',
						'type': 'line',
						'source': 'route',
						'layout': {
							'line-join': 'round',
							'line-cap': 'round'
						},
						'paint': {
							'line-color': '#53777a',
							'line-width': 6
						},
						'filter': ['==', '$type', 'LineString']
					});

					map.addLayer({
						'id': 'markers',
						'type': 'circle',
						'source': 'route',
						'paint': {
							'circle-radius': 6,
							'circle-color': '#53777a'
						},
						'filter': ['==', '$type', 'Point']
					});

					map.addLayer({
						'id': 'areas',
						'type': 'fill',
						'source': 'route',
						'paint': {
							'fill-color': '#53777a',
							'fill-opacity': 1
						},
						'filter': ['==', '$type', 'Polygon']
					});
					
					for (const [code, clr] of Object.entries(zones)) {
						setBoundary(code, clr, clr);
					}
					$('#toggles').show();

					map.fitBounds(bounds);
				});
			@else
				$('#map').attr('class', 'no-geo');
				$('#map').html('<iframe class="airtable-embed" src="https://airtable.com/embed/shreZusmuYwJNl76Q?prefill_project_id={{ $prjId }}&backgroundColor=blue" frameborder="0" onmousewheel="" width="100%" height="100%" style="background: transparent;"></iframe>');
				$('.suggest_button').remove();
			@endif
			

			commTable = $('#commitments').DataTable({
				ajax: function (url, cb) {
					fapireq("{!! $commUrl !!}", cb);
			    },
				deferRender: true,
				dom: '<"toolbar container-flex"<"row">>rt',
				columns: [
					{
						"className": 'details-control',
						"orderable": false,
						"data":  null,
						"defaultContent": ''
					},
					{data: 'description'},
					{data: 'plancommdate'},
					{data: 'commitmentdescription'},
					{data: 'typcname'},
					{data: function (r) { return toFin(r['totalplannedcommit']) }, type: 'html'}
                ]
			});


			$('#commitments tbody').on('click', 'td.details-control', function () {
				var tr = $(this).closest('tr');
				var row = commTable.row(tr);

				if (row.child.isShown()) {
					row.child.hide();
					tr.removeClass('shown');
                    tr.next('tr').removeClass('child-row');
				}
				else {
					row.child(commDetails(row.data())).show();
					tr.addClass('shown');
                    tr.next('tr').addClass('child-row');
				}
			});

		});

	</script>
	<script type="application/ld+json">{!! json_encode($schema ?? []) !!}</script>

@endsection


