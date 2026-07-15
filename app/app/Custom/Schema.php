<?php
Namespace App\Custom;
use Illuminate\Support\Str;

class Schema
{
	static function org($dd, $context=true)
	{
		preg_match_all('~^(.*?)(?:,?\s*(?:New York|NY)\s*)*([-\d]*)$~si', trim($dd['main_address'], '"'), $addr, PREG_SET_ORDER);
		return  ($context ? ['@context' => 'https://schema.org'] : []) + [
			'@type' => 'GovernmentOrganization',
			'name' => $dd['name'],
			'address' => 
				$addr[0][1] 
					? [
						'@type' => 'PostalAddress',
						'streetAddress' => $addr[0][1],
						'addressLocality' => 'New York',
						'addressRegion' => 'NY',
						'addressCountry' => 'United States',
						'postalCode' => $addr[0][2]
					]
				: [],
			'description' => preg_replace('~[\r\n]+~si', '; ', $dd['description']),
			'image' => [json_decode($dd['logo'], true)[0]['url'] ?? ''],
			'email' => $dd['email'],
			'telephone' => $dd['main_phone'],
			'faxNumber' => $dd['main_fax'],
			'sameAs' => array_diff([$dd['url'], $dd['facebook'], $dd['twitter']], ['', null]),
			'url' => route('orgProfile', ['id' => $dd['id'], 'orgslug' => Str::slug($dd['name'], '-')]),
		];
	}
	
	
	static function place($dd, $context=false)
	{
		return ($context ? ['@context' => 'https://schema.org'] : []) + [
			'@type' => 'Place',
			'name' => $dd['name'],
			'geo'=> [
				'@type' => 'GeoCoordinates',
				'latitude' => $dd['lat'],
				'longitude' => $dd['lng']
			],
		];
	}
	
	
	static function project($dd, $org, $context=true)
	{
		return ($context ? ['@context' => 'https://schema.org'] : []) + [
			'@type' => 'Project',
			'name' => $dd['PROJECT_DESCR'],
			'description' => preg_replace('~[\r\n]+~si', '; ', "{$dd['PROJECT_ID']} - {$dd['PROJECT_DESCR']}"),
			'areaServed' => self::place(['lat' => $dd['LAT'], 'lng' => $dd['LNG'], 'name' => $dd['PROJECT_ID']]),
			'memberOf' => self::org($org, false),
			'url' => route('project', ['prjId' => $dd['PROJECT_ID'], 'prjslug' => Str::slug($dd['PROJECT_DESCR'], '-')]),
		];
	}


	static function project_a($dd, $org, $context=true)
	{
		return ($context ? ['@context' => 'https://schema.org'] : []) + [
			'@type' => 'Project',
			'name' => $dd['PROJECT_DESCR'],
			'description' => preg_replace('~[\r\n]+~si', '; ', "{$dd['PROJECT_ID']} - {$dd['SCOPE_TEXT']}"),
			'areaServed' => self::place(['lat' => $dd['LAT'], 'lng' => $dd['LNG'], 'name' => $dd['PROJECT_ID']]),
			'memberOf' => self::org($org, false),
			'url' => route('project', ['prjId' => $dd['PROJECT_ID'], 'prjslug' => Str::slug($dd['PROJECT_DESCR'], '-')]),
		];
	}


	static function districtFromFile($type, $id, $org=null)
	{
		$type = strtolower($type);
		$fn = public_path('data/'. ['cc' => 'cc', 'cd' => 'cd', 'nta' => 'nta', 'sd' => 'sd'][$type] . '.geojson');
		$title = ['cc' => 'City Council District ', 'cd' => 'Community District ', 'nta' => '', 'sd' => 'School District '][$type];
		$geojson = json_decode(file_get_contents($fn), true);
		$f = $type == 'nta' ? 'nameAlt' : 'nameCol';
		foreach ($geojson['features'] as $d)
			if ($d['properties'][$f] == $id)
			{
				$pp = [];
				if ($d['geometry']['type'] == 'MultiPolygon')
				{
					$poly = [];
					foreach ($d['geometry']['coordinates'] as $tmppoly)
						$poly = array_merge($poly, $tmppoly[0]);
				} else
					$poly = $d['geometry']['coordinates'][0];
				foreach ($poly as $point)
					$pp[] = "{$point[1]},{$point[0]}";
				$dd = [
					'name' => $title . $id,
					'geo' => implode(' ', $pp),
					'type' => $type,
					'id' => $id,
				];
				return self::district($dd, $org);
			}
		return [];
	}
	
	
	static function district($dd, $org=null, $context=true)
	{
		return ($context ? ['@context' => 'https://schema.org'] : []) + [
			'@type' => 'AdministrativeArea',
			'name' => $dd['name'],
			'geo' => [
				'@type' => 'GeoShape',
				'polygon' => $dd['geo'],
			],
			'url' => route('districtsPreset', ['type' => $dd['type'], 'id' => $dd['id'], 'dslug' => Str::slug($dd['name'], '-'), 'section' => 'projects']),
		] + ($org ? ['memberOf' => self::org($org, false)] : []);
	}

}