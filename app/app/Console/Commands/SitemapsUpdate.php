<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use App\Custom\DatabookAPI;
use Illuminate\Support\Str;

class SitemapsUpdate extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'sitemaps:update {from} {to}';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'Command description';

    /**
     * Create a new command instance.
     *
     * @return void
     */
    public function __construct()
    {
        parent::__construct();
    }

    /**
     * Execute the console command.
     *
     * @return int
     */
    public function handle()
    {
		$dd = [];
		$from = $this->argument('from');
		$to = $this->argument('to');
		if (!$from)
		{
			foreach ($this->getPages() as $d)
				$dd[] = $d;
			$xml = view('sitemap', ['entries' => $dd]);
			echo "sitemap.xml\n";
			file_put_contents(public_path('sitemap.xml'), $xml);
		}
		
		$i = $from/50000 + 1;
		$dd = [];
		foreach ($this->getPeople($from, $to) as $d)
		{
			$dd[] = $d;
			if (count($dd) == 50000)
			{
				$xml = view('sitemap', ['entries' => $dd]);
				$fn = sprintf('sitemap_people_%02d.xml', $i++);
				echo "{$fn}\n";
				file_put_contents(public_path($fn), $xml);
				unset($xml, $dd);
				$dd = [];
			}
		}
		$xml = view('sitemap', ['entries' => $dd]);
		$fn = sprintf('sitemap_people_%02d.xml', $i++);
		echo "{$fn}\n";
		file_put_contents(public_path($fn), $xml);

        return 0;
    }

    public function getPages()
    {
		$dd = [];
		#orgs
			$dd[] = [route('root'), 1, 'monthly'];
			$dd[] = [route('about'), 1, 'monthly'];
			$dd[] = [route('orgs'), 1, 'monthly'];
			foreach (DatabookAPI::req('/get/orgs/directory') as $org)
				$dd[] = [route('orgProfile', [$org['id'], Str::slug($org['name'], '-')]), 0.6, 'monthly'];
		#districts
			$dd[] = [route('districts'), 1, 'monthly'];
			foreach (['cc', 'cd', 'nta'] as $type)
			{
				$fn = public_path("data/{$type}.geojson");
				$title = ['cc' => 'City Council District ', 'cd' => 'Community District ', 'nta' => ''][$type];
				$geojson = json_decode(file_get_contents($fn), true);
				$f = $type == 'nta' ? 'nameAlt' : 'nameCol';
				foreach ($geojson['features'] as $d)
				{
					$id = $d['properties'][$f];
					$name = $title . $id;
					$dd[] = [route('districtsPreset', ['type' => $type, 'id' => $id, 'dslug' => Str::slug($name, '-'), 'section' => 'capital-projects']), 0.6, 'monthly'];
				}
			}
		#projects
			$dd[] = [route('projects'), 1, 'monthly'];
			$dates = DatabookAPI::req('/get/capitalprojects/dates');
			#print_r($dates);
			foreach (DatabookAPI::req('/get/capitalprojects/all/' . $dates[0]['PUB_DATE']) as $prj)
				if (!strstr($prj['PROJECT_ID'], '&'))
					$dd[] = [route('project', ['prjId' => $prj['PROJECT_ID'], 'prjslug' => Str::slug($prj['PROJECT_DESCR'], '-')]), 0.6, 'monthly'];
		#titles
			$dd[] = [route('titles'), 1, 'monthly'];
		#notices 
			$dd[] = [route('notices'), 1, 'monthly'];
		#auctions
			$dd[] = [route('auctions'), 1, 'monthly'];
		#people	
			$dd[] = [route('people'), 1, 'monthly'];
		foreach ($dd as $d)
			yield $d;
    }

    public function getPeople($from, $to)
    {
		#people
		$pp = null;
		while ((!$pp || (count($pp) == 50000)) && ($from < $to))
		{
			unset($pp);
			$pp = DatabookAPI::req("/get/people/sitemap/{$from}");
			foreach ($pp as $p)
				if ($p['fullname'])
					yield [route('peoplePerson', ['id' => $p['perm-id'], 'slug' => Str::slug(preg_replace('~\s+~', ' ', $p['fullname']), '-')]), 0.6, 'monthly'];
			$from += count($pp);
		}
    }
}