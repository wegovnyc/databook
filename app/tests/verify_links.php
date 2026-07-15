<?php

require __DIR__ . '/../vendor/autoload.php';

use GuzzleHttp\Client;

$client = new Client(['base_uri' => 'http://127.0.0.1:8000', 'http_errors' => false]);

echo "Fetching homepage...\n";
$response = $client->get('/');
$html = (string) $response->getBody();

if ($response->getStatusCode() !== 200) {
    echo "Homepage failed with status: " . $response->getStatusCode() . "\n";
    exit(1);
}

echo "Homepage loaded successfully.\n";

// Extract links
preg_match_all('/href="([^"]+)"/', $html, $matches);
$links = array_unique($matches[1]);

$internalLinks = [];
foreach ($links as $link) {
    if (strpos($link, 'http') === 0) {
        if (strpos($link, 'http://127.0.0.1:8000') === 0) {
            $internalLinks[] = str_replace('http://127.0.0.1:8000', '', $link);
        }
    } else if (strpos($link, '/') === 0 && strpos($link, '//') !== 0) {
        $internalLinks[] = $link;
    }
}

$internalLinks = array_unique($internalLinks);
$internalLinks = array_filter($internalLinks, function($link) {
    return !in_array($link, ['#', '/logout']);
});

echo "Found " . count($internalLinks) . " internal links.\n";

$failed = false;
foreach ($internalLinks as $link) {
    echo "Testing $link ... ";
    try {
        $res = $client->get($link);
        $status = $res->getStatusCode();
        $content = (string) $res->getBody();
        
        if ($status === 200) {
            if (strpos($content, 'Whoops, looks like something went wrong') !== false) {
                echo "FAILED (Error Content)\n";
                $failed = true;
            } else {
                echo "OK\n";
            }
        } else {
            echo "FAILED ($status)\n";
            $failed = true;
        }
    } catch (\Exception $e) {
        echo "FAILED (" . $e->getMessage() . ")\n";
        $failed = true;
    }
}

if ($failed) {
    echo "Verification failed.\n";
    exit(1);
} else {
    echo "Verification passed.\n";
    exit(0);
}
