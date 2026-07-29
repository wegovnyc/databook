<?php

namespace App\Services;

use Illuminate\Support\Facades\Cache;

/**
 * PayloadService — blog/article content from the Sarapis Payload CMS
 * (multi-brand). Replaced the former StrapiService (removed once Strapi was
 * retired), keeping its method names, signatures and returned array shape, so
 * the Blade views did not have to change.
 *
 * Content is scoped to this site's brand in the Payload `sites` registry
 * (`where[sites.key][equals]=databook`), NOT by the old free-text category —
 * an article can be published to several brands at once. The `$category`
 * argument is retained only for call-site compatibility and is ignored for
 * filtering (it is still returned per-article for the badge).
 *
 * Returned per article (the shape the views expect):
 *   slug, title, category, content (HTML), description,
 *   image => ['url' => absolute], originalPublishDate, publishedAt,
 *   author => ['name' => ...]
 *
 * Config: `services.payload.url` / `services.payload.site_key`
 * (env PAYLOAD_URL / PAYLOAD_SITE_KEY). Read through config() — NOT env() —
 * because the image runs `artisan config:cache`, after which env() is null.
 */
class PayloadService
{
    /** @var string */
    protected $baseUrl;

    /** @var string */
    protected $siteKey;

    /**
     * Legacy Strapi slug => current Payload slug, for articles whose slug
     * differs (this one was imported from WordPress with a shorter slug).
     * Keeps old databook.nyc/articles/... URLs resolving.
     */
    const SLUG_ALIASES = [
        'wegovnycs-databook-featured-in-local-news-story' => 'wegovnycs-databook-featured-in-local-news',
    ];

    public function __construct()
    {
        $base = config('services.payload.url') ?: 'https://next.sarapis.org';
        $this->baseUrl = rtrim($base, '/');
        $this->siteKey = config('services.payload.site_key') ?: 'databook';
    }

    /**
     * Get latest articles for this brand.
     *
     * @param int $limit
     * @param string $category  (ignored for filtering; kept for compatibility)
     * @return array
     */
    public function getLatestArticles($limit = 3, $category = 'Databook')
    {
        $cacheKey = "payload_articles_{$this->siteKey}_{$limit}";

        return Cache::remember($cacheKey, 3600, function () use ($limit) {
            return $this->fetchList($limit);
        });
    }

    /**
     * Get all articles for the blog index, newest first.
     *
     * @param string $category  (ignored for filtering; kept for compatibility)
     * @param int $limit
     * @return array
     */
    public function getAllArticles($category = 'Databook', $limit = 100)
    {
        $cacheKey = "payload_all_articles_{$this->siteKey}_{$limit}";

        return Cache::remember($cacheKey, 3600, function () use ($limit) {
            return $this->fetchList($limit);
        });
    }

    /**
     * Get one article by slug (accepts legacy Strapi slugs).
     *
     * @param string $slug
     * @return array|null
     */
    public function getArticleBySlug($slug)
    {
        $resolved = isset(self::SLUG_ALIASES[$slug]) ? self::SLUG_ALIASES[$slug] : $slug;
        $cacheKey = "payload_article_{$resolved}";

        return Cache::remember($cacheKey, 3600, function () use ($resolved) {
            $query = http_build_query([
                'where' => [
                    'slug' => ['equals' => $resolved],
                    'sites.key' => ['equals' => $this->siteKey],
                ],
                'depth' => 2,
                'limit' => 1,
            ]);

            $json = $this->get("/api/posts?{$query}", 5);
            if (!$json || empty($json['docs'][0])) {
                return null;
            }

            return $this->mapPost($json['docs'][0]);
        });
    }

    // ---------------------------------------------------------------
    // internals
    // ---------------------------------------------------------------

