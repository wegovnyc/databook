<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Services\PayloadService;
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
        $cms = new PayloadService();
        $article = $cms->getArticleBySlug($slug);

        if (!$article) {
            abort(404);
        }

        // `content` arrives as HTML (PayloadService renders Payload's Lexical
        // rich text), so the view can output it raw.

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
        $cms = new PayloadService();
        $articles = $cms->getAllArticles('Databook', 100);

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
