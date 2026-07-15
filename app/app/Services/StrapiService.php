<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Cache;

class StrapiService
{
    protected $baseUrl;

    public function __construct()
    {
        // Use the public API URL directly as per user request/plan. 
        // In production this might need to come from ENV, but plans said "strapi.wegov.nyc".
        $this->baseUrl = 'https://strapi.wegov.nyc/api';
    }

    /**
     * Get latest articles filtered by category.
     *
     * @param int $limit
     * @param string $category
     * @return array
     */
    public function getLatestArticles($limit = 3, $category = 'Databook')
    {
        $cacheKey = "strapi_articles_{$category}_{$limit}";

        // Cache for 1 hour
        return Cache::remember($cacheKey, 3600, function () use ($limit, $category) {
            try {
                // Build query array
                $query = [
                    'populate' => '*',
                    'sort' => ['originalPublishDate:desc'],
                    'pagination' => ['limit' => $limit],
                    'filters' => [
                        'category' => [
                            '$eq' => $category
                        ]
                    ]
                ];
                
                // Build query string and decode brackets for Strapi readability if needed,
                // though standard encoding usually works. strapi qs supports brackets.
                $queryString = http_build_query($query);
                
                $url = "{$this->baseUrl}/articles?{$queryString}";
                
                $ch = curl_init();
                curl_setopt($ch, CURLOPT_URL, $url);
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_TIMEOUT, 5);
                
                $response = curl_exec($ch);
                $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
                // curl_close($ch); // Deprecated in PHP 8.0+ / 8.5

                if ($httpCode >= 200 && $httpCode < 300 && $response) {
                    $json = json_decode($response, true);
                    $data = $json['data'] ?? [];
                    
                    // Fix image URLs
                    $data = array_map(function($article) {
                        return $this->fixImageUrls($article);
                    }, $data);

                    return $data;
                }

                return [];
            } catch (\Exception $e) {
                return [];
            }
        });
    }

    /**
     * Get all articles for blog page, sorted by originalPublishDate.
     *
     * @param string $category
     * @param int $limit
     * @return array
     */
    public function getAllArticles($category = 'Databook', $limit = 100)
    {
        $cacheKey = "strapi_all_articles_{$category}_{$limit}";

        // Cache for 1 hour
        return Cache::remember($cacheKey, 3600, function () use ($limit, $category) {
            try {
                $query = [
                    'populate' => '*',
                    'sort' => ['originalPublishDate:desc'],
                    'pagination' => ['limit' => $limit],
                    'filters' => [
                        'category' => [
                            '$eq' => $category
                        ]
                    ]
                ];

                $queryString = http_build_query($query);
                $url = "{$this->baseUrl}/articles?{$queryString}";

                $ch = curl_init();
                curl_setopt($ch, CURLOPT_URL, $url);
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_TIMEOUT, 10);

                $response = curl_exec($ch);
                $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

                if ($httpCode >= 200 && $httpCode < 300 && $response) {
                    $json = json_decode($response, true);
                    $data = $json['data'] ?? [];

                    // Fix image URLs
                    $data = array_map(function($article) {
                        return $this->fixImageUrls($article);
                    }, $data);

                    return $data;
                }

                return [];
            } catch (\Exception $e) {
                return [];
            }
        });
    }

    /**
     * Get article by slug.
     * 
     * @param string $slug
     * @return array|null
     */
    public function getArticleBySlug($slug)
    {
        $cacheKey = "strapi_article_{$slug}";

        return Cache::remember($cacheKey, 3600, function () use ($slug) {
            try {
                $query = [
                    'populate' => '*',
                    'filters' => [
                        'slug' => [
                            '$eq' => $slug
                        ]
                    ]
                ];

                $queryString = http_build_query($query);
                $url = "{$this->baseUrl}/articles?{$queryString}";

                $ch = curl_init();
                curl_setopt($ch, CURLOPT_URL, $url);
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_TIMEOUT, 5);

                $response = curl_exec($ch);
                $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
                // curl_close($ch);

                if ($httpCode >= 200 && $httpCode < 300 && $response) {
                    $json = json_decode($response, true);
                    $data = $json['data'] ?? [];
                    
                    if (isset($data[0])) {
                        return $this->fixImageUrls($data[0]);
                    }
                    return null;
                }

                return null;
            } catch (\Exception $e) {
                return null;
            }
        });
    }

    private function fixImageUrls($data)
    {
        if (is_array($data)) {
            foreach ($data as $key => $value) {
                if ($key === 'url' && is_string($value) && strpos($value, '/uploads/') === 0) {
                    $data[$key] = 'https://strapi.wegov.nyc' . $value;
                } elseif (is_array($value)) {
                    $data[$key] = $this->fixImageUrls($value);
                }
            }
        }
        return $data;
    }
}
