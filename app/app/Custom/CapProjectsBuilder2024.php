<?php
Namespace App\Custom;
use Illuminate\Support\Str;

class CapProjectsBuilder2024
{
	static function build($d)
	{
		$rr = [
			'#PRJ_NAME' => 		$d['PROJECT_DESCR'],
			'#PRJ_ID' => 		$d['PROJECT_ID'],
			'#MA_PRJ_ID' => 	$d['maprojid'] ?? '',
			'#CATEGORY' => 		$d['wegov-project-category'] && !empty($d['wegov-project-category-slug'])
									? '<a href="' . ($d['wegov-project-category-slug'] ? '/projects/categories/' . $d['wegov-project-category-slug'] : '#') . 
										"\">{$d['wegov-project-category']}</a>" 
									: '',
			'#CURRENT_PHASE' => $d['CURRENT_PHASE'] ?? '',
			'#PHASE_START' => 	$d['PHASE_START'] ?? '',
			'#PHASE_END' => 	$d['PHASE_END'] ?? '',
			'#END_ORIG' => 		$d['END_ORIG'] ?? '',
			'#MANAGING_AGENCY' => $d['wegov-org-id'] 
									? '<a href="' . route('orgProfile', ['id' => $d['wegov-org-id'], 'orgslug' => Str::slug($d['wegov-org-name'], '-')]) . 
										"\">{$d['wegov-org-name']}</a>" 
									: '',
			'#SPONSOR_AGENCY' => $d['SPONSOR_AGENCY'] ?? '',
			'#MIN_DATE' => 		$d['mindate'] ?? '',
			'#MAX_DATE' => 		$d['maxdate'] ?? '',
			'#BUDGET_LINES' => 	self::genBudgetLines($d['BUDGET_LINE'] ?? ''),
			'#PRJ_TYPE' => 		self::genPrjTypes($d['wegov-project-type-names'] ?? ''),
			'#TYPECATEGORY' => $d['TYP_CATEGORY_NAME'] ?? '',
			'#CCPVERSION' => $d['ccpversion'] ?? '',

			'#budget .original' => 	sprintf('<span data-content="%s">%s</span>', 
					self::budgetRound($d['BUDG_ORIG'], 1), 
					self::toFinShortK($d['BUDG_ORIG'], 1)),
			'#budget .current' => 	sprintf('<span data-content="%s">%s</span>', 
					self::budgetRound($d['BUDG_CURR'], 1), 
					self::toFinShortK($d['BUDG_CURR'], 1)),
			'#budget .difference' => 	sprintf('<span data-content="%s">%s</span>', 
					self::budgetRound($d['BUDG_DIFF'], 1), 
					self::budgetDiff($d['BUDG_ORIG'], $d['BUDG_CURR'], 1)),

			'#end .original' => ($d['END_ORIG']) ? $d['END_ORIG'] : '-',	#self::df($d['END_ORIG']) : '-'
			'#end .current' => ($d['END_CURR']) ? $d['END_CURR'] : '-',		#self::df($d['END_CURR']) : '-'
			'#end .difference' => ($d['END_DIFF']) ? self::dateDiff($d['END_ORIG'], $d['END_CURR']) : '-',

			'#duration .original' => ($d['DURATION_ORIG']) ? "{$d['DURATION_ORIG']} years" : '-',
			'#duration .current' => ($d['DURATION_CURR']) ? "{$d['DURATION_CURR']} years" : '-',
			'#duration .difference' => ($d['DURATION_DIFF']) ? self::durationDiff($d['DURATION_ORIG'], $d['DURATION_CURR']) : '-',
			
			'#budgets .planned' => sprintf('<span data-content="%s">%s</span>', 
						self::budgetRound($d['plannedcommit_total'] ?? 0, 1), 
						self::toFinShortK($d['plannedcommit_total'] ?? 0, 1)),
			'#budgets .adopted' => sprintf('<span data-content="%s">%s</span>', 
						self::budgetRound($d['adopt_total'] ?? 0, 1), 
						self::toFinShortK($d['adopt_total'] ?? 0, 1)),
			'#budgets .allocated' => sprintf('<span data-content="%s">%s</span>', 
						self::budgetRound($d['allocate_total'] ?? 0, 1), 
						self::toFinShortK($d['allocate_total'] ?? 0, 1)),
			'#budgets .commited' => sprintf('<span data-content="%s">%s</span>', 
						self::budgetRound($d['commit_total'] ?? 0, 1), 
						self::toFinShortK($d['commit_total'] ?? 0, 1)),
			'#budgets .spent' => 	sprintf('<span data-content="%s">%s</span>', 
						self::budgetRound($d['spent_total'] ?? 0, 1), 
						self::toFinShortK($d['spent_total'] ?? 0, 1)),
			'#budgets .checkbook' => sprintf('<span data-content="%s">%s</span>', 
						self::budgetRound($d['spent_total_checkbooknyc'] ?? 0, 1), 
						self::toFinShortK($d['spent_total_checkbooknyc'] ?? 0, 1)),
		];

		$name = $rr['#PRJ_NAME'];
		$id = $d['wegov-org-id'];
		$geo_json = $d['GEO_JSON'] ? $d['GEO_JSON'] : '';
		$cc = ['Other' => '#53777a', 'Completed' => '#f5ae33', 'Pending' => '#bcbcbc', 'Pre-Design' => '#ff7c7c', 'Close-out' => '#f2c45a', 'Construction' => '#36c726', 'Construction Procurement' => '#beedb9', 'Design' => '#78c0a8'];
		if ($geo_json)
		{
			$geo_json = str_replace('"""', '"', $geo_json);
			$gj = json_decode($geo_json, true);
			$gj['properties']['custom_color'] = $cc[$d['wegov-prj-color'] ?? 'Other'] ?? '#000';
			
			$lats = []; $lons = [];
			$coords = $gj['geometry']['coordinates'];
			$type = $gj['geometry']['type'];
			
			if ($type == 'Point') {
				$lons[] = $coords[0];
				$lats[] = $coords[1];
			} elseif ($type == 'Polygon') {
				foreach ($coords[0] as $c) {
					$lons[] = $c[0];
					$lats[] = $c[1];
				}
			} elseif ($type == 'MultiPolygon') {
				foreach ($coords as $poly) {
					foreach ($poly[0] as $c) {
						$lons[] = $c[0];
						$lats[] = $c[1];
					}
				}
			}
			
			if (count($lats) > 0) {
				$gj['properties']['W'] = min($lons);
				$gj['properties']['S'] = min($lats);
				$gj['properties']['E'] = max($lons);
				$gj['properties']['N'] = max($lats);
			}
			
			$geo_json = json_encode($gj);
		}
		$cLog = ($d['LOG'] ?? null) ? self::genLog(json_decode($d['LOG'], true)) : '';

		return ['name' => $name, 'profile' => $rr, 'geo_feature' => $geo_json, 'id' => $id, 'cLog' => $cLog, 'budgPlanChartData' => ['pubdates'=>[]], 'priorSpendingChartData' => ['pubdates'=>[]]];
		#, 'budgPlanChartData' => $budgPlanChartFine, 'priorSpendingChartData' => $priorSpendingChartFine


		#########################################################################################################################
		########
		$rr = [];
		$priorSpendingChart = $budgPlanChart = [];
		$cLog = [];
		$geo_json = null;
		$name = $id = '';
		$inext = null;
		foreach ($dd as $i=>$d)
		{
			$rr[$i] = [
				'#BORO' => $d['BORO'] ?? '',
				'#MANAGING_AGCY' => $d['wegov-org-id'] 
										? '<a href="' . route('orgProfile', ['id' => $d['wegov-org-id'], 'orgslug' => Str::slug($d['wegov-org-name'], '-')]) . 
											"\">{$d['wegov-org-name']}</a>" 
										: '',
				'#PROJECT_ID' => $d['PROJECT_ID'] ?? '',
				'#PROJECT_DESCR' => $d['PROJECT_DESCR'] ?? '',
				'#PRJ_TYPE' => self::genPrjTypes($d['wegov-project-type-names']),
				'#TYP_CATEGORY_NAME' => $d['wegov-project-category'] && !empty($d['wegov-project-category-slug'])
										? '<a href="' . ($d['wegov-project-category-slug'] ? '/projects/categories/' . $d['wegov-project-category-slug'] : '#') . 
											"\">{$d['wegov-project-category']}</a>" 
										: '',
				'#BUDGET_LINE' => self::genBudgetLines($d['BUDGET_LINE'], $d['BUDGET_LINE_REL']),
				'#COMMUNITY_BOARD' => self::genCommBoards($d['COMMUNITY_BOARD']),
				'#DELAY_DESC' => $d['DELAY_DESC'] ?? '',
				'#SITE_DESCR' => $d['SITE_DESCR'] ?? '',
				'#SCOPE_TEXT' => $d['SCOPE_TEXT'] ?? '',
				'#CITY_PRIOR_ACTUAL' => ($d['CITY_PRIOR_ACTUAL'] ?? '') == '' ? '' : self::toFinShortK($d['CITY_PRIOR_ACTUAL'], 1),
				'#NONCITY_PRIOR_ACTUAL' => ($d['NONCITY_PRIOR_ACTUAL'] ?? '') == '' ? '' : self::toFinShortK($d['NONCITY_PRIOR_ACTUAL'], 1),
				'PUB_DATE_F' => self::df($d['PUB_DATE'] ?? ''),
				
				'#budget .original' => sprintf('<span data-content="%s">%s</span>', 
						self::budgetRound($d['ORIG_BUD_AMT'], 1), 
						self::toFinShortK($d['ORIG_BUD_AMT'], 1)),
				'#budget .current' => sprintf('<span data-content="%s">%s</span>', 
						#self::budgetRound($d['CITY_PRIOR_ACTUAL'] + $d['CITY_PLAN_TOTAL'], 1000), 
						#self::toFinShortK($d['CITY_PRIOR_ACTUAL'] + $d['CITY_PLAN_TOTAL'], 1000)),
						self::budgetRound($d['CITY_PLAN_TOTAL'] + $d['NONCITY_PLAN_TOTAL'], 1), 
						self::toFinShortK($d['CITY_PLAN_TOTAL'] + $d['NONCITY_PLAN_TOTAL'], 1)),
				'#budget .difference' => sprintf('<span data-content="%s">%s</span>', 
						self::budgetRound(($d['CITY_PRIOR_ACTUAL'] + $d['CITY_PLAN_TOTAL']) - $d['ORIG_BUD_AMT'], 1), 
						self::budgetDiff($d['ORIG_BUD_AMT'], $d['CITY_PRIOR_ACTUAL'] + $d['CITY_PLAN_TOTAL'], 1)
					),
				
				'#start .original' => ($d['ORIG_START'] ?? null) ? self::df($d['ORIG_START']) : '-',
				'#start .current' => ($d['CURR_START'] ?? null) ? self::df($d['CURR_START']) : '-',
				'#start .difference' => ($d['ORIG_START'] ?? null) ? self::dateDiff($d['ORIG_START'], $d['CURR_START']) : '-',
				
				'#end .original' => ($d['ORIG_END'] ?? null) ? self::df($d['ORIG_END']) : '-',
				'#end .current' => ($d['CURR_END'] ?? null) ? self::df($d['CURR_END']) : '-',
				'#end .difference' => ($d['ORIG_END'] ?? null) ? self::dateDiff($d['ORIG_END'], $d['CURR_END']) : '-',
				
				'#duration .original' => ($d['ORIG_END'] ?? null) ? self::dateDiff($d['ORIG_END'], $d['ORIG_START'], false) . ' years' : '-',
				'#duration .current' => ($d['CURR_END'] ?? null) ? self::dateDiff($d['CURR_END'], $d['CURR_START'], false) . ' years' : '-',
				'#duration .difference' => ($d['ORIG_END'] ?? null) ? self::durationDiff(self::dateDiff($d['ORIG_END'], $d['ORIG_START'], false), self::dateDiff($d['CURR_END'], $d['CURR_START'], false)) : '-',
				
				'milestones' => ($d['milestones'] ?? null) ? array_values($d['milestones']) : [],

				'costChartData' => [
					[(int)$d['FY_YR1_PLAN'] - 4, (int)$d['CITY_YR1_PLAN'], (int)$d['NONCITY_YR1_PLAN']],
					[(int)$d['FY_YR1_PLAN'] - 3, (int)$d['CITY_YR2_PLAN'], (int)$d['NONCITY_YR2_PLAN']],
					[(int)$d['FY_YR1_PLAN'] - 2, (int)$d['CITY_YR3_PLAN'], (int)$d['NONCITY_YR3_PLAN']],
					[(int)$d['FY_YR1_PLAN'] - 1, (int)$d['CITY_YR4_PLAN'], (int)$d['NONCITY_YR4_PLAN']],
					[(int)$d['FY_YR1_PLAN'] - 0, (int)$d['CITY_YR5_PLAN'], (int)$d['NONCITY_YR5_PLAN']],
				]
			];
			$name = $name ? $name : $d['PROJECT_DESCR'];
			$id = $id ? $id : $d['wegov-org-id'];
			$geo_json = $d['GEO_JSON'] ? $d['GEO_JSON'] : $geo_json;
			
			if (preg_match('~^\d{8}$~', $i))
			{
				$budgPlanChart[$i] = [(int)$d['CITY_PLAN_TOTAL'], (int)$d['NONCITY_PLAN_TOTAL']];
				$priorSpendingChart[$i] = [(int)$d['CITY_PRIOR_ACTUAL'], (int)$d['NONCITY_PRIOR_ACTUAL']];
			}
			
			if ($inext)
			{
				$logT = self::genLog($dd[$i], $dd[$inext]);
				if ($logT)
					$cLog[$i] = $logT;
			}
			$inext = $i;
			
		}
		
		$budgPlanChartFine = ['pubdates' => [], 'CITY_PLAN_TOTAL' => [], 'NONCITY_PLAN_TOTAL' => []];
		ksort($budgPlanChart);
		foreach ($budgPlanChart as $pubdate=>$vv)
		{
			$budgPlanChartFine['pubdates'][] = self::df($pubdate);
			$budgPlanChartFine['CITY_PLAN_TOTAL'][] = $vv[0];
			$budgPlanChartFine['NONCITY_PLAN_TOTAL'][] = $vv[1];
		}

		$priorSpendingChartFine = ['pubdates' => [], 'CITY_PRIOR_ACTUAL' => [], 'NONCITY_PRIOR_ACTUAL' => []];
		ksort($priorSpendingChart);
		foreach ($priorSpendingChart as $pubdate=>$vv)
		{
			$priorSpendingChartFine['pubdates'][] = self::df($pubdate);
			$priorSpendingChartFine['CITY_PRIOR_ACTUAL'][] = $vv[0];
			$priorSpendingChartFine['NONCITY_PRIOR_ACTUAL'][] = $vv[1];
		}	

		return ['name' => $name, 'items' => $rr, 'geo_feature' => str_replace('""', '"', $geo_json), 'id' => $id, 'cLog' => $cLog, 'budgPlanChartData' => $budgPlanChartFine, 'priorSpendingChartData' => $priorSpendingChartFine];

		#########################################################################################################################
		
	}
	
