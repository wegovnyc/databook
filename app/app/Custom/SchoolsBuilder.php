<?php
Namespace App\Custom;
use Illuminate\Support\Str;

class SchoolsBuilder
{
	static function schoolsWithGeoJson($rawSchools)
	{
		$rr = [];
		foreach ($rawSchools as $s)
			$rr[] = $s + ['GEO_JSON' => json_encode(self::schoolsGeoJson($s))];
		
		return ['rows' => $rr];
	}

	static function schoolsGeoJson($rawSchool)
	{
		return [
					'type' => 'Feature',
					'properties' => [
						'N' => round((float)$rawSchool['LATITUDE'] + 0.01, 6),
						'W' => round((float)$rawSchool['LONGITUDE'] - 0.01, 6),
						'S' => round((float)$rawSchool['LATITUDE'] - 0.01, 6),
						'E' => round((float)$rawSchool['LONGITUDE'] + 0.01, 6),
						'SCHOOL_ID' => $rawSchool['location_code'],
						'DBN' => $rawSchool['system_code'],
						'NAME' => $rawSchool['location_name'],
						'TYPE' => $rawSchool['location_type_description'],
						'CATEGORY' => $rawSchool['Location_Category_Description'],
						'SCHOOL_DISTRICT' => $rawSchool['Geographical_District_code'],
						'SCHOOL_DISTRICT_NAME' => $rawSchool['Geographical_District_code'],
						'PRINCIPAL_NAME' => $rawSchool['Principal_Name'],
						'PRINCIPAL_PHONE' => $rawSchool['Principal_phone_number'],
					],
					'geometry' => [
						'type' => 'Point',
						'coordinates' => [(float)$rawSchool['LONGITUDE'], (float)$rawSchool['LATITUDE']]
					]
				];
	}

}
