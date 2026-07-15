/* Helper functions */

/* Toggle in-map filter panel */
function toggleMapFilterPanel() {
	var panel = document.getElementById('mapFilterPanel');
	var toggleBtn = document.getElementById('mapFilterToggle');
	if (panel) {
		var isHidden = panel.style.display === 'none';
		panel.style.display = isHidden ? 'flex' : 'none';
		if (toggleBtn) {
			toggleBtn.style.display = isHidden ? 'none' : 'block';
		}
	}
}

function unescape(t) {
	return t.replace(/""/g, '"').replace(/''/g, "'")
}

function toDashDate(d) {
	if (!d)
		return ''
	y = d.toString().substr(0, 4)
	m = d.toString().substr(4, 2)
	d = d.toString().substr(6, 2)
	return '<span class="text-nowrap">' + y + '-' + m + '-' + d + '</span>';
}

function toDashDateNowrap(d) {
	if (!d)
		return ''
	y = d.toString().substr(0, 4)
	m = d.toString().substr(4, 2)
	d = d.toString().substr(6, 2)
	return y + '-' + m + '-' + d;
}

function toUsDateNowrap(d) {
	if (!d)
		return ''
	y = d.toString().substr(0, 4)
	m = d.toString().substr(4, 2)
	dd = d.toString().substr(6, 2)
	return m + '/' + dd + '/' + y;
}

function usToDashDate(d) {
	if (!d)
		return ''
	m = d.toString().substr(0, 2)
	dd = d.toString().substr(3, 2)
	y = d.toString().substr(8, 2)
	tt = d.toString().substr(10, 20)
	return '<span class="text-nowrap">20' + y + '-' + m + '-' + dd + tt + '</span>';
}

function usToDashDateNowrap(d, shortYr = false) {
	if (!d)
		return ''
	m = d.toString().substr(0, 2)
	dd = d.toString().substr(3, 2)
	y = shortYr
		? '20' + d.toString().substr(6, 2)
		: d.toString().substr(6, 4)
	return y + '-' + m + '-' + dd;
}

function dashToUsDate(d) {
	if (!d)
		return ''
	m = d.toString().substr(5, 2)
	dd = d.toString().substr(8, 2)
	y = d.toString().substr(2, 2)
	return m + '/' + dd + '/' + y;
}

