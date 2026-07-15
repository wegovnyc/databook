<?php
Namespace App\Custom;
use Illuminate\Support\Str;
use App\Custom\DatabookAPI;

class SchoolDatasets
{
	public $dd = [
		'schools' => [										# core dataset    182
			'fullname' => 'Schools',
			'table' => 'schoollocations',
			'hdrs' => ['Location Name', 'Location Code', 'School District', 'Managed By', 'Category', 'Grades', 'Status', 'Address', 'Neighborhood'],
			'visible' => [true, true, true, true, true, true, true, true, true],
			'flds' => [
					'function (r) { return `<a href="/s/${r.location_code}-${slug(r.location_name)}">${r.location_name}</a>` }', 
					'"location_code"', 
					'function (r) { return `<a href="/d/sd-${r[\'Geographical_District_code\']}-school-district-${r[\'Geographical_District_code\']}/schools">${r[\'Geographical_District_code\']}</a>` }', 
					//'"Geographical_District_code"', 
					'"Managed_by_name"', '"Location_Category_Description"', '"Grades_text"', '"Status_descriptions"', '"primary_address_line_1"', '"NTA_Name"'
				], 
			'hide_on_map_open' => '',
			'sort' => ['"location_code"', '"Grades_text"'],
			'filters' => [2 => null, 3 => null, 4 => null, 6 => null],
			'description' => '2019 - 2020 School Locations',
			'details' => [],
			'map' => ['sd' => 'Geographical_District_code'],
			'DBNkey' => 'system_code',
		],

		'attendance' => [								// 255
			'fullname' => '2016-17 - 2020-21 School End-of-Year Attendance and Chronic Absenteeism Data',
			'table' => 'attendance',					// Carto table
			'hdrs' => ['DBN', 'Year', 'Grade', '# Total Days', '# Days Absent', '% Attendance', '# Chronically Absent', '% Chronically Absent'],										// datatables header
			'visible' => [true, true, true, true, true, true, true, true],	// column visibility
			'flds' => ['"DBN"', '"Year"', '"Grade"', '"# Total Days"', '"# Days Absent"', '"% Attendance"', '"# Chronically Absent"', '"% Chronically Absent"'],
																		
			'filters' => [],				// filters - fld no => def value or null if empty
			'details' => [],
			'sort' => ['DBN', 'Year'],
			'DBNkey' => 'system_code',		// system_code for datasets related to schools by DBN like 26Q495, location_code - by location code Q495
		],

		'enrollment' => [					// 253
			'fullname' => '2017-18 - 2021-22 Demographic Snapshot',
			'table' => 'demographics',
			'hdrs' => ['Year', 'Total', '3K', 'PK', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true],
			'flds' => ['"Year"', 
				'function (r) { return commaThousands( r["Total Enrollment"] ); }',
				'"Grade 3K"', '"Grade PK (Half Day & Full Day)"', '"Grade 1"', '"Grade 2"', '"Grade 3"', '"Grade 4"', '"Grade 5"', '"Grade 6"', '"Grade 7"', '"Grade 8"', '"Grade 9"', '"Grade 10"', '"Grade 11"', '"Grade 12"'],
			'filters' => [],
			'details' => [],
			'sort' => ['Year', 'Total Enrollment'],
			'DBNkey' => 'system_code',
		],
		
		'building-enrollment-capacity' => [				// 275
			'fullname' => 'Enrollment Capacity And Utilization Reports - Target by Building',
			'table' => 'scaenrollmentcapacity',
			'description' => 'Enrollment, target capacity and utilization data for every building and schools in those buildings, by building',
			'hdrs' => ['Data As Of', 'Bldg ID', 'Bldg Name', 'Bldg Enroll', 'Target Bldg Cap', 'Target Bldg Util', 'No. of Cluster / Spec Rms Reported +', 'No. of Cluster Rms Needed +'],
			'visible' => [true, true, true, true, true, true, true, true],
			'flds' => ['"Data As Of"', '"Bldg ID"', '"Bldg Name"', '"Bldg Enroll"', '"Target Bldg Cap"', '"Target Bldg Util"', 
						'function (r) { return r["No. of Cluster / Spec Rms Reported +"] }',
						'function (r) { return r["No. of Cluster Rms Needed +"] }',
					   ],
			'filters' => [],
			'details' => [],
			'sort' => ['Bldg ID', 'Data As Of'],
			'DBNkey' => 'location_code',
		],
		
		'organization-enrollment-capacity' => [			// 275 same as previous!!
			'fullname' => 'Enrollment Capacity And Utilization Reports - Target by Building',
			'table' => 'scaenrollmentcapacity',
			'description' => 'Enrollment, target capacity and utilization data for every building and schools in those buildings, by building',
			'hdrs' => ['Data As Of', 'Bldg ID', 'Bldg Name', 'Organization Name', 'Org Enroll', 'Org Target Cap', 'Org Target Util', 'PreK Cap +'],
			'visible' => [true, true, true, true, true, true, true, true],
			'flds' => ['"Data As Of"', '"Bldg ID"', '"Bldg Name"', '"Organization Name"', '"Org Enroll"', '"Org Target Cap"', '"Org Target Util"', '"PreK Cap +"'],
			'filters' => [],
			'details' => [],
			'sort' => ['Bldg ID', 'Data As Of'],
			'DBNkey' => 'location_code',
		],

		'race-ethnicity-gender' => [					// 253
			'fullname' => '2017-18 - 2021-22 Demographic Snapshot',
			'table' => 'demographics',
			'hdrs' => ['DBN', 'Year', '# Female', '% Female', '# Male', '% Male', '# Asian', '% Asian', '# Black', '% Black', '# Hispanic', '% Hispanic', '# Multi-Racial', '% Multi-Racial', '# Native American', '# White', '% White', '# Missing Race/Ethnicity Data', '% Missing Race/Ethnicity Data'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true],
			'flds' => ['"DBN"', '"Year"', '"# Female"', '"% Female"', '"# Male"', '"% Male"', '"# Asian"', '"% Asian"', '"# Black"', '"% Black"', '"# Hispanic"', '"% Hispanic"', '"# Multi-Racial"', '"% Multi-Racial"', '"# Native American"', '"# White"', '"% White"', '"# Missing Race/Ethnicity Data"', '"% Missing Race/Ethnicity Data"'],
			'filters' => [],
			'details' => [],
			'sort' => ['DBN', 'Year'],
			'DBNkey' => 'system_code',
		],

		'other-demographics' => [					// 253
			'fullname' => '2017-18 - 2021-22 Demographic Snapshot',
			'table' => 'demographics',
			'hdrs' => ['DBN', 'Year', '# Students with Disabilities', '% Students with Disabilities', '# English Language Learners', '% English Language Learners', '# Poverty', '% Poverty', 'Economic Need Index'],
			'visible' => [true, true, true, true, true, true, true, true, true],
			'flds' => ['"DBN"', '"Year"', '"# Students with Disabilities"', '"% Students with Disabilities"', '"# English Language Learners"', '"% English Language Learners"', '"# Poverty"', '"% Poverty"', '"Economic Need Index"'],
			'filters' => [],
			'details' => [],
			'sort' => ['DBN', 'Year'],
			'DBNkey' => 'system_code',
		],

		'student-housing' => [					// 254
			'fullname' => '2021 Students In Temporary Housing',
			'table' => 'temphousing',
			'hdrs' => ['DBN', '# Total Students', '# Students in Temporary Housing', '% Students in Temporary Housing', '# Students Residing in Shelter', '# Residing in DHS Shelter', '# Residing in Non-DHS Shelter', '# Doubled Up'],
			'visible' => [true, true, true, true, true, true, true, true],
			'flds' => ['"DBN"', '"# Total Students"', '"# Students in Temporary Housing"', '"% Students in Temporary Housing"', '"# Students Residing in Shelter"', '"# Residing in DHS Shelter"', '"# Residing in Non-DHS Shelter"', '"# Doubled Up"'],
			'filters' => [],
			'details' => [],
			'sort' => ['DBN', 'DBN'],
			'DBNkey' => 'system_code',
		],

		'guidance-counsellors' => [					// 252
			'fullname' => 'Guidance Counselors and Social Workers',
			'table' => 'guidancecounsellors',
			'hdrs' => ['Full-time GC', 'Full-Time SW', 'Part-time GC', 'Part-Time SW', 'Bilingual GC', 'Bilingual SW', 'School Psychologist Providing Mandated Counseling'],
			'visible' => [true, true, true, true, true, true, true, true],
			'flds' => ['"Full-time GC"', '"Full-Time SW"', '"Part-time GC"', '"Part-Time SW"', '"Bilingual GC"', '"Bilingual SW"', '"School Psychologist Providing Mandated Counseling"'],
			'filters' => [],
			'details' => [],
			'sort' => ['DBN', 'DBN'],
			'DBNkey' => 'system_code',
		],

		'health-code-violations' => [					// 251
			'fullname' => 'DOHMH School Cafeteria inspections (2020 - Present)',
			'table' => 'dohmhinspections',
			'hdrs' => ['Record ID', 'School Name', 'LastInspection', 'InspectionDate', 'PTET', 'Level', 'Code', 'ViolationDescription'],
			'visible' => [true, true, true, true, true, true, true, true],
			'flds' => ['"Record ID"', '"SchoolName"', '"LastInspection"', '"InspectionDate"', '"PTET"', '"Level"', '"Code"', '"ViolationDescription"'],
			'filters' => [],
			'details' => [],
			'sort' => [],
			'DBNkey' => 'Borough_block_lot',
		],
		
		'active-projects' => [					// 190
			'fullname' => 'Active Projects Under Construction',
			'table' => 'scaactiveprojects',
			'hdrs' => ['Building ID', 'Data As Of', 'Project Description', 'Construction Award', 'Project type'],
			'visible' => [true, true, true, true, true],
			'flds' => ['"Building ID"', '"Data As Of"', '"Project Description"', 
				'function (r) { return `<span data-content="${toFin(r["Construction Award"])}">${toFin(r["Construction Award"])}</span>` }',
				'"Project type"'],
			'filters' => [],
			'details' => [],
			'sort' => ['Building ID', 'Building ID'],
			'DBNkey' => 'location_code',
		],
		
		'project-schedules' => [					// 258
			'fullname' => 'Capital Project Schedules and Budgets',
			'table' => 'scacapitalprojectschedules',
			'hdrs' => ['Project Building Identifier', 'Project Type', 'Project Description', 'Project Phase Name', 'Project Status Name', 'Project Phase Actual Start Date', 'Project Phase Planned End Date', 'Project Phase Actual End Date', 'Project Budget Amount', 'Final Estimate of Actual Costs Through End of Phase Amount', 'Total Phase Actual Spending Amount'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true],
			'flds' => ['"Project Building Identifier"', '"Project Type "', '"Project Description"', '"Project Phase Name"', '"Project Status Name"', '"Project Phase Actual Start Date"', '"Project Phase Planned End Date"', '"Project Phase Actual End Date"', 
				'function (r) { return `<span data-content="${toFin(r["Project Budget Amount"])}">${toFin(r["Project Budget Amount"])}</span>` }',
				'function (r) { return `<span data-content="${toFin(r["Final Estimate of Actual Costs Through End of Phase Amount"])}">${toFin(r["Final Estimate of Actual Costs Through End of Phase Amount"])}</span>` }',
				'function (r) { return `<span data-content="${toFin(r["Total Phase Actual Spending Amount"])}">${toFin(r["Total Phase Actual Spending Amount"])}</span>` }',
			],
			'filters' => [],
			'details' => [],
			'sort' => [],
			'DBNkey' => 'location_code',
		],
		
		'programs' => [					// 259
			'fullname' => 'School Based Programs by Borough',
			'table' => 'scaschoolprograms',
			'hdrs' => ['Building ID', 'Project #', 'Description', 'FY', 'Total'],
			'visible' => [true, true, true, true, true],
			'flds' => ['"Building ID"', '"Project #"', '"Description"', '"FY"', 
				'function (r) { return `<span data-content="${toFin(r["Total"].replace(",", ""))}">${toFin(r["Total"].replace(",", ""))}</span>` }',
			],
			'filters' => [],
			'details' => [],
			'sort' => [],
			'DBNkey' => 'location_code',
		],
		
		'current-plan' => [					// 271
			'fullname' => 'Current Plan Programs',
			'table' => 'scacurrentplan',
			'hdrs' => ['Program Name', 'Building ID', 'Constr.Start FY', 'Description'],
			'visible' => [true, true, true, true],
			'flds' => ['"Program Name"', '"Building ID"', 
							'function (r) { return r["Constr.Start FY"] }',
							'"Description"'],
			'filters' => [],
			'details' => [],
			'sort' => ['Building ID', 'Building ID'],
			'DBNkey' => 'location_code',
		],
		
		'added-projects' => [					// 277
			'fullname' => 'Added Projects',
			'table' => 'scaaddedprojects',
			'hdrs' => ['District', 'Bldg ID', 'School', 'Boro', 'Program Category'],
			'visible' => [true, true, true, true, true],
			'flds' => ['"District"', '"Bldg ID"', '"School"', '"Boro"', '"Program Category"'],
			'filters' => [],
			'details' => [],
			'sort' => [],
			'DBNkey' => 'location_code',
		],
		
	];

