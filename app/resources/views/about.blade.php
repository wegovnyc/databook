@extends('layout')


@section('head')
	<meta name="description" content="Databook combines dozens of open datasets to help people better understand New York City’s government." />
	<meta rel="canonical" href="{!! route('about') !!}" />
@endsection


@section('menubar')
	@include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
	<div class="jumbotron mb-1">
		<div class="row">
			<div class="col-lg-7 col-md-9">
				<div class="bg-white p-5 rounded shadow-sm">
					<h1 class="display-4 mb-4">About</h1>
					<p class="lead">WeGovNYC is an organizing initiative bringing public interest and civic technologists together to make New York City the best run municipality in the world.</p>
					<p class="lead">Through a combination of community building, product development and issue advocacy, WeGov advances a vision of an open source city that efficiently delivers projects and services to its residents, provides leadership to its region and actively contributes its knowledge to improve solutions for cities around the world.</p>
					<hr class="my-4">
					<p class="lead">Our initiative’s three main constituencies are:</p>
					<ul>
						<li class="lead">public servants in a position to advocate for and advance free and open source solutions within city government.</li>
						<li class="lead">concerned citizens who want to help advance an open source digital transformation of New York City.</li>
						<li class="lead">policy makers who want to use technology to improve the lives of the New Yorkers they serve.</li>
					</ul>
				</div>
			</div>
		</div>
	</div>

	<div class="row mb-5">
		<div class="col-12">
			<div class="bg-white p-4 rounded shadow-sm">
				<h2 class="mb-4">Data Sources</h2>
				<div class="table-responsive">
					<table id="datasetsTable" class="display table-striped table-hover" style="width:100%;">
						<thead>
							<tr>
								<th>Name</th>
								<th>Internal Link</th>
								<th>Description</th>
								<th>Section</th>
								<th>Last Updated</th>
								<th>Agency Records</th>
							</tr>
						</thead>
					</table>
				</div>
			</div>
		</div>
	</div>

	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/rowgroup/1.1.4/js/dataTables.rowGroup.min.js"></script>

	<script>
		var datasets = {!! json_encode($datasets) !!};
		
		$(document).ready(function() {
			$('#datasetsTable').DataTable({
				data: datasets,
				paging: false,
				columns: [
					{ title: "Name" },
					{ title: "Internal Link" },
					{ title: "Description" },
					{ title: "Section", visible: false },
					{ title: "Last Updated" },
					{ title: "Agency Records", visible: false }
				],
				order: [],
				rowGroup: { dataSrc: 3 },
				dom: 'rtp',
			});
		});
	</script>
</div>
@endsection