	static function genLog($dd)
	{
		$ff = [
			'BUDG_ORIG' => 'Original Budget',
			'BUDG_CURR' => 'Current Budget',
			'START_ORIG' => 'Original Start',
			'START_CURR' => 'Current Start',
			'END_ORIG' => 'Original End',
			'END_CURR' => 'Current End',
			'DURATION_ORIG' => 'Original Duration',
			'DURATION_CURR' => 'Current Duration',
		];

		$rr = [];
		foreach ((array)$dd as $t=>$pp)
		{	
			$r = [];
			$t = implode('/', [substr($t,4,2), substr($t,0,4)]);
			foreach ($pp as $p)
				$r[] = self::genLogItem($ff[$p['key']], $p['old_value'] ?? null, $p['new_value'] ?? null);
			$rr[$t]	= $r;
		}
		
		return $rr;
	}
	
	
	static function genLog_($pdd, $dd)
	{
		$mm = $dd['milestones'] ?? [];
		$rr = [];
		foreach ([
				'BUDG_ORIG' => 'Original Budget',
				'BUDG_CURR' => 'Current Budget',
				'START_ORIG' => 'Original Start',
				'START_CURR' => 'Current Start',
				'END_ORIG' => 'Original End',
				'END_CURR' => 'Current End',
			] as $f=>$t)
			if (($dd[$f] ?? null) <> ($pdd[$f] ?? null))
				$rr[] = self::genLogItem($t, $dd[$f] ?? null, $pdd[$f] ?? null);
		
		$pmm = [];
		foreach ($dd['milestones'] ?? [] as $m)
			$pmm[$m['TASK_DESCRIPTION']] = $m;
		
		foreach ($mm as $m)
		{
			if (!($pmm[$m['TASK_DESCRIPTION']] ?? null))
				$rr[] = ["New milestone '{$m['TASK_DESCRIPTION']}'", ''];
			else 
				foreach ([
						'ORIG_DATE_F' => 'Original',
						'CURR_DATE_F' => 'Current',
					] as $f=>$t)
					if (($m[$f] ?? null) <> ($pmm[$m['TASK_DESCRIPTION']][$f] ?? null))
						$rr[] = self::genLogItem("{$m['TASK_DESCRIPTION']} {$t}", $pmm[$m['TASK_DESCRIPTION']][$f] ?? null, $m[$f] ?? null);
		}
		return $rr;
	}
	
