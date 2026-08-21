<?php
namespace App\Custom;

use League\CommonMark\CommonMarkConverter;

/**
 * Loads a Contract Story markdown file (resources/stories/renewals/{id}.md)
 * per the design_handoff_renewal_queue/README.md format: YAML-ish front
 * matter + a body of `## Heading {#anchor-id}` sections, each optionally
 * preceded by a `<!-- kicker: ... -->` comment. Sections may contain raw
 * HTML blocks (tables, phase lists) alongside Markdown prose.
 *
 * This is a narrow, hand-rolled front-matter reader (only the handful of
 * shapes this file format actually uses — scalars, one folded ">" block,
 * one list-of-maps for `stats`) rather than a general YAML parser, since no
 * YAML library is installed and the format is fixed by the handoff spec.
 */
class RenewalStoryLoader
{
    public static function load(string $contractId): ?array
    {
        $path = resource_path("stories/renewals/{$contractId}.md");
        if (!file_exists($path)) return null;

        if (!preg_match('/^---\s*\n(.*?)\n---\s*\n(.*)$/s', file_get_contents($path), $m)) {
            return null;
        }

        $meta = self::parseFrontMatter($m[1]);
        $meta['sections'] = self::parseSections($m[2]);
        return $meta;
    }

    private static function parseFrontMatter(string $raw): array
    {
        $lines = explode("\n", $raw);
        $meta = ['stats' => []];
        $i = 0;
        $count = count($lines);

        while ($i < $count) {
            $line = $lines[$i];
            if (trim($line) === '') { $i++; continue; }

            if (!preg_match('/^(\w+):\s?(.*)$/', $line, $kv)) { $i++; continue; }
            [$full, $key, $value] = $kv;

            if ($value === '>') {
                // Folded block scalar: consume indented lines, join with spaces.
                $parts = [];
                $i++;
                while ($i < $count && preg_match('/^\s+(\S.*)$/', $lines[$i], $cm)) {
                    $parts[] = trim($cm[1]);
                    $i++;
                }
                $meta[$key] = trim(implode(' ', $parts));
                continue;
            }

            if ($value === '' && $key === 'stats') {
                // List of maps: "  - label: ..." then indented "    key: value" lines.
                $i++;
                $item = null;
                while ($i < $count && preg_match('/^\s*-?\s*(\w+):\s?(.*)$/', $lines[$i], $im)) {
                    $isNewItem = (bool) preg_match('/^\s*-\s+/', $lines[$i]);
                    if ($isNewItem) {
                        if ($item !== null) $meta['stats'][] = $item;
                        $item = [];
                    }
                    [, $ik, $iv] = $im;
                    $item[$ik] = $iv === 'true' ? true : ($iv === 'false' ? false : $iv);
                    $i++;
                }
                if ($item !== null) $meta['stats'][] = $item;
                continue;
            }

            $meta[$key] = $value;
            $i++;
        }

        return $meta;
    }

    private static function parseSections(string $body): array
    {
        // Split on each "## Title {#id}" heading, keeping the preceding
        // "<!-- kicker: ... -->" comment (if any) with its section.
        $pattern = '/(?:<!--\s*kicker:\s*(.+?)\s*-->\s*\n)?^##\s+(.+?)\s*\{#([\w-]+)\}\s*$/m';
        preg_match_all($pattern, $body, $matches, PREG_OFFSET_CAPTURE | PREG_SET_ORDER);

        if (!$matches) return [];

        $converter = new CommonMarkConverter(['html_input' => 'allow']);
        $sections = [];

        for ($i = 0; $i < count($matches); $i++) {
            $match = $matches[$i];
            $headingEnd = $match[0][1] + strlen($match[0][0]);
            $chunkEnd = $i + 1 < count($matches) ? $matches[$i + 1][0][1] : strlen($body);
            $chunk = substr($body, $headingEnd, $chunkEnd - $headingEnd);

            $sections[] = [
                'kicker' => trim($match[1][0] ?? ''),
                'title' => trim($match[2][0]),
                'id' => trim($match[3][0]),
                'html' => $converter->convertToHtml(trim($chunk)),
            ];
        }

        return $sections;
    }
}
