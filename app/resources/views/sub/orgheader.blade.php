{{-- Unified profile header + tab nav (db-* design system).
     Data hooks preserved: logo→orgProfile link, type-label (orgs?type=), tags (orgs?tag=),
     district "Representing" links, parent "Reports to" + orgsChartFocus diagram link,
     social icon loop with copyLinkM()/popover hooks + #details-permalink/#orgRSSNews textareas,
     and the $menu/$slist section nav (orgProfile/orgSection routes, $active/$activeDropDown). --}}
@php
    // NYCHA is a separate authority: every Finances subsection is empty for it
    // EXCEPT Council Discretionary Funding, and its procurement lives in the
    // dedicated /oce/nycha/* domains. Collapse the empty Finances dropdown + the
    // Procurement tab into a single "Finances & Procurement" DROPDOWN (matching
    // the other profiles' section dropdowns) whose items are the NYCHA finance
    // domains + Council Funding. Applied centrally here so it shows on every
    // NYCHA org page; guarded to NYCHA.
    $isNychaOrg = (string) ($org['id'] ?? '') === '170020034'
        || stripos($org['name'] ?? '', 'housing authority') !== false;
    if ($isNychaOrg && isset($menu)) {
        $nychaFinItems = ['procurement-highlights', 'procurement-nycha-budget',
            'procurement-nycha-revenue', 'procurement-nycha-contracts',
            'procurement-nycha-spending', 'procurement-nycha-vendors',
            'city-council-discretionary'];
        // Highlight the dropdown button across all its sub-pages (the specific
        // item highlights via $active == $subsect, so leave $active as-is). The
        // NYCHA-native vendor profile (procurement-nycha-vendor, a detail page —
        // not a menu item) passes $active='procurement-nycha-vendors' so the
        // Vendors item stays lit.
        if (isset($active) && in_array($active, $nychaFinItems, true)) {
            $activeDropDown = 'Finances & Procurement';
        }
        $newMenu = [];
        $added = false;
        foreach ($menu as $k => $v) {
            $isFinancesDD = ($k === 'Finances');
            $isProcTab = (is_string($v) && $v === 'procurement-highlights');
            if ($isFinancesDD || $isProcTab) {
                if (!$added) { $newMenu['Finances & Procurement'] = $nychaFinItems; $added = true; }
                continue;
            }
            if (is_int($k)) { $newMenu[] = $v; } else { $newMenu[$k] = $v; }
        }
        if (!$added) { $newMenu['Finances & Procurement'] = $nychaFinItems; }
        $menu = $newMenu;
        $slist = array_merge($slist ?? [], [
            'procurement-highlights'      => 'Finances Overview',
            'procurement-nycha-budget'    => 'Budget',
            'procurement-nycha-revenue'   => 'Revenue',
            'procurement-nycha-contracts' => 'Contracts',
            'procurement-nycha-spending'  => 'Spending',
            'procurement-nycha-vendors'   => 'Vendors',
            'city-council-discretionary'  => 'Council Funding',
        ]);
    }