	static function genLogItem($t, $a, $b)
	{
		$is_budg = preg_match('~(Original|Current) Budget~si', $t);
		if ($b)
		{
			if ($is_budg)
			{
				$d = (float)$b - (float)$a;
				$a = self::budgetRound((float)$a, 1);
				$b = self::budgetRound((float)$b, 1);
				return [
					"{$t} " . ($d > 0 ? 'increase &#9650; ' : 'decrease &#9660; ') . self::toFinShortK(abs($d), 1),
					"from {$a} to {$b}"
				];
			} elseif (preg_match('~Duration~si', $t)) {
				$d = (float)$b - (float)$a;
				$a = number_format($a, 1);
				$b = number_format($b, 1);
				return [
					"{$t} " . ($d > 0 ? 'increase &#9650; ' : 'decrease &#9660; ') . self::timerangeShort(abs($d * 365)),
					"from {$a} to {$b}"
				];
			} else {
				$d = self::ts2float($a) - self::ts2float($b);
				$a = date('m/d/Y', $a);
				$b = date('m/d/Y', $b);
				return [
					"{$t} " . ($d < 0 ? 'postponed &#9650; ' : 'anticipated &#9660; ') . self::timerangeShort(abs($d * 365)),
					"from {$a} to {$b}"
				];
			}
		}
		else
			return ["{$t} set to {$b}", ''];
	}
	
