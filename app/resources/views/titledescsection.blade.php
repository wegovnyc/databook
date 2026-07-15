@extends('layout')


@section('head')
	<meta name="description" content="{{ $snippet }}" />
	<meta rel="canonical" href="{!! route('titles') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar')
@endsection

@section('content')
	@include('sub.titleheader', ['active' => $section])

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/dataTables.buttons.min.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/buttons/1.6.5/js/buttons.colVis.min.js"></script>
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/1.6.5/css/buttons.dataTables.min.css"/>

	<div class="inner_container">
		<div class="container mb-5" style="padding-top: var(--db-space-3);">
			<div class="db-card" style="padding: var(--db-space-2);">
				<iframe src="https://title-viewer.wegov.nyc/no-menu/?code={{ $titles[0]['Title Code'] }}" frameborder="0" style="overflow:hidden;height:80vh;width:100%;border:0;display:block;" height="100%" width="100%"></iframe>
			</div>
		</div>
		@if (($dataset['Public Note'] ?? null))
			<div class="container mb-3">
				<p class="note_bottom db-page-lead">{{ nl2br($dataset['Public Note']) }}</p>
			</div>
		@endif
		@if ($dataset)
			<div class="container mb-4">
				<p class="bottom_lastupdate db-page-lead"><i class="bi bi-info-circle"></i> This data comes from <a href="{{ $dataset['Citation URL'] }}" target="_blank" rel="nofollow">{{ $dataset['Name'] ?? '' }}</a><span class="float-end" style="font-weight: 300;"><i>Last updated {{ explode(' ', $dataset['Last Updated'])[0] }}</i></span></p>
			</div>
		@endif
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