@endphp
<div class="db-profile-header" id="org-header">
	<div class="inner_container">
		<div class="container">
			<div class="db-profile-header-top">
				@if ($org['logo_file'] ?? null)
					<div class="db-profile-logo">
						<a href="{{ route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]) }}">
							<img class="org-logo" src="/img/logo/{{ $org['logo_file'] }}" alt="{{ $org['name'] }}" />
						</a>
					</div>
				@endif

				<div class="db-profile-main org_detailheader">
					<div class="db-profile-kicker">
						@if ($org['type'] ?? null)
							<a href="{{ route('orgs') }}?type={{ urlencode($org['type']) }}" class="no-underline">
								<span class="db-type-label">{{ $org['type'] }}</span>
							</a>
						@endif
						@if ($org['tags'] ?? null)
							@foreach (json_decode($org['tags'], true) as $tag)
								<a href="{{ route('orgs') }}?tag={{ urlencode($tag) }}" class="no-underline">
									<span class="db-tag">{{ $tag }}</span>
								</a>
							@endforeach
						@endif
					</div>

					{{--
						Show NYC's official name (`display_name`, from the OTI
						registry) and fall back to ours. ⚠ Display only — every
						URL, the contracts.agency join and the cache keys stay on
						$org['name'], which is why display_name exists at all.
					--}}
					@php $dispName = ($org['display_name'] ?? null) ?: $org['name']; @endphp
					<h1 class="db-profile-title">{{ $dispName }}</h1>
					@if ($dispName !== $org['name'])
						<div class="db-profile-meta">
							<span class="db-meta-item"><i class="bi bi-info-circle"></i>
								Also known as {{ $org['name'] }}</span>
						</div>
					@endif

					@php
						// Track B: this org is also a PASSPort vendor. Precomputed here
						// because a Blade directive glued to a word character is not
						// compiled and 500s the page while `php -l` passes clean.
						$cv = $org['civic_vendor'] ?? null;
						$cvContracts = $cv ? (int)($cv['contracts'] ?? 0) : 0;
						$cvAwarded = $cv ? (float)($cv['awarded'] ?? 0) : 0;
						$cvTier = $cv ? ($cv['match']['tier'] ?? '') : '';
						$cvLabel = $cvContracts === 1 ? 'contract' : 'contracts';
						// Say HOW the link was made rather than presenting a name-based
						// join as fact — same discipline as the NYCHA block.
						$cvHow = $cvTier === 'curated'
							? 'human-confirmed match'
							: 'matched on name (' . $cvTier . ')';
						$cvAmount = $cvAwarded >= 1000000
							? '$' . number_format($cvAwarded / 1000000, 1) . 'M'
							: '$' . number_format($cvAwarded);
					@endphp

					@if (($org['communityDistrictName'] ?? null) || ($org['cityCouncilDistrictName'] ?? null) || ($org['parent_id'] ?? null) || $cv)
						<div class="db-profile-meta">
							@if ($org['communityDistrictName'] ?? null)
								<span class="db-meta-item"><i class="bi bi-geo-alt"></i> Representing
									<a href="{{ route('districtsPreset', [
											'type' => 'cd',
											'id' => preg_replace('~(\["|"\])~', '', $org['communityDistrictId']),
											'dslug' => Str::slug($org['communityDistrictName'], '-'),
											'section' => 'city-council-discretionary',
										]) }}">{{ trim(preg_replace('~(\["|"\])~', '', $org['communityDistrictName'])) }}</a>
								</span>
							@endif
							@if ($org['cityCouncilDistrictName'] ?? null)
								<span class="db-meta-item"><i class="bi bi-geo-alt"></i> Representing
									<a href="{{ route('districtsPreset', [
											'type' => 'cc',
											'id' => preg_replace('~(\["|"\])~', '', $org['cityCouncilDistrictId']),
											'dslug' => Str::slug($org['cityCouncilDistrictName'], '-'),
											'section' => 'city-council-discretionary',
										]) }}">{{ trim($org['cityCouncilDistrictName']) }}</a>
								</span>
							@endif
							@if ($org['parent_id'] ?? null)
								<span class="db-meta-item"><i class="bi bi-diagram-3"></i> Reports to
									@if (preg_match('~Classification|Official~si', $org['parent_type'] ?? ''))
										<span>{{ trim($org['parent_name'] ?? '') }}</span>
									@else
										<a href="{{ route('orgProfile', ['id' => $org['parent_id'], 'orgslug' => $org['parent_id']]) }}">{{ trim($org['parent_name'] ?? '') }}</a>
									@endif
									<a href="{{ route('orgsChartFocus', ['id' => $org['id']]) }}" class="db-icon-btn" title="View org chart" style="width:28px;height:28px;">
										<i class="bi-diagram-3-fill"></i>
									</a>
								</span>
							@endif
							@if ($cv)
								<span class="db-meta-item" title="{{ $cvHow }}">
									<i class="bi bi-file-earmark-text"></i> Holds City contracts
									<a href="{{ route('procurement.vendor', ['id' => $cv['supplier_id']]) }}">{{ $cv['vendor_name'] }}</a>
									@if ($cvContracts)
										<span class="db-meta">({{ number_format($cvContracts) }} {{ $cvLabel }}, {{ $cvAmount }} awarded)</span>
									@endif
								</span>
							@endif
						</div>
					@endif
				</div>

				<div class="db-profile-actions icon_orgsocial">
					@foreach ($icons as $f=>$pp)
						@if ($f == 'ical')
							<a class="db-icon-btn" onclick="copyLinkM(this);" title="Copy Notices iCal feed link">
								<i class="bi-{{ $pp[0] }} share_icon_container" data-bs-toggle="popover" data-content="Agency Notices iCal feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer;"></i>
							</a>
							<textarea id="details-permalink" class="details">{!! route('orgIcalEvents', ['id' => $id]) !!}</textarea>
						@elseif ($f == 'rss')
							<a class="db-icon-btn" onclick="copyLinkM(this, 'orgRSSNews');" title="Copy News RSS feed link">
								<i class="bi-{{ $pp[0] }} share_icon_container" data-bs-toggle="popover" data-content="News RSS feed link copied to clipboard" placement="left" trigger="manual" style="cursor: pointer;"></i>
							</a>
							<textarea id="orgRSSNews" class="details">{!! route('orgRSSNews', ['id' => $id]) !!}</textarea>
						@elseif ($org[$f] ?? null)
							<a class="db-icon-btn" href="{{ $pp[1] }}{{ $org[$f] }}" target="_blank" rel="nofollow">
								<i class="bi-{{ $pp[0] }}"></i>
							</a>
						@endif
					@endforeach
				</div>
			</div>

			@if ($menu ?? null)
				<div class="db-tabs-wrap org_headermenu">
					<nav class="db-tabs submenu_org" aria-label="Organization sections">
						@foreach ($menu as $h=>$sect)
							@if (is_string($sect))
								@if ($sect == 'about')
									<a class="db-tab @if ($active == $sect) is-active @endif" href="{{ route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]) }}">{{ $slist[$sect] }}</a>
								@else
									<a class="db-tab @if ($active == $sect) is-active @endif" href="{{ route('orgSection', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-'), 'section' => $sect]) }}">{{ $slist[$sect] }}</a>
								@endif
							@else
								<div class="db-tab-dd">
									<button type="button" class="db-tab @if ($activeDropDown == $h) is-active @endif" data-dd aria-haspopup="true" aria-expanded="false" aria-controls="orgdd-{{ $loop->index }}">
										{{ $h }} <i class="bi bi-chevron-down db-caret"></i>
									</button>
									<div class="db-tab-menu" id="orgdd-{{ $loop->index }}" role="menu">
										@foreach ($sect as $subsect)
											@if ($subsect == 'about')
												<a role="menuitem" class="@if ($active == $subsect) is-active @endif" href="{{ route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-')]) }}">{{ $slist[$subsect] }}</a>
											@else
												<a role="menuitem" class="@if ($active == $subsect) is-active @endif" href="{{ route('orgSection', ['id' => $id, 'orgslug' => Str::slug($org['name'], '-'), 'section' => $subsect]) }}">{{ $slist[$subsect] }}</a>
											@endif
										@endforeach
									</div>
								</div>
							@endif
						@endforeach
					</nav>
				</div>
			@endif
		</div>
	</div>
</div>
