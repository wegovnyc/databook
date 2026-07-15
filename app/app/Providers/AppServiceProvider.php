<?php

namespace App\Providers;

use Illuminate\Support\Facades\URL;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     *
     * @return void
     */
    public function register()
    {
        //
    }

    /**
     * Bootstrap any application services.
     *
     * @return void
     */
    public function boot()
    {
        // Force HTTPS for URL generation when serving on production domain
        // Note: APP_ENV is 'local' even in production, so we detect by APP_URL or request host
        if (str_contains(config('app.url', ''), 'databook.nyc') ||
            str_contains(request()->getHost() ?? '', 'databook.nyc')) {
            URL::forceScheme('https');
        }
    }
}