	static function genBudgetLines($budgLines)
	{
		$rr = [];
		$budgLines = preg_split('/[\s,]+/', $budgLines, -1, PREG_SPLIT_NO_EMPTY);
		#$blRel = explode(' ', $blRel);
		foreach ($budgLines as $i=>$b)
			if (trim($b))
			{
				$u = route('budgetLine', ['blcode' => $b]);
				$rr[] = "<span class='badge badge-bl px-2 mr-2'><a href=\"{$u}\">{$b}</a></span>";
			}
		return implode(' ', $rr);
	}
	
	
	static function genPrjTypes($names)
	{
		$rr = [];
		$names = explode('; ', $names);
		foreach ($names as $i=>$n)
			if ($n)
				$rr[] = '<a href="' . route('prjType', ['tslug' => Str::slug($n)]) . '">' . $n . '</a>';
		return implode(' ', $rr);
	}
	
	
	static function genCommBoards($cc)
	{
		$rr = [];
		foreach (explode(' ', $cc) as $c)
			if ($c)
			{
				$u = route('districtsPreset', ['type' => 'cd', 'id' => $c, 'dslug' => '-community-district-' . $c, 'section' => 'city-council-discretionary']);
				$rr[] = "<span class='badge badge-cd px-2 mr-2'><a href=\"{$u}\">{$c}</a></span>";
			}
		return implode(' ', $rr);
	}
	
	
	static function df($d)
	{
		return preg_match('~^\d{8}$~', $d) 
				? implode('/', [substr($d,4,2), substr($d,6,2), substr($d,0,4)]) 
				: $d;
	}
	
