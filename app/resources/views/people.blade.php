@extends('layout')


@section('head')
	<meta name="description" content="The roles, positions and pay of NYC's civil servants" />
	<meta rel="canonical" href="{!! route('people') !!}" />
	<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/orgchart/3.1.1/css/jquery.orgchart.min.css" integrity="sha512-bCaZ8dJsDR+slK3QXmhjnPDREpFaClf3mihutFGH+RxkAcquLyd9iwewxWQuWuP5rumVRl7iGbSDuiTvjH1kLw==" crossorigin="anonymous" referrerpolicy="no-referrer" />
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>
	
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'orgs'])
@endsection

@section('content')

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	
	<script src="https://cdnjs.cloudflare.com/ajax/libs/orgchart/3.1.1/js/jquery.orgchart.min.js" integrity="sha512-alnBKIRc2t6LkXj07dy2CLCByKoMYf2eQ5hLpDmjoqO44d3JF8LSM4PptrgvohTQT0LzKdRasI/wgLN0ONNgmA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/0.5.0-beta4/html2canvas.min.js" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
	
	<script>
		var table = null
		var tblCode = {'civillist': 'cl', 'civillistactive': 'cla', 'nycgreenbook': 'gb', 'payrolldata': 'pr'}
		var tblNames = {'civillist': 'Civil List', 'civillistactive': 'Civil List Active', 'nycgreenbook': 'Greenbook', 'payrolldata': 'Payroll Data'}

		$(document).ready(function() {
			table = $('#titlesTable').DataTable( {
				pageLength: 5,
				deferRender: true,
				order: [[5, 'desc']],
				dom: '<"toolbar"<"row">>frtip',
				ajax: function (url, cb) {
					fapireq("{!! $url !!}", cb);
			    },
					
				columns: [
					{data: function (r) { return `<a href="/t/${r["Title Code"]}">${r["Title Code"]}</a>` }},
					{data: 'Title Description'},
					{data: 'Standard Hours'},
					{data: 'Assignment Level'},
					{data: function (r) { return r["wegov-org-id"] 
									? `<a href="/o/${r["wegov-org-id"]}-${slug(r["wegov-org-name"])}">${r["wegov-org-name"]}</a>` 
									: `<a disabled>${r["Bargaining Unit Description"]}</a>` 
								}},
					{data: 'positions'},
					{data: 'Union Description'},
					{data: function (r) { return toFin(r['Minimum Salary Rate']) }},
					{data: function (r) { return toFin(r['Maximum Salary Rate']) }}
                ],
				@if ($defSearch ?? null)
					search: {
						'search': '{{ $defSearch }}'
				    },
				@endif	

				initComplete: function () {
					this.api().columns([4]).every(function () {
						var column = this;
						var select = $('<select class="filter-top" id="filter-' + column[0][0] + '"><option value="">- Select positions by Bargaining Unit -</option></select>')
							.appendTo($('div.toolbar'))
							.on('change', function () {
								var val = $(this).val()
								column
									.search(val ? val : '', false, false)
									.draw();
							});
						var tt = []

						rg = />([^<]+)</g;
						column.data().each(function (d, j) {
							while ((t = rg.exec(d)) !== null) {
								tt.push(t[1])
							}
						})
						tt = [...new Set(tt)]

						tt.sort().forEach(function (d, j) {
							select.append( '<option value="'+d+'">'+d+'</option>' )
						});
						@if($defUnion ?? null)
							setTimeout(function(){
								select.val('{!! $defUnion !!}')
								select.trigger('change')
							}, 700);
						@endif
					});
				}
			});
		});
		
		function peopleFormSubmit() {
			var url = '{!! route('peopleSearchTbl', ['req'=>'RRRR', 'tbl'=>'TTTT']) !!}'
			var req = $('#peopleSearch').val().toLowerCase()
			var tbl = 'all'
			url = url.replace('RRRR', encodeURIComponent(req).replaceAll('%20', '+')).replace('TTTT', tbl)
			//console.log(url)
			window.location.href = url
		}
	</script>
