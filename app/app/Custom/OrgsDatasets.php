<?php

namespace App\Custom;

use Illuminate\Support\Str;

class OrgsDatasets
{
	public $dd = [
		'expense-budget' => [											#expensebudgetonnycopendata
			'fullname' => 'Expense Budget on NYC Open Data',
			'table' => 'expensebudgetonnycopendata',					// Carto table
			'hdrs' => ['Publication Date', 'Fiscal Year', 'Budget Code Name', 'Object Class Name', 'Object Code Name', 'Adopted Budget Amount', 'Current Modified Budget Amount', 'Financial Plan Amount'],										// datatables header
			'visible' => [true, true, true, true, true, true, true, true],	// column visibility
			'flds' => [
				'function (r) { return toDashDate(r["Publication Date"]) }',
				'"Fiscal Year"', '"Budget Code Name"', '"Object Class Name"', '"Object Code Name"',
				'function (r) { return toFin(r["Adopted Budget Amount"]) }',
				'function (r) { return toFin(r["Current Modified Budget Amount"]) }',
				'function (r) { return toFin(r["Financial Plan Amount"]) }',
			],
			// datatables data source/js fetch function
			'filters' => [0 => null, 1 => null],				// filters - fld no => def value or null if empty
			'details' => [												// additional details fields
				'Adopted Budget Position' => 'Adopted Budget Position',
				'Current Modified Budget Position' => 'Current Modified Budget Position',
				'Financial Plan Position' => 'Financial Plan Position',
				'Adopted Budget - Number of Contracts' => 'Adopted Budget - Number of Contracts',
				'Current Modified Budget - Number of Contracts' => 'Current Modified Budget - Number of Contracts',
				'Unit Appropriation Number' => 'Unit Appropriation Number',
				'Unit Appropriation Name' => 'Unit Appropriation Name',
				'Budget Code Number' => 'Budget Code Number',
				'Object Class Number' => 'Object Class Number',
				'Object Code' => 'Object Code',
				'Responsibility Center Name' => 'Responsibility Center Name',
				'Responsibility Center Code' => 'Responsibility Center Code',
				'Intra-City Purchase Code' => 'Intra-City Purchase Code',
				'Personal Service/Other Than Personal Service Indicator' => 'Personal Service/Other Than Personal Service Indicator',
				'Financial Plan Savings Flag' => 'Financial Plan Savings Flag',
				'Financial Plan - Number of Contracts' => 'Financial Plan - Number of Contracts'
			],
			'script' => "$('#filter-1').val($('#filter-1 option:last-child').val()).change(); $('#filter-2').val($('#filter-2 option:last-child').val()).change();",
		],
		'projects' => [						#capitalprojects
			'fullname' => 'Capital Project Detail Data - Dollars',
			'table' => 'capitalprojectsdollarscomp',
			'description' => 'This dataset contains capital commitment plan data by project type, budget line and source of funds. The dollar values are in thousands. The dataset is updated three times a year during the Preliminary, Executive and Adopted Capital Commitment Plans.',
			'hdrs' => ['Publication Date', 'Project ID', 'Name', 'Scope', 'Category', 'Borough', 'Current Budget', 'Budget Change (%)', 'Timeline Change'],
			'visible' => [false, true, true, true, true, true, true, true, true],
			'hide_on_map_open' => '0, 5, 6, 7, 8',		// +1 for details fld is already added
			'flds' => [
				'function (r) { return toDashDate(r["PUB_DATE"]) }',
				'function (r) { return `<a href="/p/${r.PROJECT_ID}_${slug(r.PROJECT_DESCR)}">${r.PROJECT_ID}</a>` }',
				'"PROJECT_DESCR"', '"SCOPE_TEXT"', '"TYP_CATEGORY_NAME"',
				'"BORO"',
				'function (r) { return `<span data-content="${toFin(r["BUDG_CURR"], 1000)}">${toFinShortK(r["BUDG_CURR"], 1000)}</span>` }',
				'function (r) { return `<span class="${r["BUDG_ORIG"] >= r["BUDG_CURR"] ? "good" : "bad "}">${toPerc(r["BUDG_ORIG"], r["BUDG_CURR"])}</span>` }',
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
				'Planned Cost' => '`<span data-content="${toFin(r["BUDG_ORIG"], 1000)}">${toFinShortK(r["BUDG_ORIG"], 1000)}</span>`',
				'Budget Increase' => '(!r["ORIG_BUD_AMT"] 
							? "NA" 
							: (r["BUDG_DIFF"] == 0 
								? "0" 
								: (r["BUDG_DIFF"] > 0 
									? "-" 
									: `${toFinShortK(-r["BUDG_DIFF"], 1000)}`
								)
							)
					)',
				'Original Budget' => '`<span data-content="${toFin(r["BUDG_ORIG"], 1000)}">${toFinShortK(r["BUDG_ORIG"], 1000)}</span>`',
				'Prior Spending' =>  '`<span data-content="${toFin(r["CITY_PRIOR_ACTUAL"], 1000)}">${toFinShortK(r["CITY_PRIOR_ACTUAL"], 1000)}</span>`',
				'Planned Spending' => '`<span data-content="${toFin(r["CITY_PLAN_TOTAL"], 1000)}">${toFinShortK(r["CITY_PLAN_TOTAL"], 1000)}</span>`',
				'Community Boards Served' => 'r["COMMUNITY_BOARD"]',
				'Budget Lines' => 'r["BUDGET_LINE"]',
				'Site Description' => 'r["SITE_DESCR"]',
				'Explanation for Delay' => 'r["DELAY_DESC"]',
			],
			'order' => [[8, 'desc']],
		],
		'benefits-api' => [						#benefitsapi
			'fullname' => 'Benefits and Programs API on NYC Open Data',
			'table' => 'benefitsapi',
			'hdrs' => ['Program Name', 'Category', 'Blurb', 'Eligibility'],
			'visible' => [true, true, true, true],
			'flds' => ['"program_name"', '"program_category"', '"brief_excerpt"', '"population_served"'],
			'filters' => [1 => null, 3 => null],
			'fltDelim' => [3 => ','],
			'details' => [
				'Description' => 'program_description',
				'Eligibility' => 'plain_language_eligibility',
				'Get Help' => 'get_help_summary',
				'Age Groups' => 'age_group',
				'How to Apply' => 'how_to_apply_summary',
				'Required Documents' => 'required_documents_summary',
				'Languages' => 'language',
				'Apply Online' => 'how_to_apply_or_enroll_online',
				'Get Help Online' => 'get_help_online',
				'Link to Online Applications' => 'url_of_online_application',
				'Link to PDFs Applications' => 'url_of_pdf_application_forms',
				'More Info' => 'office_locations_url'
			],
		],
		'public-contacts' => [							#nycgreenbook
			'fullname' => 'Greenbook',
			'table' => 'nycgreenbook',
			'hdrs' => ['First Name', 'Middle Initial', 'Last Name', 'Name Suffix', 'Office Title', 'Division Name', 'Phone 1', 'Phone 2'],
			'visible' => [true, false, true, false, true, true, true, true],
			'flds' => ['"First Name"', '"Middle Initial"', '"Last Name"', '"Name Suffix"', '"Office Title"', '"Division Name"', '"Phone 1"', '"Phone 2"'],
			'filters' => [],
			'details' => [
				'Parent Division' => 'Parent Division',
				'Grand Parent Division' => 'Grand Parent Division',
				'Great Grand Parent Division' => 'Great Grand Parent Division',
				'Address' => 'Address',
				'City' => 'City',
				'State' => 'State',
				'Zip Code' => 'Zip Code',
				'Fax 1' => 'Fax 1',
				'Fax 2' => 'Fax 2',
				'Agency Primary Phone' => 'Agency Primary Phone',
				'Division Primary Phone' => 'Division Primary Phone',
				'Section' => 'Section'
			],
		],
		/*
		'agencypmi' => [							#agencypmi
			'fullname' => 'Agency Performance Mapping Indicators – Annual',
			'table' => 'agencypmi',
			'hdrs' => ['Geographic Unit', 'Geo ID', 'Indicator', 'FY11', 'FY12', 'FY13', 'FY14', 'FY15', 'FY16', 'FY17', 'FY18', 'FY19'], 
			'visible' => [true, true, true, false, false, false, false, false, true, true, true, true],
			'flds' => ['"Geographic Unit"', '"Geographic Identifier"', '"Indicator"',
						'function (r) { return +parseFloat(r["FY2011"]).toFixed(2) }',
						'function (r) { return +parseFloat(r["FY2012"]).toFixed(2) }',
						'function (r) { return +parseFloat(r["FY2013"]).toFixed(2) }',
						'function (r) { return +parseFloat(r["FY2014"]).toFixed(2) }',
						'function (r) { return +parseFloat(r["FY2015"]).toFixed(2) }',
						'function (r) { return +parseFloat(r["FY2016"]).toFixed(2) }',
						'function (r) { return +parseFloat(r["FY2017"]).toFixed(2) }',
						'function (r) { return +parseFloat(r["FY2018"]).toFixed(2) }',
						'function (r) { return +parseFloat(r["FY2019"]).toFixed(2) }'
					],
			'filters' => [0 => null, 1 => null],
			'details' => [],
		],
		*/
		'requests' => [						#budgetrequestsregister
			'fullname' => 'Register of Community Board Budget Requests API',
			'table' => 'budgetrequestsregister',
			'hdrs' => ['Publication Date', 'Borough', 'C Board', 'Priority', 'Tracking Code', 'Request', 'Council District', 'NTA'],
			'visible' => [true, true, true, true, true, true, false, false],
			'flds' => [
				'function (r) { return toDashDate(r["Publication"]) }',
				'"Borough"', '"Community Board"', '"Priority"', '"Tracking  Code"', '"Request"', '"wegov-cd-id"', '"wegov-nta-code"'
			],
			'filters' => [0 => null, 1 => null, 2 => null, 3 => null],
			'details' => [
				'Explanation' => 'Explanation',
				'Response' => 'Response',
				'Responded By' => 'Responded By',
				'Responsible Agency' => 'Responsible Agency',
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
			'map' => ['cc' => 7, 'nta' => 8],
			'script' => "datatable.order([1, 'desc']).draw();",
		],
		'jobs' => [							#nycjobs
			'fullname' => 'NYC Jobs',
			'table' => 'nycjobs',
			'hdrs' => ['Job ID', 'Title', 'Job Category', 'Salary From', 'Salary To', 'Last Updated'],
			'flds' => [
				#'function (r) { return `<a href="https://a127-jobs.nyc.gov/index_new.html?keyword=${r["Job ID"]}" rel="nofollow">${r["Job ID"]}</a>` }',
				'function (r) { return `<a href="https://cityjobs.nyc.gov/jobs?q={${r["Job ID"]}}" rel="nofollow" target="_blank">${r["Job ID"]}</a>` }',
				'"Business Title"',
				'"Job Category"',
				'function (r) { return toFin(r["Salary Range From"]) }',
				'function (r) { return toFin(r["Salary Range To"]) }',
				'function (r) { return usToDashDate(r["Posting Updated"]) }',
			],
			'visible' => [true, true, true, true, true, true],
			'filters' => [2 => null],
			'details' => [
				'# Of Positions' => '# Of Positions',
				'Civil Service Title' => 'Civil Service Title',
				'Title Classification' => 'Title Classification',
				'Title Code No' => 'Title Code No',
				'Level' => 'Level',
				'Full-Time/Part-Time indicator' => 'Full-Time/Part-Time indicator',
				'Career Level' => 'Career Level',
				'Work Location' => 'Work Location',
				'Division/Work Unit' => 'Division/Work Unit',
				'Job Description' => 'Job Description',
				'Minimum Qual Requirements' => 'Minimum Qual Requirements',
				'Preferred Skills' => 'Preferred Skills',
				'Additional Information' => 'Additional Information',
				'To Apply' => 'To Apply',
				'Residency Requirement' => 'Residency Requirement'
			],
			'description' => 'This dataset contains current job postings available on the City of New York’s <a href="http://www.nyc.gov/html/careers/html/search/search.shtml" target="_blank" rel="nofollow"> official jobs site</a>. Internal postings available to city employees and external postings available to the general public are included.',
			'script' => "datatable.order([6, 'desc']).draw();",
		],
		'jobs-about' => [							#nycjobs - org about page
			'fullname' => 'NYC Jobs',
			'table' => 'nycjobs',
			'hdrs' => ['Job ID', 'Title', 'Job Category', 'Salary From', 'Salary To', 'Last Updated'],
			'flds' => [
				#'function (r) { return `${r["Job ID"]}` }',
				'function (r) { return `<a href="https://cityjobs.nyc.gov/jobs?q=${r["Job ID"]}" rel="nofollow" target="_blank">${r["Job ID"]}</a>` }',
				'"Business Title"',
				'"Job Category"',
				'function (r) { return toFin(r["Salary Range From"]) }',
				'function (r) { return toFin(r["Salary Range To"]) }',
				'function (r) { return usToDashDate(r["Posting Updated"]) }',
			],
			'visible' => [true, true, true, true, true, true],
			'filters' => [1 => null],
			'details' => [
				'# Of Positions' => '# Of Positions',
				'Civil Service Title' => 'Civil Service Title',
				'Title Classification' => 'Title Classification',
				'Title Code No' => 'Title Code No',
				'Level' => 'Level',
				'Full-Time/Part-Time indicator' => 'Full-Time/Part-Time indicator',
				'Career Level' => 'Career Level',
				'Work Location' => 'Work Location',
				'Division/Work Unit' => 'Division/Work Unit',
				'Job Description' => 'Job Description',
				'Minimum Qual Requirements' => 'Minimum Qual Requirements',
				'Preferred Skills' => 'Preferred Skills',
				'Additional Information' => 'Additional Information',
				'To Apply' => 'To Apply',
				'Residency Requirement' => 'Residency Requirement'
			],
			'description' => 'This dataset contains current job postings available on the City of New York’s <a href="http://www.nyc.gov/html/careers/html/search/search.shtml" target="_blank" rel="nofollow"> official jobs site</a>. Internal postings available to city employees and external postings available to the general public are included.',
		],
		'facilities' => [						#facilitydb
			'fullname' => 'NYC Facilities Database',
			'table' => 'facilitydb',
			'hdrs' => ['Name', 'Category', 'Group', 'Subgroup', 'Address', 'Borough', 'Council District', 'NTA'],
			'visible' => [true, true, true, true, true, true, false, false],
			'flds' => ['"facname"', '"facdomain"', '"facgroup"', '"facsubgrp"', '"address"', '"boro"', '"wegov-cd-id"', '"wegov-nta-code"'],
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
			'map' => ['cc' => 7, 'nta' => 8],
		],


		'indicators' => [								#onenycindicators
			'fullname' => 'OneNYC Indicators',
			'table' => 'onenycindicators',
			'hdrs' => ['Vision', 'Goal', 'Indicator', 'Report Year', 'Indicator Value', 'Measurement Type', 'Target Value', 'Target Year'],
			'visible' => [false, true, true, true, true, true, true, true, true],
			'flds' => ['"Vision"', '"Goal"', '"Indicator"', '"Report Year"', '"Indicator Value"', '"Measurement Type"', '"Target Value"', '"Target Year"'],
			'filters' => [],
			'details' => [],
			'description' => 'Annual Agency Performance Metrics',
		],
		'agency-performance' => [						#agencyperformance
			'fullname' => 'FY2021 MMR Agency Performance Indicators',
			'table' => 'fy2021mmragencyperformance',
			'hdrs' => ['Performance Indicator', 'FY17', 'FY18', 'FY19', 'FY20', 'FY21', 'TGT21', 'TGT22', '5yr Trend', 'Desired Direction', 'Outcome', 'Critical'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, false, false],
			'flds' => [
				'"Performance Indicator"', '"FY17"', '"FY18"', '"FY19"', '"FY20"', '"FY21"', '"TGT21"', '"TGT22"',
				'function (r) {
						var a = r["5yr Trend"]
						var b = r["Desired Direction"]
						var status = null
						if (a == b)
							status = "Good"
						else if (b != "*") {
							if (a == "Neutral")
								status = "Neutral"
							else if (a != b)
								status = "Bad"
						}
						return status ? `<span class="${status.toLowerCase()}">${a}</span>` : status
					}',
				'"Desired Direction"',
				'function (r) { 
						var a = r["5yr Trend"]
						var b = r["Desired Direction"]
						var status = "No Desired Direction"
						if (a == b)
							status = "Good"
						else if (b != "*") {
							if (a == "Neutral")
								status = "Neutral"
							else if (a != b)
								status = "Bad"
						}
						return status
					}',
				'"Critical"'
			],
			'filters' => [10 => null, 11 => null],
			'details' => [
				'MMR Goal' => 'MMR Goal',
				'Critical' => 'Critical',
			],
			'description' => 'NYC agency performance indicators from the FY2021 Mayor\'s Management Report (MMR). This dataset reflects measures of agency performance, organized by goal, including five full years of data for the most recent fiscal years wherever available.',
		],
		'agency-resources' => [						#agencyresources
			'fullname' => 'FY2021 MMR Agency Resources',
			'table' => 'fy2021mmragencyresources',
			'hdrs' => ['Resource Indicators', 'FY17 Actual', 'FY18 Actual', 'FY19 Actual', 'FY20 Actual', 'FY21 Actual (Not Yet Final)', 'FY21 (Authorized Bugdet Level)', 'FY22 (Authorized Bugdet Level)', '5yr Trend'],
			'visible' => [false, true, true, true, true, true, true, true, true],
			'flds' => ['"Resource Indicators"', '"FY17 Actual"', '"FY18 Actual"', '"FY19 Actual"', '"FY20 Actual"', '"FY21 Actual (Not Yet Final)"', '"FY21 (Authorized Bugdet Level)"', '"FY22 (Authorized Bugdet Level)"', '"5yr Trend"'],
			'filters' => [],
			'details' => [
				'Notes' => 'Notes'
			],
			'description' => 'NYC agency resources from the FY21 Mayor\'s Management Report (MMR), including expenditures (includes all funds), personnel, revenue and paid overtime. This data is an overview of the financial and workforce resources used by an agency over the past five fiscal years and the planned resources available to the agency in the current and upcoming fiscal years.<br/>The FY2021 MMR, archived reports, and additional information is available at <a href="https://www1.nyc.gov/site/operations/performance/mmr.page" target="_blank" rel="nofollow">https://www1.nyc.gov/site/operations/performance/mmr.page</a>.',
		],



		'local-law-251' => [								#locallaw251
			'fullname' => 'Local Law 251 of 2017: Published Data Asset Inventory',
			'table' => 'locallaw251',
			'hdrs' => ['Name', 'Type', 'Category', 'Open Data Plan', 'Last Updated', 'Visits', 'Row Count', 'Column Count', 'URL', 'Last Updated Timestamp'],
			'visible' => [true, true, true, true, true, true, false, false, false, false],
			'flds' => [
				'function (r) { return `<a href="${r["url"]}" target="_blank" rel="nofollow">${r["Name"]}</a>` }',
				'"Type"', '"Category"', '"Legislative Compliance: Dataset from the Open Data Plan?"', '"Last Data Updated Date (UTC)"', '"Visits"', '"Row Count"', '"Column Count"', '"url"',
				'function (r) { return Date.parse(r["Last Data Updated Date (UTC)"]) }',
			],
			'filters' => [1 => null, 2 => null, 3 => null],
			'details' => [
				'Description' => 'Description',
				'Update: Date Made Public' => 'Update: Date Made Public',
				'Update: Update Frequency' => 'Update: Update Frequency',
				'Legislative Compliance: Can Dataset Feasibly Be Automated?' => 'Legislative Compliance: Can Dataset Feasibly Be Automated?',
				'Update: Automation' => 'Update: Automation',
				'Legislative Compliance: Has Data Dictionary?' => 'Legislative Compliance: Has Data Dictionary?',
				'Legislative Compliance: Contains Address?' => 'Legislative Compliance: Contains Address?',
				'Legislative Compliance: Geocoded?' => 'Legislative Compliance: Geocoded?',
				'Legislative Compliance: Exists Externally? (LL 110/2015)' => 'Legislative Compliance: Exists Externally? (LL 110/2015)',
				'Legislative Compliance: External Frequency (LL 110/2015)' => 'Legislative Compliance: External Frequency (LL 110/2015)',
				'Legislative Compliance: Removed Records?' => 'Legislative Compliance: Removed Records?',
				'UID' => 'UID',
			],
			'description' => 'As per Local Law 251 of 2017, the Open Data plan is required to include the following comprehensive information on each dataset on the Open Data Portal:
- Most recent update date;
- URL;
- Whether it complies with data retention standard (which mandates that row-level data be maintained on the dataset);
- Whether it has a data dictionary;
- Whether it meets the geocoding standard, does not meet the geocoding, or is ineligible for the geospatial standard;
- Whether updates to the dataset are automated;
- Whether updates to the dataset “feasibly can be automated”.
-----
For a list of all datasets that were included on all the NYC Open Data plans (2013-2020) and their current release status, please refer to NYC Open Data Release Tracker.',
			'script' => "datatable.order([10, 'desc']).draw();",

		],
		'city-council-discretionary' => [									#nyccouncildiscretionaryfunding
			'fullname' => 'New York City Council Discretionary Funding',
			'table' => 'nyccouncildiscretionaryfunding',
			'hdrs' => ['Fiscal Year', 'Source', 'Council Member', 'Legal Name of Organization', 'Status', 'Amount ($)', 'Borough', 'Council District', 'NTA'],
			'visible' => [true, true, true, true, true, true, true, true, false],
			'flds' => [
				'"Fiscal Year"', '"Source"', '"Council Member"',
				'function (r) { return `<a href="https://projects.propublica.org/nonprofits/organizations/${r["EIN"]}" target="_blank" rel="nofollow">${r["Legal Name of Organization"]}</a>` }',
				'"Status"', '"Amount ($)"', '"Borough"', '"Council District"', '"wegov-nta-code"'
			],
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
			'map' => ['cc' => 8, 'nta' => 9],
			'script' => "datatable.order([1, 'desc']).draw();",
			#'script' => "$('#filter-1').val($('#filter-1 option:last-child').val()).change();",
		],
		'data-tracker' => [							#opendatareleasetracker
			'fullname' => 'NYC Open Data Release Tracker',
			'table' => 'opendatareleasetracker',
			'hdrs' => ['Name', 'Original Plan Date', 'Latest Plan Date', 'Release Status', 'Release Date', 'Latest Open Data Plan', 'URL', 'Frequency'],
			'visible' => [true, true, true, true, true, true, false, false],
			'flds' => [
				'function (r) { return `<a href="${r["URL"]}" target="_blank" rel="nofollow">${r["Dataset Name"]}</a>` }',
				'function (r) { return usToDashDate(r["Original Plan Date"]) }',
				'function (r) { return usToDashDate(r["Latest Plan Date"]) }',
				'"Release Status"',
				'function (r) { return usToDashDate(r["Release Date"]) }',
				'"From the Latest Open Data Plan"', '"URL"', '"Update Frequency"'
			],
			'filters' => [3 => null, 5 => null],
			'details' => [
				'Description' => 'Dataset Description',
				'UID' => 'U ID',
				'Agency Notes' => 'Agency Notes',
			],
			'description' => 'A list of all datasets that were included on all the NYC Open Data plans (2013-2019) and their current release status. For a comprehensive information on each dataset on the Open Data Portal, please refer to Local Law 251 of 2017: Published Data Asset Inventory.',
			'script' => "datatable.order([5, 'desc']).draw();",
		],

		'expense-plan' => [						#expenseplan
			'fullname' => 'Expense Financial Plan - Exec',
			'table' => 'expenseplan',
			'hdrs' => ['Publication Date', 'Line Number Description', 'Fiscal Year 1', 'Prior Year Actual', 'Year 1 Executive Bud', 'Year 1 Actual', 'Year 1 Forecast', 'Year 2 Estimate', 'Year 3 Estimate', 'Year 4 Estimate', 'Year 5 Estimate'],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true],
			'flds' => [
				'function (r) { return (r["Publication Date"].search(/[/]/g) > 0) ? usToDashDate(r["Publication Date"]) : toDashDate(r["Publication Date"]) }',
				#'"Publication Date"', 
				'"Line Number Description"', '"Fiscal Year 1"', '"Prior Year Actual"', '"Year 1 Executive Bud"', '"Year 1 Actual"', '"Year 1 Forecast"', '"Year 2 Estimate"', '"Year 3 Estimate"', '"Year 4 Estimate"', '"Year 5 Estimate"'],
			'filters' => [0 => 'option:last-child', 2 => null],
			'details' => [],
			'description' => 'This dataset contains agency summary level data for PS, OTPS and Total by type of funds. The dollar amount fields are rounded to the thousands. The Executive Budget report, published in April or May, contains previous fiscal year actuals, the current fiscal year Executive budget, eight month actuals and forecast plus four out years of data which coincide with the release of the published financial plan.',
			'script' => "$('#filter-0').val($('#filter-0 option:last-child').val()).change(); datatable.order([1, 'asc']).draw();",
		],
		'headcount-actuals' => [			#headcountactualsfunding
			'fullname' => 'Headcount Actuals By Funding Source',
			'table' => 'headcountactualsfunding',
			'hdrs' => ['Publication Date', 'Fiscal Year', 'Funding', 'Headcount'],
			'visible' => [true, true, true, true],
			'flds' => [
				'function (r) { return toDashDate(r["PUBLICATION DATE"]) }',
				#'"PUBLICATION DATE"', 
				'"FISCAL YEAR"', '"FUNDING"', '"HEADCOUNT"'
			],
			'filters' => [0 => null, 1 => null],
			'details' => [],
			'description' => 'Funding of the actual Full-Time and Full-Time equivalent headcount that appears in the Mayor\'s Message Agency Financial tables. This dataset is updated annually.',
			'charts' => true,
		],
		'expense-actuals' => [			#expenseactualsfunding
			'fullname' => 'Expense Actuals By Funding Source',
			'table' => 'expenseactualsfunding',
			'hdrs' => ['Publication Date', 'Fiscal Year', 'Funding', 'Amount'],
			'visible' => [true, true, true, true],
			'flds' => [
				'function (r) { return toDashDate(r["PUBLICATION DATE"]) }',
				#'"PUBLICATION DATE"', 
				'"FISCAL YEAR"', '"FUNDING"', '"AMOUNT"'
			],
			'filters' => [0 => null, 1 => null],
			'details' => [],
			'description' => 'Funding of actual spending that appears in the Mayor\'s Message Agency Financial tables. Dollars are in Thousands. This dataset is updated annually.',
			'script' => "$('#filter-0').val($('#filter-0 option:last-child').val()).change();",
		],
		'additional-costs-allocation' => [						#additionalcostsallocation
			'fullname' => 'Additional Costs Allocation',
			'table' => 'additionalcostsallocation',
			'hdrs' => ['Publication Date', 'Cost Category', 'Actual\Plan', 'Fiscal Year', 'Total Amount', 'City Amount', 'Intra-City Amount'],
			'visible' => [true, true, true, true, true, true, true],
			'flds' => [
				'function (r) { return toDashDate(r["PUBLICATION DATE"]) }',
				#'"PUBLICATION DATE"', 
				'"COST CATEGORY"', '"ACTUAL\\\PLAN"', '"FISCAL YEAR"', '"TOTAL AMOUNT"', '"CITY AMOUNT"', '"INTRA-CITY AMOUNT"'
			],
			'filters' => [0 => null, 1 => null, 3 => null],
			'details' => [],
			'description' => 'Additional agency costs for Pension, Fringe Benefits and Debt Service that are included in the Pensions, Miscellaneous Budget and Debit Service agencies. Dollars are In thousands. This data set is updated annually.',
			'script' => "$('#filter-0').val($('#filter-0 option:last-child').val()).change();",
		],
		'publications' => [						#govpublist
			'fullname' => 'Government Publications Listing',
			'table' => 'govpublist',
			'hdrs' => ['Title', 'Sub-Title', 'Subject', 'Description', 'Date Published', 'Report Type', 'Associated Year - Calendar', 'Last Modified'],
			'visible' => [true, true, true, true, true, true, true, true],
			'flds' => ['"Title"', '"Sub-Title"', '"Subject"', '"Description"', '"Date Published"', '"Report Type"', '"Associated Year - Calendar"', '"Last Modified"'],
			'filters' => [2 => null, 5 => null],
			'details' => [
				'Required Report Name' => 'Required Report Name',
				'Additional Creators' => 'Additional Creators',
				'Languages' => 'Languages',
				'Associated Year - Fiscal' => 'Associated Year - Fiscal',
				'Associated Borough' => 'Associated Borough',
				'Associate School District' => 'Associate School District',
				'Associated Community Board District' => 'Associated Community Board District',
				'Associated Place' => 'Associated Place',
				'Filename' => 'Filename',
			],
			'description' => 'Metadata for documents submitted to the Department of Records and Information Services in compliance with Section 1133 of the New York City Charter.',
		],
		'required-reports' => [				#govpubrequired
			'fullname' => 'Government Publication- Required Reports',
			'table' => 'govpubrequired',
			'hdrs' => ['Name', 'Description', 'Frequency', 'Local Law', 'Charter Code', 'Last Published Date'],
			'visible' => [true, true, true, true, true, true, true, true],
			'flds' => [
				'function (r) { return `<a href="${r["See All Reports"]}" target="_blank" rel="nofollow">${r["Name"]}</a>` }',
				'"Description"', '"Frequency"', '"Local Law"', '"Charter Code"', '"Last Published Date"'
			],
			'filters' => [],
			'details' => [],
			'description' => 'Metadata for documents submitted to the Department of Records and Information services which are required by legislation.',
		],
		'headcount' => [						#fteheadcount
			'fullname' => 'Full-Time and FTE Headcount including Covered Organizations',
			'table' => 'fteheadcount',
			'hdrs' => ['Agency Code', 'Agency Name', 'Fiscal Year', 'Publication Date', 'Personnel Type', 'Agency Group', 'City Funded Positions', 'Total Funded Positions'],
			'flds' => [
				'"Agency Code"', '"Agency Name"', '"Fiscal Year"',
				//'function (r) { return toDashDate(r["Publication Date"]); }',
				'function (r) { return toUsDateNowrap(r["Publication Date"]); }',
				//'"Publication Date"',
				'"Personnel Type"', '"Agency Group"', '"City Funds"', '"Total Funds"'
			],
			'visible' => [false, false, true, true, true, true, true, true],
			'filters' => [2 => null],
			'pubdate_filter' => [3 => 'option:last-child'],				# column_no, def value selector
			'details' => [],
			'description' => 'This dataset contains estimated fiscal year-end headcount information for full-time and full-time equivalent employees (FTE) for Mayoral Agencies and Covered Organizations (updated twice a year). The information is summarized by agency, fiscal year, personnel type and funding. This dataset is updated biannually.',
			'charts' => true,

		],
		'positions' => [						#positionschedule
			'fullname' => 'Position Schedule',
			'table' => 'positionschedule',
			'hdrs' => ['Publication Date', 'Agency Code', 'Agency Name', 'UA code', 'UA name', 'Title Code Name', 'Scheduled Positions', 'Minimum Salary', 'Mean Salary', 'Maximum Salary', 'Total Spent Annually'],
			'flds' => [
				//'function (r) { return toDashDate(r["PUBLICATION DATE"]); }',
				'function (r) { return toUsDateNowrap(r["PUBLICATION DATE"]); }',
				'"AGENCY CODE"', '"AGENCY NAME"', '"UA CODE"', '"UA NAME"',
				'function (r) { return `<a href="/t/${r["TITLE CODE"]}-${slug(r["TITLE CODE NAME"])}">${r["TITLE CODE NAME"]}</a>` }',
				'"POSITIONS"',
				'function (r) { return toFin(r["MINMUM SALARY"]) }',
				'function (r) { return toFin(r["MEAN SALARY"]) }',
				'function (r) { return toFin(r["MAXMUM SALARY"]) }',
				'function (r) { return toFin(r["ANNUAL RATE"]) }',

			],
			'visible' => [false, false, false, true, true, true, true, true, true, true, true, true],
			'filters' => [],
			'pubdate_filter' => [0 => 'option:last-child'],
			'details' => [],
			'description' => 'Sum of the full-time active positions in a title description published in alphabetical order. The Position Schedule is updated and included in the Departmental Estimates and the Supporting Schedule (updated twice a year). The minimum salary, maximum salary, mean salary and annual rate are to the dollar. This dataset is updated biannually.',
			'script' => "datatable.order([10, 'desc']).draw();",
			'charts' => true,
		],
		'demographics' => [						#ll18payanddemo
			'fullname' => 'Local Law 18 Pay and Demographics Report - Agency Report Table',
			'table' => 'll18payanddemo',
			'hdrs' => ['Agency Name', 'EEO-4 Job Category', 'Pay Band', 'Employee Status', 'Race', 'Ethnicity', 'Gender', 'Number of Employees'],
			'flds' => [
				'"Agency Name"', '"Equal Employment Opportunity (EEO)-4 Job Category"',
				'function (r) { 
							var bb = r["Pay Band"].split("-")
							return bb ? toFin(bb[0]) + "-" + toFin(bb[1]) : "";
						}',
				'"Employee Status"', '"Race"', '"Ethnicity"', '"Gender"', '"Number of Employees"'
			],
			'visible' => [false, true, true, true, true, true, true, true],
			'filters' => [1 => null, 4 => null, 6 => null],
			'details' => [],
			'description' => 'The Agency Report Table aggregates pay and employment characteristics in accordance with the requirements of Local Law 18 of 2019. The Table covers over 180,000 City employees and is a point-in-time snapshot of employees who were either active or on temporary leave (parental leave, military leave, illness, etc.) as of December 31st, 2018. To protect the privacy of employees, the sign “<5” is used instead of the actual number for groups of less than five (5) employees, in accordance with the Citywide Privacy Protection Policies and Protocols.<br/>The Pay and Demographics Report and the list of agencies included is available on the <a href="https://moda-nyc.github.io/Project-Library/projects/pay-and-demographics/" target="_blank" rel="nofollow">MODA Open Source Analytics Library</a>.',
			'script' => '',
		],
		'civil-list' => [						#civillist
			'fullname' => 'Civil List',
			'table' => 'civillist',
			'hdrs' => ['Calendar Year', 'Agency Code', 'Employee Name', 'Agency Name', 'Title Code', 'Pay Class', 'Salary Rate'],
			'flds' => [
				'"CALENDAR YEAR"', '"AGENCY CODE"', '"EMPLOYEE NAME"', '"AGENCY NAME"',
				'function (r) { return r["wegov-service-title-id"] ? (`<a href="/t/${r["wegov-service-title-id"]}-${slug(r["wegov-service-title-desc"])}">${r["wegov-service-title-id"]}</a>`) : "" }',
				'"PAY CLASS"', '"SALARY RATE"'
			],
			'visible' => [true, false, true, false, true, true, true],
			'filters' => [0 => null, 4 => null, 5 => null],
			'details' => [],
			'description' => 'The Civil List reports the agency code (DPT), first initial and last name (NAME), agency name (ADDRESS), title code (TTL #), pay class (PC), and salary (SAL-RATE) of individuals who were employed by the City of New York at any given time during the indicated year.',
			'script' => 'datatable.order([0, "desc"]).draw();',

		],



		'notices' => [							#notices/all
			'fullname' => 'City Record Online (CROL)',
			'table' => 'crol',
			'fapireq' => '/get/orgs/notices/%s',
			'hdrs' => ['Start Date', 'Request ID', 'Type Of Notice Description', 'Category Description', 'Short Title', 'Section Name',],
			'visible' => [true, true, true, true, true, true],
			'flds' => [
				'function (r) { return usToDashDate(r["StartDate"]); }',
				'function (r) { return `<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${r["RequestID"]}" target="_blank" rel="nofollow">${r["RequestID"]}</a>` }',
				'"TypeOfNoticeDescription"', '"CategoryDescription"', '"ShortTitle"', '"SectionName"'
			],
			'filters' => [2 => null, 3 => null, 5 => null],
			'details' => [
				'Start Date' => 'StartDate',
				'End Date' => 'EndDate',
				'Due Date' => 'DueDate',
				'PIN' => 'PIN',
				'Additional Description1' => 'AdditionalDescription1',
				'Other Info 1' => 'OtherInfo1',
				'Printout 1' => 'Printout1',
				'Address To Request' => 'AddressToRequest',
				'Contact Name' => 'ContactName',
				'Contact Phone' => 'ContactPhone',
				'Email' => 'Email',
				'Contract Amount' => 'ContractAmount',
				'Special Case Reason Description' => 'SpecialCaseReasonDescription',
				'Selection Method Description' => 'SelectionMethodDescription',
				'Contact Fax' => 'ContactFax',
				'Additional Desctription 2' => 'AdditionalDesctription2',
				'Other Info 2' => 'OtherInfo2',
				'Printout 2' => 'Printout2',
				'Additional Description 3' => 'AdditionalDescription3',
				'Other Info 3' => 'OtherInfo3',
				'Printout 3' => 'Printout3',
				'Vendor Name' => 'VendorName',
				'Vendor Address' => 'VendorAddress',
				'Document Links' => 'DocumentLinks',
			],
			'description' => 'New York City’s <a href="https://en.wikipedia.org/wiki/Government_gazette" target="_blank" rel="nofollow">official journal</a> is called “The City Record.” It’s published in print, and online as a <a href="https://www1.nyc.gov/site/dcas/about/city-record.page" target="_blank" rel="nofollow">PDF</a>, as a <a href="https://a856-cityrecord.nyc.gov/" target="_blank" rel="nofollow">website</a> and as <a href="https://data.cityofnewyork.us/City-Government/City-Record-Online/dg92-zbpx/data" target="_blank" rel="nofollow">open data</a>. We’ve used the open data version, which is updated daily, to integrate The City Record’s contents into the WeGov data system. We also created RSS news and ICS event feeds from the data, and created new ways to search and browse this information. Please <a href="https://wegov.nyc/contact/" target="_blank" rel="nofollow">let us know</a> if you have ideas for how we can improve this resource.',
			'script' => 'datatable.order([1, "desc"]).draw();',
		],
		'change-of-personnel' => [					#notices/changeofpersonnel
			'fullname' => 'City Record Online (CROL)',
			'table' => 'crol',
			'fapireq' => '/get/orgs/changeofpersonnel/%s',
			'sectionTitle' => 'Change of Personnel',
			'hdrs' => ['Effective Date', 'Provisional Status', 'Title Code', 'Reason For Change', 'Salary', 'Employee Name'],
			'flds' => [
				'function (r) { return usToDashDate(r["AdditionalDescription1"].split(";")[0].replace("Effective Date: ", "")); }',
				'function (r) { return r["AdditionalDescription1"].split(";")[1].replace("Provisional Status: ", ""); }',
				'function (r) { 
						var code = r["AdditionalDescription1"].split(";")[2].replace("Title Code: ", "").trim();
						return `<a href="/t/${code}-${code}">${code}</a>`;
					}',
				'function (r) { return r["AdditionalDescription1"].split(";")[3].replace("Reason For Change: ", ""); }',
				'function (r) { return toFin(r["AdditionalDescription1"].split(";")[4].replace("Salary: ", "")); }',
				'function (r) { return r["AdditionalDescription1"].split(";")[5].replace("Employee Name: ", ""); }',
			],
			'visible' => [true, true, true, true, true, true],
			'filters' => [3 => null],
			'details' => [],
			'description' => 'List of people moving into and out of city government positions.',
			'script' => 'datatable.order([0, "desc"]).draw();',
		],
		'public-hearings' => [					#notices/publichearings
			'fullname' => 'City Record Online (CROL)',
			'table' => 'crol',
			'fapireq' => '/get/orgs/publichearings/%s',
			'sectionTitle' => 'Public Hearings and Meetings',
			'hdrs' => ['Request ID', 'Agency Name', 'Type Of Notice Description', 'Short Title', 'Date', 'Location'],
			'flds' => [
				'function (r) { return `<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${r["RequestID"]}" target="_blank" rel="nofollow">${r["RequestID"]}</a>` }',
				'"wegov-org-name"', '"TypeOfNoticeDescription"', '"ShortTitle"',
				'function (r) { return usToDashDate(r["EventDate"]) }',
				'function (r) { 
						var rr = [r["EventStreetAddress1"], r["EventStreetAddress2"], r["EventCity"], r["EventStateCode"], r["EventZipCode"]];
						while (true) {
							var i = rr.indexOf("");
							if (i == -1) {
							  break;
							} else {
							  rr.splice(i, 1);
							}
						  }
						return rr.join(", ")
					}',
			],
			'visible' => [true, true, true, true, true, true, true, true, true, true],
			'filters' => [2 => null],
			'details' => [
				'Additional Description' => 'AdditionalDescription1',
				'Start Date' => 'StartDate',
				'End Date' => 'EndDate',
				'Event Building Name' => 'EventBuildingName',
			],
			'description' => 'Hearings and meetings open to the public.',
			'script' => 'datatable.order([1, "asc"]).draw();',
		],
		'contract-awards' => [							#notices/contractawards
			'fullname' => 'City Record Online (CROL)',
			'table' => 'crol',
			'fapireq' => '/get/orgs/contractawards/%s',
			'sectionTitle' => 'Contract Award Hearings',
			'hdrs' => ['Request ID', 'Agency Name', 'Type Of Notice Description', 'Short Title', 'Date', 'Location'],
			'flds' => [
				'function (r) { return `<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${r["RequestID"]}" target="_blank" rel="nofollow">${r["RequestID"]}</a>` }',
				'"wegov-org-name"', '"TypeOfNoticeDescription"', '"ShortTitle"',
				'function (r) { return usToDashDate(r["EventDate"]) }',
				'function (r) { 
						var rr = [r["EventStreetAddress1"], r["EventStreetAddress2"], r["EventCity"], r["EventStateCode"], r["EventZipCode"]];
						while (true) {
							var i = rr.indexOf("");
							if (i == -1) {
							  break;
							} else {
							  rr.splice(i, 1);
							}
						  }
						return rr.join(", ")
					}',
			],
			'visible' => [true, true, true, true, true, true, true, true, true, true],
			'filters' => [2 => null],
			'details' => [
				'Additional Description' => 'AdditionalDescription1',
				'Document Links' => 'DocumentLinks',
				'Start Date' => 'StartDate',
				'End Date' => 'EndDate',
				'Event Building Name' => 'EventBuildingName',
				'Additional Desctription 2' => 'AdditionalDesctription2',
				'Contact Name' => 'ContactName',
				'Contact Phone' => 'ContactPhone',
				'Email' => 'Email',
			],
			'description' => 'Any contract over $100,000 is subject to a public hearing unless excepted by the City Charter or Rules of the Procurement Policy Board.',
			'script' => 'datatable.order([1, "asc"]).draw();',
		],
		'special-materials' => [						#notices/specialmaterials
			'fullname' => 'City Record Online (CROL)',
			'table' => 'crol',
			'fapireq' => '/get/orgs/specialmaterials/%s',
			'sectionTitle' => 'Special Materials',
			'hdrs' => ['Request ID', 'Start Date', 'Agency Name', 'Type Of Notice Description', 'Short Title', 'Location'],
			'flds' => [
				'function (r) { return `<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${r["RequestID"]}" target="_blank" rel="nofollow">${r["RequestID"]}</a>` }',
				'function (r) { return usToDashDate(r["StartDate"]) }',
				'"wegov-org-name"', '"TypeOfNoticeDescription"', '"ShortTitle"',
				'function (r) { 
						var rr = [r["EventStreetAddress1"], r["EventStreetAddress2"], r["EventCity"], r["EventStateCode"], r["EventZipCode"]];
						while (true) {
							var i = rr.indexOf("");
							if (i == -1) {
							  break;
							} else {
							  rr.splice(i, 1);
							}
						  }
						return rr.join(", ")
					}',
			],
			'visible' => [true, true, true, true, true, true],
			'filters' => [3 => null],
			'details' => [
				'Additional Description' => 'AdditionalDescription1',
				'End Date' => 'EndDate',
			],
			'description' => 'Other category including things like commodity prices and concept papers.',
			'script' => 'datatable.order([1, "asc"]).draw();',
		],
		'agency-rules' => [							#notices/agencyrules
			'fullname' => 'City Record Online (CROL)',
			'table' => 'crol',
			'fapireq' => '/get/orgs/agencyrules/%s',
			'sectionTitle' => 'Agency Rules',
			'hdrs' => ['Request ID', 'Agency Name', 'Type Of Notice Description', 'Short Title', 'Date', 'Location'],
			'flds' => [
				'function (r) { return `<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${r["RequestID"]}" target="_blank" rel="nofollow">${r["RequestID"]}</a>` }',
				'"wegov-org-name"', '"TypeOfNoticeDescription"', '"ShortTitle"',
				'function (r) { return usToDashDate(r["EventDate"]) }',
				'function (r) { 
						var rr = [r["EventStreetAddress1"], r["EventStreetAddress2"], r["EventCity"], r["EventStateCode"], r["EventZipCode"]];
						while (true) {
							var i = rr.indexOf("");
							if (i == -1) {
							  break;
							} else {
							  rr.splice(i, 1);
							}
						  }
						return rr.join(", ")
					}',
			],
			'visible' => [true, true, true, true, true, true, true, true, true, true],
			'filters' => [2 => null],
			'details' => [
				'Additional Description' => 'AdditionalDescription1',
				'Start Date' => 'StartDate',
				'End Date' => 'EndDate',
				'Document Links' => 'DocumentLinks',
			],
			'description' => 'Notices related to propose and adopted rules as well as regulatory agendas.',
			'script' => 'datatable.order([1, "asc"]).draw();',
		],
		'property-disposition' => [							#notices/propertydisposition
			'fullname' => 'City Record Online (CROL)',
			'table' => 'crol',
			'fapireq' => '/get/orgs/propertydisposition/%s',
			'sectionTitle' => 'Property Disposition',
			'hdrs' => ['Request ID', 'Start Date', 'Agency Name', 'Type Of Notice Description', 'Short Title', 'Date', 'Location'],
			'flds' => [
				'function (r) { return `<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${r["RequestID"]}" target="_blank" rel="nofollow">${r["RequestID"]}</a>` }',
				'function (r) { return usToDashDate(r["StartDate"]) }',
				'"wegov-org-name"', '"TypeOfNoticeDescription"', '"ShortTitle"',
				'function (r) { return usToDashDate(r["EventDate"]) }',
				'function (r) { 
						var rr = [r["EventStreetAddress1"], r["EventStreetAddress2"], r["EventCity"], r["EventStateCode"], r["EventZipCode"]];
						while (true) {
							var i = rr.indexOf("");
							if (i == -1) {
							  break;
							} else {
							  rr.splice(i, 1);
							}
						  }
						return rr.join(", ")
					}',
			],
			'visible' => [true, true, true, true, true, true, true, true, true, true, true],
			'filters' => [3 => null],
			'details' => [
				'Additional Description' => 'AdditionalDescription1',
				'Building Name' => 'EventBuildingName',
				'Document Links' => 'DocumentLinks',
				'End Date' => 'EndDate',
			],
			'description' => 'Public auctions and sales of city items ranging including equipment, cars and real estate.',
			'script' => 'datatable.order([1, "asc"]).draw();',
		],
		'court-notices' => [						#notices/courtnotices
			'fullname' => 'City Record Online (CROL)',
			'table' => 'crol',
			'fapireq' => '/get/orgs/courtnotices/%s',
			'sectionTitle' => 'Court Notices',
			'hdrs' => ['Request ID', 'Start Date', 'Agency Name', 'Short Title', 'Date', 'Location'],
			'flds' => [
				'function (r) { return `<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${r["RequestID"]}" target="_blank" rel="nofollow">${r["RequestID"]}</a>` }',
				'function (r) { return usToDashDate(r["StartDate"]) }',
				'"wegov-org-name"', '"ShortTitle"',
				'function (r) { return usToDashDate(r["EventDate"]) }',
				'function (r) { 
						var rr = [r["EventStreetAddress1"], r["EventStreetAddress2"], r["EventCity"], r["EventStateCode"], r["EventZipCode"]];
						while (true) {
							var i = rr.indexOf("");
							if (i == -1) {
							  break;
							} else {
							  rr.splice(i, 1);
							}
						  }
						return rr.join(", ")
					}',
			],
			'visible' => [true, true, true, true, true, true, true, true, true, true],
			'filters' => [],
			'details' => [
				'Additional Description' => 'AdditionalDescription1',
				'Additional Description 2' => 'AdditionalDescription2',
				'Building Name' => 'EventBuildingName',
				'Document Links' => 'DocumentLinks',
				'End Date' => 'EndDate',
			],
			'description' => 'New York State Supreme Court motions and acquisition notices.',
			'script' => 'datatable.order([1, "asc"]).draw();',
		],
		'procurement' => [
			'fullname' => 'City Record Online (CROL)',
			'table' => 'crol',
			'fapireq' => '/get/orgs/procurement/%s',
			'sectionTitle' => 'Procurement',
			'hdrs' => ['Request ID', 'Start Date', 'Agency Name', 'Type Of Notice Description', 'Category Description', 'Short Title', 'Selection Method Description'],
			'flds' => [
				'function (r) { return `<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${r["RequestID"]}" target="_blank" rel="nofollow">${r["RequestID"]}</a>` }',
				'function (r) { return usToDashDate(r["StartDate"]) }',
				'"wegov-org-name"', '"TypeOfNoticeDescription"', '"CategoryDescription"', '"ShortTitle"', '"SelectionMethodDescription"'
			],
			'visible' => [true, true, true, true, true, true, true],
			'filters' => [3 => null],
			'details' => [
				'Additional Description' => 'AdditionalDescription1',
				'Special Case Reason Description' => 'SpecialCaseReasonDescription',
				'PIN' => 'PIN',
				'Due Date' => 'DueDate',
				'End Date' => 'EndDate',
				'Address To Request' => 'AddressToRequest',
				'Contact Name' => 'ContactName',
				'Contact Phone' => 'ContactPhone',
				'Email' => 'Email',
				'Contract Amount' => 'ContractAmount',
				'Contact Fax' => 'ContactFax',
				'Other Info' => 'OtherInfo1',
				'Vendor Name' => 'VendorName',
				'Vendor Address' => 'VendorAddress',
				'Printout' => 'Printout1',
				'Document Links' => 'DocumentLinks',
				'Building Name' => 'EventBuildingName',
				'Street Address' => 'EventStreetAddress1',
			],
			'description' => 'Over 100 city agencies post solicitations for goods and services as well as award notices.',
			'script' => 'datatable.order([1, "asc"]).draw();',
		],
		// Procurement subsection placeholders - these use OCE API via orgProcurementSection controller
		'procurement-highlights' => [
			'fullname' => 'Procurement Highlights',
			'table' => null,
			'sectionTitle' => 'Procurement Highlights',
		],
		'procurement-contracts' => [
			'fullname' => 'Procurement Contracts',
			'table' => null,
			'sectionTitle' => 'Procurement Contracts',
		],
		'procurement-solicitations' => [
			'fullname' => 'Procurement Solicitations',
			'table' => null,
			'sectionTitle' => 'Procurement Solicitations',
		],
		'procurement-vendors' => [
			'fullname' => 'Procurement Vendors',
			'table' => null,
			'sectionTitle' => 'Procurement Vendors',
		],
		'procurement-transactions' => [
			'fullname' => 'Spending Transactions',
			'table' => null,
			'sectionTitle' => 'Spending Transactions',
		],
		'events' => [
			'fullname' => 'City Record Online (CROL)',
			'fapireq' => '/get/orgs/events/%s',
			'table' => 'crol',
			'hdrs' => ['Request ID', 'Event Date', 'Section Name', 'Type Of Notice Description', 'Agency Name', 'Short Title',],
			'sectionTitle' => 'Events',
			'visible' => [true, true, true, true, true, true, true],
			'flds' => [
				'function (r) { return `<a href="https://a856-cityrecord.nyc.gov/RequestDetail/${r["RequestID"]}" target="_blank" rel="nofollow">${r["RequestID"]}</a>` }',
				'function (r) { return usToDashDate(r["EventDate"]); }',
				'"SectionName"', '"TypeOfNoticeDescription"',
				'function (r) { return `<a href="/o/${r["wegov-org-id"]}-${slug(r["wegov-org-name"])}/events">${r["wegov-org-name"]}</a>` }',
				'"ShortTitle"',
			],
			'filters' => [2 => null, 3 => null],
			'details' => [
				'Description' => 'AdditionalDescription1',
				'Building Name' => 'EventBuildingName',
				'Street Address' => 'EventStreetAddress1',
				'Street Address 2' => 'EventStreetAddress2',
				'City' => 'EventCity',
				'State' => 'EventStateCode',
				'Zip Code' => 'EventZipCode',
			],
			'description' => 'All notices with an event date.',
			'script' => '',
		],

		'candidates' => [
			'fullname' => 'Civil Service List (Active)',
			'table' => 'civillistactive',
			'hdrs' => ['Exam No', 'List No', 'First Name', 'MI', 'Last Name', 'Score', 'Agency', 'Published Date'],
			'flds' => [
				//'"Exam No"', 
				'function (r) { return r["Published Date"] ? `<a href="https://www1.nyc.gov/assets/dcas/downloads/pdf/noes/${r["Published Date"].substring(6)}${r["Exam No"]}000.pdf" target="_blank">${r["Exam No"]}</a>` : r["Exam No"]}',
				'"List No"', '"First Name"', '"MI"', '"Last Name"',
				//'"Adj. FA"', 
				'function (r) { return r["Adj. FA"] }',
				'"List Agency Desc"', '"Published Date"'
			],
			'visible' => [true, true, true, true, true, true, true, true],
			'filters' => [],
			'details' => [
				'Group No' => 'Group No',
				'List Agency Code' => 'List Agency Code',
				'List Div Code' => 'List Div Code',
				'Established Date' => 'Established Date',
				'Anniversary Date' => 'Anniversary Date',
				'Extension Date' => 'Extension Date',
				'Veteran Credit' => 'Veteran Credit',
				'Parent Lgy Credit' => 'Parent Lgy Credit',
				'Sibling Lgy Credit' => 'Sibling Lgy Credit',
				'Residency Credit' => 'Residency Credit',
			],
			'description' => 'A Civil Service List consists of all candidates who passed an exam, ranked in score order. An established list is considered active for no less than one year and no more than four years from the date of establishment. For more information visit DCAS’ “Work for the City” webpage at: https://www1.nyc.gov/site/dcas/employment/take-an-exam.page',
			'script' => 'datatable.order([5, "desc"]).draw();',
			'sort' => ['"wegov-org-id"'],
		],

		'website-data' => [
			#'fullname' => '2023 Open Data Plan: Website Data',
			'fullname' => 'NYC Open Data Plan: Website Data',
			'table' => 'publishedwebsitedata',
			'hdrs' => ['Data Set Title', 'Data Set Description', 'URL on Agency Website', 'Update Frequency', 'Automatically Updated?', 'Already on Open Data?',],
			'flds' => [
				'"Data Set Title"',
				'function (r) { return `<div style="min-width:250px;">${r["Data Set Description"]}</div>` }',
				'function (r) {
					var rr = []
					for (const u of r["URL on Agency Website"].split(" ")) {
						rr.push(`<a class="cut-text" style="display:block; max-width:220px;" href="${u}">${u}</a>`)
					}
					return rr.join(" ")
				}',
				'"Update Frequency"', '"Automatically Updated?"', '"Already on Open Data?"', 
				#'"NYC Open Data URL"', '"Scheduled for Publication?"',
				#'function (r) { return r["Public Statement \\n(Required where data is not already available"]; }',
			],
			'visible' => [true, true, true, true, true, true, true],
			'filters' => [],
			'details' => [
				#'NYC Open Data URL' => 'NYC Open Data URL',
				'NYC Open Data URL' => 'ODURL_link',
				#'Scheduled for Publication' => 'Scheduled for Publication?',
				#'Public Statement' => "Public Statement \n(Required where data is not already available",
				'Public Statement' => "Public Statement",
			],
			'description' => '',
			'script' => '',
			'sort' => [],
		],

		'payroll' => [
			'fullname' => 'Citywide Payroll Data (Fiscal Year)',
			'table' => 'payrolldata',
			'hdrs' => ['Fiscal Year', 'Name', 'Title Description', 'Agency Start Date', 'Status', 'Regular Gross Paid', 'Total OT Paid', 'Total Other Pay'],
			'flds' => [
				'"Fiscal Year"',
				'function (r) { 
					n = r["First Name"].trim() +
						(r["Mid Init"].trim() ? " " + r["Mid Init"].trim() : "") +
						(r["Last Name"].trim() ? " " + r["Last Name"].trim() : "")
					return n;
				}',
				'"Title Description"', '"Agency Start Date"', '"Leave Status as of June 30"',
				'function (r) { return toFin(r["Regular Gross Paid"]) }',	 	// '"Regular Gross Paid"', 
				'function (r) { return toFin(r["Total OT Paid"]) }',	 		// '"Total OT Paid"', 
				'function (r) { return toFin(r["Total Other Pay"]) }',	 		// '"Total Other Pay"'
			],
			'visible' => [true, true, true, true, true, true, true, true],
			'filters' => [0 => null, 4 => null],
			'details' => [
				'OT Hours' => 'OT Hours',
				'Base Salary' => 'Base Salary',
				'Regular Hours' => 'Regular Hours',
				'Pay Basis' => 'Pay Basis',
				'Payroll Number' => 'Payroll Number',
				'Work Location Borough' => 'Work Location Borough',
			],
			'description' => "Data is collected because of public interest in how the City’s budget is being spent on salary and overtime pay for all municipal employees. Data is input into the City's Personnel Management System (“PMS”) by the respective user Agencies. Each record represents the following statistics for every city employee: Agency, Last Name, First Name, Middle Initial, Agency Start Date, Work Location Borough, Job Title Description, Leave Status as of the close of the FY (June 30th), Base Salary, Pay Basis, Regular Hours Paid, Regular Gross Paid, Overtime Hours worked, Total Overtime Paid, and Total Other Compensation (i.e. lump sum and/or retro payments). This data can be used to analyze how the City's financial resources are allocated and how much of the City's budget is being devoted to overtime. The reader of this data should be aware that increments of salary increases received over the course of any one fiscal year will not be reflected. All that is captured, is the employee's final base and gross salary at the end of the fiscal year.",
			'script' => 'datatable.order([6, "desc"]).draw();',
			'sort' => [],
			'charts' => true,
		],

		'resources-mmr' => [
			'fullname' => 'Mayor\'s Management Report Agency Resources',
			'table' => 'resourcesmmr',
			'hdrs' => ['Fiscal Year', 'Resource Indicators', 'Current FY Projected', 'Current FY Authorized', 'Next FY Authorized', '5 Year Trend', 'Notes'],
			'flds' => ['"Reporting Fiscal Year"', '"Resource Indicators"', '"Current FY Projected Actual (Not Yet Finalized)"', '"Current FY  (Authorized Budget Level)"', '"Next FY  (Authorized Budget Level)"', '"5yr Trend"', '"Notes"'],
			'visible' => [true, true, true, true, true, true, true],
			'filters' => [0 => null],
			'details' => [],
			'description' => 'Includes NYC agency resources from the Mayor\'s Management Report (MMR), such as expenditures (includes all funds), personnel, revenue and paid overtime. This data is an overview of the financial and workforce resources used by an agency and the planned resources available to the agency in a given reporting fiscal year or future fiscal years.<br/>
			The MMR, archived reports, and additional information is available at: <a href="https://www1.nyc.gov/site/operations/performance/mmr.page" target="_blank"> https://www1.nyc.gov/site/operations/performance/mmr.page</a> and <a href="https://dmmr.nyc.gov/" target="_blank">https://dmmr.nyc.gov/</a>',
			'script' => "datatable.order([0, 'desc']).draw();",
			'sort' => [],
		]

	];

	public $list = [
		'about' => 'About',
		'additional-costs-allocation' => 'Additional Costs Allocation',
		#'agency-performance' => 'Agency Performance (MMR)',
		'agency-performance' => '2021 Performance MMR',
		#'agency-resources' => 'Agency Resources (MMR)',
		'agency-resources' => '2021 Resources MMR',
		'agency-rules' => 'Agency Rules',
		'benefits-api' => 'Programs & Services',
		'candidates' => 'Title Candidates',
		'projects' => 'Capital Projects',
		'city-council-discretionary' => 'Council Discretionary Funding',
		'civil-list' => 'Titled Employees',
		'change-of-personnel' => 'Change of Personnel',
		'contract-awards' => 'Contract Awards',
		'court-notices' => 'Court Notices',
		'demographics' => 'Demographics',
		'events' => 'Event Notices',
		'expense-actuals' => 'Expense Actuals',
		'expense-budget' => 'Expense Budget',
		'expense-plan' => 'Expense Plan',
		'facilities' => 'Facilities',
		'headcount' => 'Future Headcount',
		'headcount-actuals' => 'Past Headcount',
		'jobs' => 'Job Opportunities',
		#'indicators' => 'OneNYC',
		'local-law-251' => 'Data Assets',
		'notices' => 'All Notices',
		'payroll' => 'Payroll',
		'positions' => 'Positions',
		'procurement' => 'Procurement',
		'procurement-highlights' => 'Procurement',
		'procurement-contracts' => 'Contracts',
		'procurement-solicitations' => 'Solicitations',
		'procurement-vendors' => 'Vendors',
		'procurement-transactions' => 'Transactions',
		'public-contacts' => 'Public Contacts',
		'property-disposition' => 'Property Disposition',
		'public-hearings' => 'Public Hearings',
		'publications' => 'Publications',
		'resources-mmr' => 'Mayor’s Management Report',
		'requests' => 'Community Board Requests',
		'required-reports' => 'Required Reports',
		'special-materials' => 'Special Materials',
		'data-tracker' => 'Data Tracker',
		'website-data' => 'Data on Websites',

	];

	public $menu = [
		'about',
		'Notices' =>
		[
			'notices',
			'events',
			'public-hearings',
			'procurement',
			'contract-awards',
			'agency-rules',
			'property-disposition',
			'court-notices',
			'change-of-personnel',
			'special-materials',
		],
		'Work' =>
		[
			'projects',
			'benefits-api',
			'facilities',
			'requests',
		],
		'Reports & Data' =>
		[
			'publications',
			'required-reports',
			'resources-mmr',
			'data-tracker', //Tracker	
			'local-law-251', //Assets
			'website-data',
		],
		'People' =>
		[
			'public-contacts',
			'civil-list',
			'candidates',
			'payroll',
			'jobs',
			'headcount',
			'headcount-actuals',
			'positions',
			'demographics',
		],
		'Finances' =>
		[
			'expense-plan',
			'expense-budget',
			'expense-actuals',
			'additional-costs-allocation',
			'city-council-discretionary',
		],
		// Procurement is a single tab → the unified overview (highlights + contracts
		// + solicitations + vendors + transactions on one page). The per-subsection
		// procurement-* routes still resolve (for old deep links) but are no longer
		// separate nav items now that the body shows everything at once.
		'procurement-highlights',
		// 'Indicators' => 
		// 	[
		// 		'agency-performance',
		// 		'agency-resources',
		// 	],
	];

	public function menuActiveDD($sect)
	{
		foreach ($this->menu as $h => $items)
			if (is_array($items) && (array_search($sect, $items) !== false))
				return $h;
		return '';
	}

	public $socicons = [
		'main_address' => ['geo-alt-fill', 'https://www.google.com/maps?q='],
		'email' => ['envelope', 'mailto:'],
		'url' => ['link-45deg', ''],
		'twitter' => ['twitter', ''],
		'facebook' => ['facebook', ''],
		'main_phone' => ['telephone', 'tel:'],
		'main_fax' => ['printer', 'fax:'],
		'rss' => ['rss', ''],
		'ical' => ['calendar-event-fill', ''],
	];

	public function get($section)
	{
		$dd = $this->dd[strtolower($section)] ?? null;
		if (!$dd)
			return $dd;
		$dd['detFlag'] = $inc = $dd['details'] ?? null ? 1 : 0;
		$flts = [];
		foreach ((array)$dd['filters'] as $i => $v)
			$flts[$i + $inc] = $v;
		$dd['filters'] = $flts;

		$fltDel = [];
		foreach ((array)($dd['fltDelim'] ?? []) as $i => $v)
			$fltDel[$i + $inc] = $v;
		$dd['fltDelim'] = $fltDel;

		$dd['fltsCols'] = implode(',', array_keys($dd['filters']));
		return $dd;
	}
	
	/*
	public function getAbout($section)
	{
		$dd = $this->dd[strtolower($section)] ?? null;
		if (!$dd)
			return $dd;
		$dd['detFlag'] = $inc = $dd['details'] ?? null ? 1 : 0;
		$flts = [];
		foreach ((array)$dd['filtersAbout'] as $i => $v)
			$flts[$i + $inc] = $v;
		$dd['filters'] = $flts;

		$fltDel = [];
		foreach ((array)($dd['fltDelim'] ?? []) as $i => $v)
			$fltDel[$i + $inc] = $v;
		$dd['fltDelim'] = $fltDel;

		$dd['fltsCols'] = implode(',', array_keys($dd['filters']));
		return $dd;
	}
	*/

	public function all_data_sources($dd)
	{
		$rr = $ii = [];
		if (is_array($dd)) {
			foreach ($dd as $d)
				$ii[strtolower(str_replace('.csv', '', $d['Output Path']))] = $d;
		}

		$globalRoutes = [
			'projects' => route('capital'),
			'notices' => route('notices'),
			'people' => route('people'),
			'titles' => route('titles'),
			'auctions' => route('auctions'),
			'districts' => route('districts'),
			'schools' => route('schools'),
		];

		foreach ($this->menu as $k => $mm) {
			if ($mm == 'about')
				continue;
			if (is_string($mm)) {
				$k = $this->list[$mm];
				$mm = [$mm];
			}
			foreach ($mm as $m) {
				$s = strstr($m, 'notices/') ? 'crol' : ($this->dd[$m]['table'] ?? '');
				if (!$s || !isset($ii[$s])) continue;
				
				$internalLink = $this->list[$m];
				if (isset($globalRoutes[$m])) {
					$internalLink = "<a href=\"{$globalRoutes[$m]}\">{$this->list[$m]}</a>";
				}

				$rr[] = [
					"<a href=\"{$ii[$s]['Citation URL']}\" target=\"_blank\" rel=\"nofollow\">{$ii[$s]['Name']}</a>",
					$internalLink,
					$this->dd[$m]['description'] ?? $ii[$s]['Descripton'],
					$k,
					$ii[$s]['Last Updated'],
					'<span id="stats_' . str_replace('/', '_', $m) . '"></span>',
				];
			}
		}
		return $rr;
	}

	public function data_sources($dd, $id, $orgname)
	{
		$rr = $ii = [];
		if (!is_array($dd)) return $rr;
		foreach ($dd as $d)
			$ii[strtolower(str_replace('.csv', '', $d['Output Path']))] = $d;
		foreach ($this->menu as $k => $mm) {
			if ($mm == 'about')
				continue;
			if (is_string($mm)) {
				$k = $this->list[$mm];
				$mm = [$mm];
			}
			foreach ($mm as $m) {
				$s = strstr($m, 'notices/') ? 'crol' : ($this->dd[$m]['table'] ?? '');
				if (!$s || !isset($ii[$s])) continue;
				$rr[] = [
					"<a href=\"{$ii[$s]['Citation URL']}\" target=\"_blank\" rel=\"nofollow\">{$ii[$s]['Name']}</a>",
					'<a href="' . route('orgSection', ['id' => $id, 'orgslug' => Str::slug($orgname, '-'), 'section' => $m]) . "\">{$this->list[$m]}</a>",
					$this->dd[$m]['description'] ?? $ii[$s]['Descripton'],
					$k,
					$ii[$s]['Last Updated'],
					'<span id="stats_' . str_replace('/', '_', $m) . '"></span>',
				];
			}
		}
		return $rr;
	}
}
