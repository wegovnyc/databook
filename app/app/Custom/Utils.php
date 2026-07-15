<?php
namespace App\Custom;

class Utils
{
    static function currency($amount)
    {
        if ($amount === null || $amount === '') return 'N/A';
        return '$' . number_format((float)$amount, 2);
    }
}
