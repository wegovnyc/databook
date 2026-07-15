<?php

return [

	'geoclient_key' => env('GEOCLIENT_KEY', ''),

    /*
	 |	App api key
    */
	'app_key' => env('APP_API_KEY', 'default_insecure_key_change_me'),
    'fapi_entry' => env('FAPI_ENTRY', 'http://127.0.0.1:5539'),
    'fapi_public_entry' => env('FAPI_PUBLIC_ENTRY', 'https://api.databook.nyc'),
    'fapi_key' => env('FAPI_KEY', ''),
];