    /**
     * @param int $limit
     * @return array
     */
    protected function fetchList($limit)
    {
        $query = http_build_query([
            'where' => ['sites.key' => ['equals' => $this->siteKey]],
            'sort' => '-publishedAt',
            'depth' => 2,
            'limit' => $limit,
        ]);

        $json = $this->get("/api/posts?{$query}", 10);
        if (!$json || empty($json['docs'])) {
            return [];
        }

        $out = [];
        foreach ($json['docs'] as $doc) {
            $out[] = $this->mapPost($doc);
        }

        return $out;
    }

    /**
     * GET JSON from Payload. Returns null on any failure (fail-soft, as before).
     *
     * @param string $path
     * @param int $timeout
     * @return array|null
     */
    protected function get($path, $timeout = 5)
    {
        try {
            $ch = curl_init();
            curl_setopt($ch, CURLOPT_URL, $this->baseUrl . $path);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
            curl_setopt($ch, CURLOPT_HTTPHEADER, ['Accept: application/json']);

            $response = curl_exec($ch);
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

            if ($httpCode >= 200 && $httpCode < 300 && $response) {
                $json = json_decode($response, true);
                return is_array($json) ? $json : null;
            }

            return null;
        } catch (\Exception $e) {
            return null;
        }
    }

    /**
     * Payload post => the flat article array the views expect.
     *
     * @param array $doc
     * @return array
     */
    protected function mapPost(array $doc)
    {
        // Hero: heroImage, else the SEO meta image.
        $image = null;
        $hero = isset($doc['heroImage']) && is_array($doc['heroImage']) ? $doc['heroImage'] : null;
        if (!$hero && isset($doc['meta']['image']) && is_array($doc['meta']['image'])) {
            $hero = $doc['meta']['image'];
        }
        if ($hero && !empty($hero['url'])) {
            $image = ['url' => $this->absolute($hero['url'])];
            if (!empty($hero['alt'])) {
                $image['alt'] = $hero['alt'];
            }
        }

        // Category badge: first related category title.
        $category = null;
        if (!empty($doc['categories'][0]) && is_array($doc['categories'][0])) {
            $category = isset($doc['categories'][0]['title']) ? $doc['categories'][0]['title'] : null;
        }

        // Tags -> plain strings (views may show them).
        $tags = [];
        if (!empty($doc['tags']) && is_array($doc['tags'])) {
            foreach ($doc['tags'] as $t) {
                if (is_array($t) && isset($t['title'])) {
                    $tags[] = $t['title'];
                } elseif (is_string($t)) {
                    $tags[] = $t;
                }
            }
        }

        // Author name (Strapi gave author => ['name' => ...]).
        $author = null;
        if (!empty($doc['populatedAuthors'][0]['name'])) {
            $author = ['name' => $doc['populatedAuthors'][0]['name']];
        }

        $published = isset($doc['publishedAt']) ? $doc['publishedAt'] : (isset($doc['createdAt']) ? $doc['createdAt'] : null);

        return [
            'id' => isset($doc['id']) ? $doc['id'] : null,
            'slug' => isset($doc['slug']) ? $doc['slug'] : null,
            'title' => isset($doc['title']) ? $doc['title'] : '',
            'category' => $category,
            'tags' => $tags,
            'description' => isset($doc['meta']['description']) ? $doc['meta']['description'] : null,
            'content' => $this->lexicalToHtml(isset($doc['content']) ? $doc['content'] : null),
            'image' => $image,
            'author' => $author,
            'originalPublishDate' => $published,
            'publishedAt' => $published,
        ];
    }

    /**
     * @param string $url
     * @return string
     */
    protected function absolute($url)
    {
        if (strpos($url, 'http://') === 0 || strpos($url, 'https://') === 0 || strpos($url, '//') === 0) {
            return $url;
        }

        return $this->baseUrl . $url;
    }

    // ---------------------------------------------------------------
    // Lexical (Payload rich text) -> HTML
    // ---------------------------------------------------------------