	public $list = [
		'schools' => 'Schools',
		'attendance' => 'Attendance',
		'enrollment' => 'Enrollment',
		'building-enrollment-capacity' => 'Building',
		'organization-enrollment-capacity' => 'Organization',
		'race-ethnicity-gender' => 'Race/Ethnicity & Gender',
		'other-demographics' => 'Other Demographics',
		'student-housing' => 'Student Housing',
		
		'guidance-counsellors' => 'Guidance Counsellors',
		'health-code-violations' => 'Health Code Violations',
		
		'active-projects' => 'Active Projects Under Construction',
		'project-schedules' => 'Project Schedules',
		'programs' => 'Programs',
		'current-plan' => 'Current Plan',
		'added-projects' => 'Added Projects',
	];
	
	public $menu = [
		'enrollment',
		'attendance',
		'Capacity' =>
			[
				'building-enrollment-capacity',
				'organization-enrollment-capacity',
			],
		'Demographics' => 
			[
				'race-ethnicity-gender',
				'other-demographics',
				'student-housing',
			],
		'Health' => 
			[
				'guidance-counsellors',
				'health-code-violations',
			],
		'Projects' => 
			[
				'active-projects',
				'project-schedules',
				'programs',
				'current-plan',
				'added-projects',
			],
	];
	