<div class="inner_container">
	<div class="mt-4 mb-4 mx-3">
		<div class="db-eyebrow">People</div>
		<h1 class="main_hdr">People</h1>

		<div class="row mt-4">
			<!-- Search for Individuals -->
			<div class="col-md-6 mb-4">
				<div class="db-card h-100">
					<div class="db-card-body">
						<h5 class="db-card-title">Search for Individuals</h5>
						<p class="card-text">Find people who work in New York City government or have applied to work in it.</p>
						<div class="db-filter-bar mt-3">
							<div class="db-search" style="flex: 1 1 auto;">
								<i class="bi bi-search"></i>
								<input type="search" id="peopleSearch" placeholder="Search people…" aria-label="Search people" @if($req ?? null ) value="{!! $req !!}" @endif>
							</div>
							<button type="button" class="db-btn db-btn-primary" onclick="peopleFormSubmit();">Search</button>
						</div>
					</div>
				</div>
			</div>

			<!-- Search for Titles -->
			<div class="col-md-6 mb-4">
				<div class="db-card h-100">
					<div class="db-card-body">
						<h5 class="db-card-title">Search for Titles</h5>
						<p class="card-text">Titles are the official descriptions of the work that city employees perform.</p>
						<a href="{!! route('titles') !!}" class="db-btn db-btn-outline mt-3">View Titles</a>
					</div>
				</div>
			</div>
		</div>
	</div>


	<div class="container mb-5">
		<h5 class="mt-5">Organizational Chart</h5>
		<p>New York City has the largest municipal government in the USA, employing over 300,000 people in over 160 different organizations.</p>
		<p>This interactive chart is modeled after the city’s <a href="https://www1.nyc.gov/assets/home/downloads/pdf/office-of-the-mayor/misc/NYC-Organizational-Chart.pdf" target="_blank">official organization chart</a>. It documents the relationship between city officials and agencies. Click and drag to view the full chart and click on the entities to see their WeGov profiles.</p>
		
		<div id="chart-container" style="height: 1200px!important; margin-bottom: 25px;"></div>

		<a href="{!! route('orgs') !!}" class="db-btn db-btn-outline db-btn-sm" role="button">More Organizations</a>
	</div>
</div>

<script>
		var oc = $('#chart-container').orgchart({
		  'data' : '/data/orgChart.json',
		  nodeContent: 'title',
		  pan: true,
		  verticalLevel: 4,
		  visibleLevel: 20
		});
		@if ($defId ?? null)
			$('#chart-container').on('init.orgchart', function() {
				setTimeout(function () {
					$('a[href*="{{ $defId }}"]').parent().parent().attr('class', 'node node_focused');
					var w = window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;
					var h = window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight;
					var l = $('.node_focused').offset().left;
					var t = $('.node_focused').offset().top;
					var offX = (w - 160)/2 - l;
					var offY = Math.min(t, h/2) - t;
					console.log(w,'w')
					$('.orgchart').attr('style', 'cursor:default; transform: matrix(1, 0, 0, 1, '+offX+', '+offY+');')
				}, 1000);
			});
		@endif
		$(document).ready(function() {
			$('.orgchart').mousedown(function(e) {
				$(this).css('cursor', 'grabbing');
				setTimeout(function () {
					var element = document.querySelector('.orgchart');
					var matrix = window.getComputedStyle(element).transform;
					var matrixArray = matrix.replace("matrix(", "").split(",");
					var scaleX = parseFloat(matrixArray[0]); // convert from string to number
					var scaleY = parseFloat(matrixArray[3]);
					var translateX = parseFloat(matrixArray[4]);
					var translateY = parseFloat(matrixArray[5])
					var node_width = $('ul .nodes').width();
					var boundary = element.getBoundingClientRect().width
					console.log($('ul .nodes').width(),element.getBoundingClientRect().width,boundary-node_width);
					if(translateY > 0){
						$('.orgchart').attr('style', 'cursor:default; transform: matrix(1, 0, 0, 1, '+translateX+', 0);')
					}
					if(translateX > 0){
						$('.orgchart').attr('style', 'cursor:default; transform: matrix(1, 0, 0, 1, 0, '+translateY+');')
					}
					if((boundary-node_width) > translateX){
						$('.orgchart').attr('style', 'cursor:default; transform: matrix(1, 0, 0, 1, '+(boundary-node_width - 20)+', 0);')
					}
					if(translateY > 0 && translateX > 0){
						$('.orgchart').attr('style', 'cursor:default; transform: matrix(1, 0, 0, 1, 0,0);')
					}
				}, 1000);
			});
			$('.orgchart').mouseup(function(e) {
				setTimeout(() => {
					$(this).css('cursor', 'grab');
				},5);
			});
		});
</script>

	
@endsection
