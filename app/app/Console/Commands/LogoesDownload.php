<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use App\Custom\DatabookAPI;
Use App\Custom\Curl2 as Curl;

class LogoesDownload extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'logoes:download';

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
		$orgs = DatabookAPI::req('/get/orgs/all');
		echo "\nLogoesDownload ===== " . date('Y-m-d H:i:s') . " =====================\n";
		if (!is_dir(public_path('img/logo/')))
			mkdir(public_path('img/logo/'), 0777, true);
		foreach ($orgs as $i=>$org)
		{
			if ($org['logo'])
			{
				$uu = json_decode(str_replace('\"', '"', $org['logo']), true);
				$fn = preg_replace('~\?.*~si', '', basename($uu[0]['url']));
				#$fullfn = public_path("img/logo/{$org['id']}_" . urldecode($fn));
				$fullfn = public_path("img/logo/{$org['id']}");
				echo $fullfn . ' ';
				if (!file_exists($fullfn))
				{
					$img = Curl::exec($uu[0]['url'], 'get');
					if ($img && (strlen($img) > 30))
					{
						file_put_contents($fullfn, $img);
					}
					echo $org['id'] . ($img ? '+; ' : '-; ') . "\n";
				}
				flush();
			}	
		}
        return 0;
    }
}