	public function menuActiveDD($sect)
	{
		foreach ($this->menu as $h=>$items)
			if (is_array($items) && (array_search($sect, $items) !== false))
				return $h;
		return '';
	}
	
	public function get($section)
	{
		$dd = $this->dd[strtolower($section)] ?? null;
		if (!$dd)
			return $dd;
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
	
	public function stats_data_sources($dd, $school, $all=false)
	{
		$rr = $uu = $ii = [];
		
		if ($dd)
			foreach ($dd as $d)
				$ii[strtolower(str_replace('.csv', '', $d['Output Path']))] = $d;
		foreach ($dslist ?? array_merge(['schools'], $this->menu) as $k=>$mm)
		{
			if (is_string($mm))
			{
				$k = $this->list[$mm];
				$mm = [$mm];
			}
			foreach ($mm as $m)
			{
				$tbl = $this->dd[$m]['table'];
				// Check if dataset info exists before accessing it
				if (isset($ii[$tbl])) {
					// Check if school array has required keys
					if (!empty($school) && isset($school['location_code']) && isset($school['location_name'])) {
						$rr[$tbl] = [
							"<a href=\"{$ii[$tbl]['Citation URL']}\" target=\"_blank\" rel=\"nofollow\">{$ii[$tbl]['Name']}</a>",
							'<a href="' . route('schoolSection', ['code' => $school['location_code'], 'slug' => Str::slug($school['location_name'], '-'), 'section' => $m]) . "\">{$this->list[$m]}</a>",
							$this->dd[$m]['description'] ?? $ii[$tbl]['Descripton'],
							$ii[$tbl]['Last Updated'],
							'<span id="stats_' . str_replace('/', '_', $tbl) . '"></span>',
						];
					} else {
						// Fallback when school data is missing
						$rr[$tbl] = [
							"<a href=\"{$ii[$tbl]['Citation URL']}\" target=\"_blank\" rel=\"nofollow\">{$ii[$tbl]['Name']}</a>",
							$this->list[$m] ?? ucwords(str_replace('-', ' ', $m)),
							$this->dd[$m]['description'] ?? $ii[$tbl]['Descripton'],
							$ii[$tbl]['Last Updated'],
							'<span id="stats_' . str_replace('/', '_', $tbl) . '"></span>',
						];
					}
				} else {
					// Provide fallback data when dataset info is missing
					if (!empty($school) && isset($school['location_code']) && isset($school['location_name'])) {
						$rr[$tbl] = [
							"Dataset: " . ucwords(str_replace('_', ' ', $tbl)),
							'<a href="' . route('schoolSection', ['code' => $school['location_code'], 'slug' => Str::slug($school['location_name'], '-'), 'section' => $m]) . "\">{$this->list[$m]}</a>",
							$this->dd[$m]['description'] ?? "No description available",
							"N/A",
							'<span id="stats_' . str_replace('/', '_', $tbl) . '"></span>',
						];
					} else {
						$rr[$tbl] = [
							"Dataset: " . ucwords(str_replace('_', ' ', $tbl)),
							$this->list[$m] ?? ucwords(str_replace('-', ' ', $m)),
							$this->dd[$m]['description'] ?? "No description available",
							"N/A",
							'<span id="stats_' . str_replace('/', '_', $tbl) . '"></span>',
						];
					}
				}
				// Only set URL if school data is available
				if (!empty($school) && isset($school[$this->dd[$m]['DBNkey']])) {
					$uu[$tbl] = $all 
							? DatabookAPI::url("/get/schools/pstats-records_no/all/{$tbl}")
							: DatabookAPI::url("/get/schools/pstats-records_no/{$school[$this->dd[$m]['DBNkey']]}/{$tbl}");
				}
			}
		}
		return ['tbl' => $rr, 'urls' => $uu];
	}
}