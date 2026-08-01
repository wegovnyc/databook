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
	
	/**
	 * Call an authenticated /admin/* endpoint SERVER-SIDE and return
	 * [status, decoded-body].
	 *
	 * ⚠ Why the browser never talks to the API directly here: the credential is
	 * a long-lived write-scoped bearer token in this app's .env. Handing it to a
	 * page would publish it to anyone who opens devtools. So the editing UI
	 * posts to Laravel, Laravel calls the API, and the token stays on the server.
	 *
	 * ⚠ Unlike req()/reqOCE() this returns the STATUS as well as the body,
	 * because the whole point of the org-admin endpoints is that they refuse
	 * things — a 409 on an unconfirmed rename and a 400 on an invalid type are
	 * the feature. Collapsing them to false (as req() does) would turn every
	 * refusal into a generic failure and hide the reason from the human.
	 */
	static function adminReq($uri, $method = 'get', $payload = null)
	{
		$opts = [
			CURLOPT_HTTPHEADER => [
				'Authorization: Bearer ' . config('apis.fapi_key'),
				'Accept: application/json',
			],
			CURLOPT_TIMEOUT => 20,
			CURLOPT_CONNECTTIMEOUT => 5,
			// A 405/409 must come back as itself, not be chased or swallowed.
			CURLOPT_FOLLOWLOCATION => 0,
			CURLOPT_HEADER => 0,
		];
		$ch = Curl2::init(config('apis.fapi_entry') . $uri, $method, $opts, '',
			$payload === null ? '' : json_encode($payload));
		$body = curl_exec($ch);
		$status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
		if ($body === false)
			return [0, ['detail' => 'the API could not be reached']];
		return [$status, json_decode($body, true)];
	}

	static function url($uri)
	{
		return config('apis.fapi_public_entry') . $uri;
	}
}