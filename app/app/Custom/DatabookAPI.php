<?php
Namespace App\Custom;

class DatabookAPI
{
	static function uploadS3($url, $idxs=[])
	{
		$uri = sprintf('/upload?url=%s&idxs=%s', urlencode($url), implode(',', $idxs));
		return self::req($uri);
	}
	
	static function req($uri)
	{
		// Short timeout prevents page render hangs when API is under load
		$resp = Curl2::exec(config('apis.fapi_entry') . $uri, 'get', [
			CURLOPT_HTTPHEADER => [
                'Authorization: Bearer ' . config('apis.fapi_key')
            ],
			CURLOPT_TIMEOUT => 5,
			CURLOPT_CONNECTTIMEOUT => 3
		]);
		#echo DB_API_ENTRY . "{$uri}<br/>";
		#echo 'Authorization: Bearer ' . DB_API_KEY . "<br/>";
		#echo $resp;
		$jj = json_decode($resp, true);
		return $jj['rows'] ?? false;
	}

    static function reqOCE($uri, $timeout = 5)
	{
		$resp = Curl2::exec(config('apis.fapi_entry') . $uri, 'get', [
			CURLOPT_HTTPHEADER => [
                'Authorization: Bearer ' . config('apis.fapi_key')
            ],
			CURLOPT_TIMEOUT => $timeout,
			CURLOPT_CONNECTTIMEOUT => 3
		]);
		return json_decode($resp, true) ?? false;
	}
	
	static function url($uri)
	{
		return config('apis.fapi_public_entry') . $uri;
	}
}