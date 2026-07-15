<?php
Namespace App\Custom;
use Illuminate\Support\Str;

class Breadcrumbs
{
	static public $root = [];

	static function root()
	{
		$rr = self::$root;
		return $rr;
	}

	static function about()
	{
		return array_merge(self::$root, [['', 'About']]);
	}

	static function orgs()
	{
		return array_merge(self::$root, [[route('orgs'), 'Organizations'], [route('orgs'), 'Directory']]);
	}

	static function orgsChart()
	{
		return array_merge(self::$root, [[route('orgs'), 'Organizations'], [route('orgsChart'), 'Chart']]);
	}

	static function orgsAll()
	{
		return array_merge(self::$root, [[route('orgs'), 'Organizations'], [route('orgsAll'), 'All']]);
	}

	static function org($id, $name)
	{
		return array_merge(self::$root, [
				[route('orgs'), 'Organizations'], 
				[route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($name, '-')]), $name]
			]);
	}

	static function orgSect($id, $name, $sect, $sectN)
	{
		return array_merge(self::$root, [
				[route('orgs'), 'Organizations'], 
				[route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($name, '-')]), $name],
				[route('orgSection', ['id' => $id, 'orgslug' => Str::slug($name, '-'), 'section' => $sect]), $sectN]
				//["/organization/{$id}/{$sect}", $sectN]
			]);
	}

	static function orgPrj($id, $name, $sect, $sectN, $prjId, $prjN)
	{
		return array_merge(self::$root, [
				[route('capital'), 'Capital'], 												
				[route('projects'), 'Projects'], 												
				[route('orgProfile', ['id' => $id, 'orgslug' => Str::slug($name, '-')]), $name], 		//["/o/{$id}-" . Str::slug($name, '-'), $name], 
				[route('project', ['prjId' => $prjId, 'prjslug' => Str::slug($prjN, '-')]), $prjId], 		//["/organization/{$id}/{$sect}/{$prjId}", $prjId]
			]);
	}

	static function purePrj($prjId, $prjN)
	{
		return array_merge(self::$root, [
				[route('projects'), 'Capital Projects'], 												//['/capitalprojects', 'Capital Projects'], 
				[route('project', ['prjId' => $prjId, 'prjslug' => Str::slug($prjN, '-')]), $prjId], 		//["/organization/{$id}/{$sect}/{$prjId}", $prjId]
			]);
	}

	static function districts()
	{
		return array_merge(self::$root, [[route('districts'), 'Districts']]);
	}


	static function schools()
	{
		return array_merge(self::$root, [
				[route('schools'), 'Schools'], 
			]);
	}


	static function schoolSect($distId, $distName, $code, $schoolName, $sect, $sectN)
	{
		return array_merge(self::$root, [
				[route('schools'), 'Schools'],
				[route('districtsPreset', ['type'=> 'sd', 'id' => $distId, 'section' => 'schools', 'dslug' => Str::slug($distName, '-')]), $distName],
				[route('school', ['code' => $code, 'slug' => Str::slug($schoolName, '-')]), $schoolName],
				[route('schoolSection', ['code' => $code, 'slug' => Str::slug($schoolName, '-'), 'section' => $sect]), $sectN]
			]);
	}


	static function auctions()
	{
		return array_merge(self::$root, [[route('auctions'), 'Auctions']]);
	}

	static function capital()
	{
		return array_merge(self::$root, [[route('capital'), 'Capital']]);
	}

	static function projects()
	{
		return array_merge(self::$root, [[route('capital'), 'Capital'], [route('projects'), 'Projects']]);
	}

	static function mProjects()
	{
		return array_merge(self::$root, [[route('capital'), 'Capital'], [route('mProjects'), 'Minor Projects']]);
	}

	static function mProject($maprojid, $pName)
	{
		return array_merge(self::$root, [[route('capital'), 'Capital'], [route('mProjects'), 'Minor Projects'], [route('mProject', ['maprojid' => $maprojid]), "{$pName} ({$maprojid})"]]);
	}

	static function prjTypes()
	{
		return array_merge(self::$root, [[route('projects'), 'Capital'], [route('prjTypes'), 'Project Types']]);
	}

	static function prjType($tname)
	{
		return array_merge(self::$root, [
				[route('capital'), 'Capital'], 
				[route('prjTypes'), 'Project Types'],
				[route('prjType', ['tslug' => Str::slug($tname, '-')]), $tname],
			]);
	}

	static function categories()
	{
		return array_merge(self::$root, [	
				[route('capital'), 'Capital'],
				[route('prjCategories'), 'Project Categories'],
			]);
	}

	static function category($cname)
	{
		return array_merge(self::$root, [
				[route('capital'), 'Capital'],
				[route('prjCategories'), 'Project Categories'],
				[!empty($cname) ? route('prjStratCategory', ['cslug' => Str::slug($cname, '-')]) : '#', $cname ?: 'Category'],
			]);
	}

	static function budgetLines()
	{
		return array_merge(self::$root, [
				[route('capital'), 'Capital'],
				[route('budgetLines'), 'Budget Lines'],
			]);
	}

	static function budgetLine($blcode, $bltitle)
	{
		return array_merge(self::$root, [
				[route('capital'), 'Capital'],
				[route('budgetLines'), 'Budget Lines'],
				[route('budgetLine', ['blcode' => $blcode]), "{$blcode}-{$bltitle}"],
			]);
	}

	static function prjCommitments()
	{
		return array_merge(self::$root, [
				[route('capital'), 'Capital'],
				[route('prjCommitments'), 'Commitments'],
			]);
	}

	#### archived projects — delegate to /projects/ breadcrumbs #####

		static function capital_a() { return self::capital(); }
		static function projects_a() { return self::projects(); }
		static function prjTypes_a() { return self::prjTypes(); }
		static function prjType_a($tname) { return self::prjType($tname); }
		static function categories_a() { return self::categories(); }
		static function category_a($cname) { return self::category($cname); }
		static function budgetLines_a() { return self::budgetLines(); }
		static function budgetLine_a($blcode, $bltitle) { return self::budgetLine($blcode, $bltitle); }
		static function prjCommitments_a() { return self::prjCommitments(); }

	#### / archived projects #####

	static function titles()
	{
		return array_merge(self::$root, [[route('titles'), 'Titles']]);
	}

	static function titleSect($id, $name, $sect, $sectN)
	{
		return array_merge(self::$root, [
				[route('titles'), 'Titles'], 
				[route('title', ['id' => $id]), $name],									//["/titles/{$id}", $name], 
				[route('titleSection', ['id' => $id, 'section' => $sect]), $sectN],		//["/titles/{$id}/{$sect}", $sectN]
			]);
	}

	static function notices()
	{
		return array_merge(self::$root, [
				[route('notices'), 'Notices']
			]);
	}

	static function noticesSect($sect, $sectN)
	{
		return array_merge(self::$root, [
				[route('notices'), 'Notices'],
				[route('noticesSection', ['section' => $sect]), $sectN]
			]);
	}

	static function people()
	{
		return array_merge(self::$root, [[route('people'), 'People']]);
	}

	static function person($id, $slug, $name)
	{
		return array_merge(self::$root, [
				[route('people'), 'People'],
				[route('peoplePerson', ['id' => $id, 'slug' => $slug]), $name]
			]);
	}


	static function procurement()
	{
		return array_merge(self::$root, [[route('procurement.index'), 'Procurement']]);
	}

	static function procurementVendors()
	{
		return array_merge(self::$root, [[route('procurement.index'), 'Procurement'], [route('procurement.vendors'), 'Vendors']]);
	}

	static function procurementContracts()
	{
		return array_merge(self::$root, [[route('procurement.index'), 'Procurement'], [route('procurement.contracts'), 'Contracts']]);
	}

	static function procurementSolicitations()
	{
		return array_merge(self::$root, [[route('procurement.index'), 'Procurement'], [route('procurement.solicitations'), 'Solicitations']]);
	}

	static function procurementAgency($name)
	{
		return array_merge(self::$root, [
				[route('procurement.index'), 'Procurement'],
				[route('procurement.agencies'), 'Agencies'],
				[null, $name]
			]);
	}

	static function procurementVendor($id, $name)
	{
		return array_merge(self::$root, [
				[route('procurement.index'), 'Procurement'],
				[route('procurement.vendors'), 'Vendors'],
				[route('procurement.vendor', ['id' => $id]), $name]
			]);
	}

	static function procurementContract($id, $name)
	{
		return array_merge(self::$root, [
				[route('procurement.index'), 'Procurement'],
				[route('procurement.contracts'), 'Contracts'],
				[route('procurement.contract', ['id' => $id]), $name]
			]);
	}

	static function procurementSolicitation($epin, $name)
	{
		return array_merge(self::$root, [
				[route('procurement.index'), 'Procurement'],
				[route('procurement.solicitations'), 'Solicitations'],
				[route('procurement.solicitation', ['epin' => $epin]), $name]
			]);
	}

	static function procurementTransactions()
	{
		return array_merge(self::$root, [[route('procurement.index'), 'Procurement'], [route('procurement.transactions'), 'Transactions']]);
	}

}