	static function ds($d)
	{
		return date('Ymd', strtotime($d));
	}
	
	static function dateDiff($dP, $dA, $format=true)
	{
		$r = self::date2float($dP) - self::date2float($dA);
		$r = round($r, 1);
		if (!$format)
			return $r;
		switch ($r <=> 0)
		{
			case 0:
				return "<span class='good'>on time</span>";
				break;
			case -1:
				$r = -$r;
				return "<span class='bad'>{$r} years late</span>";
				break;
			case 1:
				return "<span class='good'>{$r} years early</span>";
				break;
		}
	}
	
	static function date2float($d)
	{
		$t = strtotime($d);
		return (int)date('Y', $t) + (float)date('z', $t)/365;
	}
	
	static function ts2float($t)
	{
		return (int)date('Y', $t) + (float)date('z', $t)/365;
	}
	
	static function durationDiff($dP, $dA, $format=true)
	{
		$r = (float)$dP - (float)$dA;
		$r = round($r, 1);
		if (!$format)
			return $r;
		$p = $dP ? self::perc($dA, $dP) : '';
		switch ($r <=> 0)
		{
			case 0:
				return "<span class='good'>on time</span>";
				break;
			case -1:
				$r = -$r;
				return "<span class='bad'>{$r} years over <small><i>({$p})</i></small></span>";
				break;
			case 1:
				return "<span class='good'>{$r} years below <small><i>({$p})</i></small></span>";
				break;
		}
	}
	
