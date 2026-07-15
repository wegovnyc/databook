<?php
Namespace App\Custom;

class DistDatasets
{
	public $dd = [
		'requests' => [
			'fullname' => 'Register of Community Board Budget Requests API',
			'table' => 'budgetrequestsregister',
			'hdrs' => ['Publication Date', 'Borough', 'C Board', 'Priority', 'Tracking Code', 'Request', 'Council District', 'NTA', 'Agency'],
			'visible' => [true, false, false, true, true, true, false, false, true],
			'flds' => [ 
						'function (r) { return toDashDate(r["Publication"]) }', 
						'"Borough"', '"Community Board"', '"Priority"', '"Tracking  Code"', '"Request"', '"wegov-cd-id"', '"wegov-nta-code"',
						'function (r) { return `<a href="/o/${r["wegov-org-id"]}-${slug(r["wegov-org-name"])}/requests">${r["wegov-org-name"]}</a>` }',
					  ], 
			'sort' => ['"Publication"', '"Borough"',],
			'filters' => [0 => '2020-07-01', 1 => null, 2 => null, 3 => null],
			'details' => [
						'Explanation' => 'Explanation',
						'Response' => 'Response',
						'Responded By' => 'Responded By',
						#'Responsible Agency' => 'Responsible Agency',
						'Site Street' => 'Site Street',
						'Number' => 'Number',
						'Street' => 'Street',
						'Block' => 'Block',
						'Lot' => 'Lot',
						'Postcode' => 'Postcode',
						'Council District' => 'Council District',
						'BIN' => 'BIN',
						'BBL' => 'BBL',
						'NTA' => 'NTA'			
			],
			'map' => ['cd' => 'Community Board', 'cc' => 'Council District', 'nta' => 'wegov-nta-code'],
		],
		
		'facilities' => [
			'fullname' => 'NYC Facilities Database',
			'table' => 'facilitydb',
			'hdrs' => ['Name', 'Category', 'Group', 'Subgroup', 'Address', 'Borough', 'Council District', 'NTA'],
			'visible' => [true, true, true, true, true, true, false, false],
			'flds' => ['"facname"', '"facdomain"', '"facgroup"', '"facsubgrp"', '"address"', '"boro"', '"wegov-cd-id"', '"wegov-nta-code"'], 
			'sort' => ['"facname"', '"facdomain"'],
			'filters' => [1 => null, 2 => null, 3 => null, 5 => null],
			'details' => [
					'Number' => 'number',
					'Street' => 'street',
					'City' => 'city',
					'Zipcode' => 'postcode',
					'Latitude' => 'latitude',
					'Longitude' => 'longitude',
					'BIN' => 'bin',
					'BBL' => 'bbl',
					'Community Board' => 'community board',
					'Council District' => 'council district',
					'Neighborhood' => 'nta',
					'Facility Type' => 'factype',
					'Capacity' => 'capacity',
					'Capital Type' => 'captype',
					'Property Type' => 'proptype'			
			],
			'description' => 'The Facilities Database (FacDB) captures the locations and descriptions of public and private facilities ranging from the provision of social services, recreation, education, to solid waste management.',
			'map' => ['cd' => 'wegov-comd-id', 'cc' => 'wegov-cd-id', 'nta' => 'wegov-nta-code'],	
		],

		'city-council-discretionary' => [								#nyccouncildiscretionaryfunding
			'fullname' => 'New York City Council Discretionary Funding',
			'table' => 'nyccouncildiscretionaryfunding',
			'hdrs' => ['Fiscal Year', 'Source', 'Council Member', 'Legal Name of Organization', 'Status', 'Amount ($)', 'Borough', 'Council District', 'NTA'],
			'visible' => [true, true, true, true, true, true, true, true, false],
			'flds' => [
					'"Fiscal Year"', '"Source"', '"Council Member"', 
					'function (r) { return `<a href="https://projects.propublica.org/nonprofits/organizations/${r["EIN"]}" target="_blank" rel="nofollow">${r["Legal Name of Organization"]}</a>` }',
					'"Status"', '"Amount ($)"', '"Borough"', '"Council District"', '"NTA"'
				], 
			'sort' => ['"Fiscal Year"', '"Source"'],
			'filters' => [0 => null, 1 => null, 2 => null, 6 => null, 7 => null],
			'details' => [
				'EIN' => 'EIN',
				'MOCS ID' => 'MOCS ID',
				'Program Name' => 'Program Name',
				'Address' => 'Address',
				'Address 2 (optional)' => 'Address 2 (optional)',
				'City' => 'City',
				'State' => 'State',
				'Postcode' => 'Postcode',
				'Purpose of Funds' => 'Purpose of Funds',
				'Fiscal Conduit Name' => 'Fiscal Conduit Name',
				'FC EIN' => 'FC EIN',
				'Latitude' => 'Latitude',
				'Longitude' => 'Longitude',
				'Community Board' => 'Community Board',
				'Census Tract' => 'Census Tract',
				'BIN' => 'BIN',
				'BBL' => 'BBL',
				'NTA' => 'NTA',
			],
			'description' => 'The dataset reflects applications for discretionary funding to be allocated by the New York City Council.',
			// No 'nta' mapping: this dataset's NTA column is 2010-vintage (stores 2010 NTA
			// *names*), but the district pages use 2020 NTAs — and 2010↔2020 differ in actual
			// boundaries, not just labels, so there is no valid crosswalk. Omitting the key
			// hides this section from NTA pages (menu() gates on map[$type]) and 404s any
			// direct URL (get() returns null). cd/cc are unaffected — they key on Community
			// Board / Council District, which are stored correctly.
			'map' => ['cd' => 'Community Board', 'cc' => 'Council District'],
		],

		'projects' => [
			'fullname' => 'Capital Project Detail Data - Dollars',
			'table' => 'capitalprojectsdollarscomp',
			'description' => 'This dataset contains capital commitment plan data by project type, budget line and source of funds. The dollar values are in thousands. The dataset is updated three times a year during the Preliminary, Executive and Adopted Capital Commitment Plans.',
			'hdrs' => ['Publication Date', 'Project ID', 'Name', 'Scope', 'Category', 'Borough', 'Planned Cost', 'Budget Increase', 'Timeline Change'],
			'sort' => ['"Project ID"', '"Publication Date"'],
			'visible' => [false, true, true, true, true, true, true, true, true],
			'hide_on_map_open' => '0, 4, 6, 7, 8',
			'flds' => [
					'function (r) { return toDashDate(r["PUB_DATE"]) }',
					'function (r) { return `<a href="/p/${r.PROJECT_ID}_${slug(r.PROJECT_DESCR)}">${r.PROJECT_ID}</a>` }', 
					'"PROJECT_DESCR"', '"SCOPE_TEXT"', '"TYP_CATEGORY_NAME"', 
					'"BORO"', 
					'function (r) { return `<span data-content="${toFin(r["BUDG_ORIG"], 1000)}">${toFinShortK(r["BUDG_ORIG"], 1000)}</span>` }',
					'function (r) { 
						if (!r["ORIG_BUD_AMT"])
							return "NA"
						return r["BUDG_DIFF"] == 0 ? "0" :
							(r["BUDG_DIFF"] > 0 
								? `<span class="good" data-content="-${toFin(r["BUDG_DIFF"], 1000)}">-${toFinShortK(r["BUDG_DIFF"], 1000)}</span>` 
								: `<span class="bad" data-content="${toFin(-r["BUDG_DIFF"], 1000)}">${toFinShortK(-r["BUDG_DIFF"], 1000)}</span>`);
					}',
					'function (r) { 
						if ((r["END_DIFF"] == "-") || (r["END_DIFF"] == "12/31/1969"))
							return "NA"
						var v = parseFloat(r["END_DIFF"]).toFixed(1).toString()
						if (v < 0)
							return `<span class="bad">${-v} years late</span>`
						return v > 0 ? `<span class="good">${v} years early</span>` : `<span class="good">on time</span>`;
					}'
				],
			'filters' => [4 => null],
			'details' => [
					'Original Budget' => '`<span data-content="${toFin(r["BUDG_ORIG"], 1000)}">${toFinShortK(r["BUDG_ORIG"], 1000)}</span>`',
					'Prior Spending' =>  '`<span data-content="${toFin(r["CITY_PRIOR_ACTUAL"], 1000)}">${toFinShortK(r["CITY_PRIOR_ACTUAL"], 1000)}</span>`', 
					'Planned Spending' => '`<span data-content="${toFin(r["CITY_PLAN_TOTAL"], 1000)}">${toFinShortK(r["CITY_PLAN_TOTAL"], 1000)}</span>`',
					'Community Boards Served' => 'r["COMMUNITY_BOARD"]',
					'Budget Lines' => 'r["BUDGET_LINE"]',
					'Site Description' => 'r["SITE_DESCR"]',
					'Explanation for Delay' => 'r["DELAY_DESC"]',
			],
			'order' => [[8, 'asc']],
			'map' => ['cd' => 'wegov-comd-id', 'cc' => 'Council District', 'nta' => 'wegov-nta-code'],
		],

	// ------ shools ------------------------

		'schools' => [
			'fullname' => 'Schools',
			'table' => 'schoollocations',
			'hdrs' => ['Location Name', 'Location Code', 'Managed By', 'Category', 'Grades', 'Status', 'Address', 'Neighborhood'],
			'visible' => [true, true, true, true, true, true, true, true],
			'flds' => [
					'function (r) { return `<a href="/s/${r.location_code}-${slug(r.location_name)}">${r.location_name}</a>` }', 
					'"location_code"', '"Managed_by_name"', '"Location_Category_Description"', '"Grades_text"', '"Status_descriptions"', '"primary_address_line_1"', '"NTA_Name"'
				], 
			'hide_on_map_open' => '',
			'sort' => ['"location_code"', '"Grades_text"'],
			'filters' => [2 => null, 5 => null, ],
			'description' => '2019 - 2020 School Locations',
			'details' => [],
			'map' => ['sd' => 'Geographical_District_code'],
		],

		'school-projects' => [
			'fullname' => 'School Projects',
			'table' => 'scacapitalprojectschedules',
			'hdrs' => ['Project School Name', 'Project Type', 'Project Description', 'Project Phase Name', 'Project Status Name', 'Project Phase Actual Start Date', 'Project Phase Planned End Date', 'Project Phase Actual End Date', 'Project Budget Amount', 'Final Estimate of Actual Costs Through End of Phase Amount', 'Total Phase Actual Spending Amount'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true],
			'flds' => [
					'"Project School Name"', '"Project Type"', '"Project Description"', '"Project Phase Name"', '"Project Status Name"', '"Project Phase Actual Start Date"', '"Project Phase Planned End Date"', '"Project Phase Actual End Date"', '"Project Budget Amount"', '"Final Estimate of Actual Costs Through End of Phase Amount"', '"Total Phase Actual Spending Amount"'
				], 
			'sort' => ['"Project School Name"', '"Project Type"'],
			'filters' => [],
			'description' => 'Capital Project Schedules and Budgets',
			'details' => [],
			'map' => ['sd' => 'Project Geographic District'],
		],

		'enrollment' => [
			'fullname' => 'Current & Future Enrollment',
			'sectionTitle' => 'Future Enrollment',
			'table' => 'scademostats',
			'hdrs' => ['Data Type', 'Year', 'PK', 'K', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', 'GED', 'SE1', 'Total'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true],
			'flds' => [
					'"Data Type"', '"Year"', '"PK"', '"K"', '"1"', '"2"', '"3"', '"4"', '"5"', '"6"', '"7"', '"8"', '"9"', '"10"', '"11"', '"12"', '"GED"', '"SE1"', '"Total"'
				], 
			'sort' => ['"Year"', '"Data Type"'],
			'filters' => [],
			'description' => 'Demographic Projection Report - Enrollment Projections - New York City Public Schools prepared by Statistical Forecasting.',
			'details' => [],
			'map' => ['sd' => 'Borough or District'],
		],

		'enrollment-past' => [
			'fullname' => '2017-18 - 2021-22 Demographic Snapshot',
			'sectionTitle' => 'Past Enrollment',
			'table' => 'demographics',
			'hdrs' => ['Year', 'Total', '3K', 'PK', 'K', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true],
			'flds' => [
					'"Year"', 
					'function (r) { return commaThousands( r["Total Enrollment"] ); }',
					'function (r) { return commaThousands( r["Grade 3K"] ); }',
					'function (r) { return commaThousands( r["Grade PK (Half Day & Full Day)"] ); }',
					'function (r) { return commaThousands( r["Grade K"] ); }',
					'function (r) { return commaThousands( r["Grade 1"] ); }',
					'function (r) { return commaThousands( r["Grade 2"] ); }',
					'function (r) { return commaThousands( r["Grade 3"] ); }',
					'function (r) { return commaThousands( r["Grade 4"] ); }',
					'function (r) { return commaThousands( r["Grade 5"] ); }',
					'function (r) { return commaThousands( r["Grade 6"] ); }',
					'function (r) { return commaThousands( r["Grade 7"] ); }',
					'function (r) { return commaThousands( r["Grade 8"] ); }',
					'function (r) { return commaThousands( r["Grade 9"] ); }',
					'function (r) { return commaThousands( r["Grade 10"] ); }',
					'function (r) { return commaThousands( r["Grade 11"] ); }',
					'function (r) { return commaThousands( r["Grade 12"] ); }',
				], 
			'sort' => ['"Year"', '"Total Enrollment"'],
			'filters' => [],
			'description' => 'Enrollment counts are based on the October 31 Audited Register for the 2017-18 to 2019-20 school years. To account for the delay in the start of the school year, enrollment counts are based on the November 13 Audited Register for 2020-21 and the November 12 Audited Register for 2021-22.',
			'details' => [],
			'map' => ['sd' => 'wegov-sd-id'],
		],

		'city-council-stat-cases' => [
			'fullname' => 'NYC Council Constituent Services',
			'sectionTitle' => 'CouncilStat Cases',
			'table' => 'councilstatcases',
			'hdrs' => ['ID', 'Submitted By', 'Opened', 'Complaint Type', 'Description', 'Closed'],
			'visible' => [true, true, true, true, true, true],
			'flds' => ['"UNIQUE_KEY"', '"ACCOUNT"', '"OPENDATE"', '"COMPLAINT_TYPE"', '"DESCRIPTOR"', '"CLOSEDATE"'], 
			'sort' => ['"UNIQUE_KEY"', '"ACCOUNT"'],
			'filters' => [],
			'description' => 'The dataset comes from CouncilStat, which is used by many NYC Council district offices to enter and track constituent cases that can range from issues around affordable housing, to potholes and pedestrian safety. This dataset aggregates the information that individual staff have input. However, district staffs handle a wide range of complex issues. Each offices uses the program differently, and thus records cases, differently and so comparisons between accounts may be difficult. Not all offices use the program. For more info - <a href="http://labs.council.nyc/districts/data/">http://labs.council.nyc/districts/data/</a>',
			'details' => [
				'Zipcode' => 'ZIP',
				'Borough' => 'BOROUGH',
				'City' => 'CITY',
				'Council District' => 'COUNCIL_DIST',
				'Community Board' => 'COMMUNITY_BOARD',
			],
			'map' => ['cd' => 'Community Board', 'cc' => 'Council District'],
		],
	];

	public $list = [
		'city-council-discretionary' => 'City Council Discretionary Spending',
		'city-council-stat-cases' => 'City Council Stat Cases',
		'projects' => 'Projects',
		'requests' => 'Requests',
		'facilities' => 'Facilities',
		'enrollment' => 'Future',
		'enrollment-past' => 'Past',
		'schools' => 'Schools',
		'school-projects' => 'Projects',
	];
	
	public $menu = [
		'cd' => [
			'city-council-discretionary',
			'city-council-stat-cases',
			'projects',
			'requests',
			'facilities',
		],
		'cc' => [
			'city-council-discretionary',
			'city-council-stat-cases',
			'projects',
			'requests',
			'facilities',
		],
		'nta' => [
			// 'city-council-discretionary' intentionally omitted — its NTA data is
			// 2010-vintage and incompatible with the 2020 NTA geography (see the
			// 'city-council-discretionary' map comment above).
			'projects',
			'requests',
			'facilities',
		],
		'sd' => [
			'schools',
			'school-projects',
			'Enrollment' => [
				'enrollment',
				'enrollment-past',
			]
		],
	];
	
	public $cdAltName = ['101' => 'MN01', '102' => 'MN02', '103' => 'MN03', '104' => 'MN04', '105' => 'MN05', '106' => 'MN06', '107' => 'MN07', '108' => 'MN08', '109' => 'MN09', '110' => 'MN10', '111' => 'MN11', '112' => 'MN12', '201' => 'BX01', '202' => 'BX02', '203' => 'BX03', '204' => 'BX04', '205' => 'BX05', '206' => 'BX06', '207' => 'BX07', '208' => 'BX08', '209' => 'BX09', '210' => 'BX10', '211' => 'BX11', '212' => 'BX12', '301' => 'BK01', '302' => 'BK02', '303' => 'BK03', '304' => 'BK04', '305' => 'BK05', '306' => 'BK06', '307' => 'BK07', '308' => 'BK08', '309' => 'BK09', '310' => 'BK10', '311' => 'BK11', '312' => 'BK12', '313' => 'BK13', '314' => 'BK14', '315' => 'BK15', '316' => 'BK16', '317' => 'BK17', '318' => 'BK18', '401' => 'QN01', '402' => 'QN02', '403' => 'QN03', '404' => 'QN04', '405' => 'QN05', '406' => 'QN06', '407' => 'QN07', '408' => 'QN08', '409' => 'QN09', '410' => 'QN10', '411' => 'QN11', '412' => 'QN12', '413' => 'QN13', '414' => 'QN14', '501' => 'SI01', '502' => 'SI02', '503' => 'SI03'];
	
	
	
	public function menu($type)
	{
		$rr = [];
		foreach ($this->menu[$type] as $h=>$vv)
			if (is_array($vv))
			{
				foreach ($vv as $i=>$v)
					if (isset($this->dd[$v]['map'][$type]))
						$rr[$h][$i] = $v;
			} elseif (isset($this->dd[$vv]['map'][$type]))
				$rr[$h] = $vv;
		return $rr;
	}
	
	public function menuActiveDD($type, $sect)
	{
		foreach ($this->menu[$type] as $h=>$items)
			if (is_array($items) && (array_search($sect, $items) !== false))
				return $h;
		return '';
	}
	
	public function get($section, $type)
	{
		$dd = $this->dd[strtolower($section)] ?? null;
		if (!$dd)
			return $dd;
		if (!isset($dd['map']) || !isset($dd['map'][$type]))
			return null;
		
		$dd['detFlag'] = $inc = $dd['details'] ?? null ? 1 : 0;
		$flts = [];
		foreach ((array)$dd['filters'] as $i=>$v)
			$flts[$i + $inc] = $v;
		$dd['filters'] = $flts;
		
		$fltDel = [];
		foreach ((array)($dd['fltDelim'] ?? []) as $i=>$v)
			$fltDel[$i + $inc] = $v;
		$dd['fltDelim'] = $fltDel;
		
		$dd['fltsCols'] = implode(',', array_keys($dd['filters']));
		return $dd;
	}


	

	public function stats_data_sources($dd, $id, $type, $dslist=null)
	{
		$stats_datasets = [
			
			'nyccouncildiscretionaryfunding' => [																				# table => route
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'Discretionary Funding'
			],
			'capitalprojectsdollarscomp' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'projects']),
				'Projects'
			],
			'budgetrequestsregister' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'requests']),
				'Budget Requests'
			],
			'facilitydb' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'facilities']),
				'Facilities'
			],
			'ccmembers' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],
			'nyccommunityboards' => [
				route('districtsPreset', ['id'=>$id, 'type'=>$type, 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],
			'nta' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'nta', 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],
			'cd' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'cd', 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],
			'cc' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'cc', 'dslug'=>'-', 'section'=>'city-council-discretionary']),
				'District'
			],

			'scademostats' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'enrollment']),
				'District'
			],
			'demographics' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'enrollment-past']),
				'District'
			],
			'schoollocations' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'schools']),
				'District'
			],
			'scacapitalprojectschedules' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'school-projects']),
				'District'
			],
			'sd' => [
				route('districtsPreset', ['id'=>$id, 'type'=>'sd', 'dslug'=>'-', 'section'=>'enrollment']),
				'District'
			],
			
		];

		$rr = [];
		$ii = [
			'nta' => [
				'Citation URL' => 'https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-Tabular/9nt8-h7nd', 
				'Name' => '2020 Neighborhood Tabulation Areas (NTAs)',
				'Descripton' => '2020 Neighborhood Tabulation Areas (NTAs) are medium-sized statistical geographies for reporting Decennial Census and American Community Survey (ACS). 2020 NTAs are created by aggregating 2020 census tracts and nest within Community District Tabulation Areas (CDTA). NTAs were delineated with the need for both geographic specificity and statistical reliability in mind. Consequently, each NTA contains enough population to mitigate sampling error associated with the ACS yet offers a unit of analysis that is smaller than a Community District.',
				'Last Updated' => '4/6/2023 11:00pm'
			],
			'cd' => [
				'Citation URL' => 'https://data.cityofnewyork.us/City-Government/Community-Districts/yfnk-k7r4', 
				'Name' => 'Community Districts',
				'Descripton' => 'GIS data: Boundaries of Community Districts.',
				'Last Updated' => '4/6/2023 11:00pm'
			],
			'cc' => [
				'Citation URL' => 'https://data.cityofnewyork.us/City-Government/City-Council-Districts/yusd-j4xi', 
				'Name' => 'City Council Districts',
				'Descripton' => 'GIS data: Boundaries of City Council Districts.',
				'Last Updated' => '4/6/2023 11:00pm'
			],
			'sd' => [
				'Citation URL' => 'https://data.cityofnewyork.us/Education/School-Districts/r8nu-ymqj', 
				'Name' => 'School Districts',
				'Descripton' => 'GIS data: Boundaries of School Districts.',
				'Last Updated' => '4/6/2023 11:00pm'
			],
		];
		foreach ($dd as $d)
			$ii[strtolower(str_replace('.csv', '', $d['Output Path']))] = $d;
		foreach ($dslist ?? array_keys($stats_datasets) as $tbl)
		{
			$route = $stats_datasets[$tbl];
			$rr[$tbl] = [
				"<a href=\"{$ii[$tbl]['Citation URL']}\" target=\"_blank\" rel=\"nofollow\">{$ii[$tbl]['Name']}</a>",
				'<a href="' . $route[0] . "\">{$route[1]}</a>",
				$ii[$tbl]['Descripton'],
				$ii[$tbl]['Last Updated'],
				'<span id="stats_' . $tbl . '"></span>',
			];
		}
		return $rr;
	}
	

}