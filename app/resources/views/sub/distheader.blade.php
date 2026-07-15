{{-- District section nav (db-* design system). Data hooks preserved:
     .dsmenu + #dsmenu-{section} ids + mapAction() onclick (in-page AJAX section switch),
     $activeDropDown active marker, #details-permalink textarea + copyLink() share.
     The lone dropdown (sd → "Enrollment") stays a Bootstrap dropdown so it keeps working
     after mapAction() replaces #section_content (the layout's .db-tab-dd JS binds once at
     page load and would not rebind the re-inserted markup). --}}
<div class="inner_container">
	<div class="container">
		<div class="db-tabs-wrap district_headermenu">
			<nav class="db-tabs submenu_org" aria-label="District sections">
				@foreach ($menu as $h=>$sect)
					@if (is_string($sect))
						<a class="db-tab dsmenu @if ($active == $sect) is-active @endif" id="dsmenu-{{ $sect }}" onclick="mapAction(globfilter, '{{ $type }}', '{{ $sect }}');" style="cursor:pointer;">{{ $slist[$sect] }}</a>
					@else
						<div class="dropdown">
							<button type="button" class="db-tab @if ($activeDropDown == $h) is-active @endif" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false">{{ $h }} <i class="bi bi-chevron-down db-caret"></i></button>
							<div class="dropdown-menu">
								@foreach ($sect as $subsect)
									<a class="dropdown-item dsmenu @if ($active == $subsect) is-active active @endif" id="dsmenu-{{ $subsect }}" onclick="mapAction(globfilter, '{{ $type }}', '{{ $subsect }}');" style="cursor:pointer;">{{ $slist[$subsect] }}</a>
								@endforeach
							</div>
						</div>
					@endif
				@endforeach

				<span class="db-tabs-share" style="margin-left:auto; display:inline-flex; align-items:center;" data-bs-toggle="popover" data-content="Link copied to clipboard" placement="left" trigger="manual">
					<textarea id="details-permalink" class="details">{!! route('districtsPreset', compact(['type', 'id', 'section']) + ['dslug' => 'dslug']) !!}</textarea>
					<span id="details-addr"></span>
					<a class="db-icon-btn" title="Share direct link" onclick="copyLink();" style="cursor:pointer;">
						<i class="bi bi-share"></i>
					</a>
				</span>
			</nav>
		</div>
	</div>
</div>
