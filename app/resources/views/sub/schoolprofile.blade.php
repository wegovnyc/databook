<div class="inner_container">


	<div class="row justify-content-center map_right">

		@if ($school['LATITUDE'] ?? null)
			<div id="map_container" class="col-lg-5 col-md-12 col-sm-12 col-12 mt-4" style="display:block; min-height:410px;">
				<!--
				<button id="map_button_alt" class="btn btn-outline map_btn" style="margin:0 20px 20px 10px; z-index: 10; max-width: 40px; float:right;" onclick="toggleMap();"><img src="/img/map_location.png" alt=""></button>
				-->
				<!-- toggles -->
				<div class="select_district" id="toggles" style="left:0px; top:10px;">
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
				<div id="map" class="map flex-fill d-flex" style="width:100%;height:100%;border:4px solid #112F4E; position:relative; min-height:400px;"></div>
			</div>
		@endif

		<div class="col-lg-7 col-md-12 col-sm-12 col-12">
			<div class="db-profile-main mb-3">
				<div class="db-profile-kicker">
					<span class="db-type-label">School</span>
					@if($school['Status_descriptions'] ?? null)
						<span class="db-badge db-badge-neutral">{{ $school['Status_descriptions'] }}</span>
					@endif
				</div>
				<h1 class="db-profile-title">{{ $school['location_name'] }}</h1>
			</div>

			<div class="row mx-0 my-1">
				<div class="col-lg-4 col-md-4 col-sm-6 col-12">
					<small class="text-muted">Address</small><br />
					<h6>{{ $school['primary_address_line_1'] }}</h6>
				</div>
				<div class="col-lg-4 col-md-4 col-sm-6 col-12">
					<small class="text-muted">Managed By</small><br />
					<h6>{{ $school['Managed_by_name'] }}</h6>
				</div>

				<div class="col-lg-4 col-md-4 col-sm-6 col-12">
					<small class="text-muted">Status</small><br />
					<h6>{{ $school['Status_descriptions'] }}</h6>
				</div>
			</div>

			<div class="row mx-0 mb-3">
				<div class="col-lg-4 col-md-4 col-sm-6 col-12">
					<small class="text-muted">Type</small><br />
					<h6>{{ $school['location_type_description'] }}</h6>
				</div>
				<div class="col-lg-4 col-md-4 col-sm-6 col-12">
					<small class="text-muted">Category</small><br />
					<h6>{{ $school['Location_Category_Description'] }}</h6>
				</div>

				<div class="col-lg-4 col-md-4 col-sm-6 col-12">
					<small class="text-muted">Grades</small><br />
					<h6>{{ $school['Grades_text'] }}</h6>
				</div>
			</div>

			<h4>Profiles</h4>
			<div class="row mx-0 my-1">
				<div class="col-lg-6 col-md-6 col-sm-12 col-12">
					<small class="text-muted">DOE School Profile</small><br />
					<h6><a href="https://www.schools.nyc.gov/schools/{{ $school['location_code'] }}" target="_blank">https://www.schools.nyc.gov/schools/{{ $school['location_code'] }}</a></h6>
				</div>
				<div class="col-lg-6 col-md-6 col-sm-12 col-12">
					<small class="text-muted">The City Mental Health Project</small><br />
					<h6><a href="https://projects.thecity.nyc/school-mental-health/{{ $school['system_code'] }}" target="_blank">https://projects.thecity.nyc/school-mental-health/{{ $school['system_code'] }}</a></h6>
				</div>
			</div>

			<h4>Districts</h4>
			<div class="row mx-0 my-1">
				<div class="col-lg-3 col-md-3 col-sm-6 col-12">
					<small class="text-muted">School District</small><br />
					<h6><a href="{{ route('districtsPreset', ['type' => 'sd', 'id' => $school['Geographical_District_code'], 'dslug' => "school-district-{$school['Geographical_District_code']}", 'section' => 'schools']) }}">{{ $school['Geographical_District_code'] }}</a></h6>
				</div>
				<div class="col-lg-3 col-md-3 col-sm-6 col-12">
					<small class="text-muted">Neighborhood</small><br />
					<h6>{{ $school['NTA'] }}</h6>
				</div>
				<div class="col-lg-3 col-md-3 col-sm-6 col-12">
					<small class="text-muted">Council District</small><br />
					<h6>{{ $school['Council-district'] }}</h6>
				</div>
				<div class="col-lg-3 col-md-3 col-sm-6 col-12">
					<small class="text-muted">Community District</small><br />
					<h6>{{ $school['Community_district'] }}</h6>
				</div>
			</div>

			<h4>IDs & Codes</h4>
			<div class="row mx-0 my-1 id_code_school">
				<div class="col-lg-3 col-md-4 col-sm-6 col-12">
					<small class="text-muted">DBN</small><br />
					<h6>{{ $school['system_code'] ?? '' }}</h6>
				</div>
				<div class="col-lg-3 col-md-4 col-sm-6 col-12">
					<small class="text-muted">Building Code</small><br />
					<h6>{{ $school['location_code'] ?? '' }}</h6>
				</div>
				<div class="col-lg-3 col-md-4 col-sm-6 col-12">
					<small class="text-muted">BBL</small><br />
					<h6>{{ $school['Borough_block_lot'] ?? '' }}</h6>
				</div>
				<div class="col-lg-3 col-md-4 col-sm-6 col-12">
					<small class="text-muted">BEDS</small><br />
					<h6>{{ $school['BEDS'] ?? '' }}</h6>
				</div>
				<div class="col-lg-3 col-md-4 col-sm-6 col-12">
					<small class="text-muted">Facility Name</small><br />
					<h6>{{ $school['primary_address_line_1'] ?? '' }}</h6>
				</div>
				<div class="col-lg-3 col-md-4 col-sm-6 col-12">
					<small class="text-muted">NYPD Campus Name</small><br />
					<h6>{{ $school['schoolcampus'] ?? '' }}</h6>
				</div>
			</div>

		</div>

	</div>


	<div id="stats_collapse" class="collapse show mt-3 mb-4">
		<div class="db-stat-grid">
			<div class="db-stat"><div class="db-stat-label">% Students in Poverty</div><div class="db-stat-value prj_stat" id="povetry_perc">&nbsp;</div></div>
			<div class="db-stat"><div class="db-stat-label"># of Students</div><div class="db-stat-value prj_stat" id="students_no">&nbsp;</div></div>
			<div class="db-stat"><div class="db-stat-label"># of Projects</div><div class="db-stat-value prj_stat" id="prj_no">&nbsp;</div></div>
			<div class="db-stat"><div class="db-stat-label">Projects Budget</div><div class="db-stat-value prj_stat" id="prj_budget">&nbsp;</div></div>
			<div class="db-stat"><div class="db-stat-label">Project Costs</div><div class="db-stat-value prj_stat" id="prj_costs">&nbsp;</div></div>
			<div class="db-stat"><div class="db-stat-label">Project Cost per Student</div><div class="db-stat-value prj_stat" id="pcosts_per_student">&nbsp;</div></div>
		</div>
	</div>






		<div class="db-tabs-wrap org_headermenu">
		@if ($menu ?? null)
			<nav class="db-tabs submenu_org" aria-label="School sections">
				@foreach ($menu as $h=>$sect)
					@if (is_string($sect))
						<a class="db-tab @if ($active == $sect) is-active @endif" href="{{ route('schoolSection', ['code' => $code, 'slug' => Str::slug($school['location_name'], '-'), 'section' => $sect]) }}">{{ $slist[$sect] }}</a>
					@else
						<div class="db-tab-dd">
							<button type="button" class="db-tab @if (($activeDropDown ?? '') == $h) is-active @endif" data-dd aria-haspopup="true" aria-expanded="false" aria-controls="schooldd-{{ $loop->index }}">
								{{ $h }} <i class="bi bi-chevron-down db-caret"></i>
							</button>
							<div class="db-tab-menu" id="schooldd-{{ $loop->index }}" role="menu">
								@foreach ($sect as $subsect)
									<a role="menuitem" class="@if ($active == $subsect) is-active @endif" href="{{ route('schoolSection', ['code' => $code, 'slug' => Str::slug($school['location_name'], '-'), 'section' => $subsect]) }}">{{ $slist[$subsect] }}</a>
								@endforeach
							</div>
						</div>
					@endif
				@endforeach
				<a class="db-icon-btn share_icon_container" style="margin-left:auto; cursor:pointer;" data-bs-toggle="popover" data-content="Link copied to clipboard" placement="left" trigger="manual" title="Share direct link" onclick="copyLink();">
					<i class="bi bi-share"></i>
					<textarea id="details-permalink" class="details">{!! route('schoolSection', compact(['code', 'slug', 'section'])) !!}</textarea>
					<span id="details-addr"></span>
				</a>
			</nav>
		@endif
		</div>

</div>
