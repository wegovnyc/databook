<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Services\StrapiService;
use App\Custom\Breadcrumbs;
use Illuminate\Support\Str;

class Articles extends Controller
{
    /**
     * Show article detail.
     *
     * @param  string  $slug
     * @return \Illuminate\View\View
     */
    public function show($slug)
    {
        $strapi = new StrapiService();
        $article = $strapi->getArticleBySlug($slug);

        if (!$article) {
            abort(404);
        }

        // Parse content - rudimentary markdown/html handling if needed, 
        // but Strapi usually returns rich text HTML or blocks.
        // Assuming 'content' is HTML or we display as raw.

        return view('article', [
            'article' => $article,
            'pagetitle' => $article['title'] . " | NYC Databook",
            'breadcrumbs' => [
                [route('root'), 'Home'],
                [null, $article['title']],
            ],
        ]);
    }

    /**
     * Show blog index page with all Databook articles.
     *
     * @return \Illuminate\View\View
     */
    public function index()
    {
        $strapi = new StrapiService();
        $articles = $strapi->getAllArticles('Databook', 100);

        return view('blog', [
            'articles' => $articles,
            'pagetitle' => 'Blog | WeGovNYC Databook',
            'breadcrumbs' => [
                [route('root'), 'Home'],
                [null, 'Blog'],
            ],
        ]);
    }
}
