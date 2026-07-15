<?php
Namespace App\Custom;

class TitlesDatasets
{
	public $dd = [
		'positions' => [
			'fullname' => 'Position Schedule',
			'table' => 'positionschedule',
			'hdrs' => ['Publication Date', 'Agency Code', 'Agency Name', 'UA code', 'UA name', 'Agency Name', 'Scheduled Positions', 'Minimum Salary', 'Mean Salary', 'Maximum Salary', 'Total Spent Annually'],
			'flds' => ['"PUBLICATION DATE"', '"AGENCY CODE"', '"AGENCY NAME"', '"UA CODE"', '"UA NAME"', 
						'function (r) { return `<a href="/o/${r["wegov-org-id"]}-${slug(r["wegov-org-name"])}">${r["wegov-org-name"]}</a>` }',
						'"POSITIONS"', 
						'function (r) { return toFin(r["MINMUM SALARY"]) }', 
						'function (r) { return toFin(r["MEAN SALARY"]) }', 
						'function (r) { return toFin(r["MAXMUM SALARY"]) }', 
						'function (r) { return toFin(r["ANNUAL RATE"]) }', 
					  ],
			'visible' => [false, false, false, true, true, true, true, true, true, true, true, true],
			'filters' => [0 => null],
			'details' => [],
			'description' => 'Sum of the full-time active positions in a title description published in alphabetical order. The Position Schedule is updated and included in the Departmental Estimates and the Supporting Schedule (updated twice a year). The minimum salary, maximum salary, mean salary and annual rate are to the dollar. This dataset is updated biannually.',
			'script' => '$("#filter-0 option:last-child").attr("selected", true);$("#filter-0 option:last-child").change();',
			'sort' => ['"wegov-org-id"'],
		],
		'jobs' => [
			'fullname' => 'NYC Jobs',
			'table' => 'nycjobs',
			'hdrs' => ['Job ID', 'Title', 'Job Category', 'Salary From', 'Salary To', 'Last Updated'],
			'flds' => [
					'function (r) { return `<a href="https://cityjobs.nyc.gov/jobs?q=${r["Job ID"]}">${r["Job ID"]}</a>` }', 
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
			'description' => 'This dataset contains current job postings available on the City of New York’s <a href="http://www.nyc.gov/html/careers/html/search/search.shtml"> official jobs site</a>. Internal postings available to city employees and external postings available to the general public are included.',
			'sort' => ['"wegov-org-id"'],
		],
		'employees' => [
			'fullname' => 'Civil List',
			'table' => 'civillist',
			'hdrs' => ['Calendar Year', 'Agency Code', 'Employee Name', 'Agency Name', 'Title Code', 'Pay Class', 'Salary Rate'],
			'flds' => ['"CALENDAR YEAR"', '"AGENCY CODE"', '"EMPLOYEE NAME"', '"AGENCY NAME"', '"TITLE CODE"', '"PAY CLASS"', '"SALARY RATE"'],
			'visible' => [true, false, true, false, false, true, true],
			'filters' => [0 => null],
			'details' => [],
			'description' => 'The Civil List reports the agency code (DPT), first initial and last name (NAME), agency name (ADDRESS), title code (TTL #), pay class (PC), and salary (SAL-RATE) of individuals who were employed by the City of New York at any given time during the indicated year.',
			'script' => 'datatable.order([0, "desc"]).draw();',
			'sort' => ['"wegov-org-id"'],
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
				'"List Agency Desc"', '"Published Date"'],
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
				'Residency Credit' => 'Residency Credit',			],
			'description' => 'A Civil Service List consists of all candidates who passed an exam, ranked in score order. An established list is considered active for no less than one year and no more than four years from the date of establishment. For more information visit DCAS’ “Work for the City” webpage at: https://www1.nyc.gov/site/dcas/employment/take-an-exam.page',
			'script' => 'datatable.order([5, "desc"]).draw();',
			'sort' => ['"wegov-org-id"'],
		],

	];

	public $list = [
		'description' => 'About',
		'positions' => 'Positions',
		'jobs' => 'Job Opportunities',
		'employees' => 'Employees',
		'candidates' => 'Candidates',
		'exams' => 'Exams',
	];
	
	public $menu = [
		'positions',
		'jobs',
		'exams',
		'employees',
		'candidates',
		'description',
	];
	
	
	public function menu($type)
	{
		$rr = [];
		foreach ($this->menu as $h=>$vv)
			if (is_array($vv))
			{
				foreach ($vv as $i=>$v)
					if (isset($this->dd[$v]['map'][$type]))
						$rr[$h][$i] = $v;
			} elseif (isset($this->dd[$vv]['map'][$type]))
				$rr[$h] = $vv;
		return $rr;
	}
	
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
}