    /**
     * Payload stores rich text as a Lexical node tree; the views render
     * `content` as raw HTML, so convert. Covers what the articles use:
     * headings, paragraphs, lists, quotes, links, formatted text, uploads,
     * tables, hr, line breaks. Unknown containers render their children.
     *
     * @param array|null $content
     * @return string
     */
    protected function lexicalToHtml($content)
    {
        if (!is_array($content) || empty($content['root'])) {
            return '';
        }

        return $this->childrenHtml($content['root']);
    }

    /**
     * @param array $node
     * @return string
     */
    protected function childrenHtml($node)
    {
        if (!is_array($node) || empty($node['children']) || !is_array($node['children'])) {
            return '';
        }

        $out = '';
        foreach ($node['children'] as $child) {
            $out .= $this->nodeHtml($child);
        }

        return $out;
    }

    /**
     * @param mixed $n
     * @return string
     */
    protected function nodeHtml($n)
    {
        if (!is_array($n)) {
            return '';
        }

        $type = isset($n['type']) ? $n['type'] : '';

        switch ($type) {
            case 'text':
                return $this->textHtml($n);

            case 'linebreak':
                return '<br />';

            case 'paragraph':
                $inner = $this->childrenHtml($n);
                return $inner === '' ? '' : "<p>{$inner}</p>";

            case 'heading':
                $tag = isset($n['tag']) && preg_match('/^h[1-6]$/', $n['tag']) ? $n['tag'] : 'h2';
                return "<{$tag}>" . $this->childrenHtml($n) . "</{$tag}>";

            case 'quote':
                return '<blockquote>' . $this->childrenHtml($n) . '</blockquote>';

            case 'list':
                $listType = isset($n['listType']) ? $n['listType'] : (isset($n['tag']) ? $n['tag'] : '');
                $tag = ($listType === 'number' || $listType === 'ol') ? 'ol' : 'ul';
                return "<{$tag}>" . $this->childrenHtml($n) . "</{$tag}>";

            case 'listitem':
                return '<li>' . $this->childrenHtml($n) . '</li>';

            case 'link':
            case 'autolink':
                $url = '#';
                if (isset($n['fields']['url'])) {
                    $url = $n['fields']['url'];
                } elseif (isset($n['url'])) {
                    $url = $n['url'];
                }
                $target = !empty($n['fields']['newTab']) ? ' target="_blank" rel="noopener noreferrer"' : '';
                return '<a href="' . $this->esc($url) . '"' . $target . '>' . $this->childrenHtml($n) . '</a>';

            case 'horizontalrule':
                return '<hr />';

            case 'upload':
                if (empty($n['value']['url'])) {
                    return '';
                }
                $alt = !empty($n['value']['alt']) ? $n['value']['alt'] : '';
                return '<img src="' . $this->esc($this->absolute($n['value']['url'])) . '" alt="' . $this->esc($alt) . '" />';

            case 'table':
                return '<table class="table">' . $this->childrenHtml($n) . '</table>';

            case 'tablerow':
                return '<tr>' . $this->childrenHtml($n) . '</tr>';

            case 'tablecell':
                $cell = !empty($n['headerState']) ? 'th' : 'td';
                return "<{$cell}>" . $this->childrenHtml($n) . "</{$cell}>";

            default:
                return $this->childrenHtml($n);
        }
    }

    /**
     * @param array $n
     * @return string
     */
    protected function textHtml($n)
    {
        $t = $this->esc(isset($n['text']) ? $n['text'] : '');
        $f = isset($n['format']) ? (int) $n['format'] : 0;

        if ($f & 1) { $t = "<strong>{$t}</strong>"; }
        if ($f & 2) { $t = "<em>{$t}</em>"; }
        if ($f & 4) { $t = "<s>{$t}</s>"; }
        if ($f & 8) { $t = "<u>{$t}</u>"; }
        if ($f & 16) { $t = "<code>{$t}</code>"; }

        return $t;
    }

    /**
     * @param string $s
     * @return string
     */
    protected function esc($s)
    {
        return htmlspecialchars((string) $s, ENT_QUOTES, 'UTF-8');
    }
}
