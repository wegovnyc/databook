<?php

namespace App\Custom;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Why: The footer email subscription form calls this class via the
 * /api/newsletter_subscription route. Stores subscriber emails in a
 * local JSON file and syncs them to Airtable.
 */
class NewsletterAPI
{
    private static $file = null;

    private static function getFilePath(): string
    {
        if (self::$file === null) {
            self::$file = storage_path('app/newsletter_subscribers.json');
        }
        return self::$file;
    }

    public static function subscribe(array $params): string
    {
        $email = trim($params['email'] ?? '');

        if (empty($email) || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
            return json_encode(['success' => false, 'error' => 'Invalid email address']);
        }

        $filePath = self::getFilePath();
        $subscribers = [];

        if (file_exists($filePath)) {
            $content = file_get_contents($filePath);
            $subscribers = json_decode($content, true) ?: [];
        }

        // Check for duplicates locally
        $existingEmails = array_column($subscribers, 'email');
        if (in_array(strtolower($email), array_map('strtolower', $existingEmails))) {
            return json_encode(['success' => true, 'message' => 'Already subscribed']);
        }

        $subscribers[] = [
            'email' => $email,
            'subscribed_at' => date('c'),
        ];

        file_put_contents($filePath, json_encode($subscribers, JSON_PRETTY_PRINT));

        // Push to Airtable
        $airtableKey = env('AIRTABLE_KEY');
        if (!empty($airtableKey)) {
            try {
                $response = Http::withHeaders([
                    'Authorization' => 'Bearer ' . $airtableKey,
                    'Content-Type' => 'application/json',
                ])->post('https://api.airtable.com/v0/appqM0y7hc7IMfnAa/tblXGW9D9GdSLKWrp', [
                    'records' => [
                        [
                            'fields' => [
                                'Email' => $email
                            ]
                        ]
                    ]
                ]);

                if (!$response->successful()) {
                    Log::error('Airtable newsletter sync failed', ['response' => $response->body()]);
                }
            } catch (\Exception $e) {
                Log::error('Airtable newsletter connection failed', ['error' => $e->getMessage()]);
            }
        }

        return json_encode(['success' => true]);
    }
}
