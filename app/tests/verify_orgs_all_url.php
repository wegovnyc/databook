<?php
require __DIR__ . '/../vendor/autoload.php';
$app = require_once __DIR__ . '/../bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Http\Kernel::class);
$response = $kernel->handle(
    $request = Illuminate\Http\Request::capture()
);

use App\Custom\DatabookAPI;

$url = DatabookAPI::url('/get/orgs/all');
echo "Generated URL: " . $url . "\n";

// Parse the token
$parts = preg_split('/[\?&]token=/', $url);
$api_url = $parts[0];
$token = $parts[1];

echo "API URL: " . $api_url . "\n";
echo "Token: " . $token . "\n";

// Test with curl
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $api_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
curl_setopt($ch, CURLOPT_HTTPHEADER, array(
    'Authorization: Bearer ' . $token
));
$output = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
// curl_close($ch);

echo "HTTP Code: " . $http_code . "\n";
if ($http_code == 200) {
    $data = json_decode($output, true);
    if (isset($data['rows']) && count($data['rows']) > 0) {
        echo "Success: Retrieved " . count($data['rows']) . " organizations.\n";
    } else {
        echo "Failure: No rows returned or missing 'rows' key.\n";
        echo "Output: " . substr($output, 0, 500) . "...\n";
    }
} else {
    echo "Failure: HTTP " . $http_code . "\n";
    echo "Output: " . $output . "\n";
}