	static function budgetDiff($b1, $b2, $m=1)
	{
		$d = (int)$b1 - (int)$b2;
		$df = self::toFinShortK(abs($d), $m);
		if (abs($d) < 250)
			$d = 0;
		$p = $b1 ? self::perc($b2, $b1) : '';
		switch ($d <=> 0)
		{
			case 0:
				return "<span class='good'>Fit</span>";
			case -1:
				return "<span class='bad'>{$df} over <small><i>({$p})</i></small></span>";
			case 1:
				return "<span class='good'>{$df} below <small><i>({$p})</i></small></span>";
		}
	}

	static function budgetRound($b, $m=1)
	{
		return '$' . number_format((int)$b * $m);
	}
	
	static function perc($c, $p)
	{
		if ((float)$p == 0) return '0%';
		return number_format(abs((float)$c/(float)$p - 1) * 100) . '%';
	}
	
	static function toFinShortK($b, $m=1)
	{
		$b = (int)$b * $m;
		if ($b < 1000)
			return '$' . number_format($b);
		$units = [0 => 'K', 1 => 'M', 2 => 'B'];
		for ($u = 0; $u <= 2; $u++)
		{
			$b = $b / 1000;
			if ($b < 1000)
			{
				if ($b >= 100)
					return '$' . number_format($b) . $units[$u];
				elseif ($b >= 10)
					return '$' . number_format($b, 1) . $units[$u];
				else if ($b >= 1)
					return '$' . number_format($b, 2) . $units[$u];
			}
		}
		return '$' . number_format($b) . $units[$u - 1];
	}
	
	static function timerangeShort($d)
	{
		if (abs($d) > 365)
			return number_format($d / 365, 1) . ' years';
		if (abs($d) > 30)
			return number_format($d / 30, 1) . ' months';
		return number_format($d, 0) . ' days';
	}
}