function toFin(d, m = 1) {
	if (Object.is(d, null) || d === '') return '';
	let val = parseFloat(d);
	if (isNaN(val)) return '';
	return '$' + (val * m).toFixed(0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")
}

function commaThousands(d, m = 1) {
	if (Object.is(d, null) || d === '') return '';
	let val = parseFloat(d);
	if (isNaN(val)) return '';
	return (val * m).toFixed(0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")
}

function toFinShortK(d, m = 1) {
	if (Object.is(d, null) || d === '') return '';
	d = parseFloat(d) * m
	if (isNaN(d)) return '';
	if (d < 1000)
		return '$' + d.toFixed(0)
	var units = { 0: 'K', 1: 'M', 2: 'B' }
	for (let u = 0; u <= 2; u++) {
		d = d / 1000
		if (d < 1000) {
			if (d >= 100) {
				return '$' + d.toFixed(0) + units[u]
			} else if (d >= 10) {
				return '$' + d.toFixed(1) + units[u]
			} else if (d >= 1) {
				return '$' + d.toFixed(2) + units[u]
			}
		}
	}
}

function toPerc(p, a) {
	if (!parseFloat(p))
		return '-'
	return ((parseFloat(a) / parseFloat(p) - 1) * 100).toFixed(0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + '%'
}


function sortUsDatesList(dd, shortYr = false) {
	return dd.sort(function (a, b) {
		aa = usToDashDateNowrap(a, shortYr)
		bb = usToDashDateNowrap(b, shortYr)
		if (aa < bb)
			return -1
		if (aa > bb)
			return 1
		return 0
	})
}



function globStatView(dd) {
	for (const [sel, val] of Object.entries(dd)) {
		ee = $('#' + sel)
		if (!ee.length)
			continue;
		el = ee[0]
		if (sel == 'latest_update') {
			var d = new Date(val);
			var options = {
				year: 'numeric', month: 'numeric', day: 'numeric',
				hour: 'numeric', minute: 'numeric',
				timeZone: 'America/New_York'
			};
			$(el).text(d.toLocaleString('en-US', options));
		}
		else if ($(el).hasClass('gs_fin'))
			$(el).text(toFin(val))
		else if ($(el).hasClass('gs_finshort'))
			$(el).text(toFinShortK(val, $(el).data('multiplier') ? parseFloat($(el).data('multiplier')) : 1))
		else if ($(el).hasClass('gs_perc'))
			$(el).text(toPerc(val))
		else if ($(el).hasClass('gs_thousandscomma'))
			$(el).text(commaThousands(val))
		else
			$(el).text(val)
	}
}


window.onscroll = function () { scrollFunction() }

function scrollFunction() {
	if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
		$('#return-to-top').show()
	} else {
		$('#return-to-top').hide()
	}
}

function topFunction() {
	document.body.scrollTop = 0; // For Safari
	document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
}

function subscribe_newsletter() {
	var email = $('#newsletter-email').val()
	$.get(`/api/newsletter_subscription`, { 'key': 'as9s8d6d78as6f9sdf876', 'email': email }, function (data) {
		var jj = JSON.parse(data)
		if (jj['success']) {
			$('#newsletter-subs div.row').html('<div class="col-sm-12 col-form-label" style="color:#fff;">✓ Thank you for subscribing!</div>');
			$('#newsletter-subs small').html('Your email address');
			$('#newsletter-subs small').attr('style', 'color:white;');
		}
		else {
			$('#newsletter-subs small').html('Failed. Please try again');
			$('#newsletter-subs small').attr('style', 'color:red;');
		}
	})
}

function intWithCommas(x) {
	return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function initPopovers() {
	$('[data-content]').each(function () {
		$(this).attr('data-container', 'body')
		$(this).attr('data-toggle', 'popover')
		$(this).attr('data-placement', 'bottom')
		$(this).popover()
		$(this).on('show.bs.popover', function () {
			$('[data-content]').not(this).popover('hide')
			$('.popover').hide()
		})

	});
}


/** maps ******************************************/


var map = null
var zones = { 'cc': '#9abe0c', 'cd': '#bc2b32', 'nta': '#185892', 'ed': '#a881c2', 'pp': '#be7957', 'dsny': '#d2ac6d', 'fb': '#77aa98', 'sd': '#3e7864', 'hc': '#085732', 'nycongress': '#f3bd1c', 'sa': '#f5912f', 'ss': '#dc2118', 'bid': '#39a6a5', 'zipcode': '#7a7e5a' }
var filtFields = { 'cd': 'nameCol', 'cc': 'nameCol', 'nta': 'nameAlt', 'sd': 'nameCol' }

function newMap() {
	mapboxgl.accessToken = 'pk.REPLACE_WITH_YOUR_MAPBOX_TOKEN';

	var center = (typeof center == 'undefined') ? [-73.957, 40.727] : center;
	var zoom = (typeof zoom == 'undefined') ? 11 : zoom;

	map = new mapboxgl.Map({
		container: 'map',
		style: 'mapbox://styles/mapbox/light-v10',
		center: center,
		zoom: zoom
	});

	// Zoom stepper bottom-right (no compass) so it clears the top-right overlay controls
	map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right');

}


/** org section map ******************************************/

function applyFilterOnClick(e) {
	var chckbox = $('#map-controls input:checked')
	//console.log(chckbox, typeof chckbox)
	if (typeof chckbox.attr('id') == 'undefined') {
		var code = $('#button-addon3 span').attr('trg')
		var col = { 'cc': 'city-council-discretionary', 'cd': 'city-council-discretionary', 'nta': 'city-council-discretionary', 'sd': 'schools' }[code]
	} else {
		var code = chckbox.attr('id').replace('-filter-switch', '')
		var col = chckbox.attr('param')
	}
	var filtField = filtFields[code]

	var bbox = [
		[e.point.x, e.point.y],
		[e.point.x, e.point.y]
	];
	var features = map.queryRenderedFeatures(bbox, {
		layers: [code + 'FHH']
	});

	var filter = features.reduce(
		function (memo, feature) {
			memo.push(feature.properties[filtField]);
			return memo;
		},
		['in', filtField]
	);

	mapAction(filter, code, col);

	map.setFilter(code + 'FH', filter);
}


function orgSectionMapInit(filters, filterType) {
	newMap();

	$('select, option').click(function (e) {
		e.stopPropagation();
	});

	var geojson = { 'type': 'FeatureCollection', 'features': [] };

	/*
	if (filterType == 'sd')
		schoolsMapInit(true);
	else
	*/
	projectsMapInit(true);

	map.on('load', function () {

		for (const [code, clr] of Object.entries(zones)) {
			setBoundary(code, clr, clr);
		}

		for (const [code, col] of Object.entries(filters)) {
			setFilter(code, col);
		}

		if (typeof filterType == 'undefined')
			window.setTimeout(function () {
				if (!$('#map-controls div:nth-child(2) input:checked').length)
					$('#map-controls div:nth-child(2) input')[0].click();
			}, 500
			)
		else
			window.setTimeout(function () {
				//	enable preset filter
				$(`#${filterType}-filter-switch`).click();
				$(`#${filterType}-button`).click();
			}, 500
			)

		map.on('click', function (e) { applyFilterOnClick(e); })

	});

}

function setBoundary(code, lineClr, symbClr) {

	map.addSource(code, {
		type: "geojson",
		data: `/data/${code}.geojson`
	});

	map.addLayer({
		"id": code + 'L',
		"type": "line",
		"source": code,
		"layout": {
			'visibility': 'none',
		},
		"paint": {
			"line-color": lineClr,
			"line-width": 1
		}
	});

	map.addLayer({
		"id": code + 'S',
		"type": "symbol",
		"source": code,
		"layout": {
			'text-field': '{nameCol}',
			'visibility': 'none',
			'text-size': {
				"base": 1,
				"stops": [
					[12, 12],
					[16, 16]
				]
			},
		},
		"paint": {
			"text-color": symbClr,
			"text-halo-color": "hsl(0, 0%, 100%)",
			"text-halo-width": 0.5,
			"text-halo-blur": 1
		}
	});

	$(`#${code}-switch`).change(function () {
		if ($(this).is(':checked')) {
			map.setLayoutProperty(code + 'L', 'visibility', 'visible');
			map.setLayoutProperty(code + 'S', 'visibility', 'visible');
		} else {
			map.setLayoutProperty(code + 'L', 'visibility', 'none');
			map.setLayoutProperty(code + 'S', 'visibility', 'none');
		}
	});

	$(`label[for="${code}-switch"] hr`).attr('style', `background-color: ${lineClr};`);
}

function setFilter(code, col) {
	var clr = zones[code]
	var filtField = filtFields[code]
	map.addLayer({
		"id": code + 'FH',
		"type": "fill",
		"source": code,
		"layout": {
			'visibility': 'none',
		},
		'paint': {
			'fill-outline-color': clr,
			'fill-color': clr,
			'fill-opacity': 0.4
		},
		'filter': ['in', filtField, '']
	},
		'settlement-label'
	);

	var filter = ['has', 'nameCol']

	if (typeof datatable != 'undefined') {
		datatable.columns([col]).every(function (c, a, i) {
			var vv = []
			this.data().each(function (d, j) {
				d = typeof d == 'string' ? d.replace(/<[^>]+>/gi, '') : d
				if (d)
					vv.push(d)
			})
			vv = [...new Set(vv)]
			filter = vv.reduce(
				function (memo, v) {
					memo.push(v);
					return memo;
				},
				['in', filtField]
			);
		});
	}

	map.addLayer({
		"id": code + 'FHH',
		"type": "fill",
		"source": code,
		"layout": {
			'visibility': 'none',
		},
		'paint': {
			'fill-color': clr,
			'fill-opacity': 0.3
		},
		'filter': filter
	},
		'settlement-label'
	);
	map.addLayer({
		"id": code + 'FL',
		"type": "line",
		"source": code,
		"layout": {
			'visibility': 'none',
		},
		"paint": {
			"line-color": clr,
			"line-width": 1
		},
		'filter': filter
	},
		'settlement-label'
	);
	map.addLayer({
		"id": code + 'FS',
		"type": "symbol",
		"source": code,
		"layout": {
			'text-field': '{nameCol}',
			'visibility': 'none',
			'text-size': {
				"base": 1,
				"stops": [
					[12, 12],
					[16, 16]
				]
			},
		},
		"paint": {
			"text-color": clr,
			"text-halo-color": "hsl(0, 0%, 100%)",
			"text-halo-width": 0.5,
			"text-halo-blur": 1
		},
		'filter': filter
	},
		'settlement-label'
	);

}
/** /org section map ******************************************/



/** projects map ******************************************/

var popup = null
function mapPopup(e) {
	var obj = e.features[0].properties;
	//console.log('mapPopup', obj);
	var description = ('SCHOOL_ID' in obj)

		? `
		<table><tbody>
			<tr><th scope="row">Name</th><td><a href="/s/${obj.SCHOOL_ID}-${slug(obj.NAME)}">${obj.NAME}</a></td></tr>
			<tr>
				<th scope="row">School District</th>
				<td><a href="/d/sd-${obj.SCHOOL_DISTRICT}-${slug('COMMUNITY SCHOOL DISTRICT ' + obj.SCHOOL_DISTRICT)}/schools">${obj.SCHOOL_DISTRICT}</a></td>
			</tr>
			<tr><th scope="row">Type</th><td>${obj.TYPE}</td></tr>
			<tr><th scope="row">Category</th><td>${obj.CATEGORY}</td></tr>
			<tr><th scope="row">Principal Name</th><td>${obj.PRINCIPAL_NAME}</td></tr>
			<tr><th scope="row">Phone</th><td>${obj.PRINCIPAL_PHONE}</td></tr>
		</tbody></table>`

		: `<table><tbody>
		<tr><th scope="row">Name</th><td><a href="/p/${obj.PRJ_ID}_${slug(obj.NAME)}">${obj.NAME}</a></td></tr>
		<tr><th scope="row">Agency</th><td>${obj.AGENCY}</td></tr>
		<tr><th scope="row">Category</th><td>${obj.CATEGORY}</td></tr>
		<tr><th scope="row" class="pr-2">Planned Cost</th><td data-content="${toFin(obj.PLANNEDCOST.replaceAll(',', ''), 1)}">${toFinShortK(obj.PLANNEDCOST.replaceAll(',', ''), 1)}</td></tr>
		<tr><th scope="row">Start</th><td>${obj.START_CURR}</td></tr>
		<tr><th scope="row">End</th><td>${obj.END_CURR}</td></tr>
	</tbody></table>`;

	map.fitBounds([
		[obj.W, obj.S],
		[obj.E, obj.N]
	], {
		padding: [50, 50],
		maxZoom: 18,
		duration: 1000,
		animate: true,
		essential: true,
	});

	if (popup)
		popup.remove();

	popup = new mapboxgl.Popup()
		.setLngLat(e.lngLat)
		.setHTML(description)
		.addTo(map);
	initPopovers();
	e.stopPropagation();
}


function projectsMapInit(as_addon = false) {
	if (!as_addon)
		newMap();

	map.on('load', function () {
		map.addSource('route', {
			type: "geojson",
			data: {
				"type": "FeatureCollection",
				"features": [{ "type": "Feature", "properties": { "custom_color": "#C0DDC0" }, "geometry": { "type": "Point", "coordinates": ["-73.95098200", "40.82387280"] } }]
			}
		});
		map.addLayer({
			'id': 'markers',
			'type': 'circle',
			'source': 'route',
			'paint': {
				'circle-radius': 5,
				'circle-color': ['get', 'custom_color']
			},
			'filter': ['==', '$type', 'Point']
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
				'line-color': ['get', 'custom_color'],
				'line-width': 5
			},
			'filter': ['==', '$type', 'LineString']
		});

		map.addLayer({
			'id': 'areas',
			'type': 'fill',
			'source': 'route',
			'paint': {
				'fill-color': ['get', 'custom_color'],
				'fill-opacity': 0.75
			},
			'filter': ['==', '$type', 'Polygon']
		});
		map.on('zoom', () => {
			var z = map.getZoom();
			const zz = { 12: 6, 11: 5, 10: 4, 9: 3, 8: 2 }
			for (const [l, r] of Object.entries(zz)) {
				if (z > l) {
					map.setPaintProperty('markers', 'circle-radius', r);
					map.setPaintProperty('streets', 'line-width', r);
				}
			}
		});

		map.on('click', 'areas', mapPopup);
		map.on('click', 'streets', mapPopup);
		map.on('click', 'markers', mapPopup);

		// Change the cursor to a pointer when the mouse is over the places layer.
		map.on('mouseenter', 'streets', function () { map.getCanvas().style.cursor = 'pointer'; });
		map.on('mouseenter', 'markers', function () { map.getCanvas().style.cursor = 'pointer'; });
		map.on('mouseenter', 'areas', function () { map.getCanvas().style.cursor = 'pointer'; });

		// Change it back to a pointer when it leaves.
		map.on('mouseleave', 'streets', function () { map.getCanvas().style.cursor = ''; });
		map.on('mouseleave', 'markers', function () { map.getCanvas().style.cursor = ''; });
		map.on('mouseleave', 'areas', function () { map.getCanvas().style.cursor = ''; });

		if (!as_addon) {
			for (const [code, clr] of Object.entries(zones)) {
				setBoundary(code, clr, clr);
			}
		}
	});
}


function schoolsMapDrawFeatures(dd, do_fitbounds = true) {
	projectsMapDrawFeatures(dd, do_fitbounds);
}


function projectsMapDrawFeatures(dd, do_fitbounds = true) {
	var bounds = [[360, 180], [-360, -180]];
	//var colors_depr = ['#ecd078', '#d95b43', '#c02942', '#542437', '#53777a', '#f5ae33', '#99ac40', '#ff7c7c', '#78c0a8', '#7a6a53', '#6c5b7b', '#c06c84', '#d2ff0f', '#f2c45a', '#3b2d38', '#b8af03', '#d1e751', '#ff3a31', '#99b59a', '#676970', '#ecd078', '#618eff', '#7dffff', '#f07241', '#bcbcbc'];

	dd.forEach(function (el, i) {
		if (!el.properties)
			console.log('undefined props', el)
		bounds[0][0] = Math.min(bounds[0][0], el.properties.W - 0.01);
		bounds[0][1] = Math.min(bounds[0][1], el.properties.S - 0.01);
		bounds[1][0] = Math.max(bounds[1][0], el.properties.E + 0.01);
		bounds[1][1] = Math.max(bounds[1][1], el.properties.N + 0.01);
		//dd[i].properties.custom_color = colors[i % 25]
		dd[i].properties.custom_color = (dd[i].properties.custom_color ?? null) ? dd[i].properties.custom_color : '#53777a';
	});

	if (bounds[0][0] == 360)
		bounds = [[-74.05395, 40.68309], [-73.944433, 40.797808]]

	bounds[0][0] = Math.max(bounds[0][0], -74.275);
	bounds[0][1] = Math.max(bounds[0][1], 40.503);
	bounds[1][0] = Math.min(bounds[1][0], -73.690);
	bounds[1][1] = Math.min(bounds[1][1], 40.974);

	var src = map.getSource('route')
	src.setData({ "type": "FeatureCollection", "features": dd });
	if (popup)
		popup.remove();
	if (do_fitbounds)
		map.fitBounds(bounds, {
			padding: [50, 50],
			maxZoom: 18,
			duration: 1000,
			animate: true,
			essential: true,
		});
}


function fitBounds(bounds) {
	map.fitBounds(bounds);
}


/** /projects map ******************************************/


/** share button ******************************************/

function copyLinkM(a, sel = "details-permalink") {
	var el = document.getElementById(sel);
	el.select();
	el.setSelectionRange(0, 99999);
	document.execCommand("copy");
	$(a).find('.share_icon_container').popover('show')
	setTimeout(function () {
		$(a).find('.share_icon_container').popover('hide')
	}, 3000);
	event.stopPropagation()
}

function copyLink() {
	var el = document.getElementById("details-permalink");
	el.select();
	el.setSelectionRange(0, 99999);
	document.execCommand("copy");
	$('.share_icon_container').popover('show')
	setTimeout(function () {
		$('.share_icon_container').popover('hide')
	}, 3000);
}

/** /share button ******************************************/

/** fapi requests ******************************************/
function fapireq(url, cb) {
	$.ajax({
		url: url,
		success: function (data) {
			//console.log('raw', data)
			cb(data['rows'] ? { 'data': data['rows'] } : [])
		},
		error: function (jqXHR, textStatus, errorThrown) {
			cb({ 'data': [], 'error': errorThrown })
		}
	})
}
/** /fapi requests ******************************************/


/** slugged urls ******************************************/
function slug(n) {
	return n ? n.toString().toLowerCase().replace(/\s+/g, '-').replace(/[^-\w]/g, '') : ''
}
/** /fapi requests ******************************************/
