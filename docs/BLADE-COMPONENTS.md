# Blade components (`<x-db.*>`)

> Phase B of [COMPONENT-LIBRARY-PLAN.md](COMPONENT-LIBRARY-PLAN.md). Thin
> **anonymous Blade components** that emit the canonical `.db-*` markup so new
> pages compose components instead of copy-pasting HTML. They wrap the existing
> CSS — no new styling, one source of truth. Live demo: **`/styleguide/components`**;
> full visual reference: `/styleguide`.

Files live in `app/resources/views/components/db/`. Laravel 7 auto-discovers
them as `<x-db.NAME>`.

## Conventions

- **Additive, hook-safe.** Every component uses `$attributes->merge(...)`, so
  caller-supplied `id`, `class`, `data-*`, `name`, etc. pass through and
  concatenate. Keep DataTables IDs, `prj_stat`/`gs_*`, `fapireq()` targets,
  Mapbox layer ids, and form `name`s on the elements you pass in — put such
  hooks in the slot/attributes and they survive (verified).
- **Icons** are Bootstrap Icons only (`<x-db.icon name="…" />` → `bi bi-…`).
- Value/content is the **slot** wherever a hook might live (e.g. stat value),
  so you can wrap it in your own `<span id=… class="prj_stat">`.

## Catalog

| Component | Key props | Example |
|---|---|---|
| `x-db.button` | `variant=primary\|outline\|ghost`, `size=sm\|lg`, `href` | `<x-db.button variant="outline" href="/x">Go</x-db.button>` |
| `x-db.card` | `hoverable`, `title` | `<x-db.card title="Snapshot">…</x-db.card>` |
| `x-db.badge` | `tone=navy\|neutral\|success\|warning\|danger\|info`, `dot` | `<x-db.badge tone="success" dot>Active</x-db.badge>` |
| `x-db.stat-grid` | — | wraps `x-db.stat` tiles |
| `x-db.stat` | `label`, `sub`, `accent` | `<x-db.stat label="Agencies" accent><span id="agencies_no" class="prj_stat">167</span></x-db.stat>` |
| `x-db.table` | (pass `id`, etc.) | `<x-db.table id="myTable"><thead>…</x-db.table>` |
| `x-db.table-wrap` | — | horizontal-scroll wrapper |
| `x-db.tabs` | `scroll` | wraps `x-db.tab` |
| `x-db.tab` | `href`, `active` | `<x-db.tab href="#" active>Overview</x-db.tab>` |
| `x-db.alert` | `tone`, `dismissible`, `icon` | `<x-db.alert tone="warning">Heads up.</x-db.alert>` |
| `x-db.eyebrow` | — | `<x-db.eyebrow>Procurement</x-db.eyebrow>` |
| `x-db.hero` | `title`, `eyebrow` | `<x-db.hero title="Agencies" eyebrow="Directory">…</x-db.hero>` |
| `x-db.search` | `placeholder` (+ `name`/`id` pass through to input) | `<x-db.search name="q" placeholder="Search…" />` |
| `x-db.empty` | `icon`, `title` | `<x-db.empty title="No results">Try another filter.</x-db.empty>` |
| `x-db.icon` | `name` | `<x-db.icon name="arrow-right" />` |
| `x-db.chart-card` | `title` | wraps a `<canvas>` in the fixed-height `.db-chart-body` |

## Notes / limits

- **Laravel 7**: anonymous components + `@props` + `$attributes->merge()` (class
  concatenation) all work; the `@class` directive and `$attributes->class()`
  helper are 8+ — don't use them here.
- The dropdown-tab (`.db-tab-dd` + JS menu), profile headers, facet rails, map
  controls, org chart, jobs grid, and the orange Analysis components are v2 —
  use raw `.db-*` markup for those until componentized.
- Adoption is incremental: new/touched pages use `<x-db.*>`; existing pages keep
  working on raw classes and migrate opportunistically.
