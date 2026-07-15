# Databook — Visual Style Reference (for integrators)

> Purpose: give another project/agent enough to build UI that **looks like databook.nyc**
> without guessing. Databook has no component library yet — its design system is a
> hand-authored CSS layer (`.db-*` classes) **on top of Bootstrap 5.3.3** (CDN, no build
> step), consumed by server-rendered Laravel Blade. This doc is the portable summary; the
> files named below are the ground truth.

## Ground truth (read these for exact values)

On the same machine as databook (`<repo-root>`):

- **Tokens:** `app/public/css/databook-tokens.css` (inlined in full below)
- **Components:** `app/public/css/databook-components.css` (~743 lines; class catalog below)
- **Charts:** `app/public/js/db-charts.js` (`DBChart` factory — themes Chart.js to the palette)
- **Live rendered reference:** https://databook.nyc/styleguide  ← the single best "what it looks like"
- **Screens (real renders):** `docs/design-handoff*/mockups/*.png`
  (e.g. `docs/design-handoff/mockups/08-design-system-styleguide.png`, `01-global-shell.png`, `02-org-profile.png`)

## Identity in one paragraph

Government-data product in the **USWDS spirit**: deep **navy** brand (`#162e51`), calm blue
functional accents (`#2491ff` active/focus, `#005ea2` links), **civic orange** used *only* for
the `DATABOOK.NYC` wordmark and the editorial "Analysis" surface (`#ff941f`). Typeface is
**Public Sans** (Inter fallback), monospace **Roboto Mono**. 8px spacing base, 8px default
radius, restrained shadows. Dense, legible tables; navy section heads; generous whitespace.
Icons are **Bootstrap Icons** (`bi-*`) — never Font Awesome (it isn't loaded).

## Hard conventions (do these, or it won't look like databook)

- **Base = Bootstrap 5.3.3**; `.db-*` classes are *additive skins* over it. The token file
  also re-points Bootstrap's `--bs-*` theme vars at the navy tokens, so plain `.btn-primary`,
  links, and focus rings inherit the system for free.
- **Color use:** money/values in **navy** (not green). Green (`--db-success`) is for *status
  only*. Orange (`--db-brand`) is reserved for the wordmark + Analysis pages — don't use it as
  a general accent.
- **Icons:** Bootstrap Icons `bi-*` only.
- **Type scale + spacing:** use the `--db-*` tokens below, not ad-hoc px.
- **Charts:** if using Chart.js, theme via the `DBChart` palette (navy/accent), money-formatted.

## Design tokens (verbatim from `databook-tokens.css`)

```css
:root {
  /* BRAND / NAVY */
  --db-navy-900:#0b1f3a; --db-navy-800:#102742; --db-primary:#162e51;
  --db-navy-600:#1f3a63; --db-navy-500:#2c4a73; --db-navy-100:#e7ecf3; --db-navy-050:#f3f6fa;
  /* LINKS / ACCENT */
  --db-link:#005ea2; --db-link-hover:#004080; --db-link-visited:#54278f;
  --db-accent:#2491ff; --db-accent-soft:#d3e6fb;
  /* BRAND WORDMARK (orange — wordmark + Analysis only) */
  --db-brand:#ff941f; --db-brand-hover:#ffb154;
  /* NEUTRALS (USWDS-adjacent) */
  --db-white:#fff; --db-gray-050:#f9fafb; --db-gray-100:#f0f2f4; --db-gray-200:#e6e9ec;
  --db-gray-300:#dfe1e2; --db-gray-400:#c6cacd; --db-gray-500:#9aa0a6; --db-gray-600:#757575;
  --db-gray-700:#4b5159; --db-gray-800:#2d3239; --db-gray-900:#171717;
  /* SEMANTIC SURFACES */
  --db-bg:var(--db-white); --db-bg-secondary:var(--db-gray-100); --db-bg-tertiary:var(--db-gray-050);
  --db-bg-band:var(--db-navy-050); --db-text:var(--db-gray-900); --db-text-muted:var(--db-gray-600);
  --db-text-on-navy:#eef3f9; --db-text-on-navy-muted:#aebfd4;
  --db-border:var(--db-gray-300); --db-border-strong:var(--db-gray-400);
  /* STATE (each has -bg fill + -fg text) */
  --db-success:#2e8540; --db-success-bg:#ecf3ed; --db-success-fg:#1a5128;
  --db-danger:#b50909;  --db-danger-bg:#f8eded;  --db-danger-fg:#8a0707;
  --db-warning:#c2850c; --db-warning-bg:#faf3e0; --db-warning-fg:#7a5408;
  --db-info:#005ea2;    --db-info-bg:#e7f1f9;    --db-info-fg:#00477a;
  /* TYPE */
  --db-font-sans:'Public Sans','Inter',-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  --db-font-mono:'Roboto Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  /* type scale (rem, 16px base): 3xs .75 / 2xs .8125 / xs .875 / sm .9375 / base 1 /
     md 1.0625 / lg 1.25(H4) / xl 1.5(H3) / 2xl 1.875(H2) / 3xl 2.25(H1) / 4xl 3 / 5xl 3.75 */
  --db-weight-thin:300; --db-weight-normal:400; --db-weight-medium:500;
  --db-weight-semibold:600; --db-weight-bold:700;
  --db-leading-tight:1.15; --db-leading-snug:1.3; --db-leading-normal:1.5; --db-leading-relaxed:1.65;
  --db-tracking-tight:-0.01em; --db-tracking-wide:0.02em; --db-tracking-caps:0.06em; /* eyebrows */
  /* SPACING (8px base): 05 4 / 1 8 / 15 12 / 2 16 / 3 24 / 4 32 / 5 40 / 6 48 / 7 64 / 8 80 (px) */
  /* RADIUS */ --db-radius-sm:4px; --db-radius:8px; --db-radius-lg:12px; --db-radius-pill:999px;
  /* ELEVATION */
  --db-shadow-sm:0 1px 2px rgba(11,31,58,.06); --db-shadow-md:0 4px 10px rgba(11,31,58,.08);
  --db-shadow-lg:0 12px 28px rgba(11,31,58,.12); --db-shadow-focus:0 0 0 3px var(--db-accent-soft);
  /* LAYOUT */ --db-container-max:1280px; --db-header-h:56px; --db-submenu-h:44px;
  /* MOTION */ --db-transition:.18s ease; --db-transition-slow:.3s ease;
}
```

## Component catalog (`.db-*` classes — see `databook-components.css` for rules)

- **Shell / layout:** `db-container`, `db-hero` (+ `db-hero-inner/-copy`), `db-eyebrow` (uppercase
  tracked overline), `db-anchor`, `db-toc`, `db-brand`/`db-brand-mark` (wordmark).
- **Cards:** `db-card` (+ `db-card-body`, `db-card-title`, `is-hoverable`).
- **Tables:** `db-table` (dense, navy heads; the jQuery DataTables skin), `db-table-wrap`
  (h-scroll), `db-stat-grid` + stat tiles.
- **Buttons:** `db-btn` (+ `db-btn-primary`, `db-btn-outline`, `db-btn-ghost`, `db-btn-icon`,
  `db-btn-sm`, `db-btn-lg`).
- **Badges / pills:** `db-badge` (+ `-navy`, `-neutral`, `-success`, `-warning`, `-danger`,
  `-info`), `db-dot` (status dot), `db-filter-pill`, `db-deadline`, `db-money`.
- **Alerts:** `db-alert` (+ `-info/-success/-warning/-danger`, `db-alert-body`, `db-alert-close`).
- **Tabs / nav:** `db-tabs`/`db-tab` (+ `db-tabs-wrap.is-scroll`, dropdown-tab `db-tab-dd`),
  `db-breadcrumb`.
- **Profiles:** `db-profile-header`, `db-avatar` (+ `-sm/-lg`), `dp-meta`/`dp-census` grids.
- **Search / filters:** `db-search`, `db-filter-bar` (horizontal), `db-facets`/`db-facet`
  (faceted sidebar), `db-active-filters`, `db-range`.
- **Lists / jobs:** `db-jobs-grid`, `db-list-item`, `db-panel`, `db-feature-card`.
- **Charts:** `db-chart-card` (+ `db-chart-head/-title/-body/-legend`). ⚠ any Chart.js canvas
  with `maintainAspectRatio:false` MUST sit in a fixed-height `.db-chart-body` wrapper.
- **Maps:** `db-map-control`, `db-map-search` (floating overlay controls over Mapbox).
- **Empty states:** `db-empty` (+ `-icon/-title/-text`).
- **Org chart:** `db-tree` / `db-orgchart`.
- **Analysis (editorial, orange):** `db-analysis-badge/-banner/-menu/-toggle` — only for the
  Digital Services Analysis product.

## Minimal on-brand example

```html
<!-- load order: Bootstrap 5.3.3 CSS (CDN) -> databook-tokens.css -> databook-components.css;
     Public Sans + Roboto Mono from Google Fonts; Bootstrap Icons for bi-* -->
<section class="db-card">
  <div class="db-card-body">
    <div class="db-eyebrow">Procurement</div>
    <h2 class="db-card-title">Recent contracts</h2>
    <p style="color:var(--db-text-muted)">Awarded this quarter</p>
    <span class="db-badge db-badge-success"><span class="db-dot"></span> Active</span>
    <a class="db-btn db-btn-primary" href="#"><i class="bi bi-arrow-right"></i> View all</a>
  </div>
</section>
```

## How to hand this off

- **Same machine:** point the other session at this file
  (`<repo-root>/docs/DATABOOK-STYLE.md`) plus the two CSS files above, and
  have it view a mockup PNG or `https://databook.nyc/styleguide`.
- **Otherwise:** paste this file's contents; for exact component rules also paste
  `databook-components.css`. For the visual, share a screenshot of `/styleguide`.
