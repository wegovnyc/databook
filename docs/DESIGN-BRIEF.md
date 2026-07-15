# Databook.nyc — Frontend Design Brief

> **Audience:** Claude Design (or any designer) tasked with producing a unified visual
> system + per-page-family mockups for Databook.nyc.
> **Author:** Claude Code (audit of the live codebase, 2026-06-15).
> **Goal of the project:** unify and sharpen the frontend without rewriting the stack
> or breaking the data layer.

This document is everything Design needs to start. It describes **what exists today**
(stack, tokens, components, page families, inconsistencies, constraints) so Design can
propose a target system grounded in reality rather than guesswork. Claude Code will
implement whatever Design specs, in the real codebase, behind a screenshot-regression net.

> ## Decisions already made (by the project owner)
> 1. **Brand basis = the live `style.css` tokens** (navy `#162E51` primary, Inter-first, the
>    `--db-*` block in §6.1). The deployed NYC-gov-adjacent look is canonical; where the
>    `/styleguide` page disagrees (Bootstrap `#007bff` + Public Sans), **the live tokens win** —
>    the styleguide page should be brought *into line with the system*, not the reverse.
> 2. **Scope = "Unify + consolidate."** Beyond visual unification (tokens + component restyle +
>    eradicating inline styles), Design should also: collapse the **3 divergent profile headers**
>    (`sub/orgheader`/`distheader`/`titleheader`) into **one** parameterized design; spec a
>    **single templated treatment** for DataTables and Chart.js; and identify shared partials to
>    extract. Information architecture / navigation structure stays as-is for now (not in scope).
> 3. **Deliver a *lightweight* design system, layered on Bootstrap 5 — not a new framework.**
>    Express it as a **token + component layer that extends the existing `--db-*` custom
>    properties** and works *with* Bootstrap 5's grid/utilities/components. Do **not** introduce
>    a competing CSS framework or swap Bootstrap out. You **may use USWDS (the U.S. Web Design
>    System) as a reference** for conventions — its spacing units, type scale, and the
>    Public Sans pairing — since the site already leans that way (Public Sans is the USWDS
>    typeface; the navy palette is gov-adjacent). Borrow its *decisions*, not its codebase.
> 4. **This pass = clean up & standardize the *existing* design only.** Rationalize what's
>    here into a coherent system; preserve the current structure, content, and IA. Bolder
>    moves — a system-wide visual refresh, new components, and new features — are explicitly
>    **welcome in future passes**, just not this one. Design the foundation now so those later
>    changes are cheap.

---

## 0. How to use this brief

1. **Read §1–§3** to understand the medium you're designing for (server-rendered Blade +
   Bootstrap 5, not React). This constrains what's cheap vs. expensive to change.
2. **Open the live pages in §5** — that's the real current-state. Capture your own
   screenshots there; the codebase has no running preview in this environment and the
   live site (with real data) is the truest reference.
3. **Use §6 (existing tokens) and §7 (component inventory)** as the raw material to
   rationalize into a system.
4. **Respect §9 (constraints).** Several things look like free design choices but are
   load-bearing (data fallbacks, jQuery/DataTables, the nonprofit disclaimer).
5. **Produce the deliverables in §10.**

---

## 1. What the frontend actually is

- **Laravel 7 server-rendered Blade app.** PHP 7.2/8. No React/Next, no SPA. Pages are
  HTML assembled server-side from `.blade.php` templates. (The root `CLAUDE.md` mention of
  "React/Next, SimStyle" is inaccurate — ignore it.)
- **84 Blade templates, ~27,700 lines** in `app/resources/views/`.
- **CSS:** Bootstrap 5.3.3 (CDN) is the base framework, layered with a hand-written
  `app/public/css/style.css` (2,361 lines — **this already contains a design-token block**),
  plus `responsive.css` and `loader.css`. Bootstrap **Icons** 1.11.3 for iconography.
- **JS:** jQuery 3.5.1 + DataTables 1.10.23 (+ buttons/colVis/responsive extensions) +
  Chart.js 3.8.0 + Mapbox GL 2.4.1 + Twitter Typeahead + Bootstrap 5 bundle. Hand-written
  `app/public/js/script.js` (710 lines) holds the API wrapper (`fapireq`) and utilities.
- **Fonts:** Google Fonts — **Inter** and **Public Sans** (both loaded; see §6.3 for the
  ambiguity about which is canonical).

### 1.1 The build-pipeline footgun (important for implementation)
The repo has laravel-mix/webpack wired up, **but it is vestigial**: `resources/sass/app.scss`
is empty, `resources/js/app.js` is a one-line stub, and the compiled `public/js/app.js`
(610 KB) and `public/css/app.css` (0 bytes) are stale/empty. **The live styling is the
hand-edited `public/css/style.css`; the live behavior is `public/js/script.js`.** Any CSS
change must go into `public/css/style.css` (or a new file linked in the layout), *not* the
"intended" `resources/sass/app.scss`, which compiles to nothing. Design doesn't need to act
on this, but it explains why the current CSS is one big flat file rather than componentized.

---

## 2. The numbers (why "unify" is non-trivial)

| Metric | Count |
|---|---|
| Blade templates | 84 |
| Total Blade lines | ~27,700 |
| Inline `style="..."` attributes across views | **585** |
| Views containing `<style>` blocks | **37** |
| Views containing inline `<script>` blocks | **62** |
| Hand-written CSS (`style.css`) | 2,361 lines |
| Distinct hex colors in `style.css` | ~40 |
| Distinct hex colors in inline view styles | ~60 (diverging from the palette) |

The inline styles + per-view `<style>` blocks are the central obstacle to unification:
they locally override the shared CSS, so a global change is fought page-by-page. A unified
system requires moving these into token-driven classes.

---

## 3. Top inline-style hotspots (where the visual entropy concentrates)

These views carry the most inline `style=` attributes — the highest-value targets for
standardization, and the pages whose current look is least controlled by the shared CSS:

| Inline `style=` count | View | Page family |
|---|---|---|
| 60 | `root.blade.php` | **Home page** |
| 34 | `titles_overview.blade.php` | Jobs dashboard |
| 23 | `organization.blade.php` | Org profile (also 4 `<style>` blocks, 21 `<script>`) |
| 21 | `orgprojectA.blade.php` | Project profile (legacy/orphan — see §8) |
| 21 | `budgetLineA.blade.php` | Budget line |
| 19 | `projects.blade.php` | Projects map |
| 19 | `about/project.blade.php` | About |
| 18 | `distsection.blade.php` | District section |
| 17 | `orgproject.blade.php` | Project profile (live) |
| 17 | `categoryA.blade.php` | Project category |
| 16 | `procurement/org_procurement.blade.php` | Procurement |
| 15 | `sub/menubar.blade.php` | **Global nav (every page)** |

`organization.blade.php` is the single most complex page (1,176 lines, 4 `<style>` blocks,
21 `<script>` blocks, 23 inline styles) — treat the **org profile** as the canonical
"hard" page family to design first.

---

## 4. Page-family taxonomy

The 84 views collapse into these families. Designing one canonical treatment per family
(then applying it to the members) is the efficient path.

| Family | Representative views | Notes |
|---|---|---|
| **Home / landing** | `root.blade.php` | Highest inline-style count; sets first impression |
| **Organizations** | `orgsDirectory`, `orgsAgencies`, `orgsAll`, `orgsChart`, `organization`, `orgsection`, `org_procurement_section` | Directory + profile + org-chart viz |
| **Org profile sub-views** | `sub/orgheader`, `orgCharts/{headcount,headcount-actuals,payroll,positions}` | Profile header + Chart.js tabs |
| **People** | `people`, `peoplesearchresults`, `person` | DataTables-heavy search |
| **Titles / Jobs** | `titles`, `titlesection`, `title_stats`, `titles_overview`, `titleexams`, `titledescsection`, `jobs`, `jobs_exams`, `sub/titleheader` | Charts + tables + exam data |
| **Projects / Capital** | `projects` (map), `capital`, `prjTypesA`, `prjTypeA`, `categoriesA`, `categoryA`, `budgetLinesA`, `budgetLineA`, `prjCommitmentsA`, `mProjects`, `mProject` | Map UI + directory tables + profiles |
| **Project profile** | `orgproject` (live), `pureproject`, `orgprojectsection` | Metadata + budget/schedule charts |
| **Districts / Schools** | `districts`, `distsection`, `distprojectsection`, `schools`, `schoolSection`, `sub/distheader`, `sub/schoolprofile` | Map + section navigation |
| **Notices / Auctions / Council** | `notices`, `noticessection`, `auctions`, `council`, `icalevents`, `rss` | Card lists + feeds (RSS/iCal) |
| **Procurement** | `procurement/{index,vendors,vendor_profile,agencies,contracts,contract_profile,solicitations,solicitation_profile,transactions,transactions_search,data_sources,digital-reform,org_procurement}` + `partials/{source_badge,transactions_table}` | **Most internally consistent** family — already uses partials; good reference for "what good looks like" |
| **Content / static** | `about`, `about/project`, `blog`, `article`, `mcp`, `styleguide`, `sitemap` | Editorial pages |
| **Admin** | `admin/{index,data_health,datatables,ingestion_log}` | Internal-facing |

---

## 5. Live URLs to view (capture current-state here)

Base: `https://databook.nyc`. Navigate to entity profiles from the directory pages
(IDs change; don't hardcode). Suggested capture set, one per family:

- **Home:** `/`
- **Existing styleguide (READ FIRST):** `/styleguide` — the current, half-built design reference
- **Org directory:** `/organizations` → **Org agencies:** `/organizations/agencies` → **Org chart:** `/organizations/chart`
- **Org profile:** pick an org from `/organizations` (URL form `/o/{id}-{slug}`) — *the hardest page; design this carefully*
- **People:** `/people` ; **Person:** open a result
- **Titles:** `/titles` ; **Title profile:** open a result (`/t/{id}`)
- **Jobs:** `/jobs` ; **Jobs exams:** `/jobs-exams` ; **Jobs dashboard:** `/jobs-dashboard`
- **Projects map:** `/projects` ; **Capital:** `/projects/capital` ; **Types:** `/projects/types` ; **Categories:** `/projects/categories` ; **Budget lines:** `/projects/budget-lines` ; **Commitments:** `/projects/commitments`
- **Project profile:** open a project from any list (`/p/{prjId}`)
- **Districts:** `/districts` ; **Schools:** `/schools`
- **Notices:** `/notices` ; **Auctions:** `/auctions` ; **Council:** `/council`
- **Procurement:** `/procurement`, `/procurement/vendors`, `/procurement/contracts`, `/procurement/solicitations`, `/procurement/transactions`, `/procurement/agencies`
- **About:** `/about` ; **Blog:** `/blog` ; **MCP:** `/mcp`

> Note: there is no running local preview in this environment, and a local boot would have
> an empty database. Use the live site — it has real data and is the accurate reference.

---

## 6. The existing design system (raw material to rationalize)

### 6.1 Design tokens (verbatim from `public/css/style.css`)
A token block already exists — Design should *evolve* this into a full system, not start blank:

```css
:root {
  /* Brand colors */
  --db-primary: #162E51;      /* dark navy — NYC-gov-ish */
  --db-link: #005EA2;
  --db-link-hover: #004080;

  /* Light mode colors */
  --db-bg: #ffffff;
  --db-bg-secondary: #f0f0f0;
  --db-bg-tertiary: #f9f9f9;
  --db-text: #171717;
  --db-text-muted: #757575;
  --db-border: #dfe1e2;

  /* Shadows & Effects */
  --db-shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --db-shadow-md: 0 4px 6px rgba(0,0,0,0.07);
  --db-shadow-lg: 0 10px 25px rgba(0,0,0,0.1);
  --db-radius: 8px;
  --db-radius-lg: 12px;

  /* Transitions */
  --db-transition: 0.2s ease;
}
```

**Gaps to fill:** no spacing scale, no type scale, no semantic state colors
(success/danger/warning are pulled ad-hoc from Bootstrap), no dark-mode (tokens are named
"Light mode" implying one was intended).

### 6.2 Color reality vs. the tokens
The *defined* palette is small and coherent (navy `#162E51`, link blue `#005EA2`, neutrals).
But inline styles have introduced **~60 additional one-off hex values** that drift from it.
Most-used colors:

- **In `style.css` (intended):** `#162E51` (navy), `#005EA2` (link), `#171717` (text),
  `#757575` (muted), `#f0f0f0`/`#f9f9f9` (bg), `#dfe1e2` (border), `#4299e1` (a secondary blue used in submenus).
- **In inline styles (drift to reconcile):** `#6c757d`, `#cccccc`, `#444`, `#53777a`,
  `#2563eb`, `#0d6efd`, `#28a745`, `#2e7d32`, `#1f5673`, `#759fbc`, `#90c3c8`, and many more —
  a mix of Bootstrap defaults and arbitrary values. **These are the palette's main inconsistency.**

The **existing `/styleguide` page** documents a *different* set again (Bootstrap's
`#007bff` primary, plus the custom `#162E51`) — i.e. the styleguide and the real CSS tokens
already disagree. Design should pick one source of truth.

### 6.3 Typography
- Two families loaded: **Inter** (300–700) and **Public Sans** (200–800).
- `style.css` body uses `'Inter', 'Public Sans', -apple-system, …`; the `/styleguide` page
  text claims **"Public Sans"** is the font family. **Pick one** as primary and define a scale.
- The styleguide states a heading scale (H1 36px → H6 16px) — a starting point, not enforced.

### 6.4 Custom component classes already in `style.css`
These exist and are referenced by views — Design should decide which to keep/restyle/retire:
`.submenu-bar`, `.submenu-nav`, `.type-label`, `.tag-label`, `.outline_btn`, `.org-header`,
`.org_detailheader`, `.org_detailtitle`, `.submenu_org`, `.stats-table`, `.chartCard`,
`.map-filter-panel`, `.map-filter-toggle-btn`, `.icon_orgsocial`, `.share_icon_container`,
`.orgchart .node…`, `.twitter-typeahead`/`.tt-menu` (autocomplete), `.loading`.

---

## 7. Component inventory (what the system must standardize)

These recurring patterns appear across the views with **divergent implementations** — the
core of the unification work. Each needs a single canonical spec from Design.

1. **Global nav bar** — `sub/menubar.blade.php`. Bootstrap navbar + custom `.CustomDatabookNav`,
   brand "DATABOOK.NYC", 8–9 top items.
2. **Submenu bars** — also in `sub/menubar.blade.php`. **11 different hardcoded submenu
   structures** (Projects, Organizations, Notices, Procurement, About…), no reuse. Styled via
   `.submenu-bar`/`.submenu-nav` (`#1a3a5c` bg, `#4299e1` accent).
3. **Breadcrumbs** — Bootstrap `.breadcrumb`; shown inconsistently (explicitly suppressed on
   many routes).
4. **Profile headers** — **3 divergent variants** for the same concept: `sub/orgheader`,
   `sub/distheader`, `sub/titleheader` (the title header also embeds Chart.js inline). Logo
   presence flips the layout between 2-col and full-width. Prime consolidation target.
5. **Stat / metric cards** — `projects`, `organization`, `styleguide`. API-hydrated numbers
   via JS classes (`.prj_stat`, `.gs_thousandscomma`, `.gs_finshort`). Layouts differ
   (single-value vs. multi-row tables).
6. **Data tables (DataTables.js)** — 6+ views (`peoplesearchresults`, `prjTypesA`,
   `noticessection`, `organization`, `pureproject`, `schools`). Each has bespoke AJAX/filter/
   column config; filter placement inconsistent. Heaviest interactive surface.
7. **Search + autocomplete** — `peoplesearchresults`, `schools`, `projects`. Typeahead only in
   geo contexts; plain inputs elsewhere. No unified search component.
8. **Filter controls** — three idioms: horizontal form (procurement), dark sidebar
   `.map-filter-panel` (projects map), inline table-cell dropdowns (notices).
9. **Badges / labels / tags** — Bootstrap `.badge` mixed with custom `.type-label`
   (navy pill used as both button and label) and `.tag-label` (comma-separated muted tags).
   Semantics blurred.
10. **Cards / list items** — `notices` (compact horizontal), `blog` (rich w/ image + inline JS
    hover), `organization` (nested table). Hover effects split between CSS and inline JS.
11. **Pagination** — Bootstrap `.pagination-sm`, fairly consistent (procurement). A
    `.pagination-btn` custom class is defined but unused.
12. **Loaders** — 4 patterns: full-page `.loading`, scoped map overlay (`@keyframes mapSpin`),
    Bootstrap `.spinner-border`, ad-hoc text. No single pattern.
13. **Charts (Chart.js)** — `titleheader`, `orgCharts/*`, `orgproject`, `budgetLineA`. Config
    duplicated per view (`responsive:false` everywhere), custom tooltips/legends. No template.
14. **Tabs / section nav** — Bootstrap pills (`data-bs-toggle="pill"`) in `titleheader`,
    `orgCharts/*`. Reasonably consistent.
15. **Buttons** — mix of Bootstrap `.btn*`, custom `.outline_btn`, and `.type-label` (a
    span/div styled as a button — non-semantic). Needs rationalizing into a button system.
16. **Profile metadata (key/value)** — `orgproject` (flex rows), `schools` (tables). No shared
    component.
17. **Share / feed links** — `orgheader`, `notices`: icon + Bootstrap popover ("copied!") +
    hidden textarea + `copyLinkM()` handler. Consistent pattern, could be a partial.
18. **Footer + newsletter** — in `layout.blade.php`; consistent (single source). Newsletter
    signup posts to `subscribe_newsletter()`.
19. **Org chart viz** — `orgsChart` + `.orgchart .node…` (heavy per-unit custom CSS), separate
    library. Specialized.
20. **Map UI** — `projects` (Mapbox GL): `.map-filter-panel`, `.map-filter-toggle-btn`,
    popup styling. Well-isolated; specialized.

> **Reference family:** the `procurement/` views already use shared partials
> (`partials/source_badge`, `partials/transactions_table`) and a consistent filter form —
> this is the closest thing to "done right" in the codebase and a good north star for structure.

---

## 8. Dead code / duplication map (so Design doesn't design orphans)

Several views are **legacy forks not reachable by any live route** — do not spend design
effort on them; they should be deleted during implementation. *(Verified against
`routes/web.php` and the controllers' `return view()` calls.)*

| View | Status | Canonical sibling |
|---|---|---|
| `capital.blade.php` | **LIVE** (`/projects/capital`) | — |
| `capitalA.blade.php` | **ORPHAN** (`main_a()` unrouted) | superseded by `capital` |
| `projects.blade.php` | **LIVE** (`/projects`, map UI) | — |
| `projectsA.blade.php` | **ORPHAN** (`projects_a()` unrouted, old table UI) | superseded by `projects` |
| `orgproject.blade.php` | **LIVE** (`/p/{prjId}`, 2024 design) | — |
| `orgprojectA.blade.php` | **ORPHAN** (`project_a()` unrouted, pre-2024, self-deprecating banner) | superseded by `orgproject` |
| `prjTypesA`, `prjTypeA`, `categoriesA`, `categoryA`, `budgetLinesA`, `budgetLineA`, `prjCommitmentsA` | **LIVE** | the "A" suffix is historical; these are the *only* version — treat as canonical |

**Implication for Design:** the `*A` suffix is **not** a reliable signal of "old." Three
`*A`-style files are dead (`capitalA`, `projectsA`, `orgprojectA`), but the project
directory/profile pages ending in `A` (`prjTypesA`, `budgetLineA`, etc.) are the **live,
canonical** pages. Design the live ones; ignore the three orphans.

---

## 9. Constraints Design must respect

1. **It's server-rendered Blade, not a component framework.** "Components" will be implemented
   as Blade partials/`@include`s and CSS classes. Designs should map to reusable partials and
   token-driven utility classes — not React components or build-time theming.
2. **Bootstrap 5 is the substrate.** Working *with* Bootstrap's grid/utilities/components is
   far cheaper than replacing it. Prefer restyling Bootstrap via tokens over a from-scratch
   CSS framework.
3. **Don't break the data layer.** Views bind to specific controller/FastAPI data shapes and
   JS hydration hooks (e.g. `.prj_stat`, `#summary_headcount`, `fapireq()` AJAX, DataTables
   IDs like `#peopleTable`). Visual redesigns must preserve these IDs/classes or coordinate
   their renaming. *A page can return HTTP 200 with its chrome intact while its data layer is
   silently broken* — visual correctness ≠ working.
4. **Preserve resilient fallbacks.** The app deliberately shows "Title + warning badge" when an
   ID/record is missing. Keep a designed empty/error/missing state — don't assume data is
   always present.
5. **jQuery + DataTables coupling.** Table interactivity (sort/search/colvis/detail-rows)
   depends on jQuery/DataTables init in inline scripts. A "sharper" table design must keep
   these working or explicitly re-spec them.
6. **The nonprofit disclaimer bar** (top of `layout.blade.php`, dismissible) and the
   **WeGov/Sarapis footer + CC-license badges** are required brand/legal elements — keep them.
7. **Icons = Bootstrap Icons only.** Bootstrap Icons 1.11.3 is loaded in the layout and used
   (`.bi-*`) across 42 views — this is canonical. **Do not introduce Font Awesome** (avoid
   double-loading). Note a latent bug: `titles_overview.blade.php` (Jobs Dashboard) uses
   ~20 `fas fa-*` Font-Awesome classes with no FA stylesheet loaded, so those icons are
   currently broken — Code will convert them to `.bi-*` during implementation.
8. **Accessibility & gov-data audience.** This is civic data used by journalists, researchers,
   and the public — favor clarity, legibility, scannable tables, strong contrast, and
   reasonable a11y (the navy `#162E51`/white pairing reads as deliberately NYC-gov-adjacent).
9. **Performance.** Everything loads from CDNs in `<head>` (jQuery, DataTables, Bootstrap,
   Mapbox, fonts). Adding heavy assets has a real cost; prefer the existing libraries.

---

## 10. Requested deliverables from Design

**Format:** deliver **both** code-ready artifacts (CSS custom properties + written component
specs) **and** visual mockups, weighted equally — the mockups for sign-off, the tokens/specs
so Code can implement without re-deriving them from images.

**Ambition for this pass: "consistent & clean."** The goal is sameness and removed drift —
one coherent look applied everywhere, no surprises. This is *not* a glow-up or redesign;
hold bolder polish and new ideas for future passes (per decision #4).

**Pilot first:** start with the **global shell** — `layout.blade.php` header/nav, the
submenu bars (`sub/menubar.blade.php`), footer, and the nonprofit disclaimer bar. It appears
on every page, is the fastest visible win, and carries the least data-layer risk. Deliver the
shell mockup + its tokens/specs first; the rest of the families can follow once the shell is
validated.

To hand back to Claude Code for implementation:

1. **A consolidated token system** — color palette (reconciling §6.1/§6.2 drift into one
   scale), type scale + chosen primary font (§6.3), spacing scale, radius/shadow/elevation,
   semantic state colors. Expressed as CSS custom properties (extending the existing `--db-*`).
2. **A component spec sheet** for the §7 inventory — canonical visual treatment for: nav +
   submenu, profile header (one design that covers org/district/title), stat card, data table,
   search, filter panel, badges/tags, buttons, cards, pagination, loader, tabs, metadata
   key/value, charts. Note states (hover/active/disabled/empty/error).
3. **Per-family page mockups** — at minimum: Home (`root`), Org profile (`organization` — the
   hard one), a directory/table page (e.g. `procurement/contracts` or `people`), a profile
   page (project `orgproject` or `titlesection`), and the Projects map (`projects`). These
   anchor the rest of each family.
4. **A redlined treatment of the global shell** — `layout.blade.php` header/nav/footer +
   disclaimer bar — since it appears on every page and is the fastest unification win.
5. **Migration notes / priorities** — if helpful, which families to do first and any
   intentional behavior changes (so Code can flag data-contract impacts).

---

## 11. Implementation context (FYI — Claude Code owns this)

- Edits land in `app/public/css/style.css` (+ possibly a new linked stylesheet) and Blade
  views/partials under `app/resources/views/`. The webpack pipeline is not used (§1.1).
- Regression safety: there's a Playwright suite (`app/e2e`, `playwright.config.js`) and a
  read-only `scripts/prod-smoke.sh`; Code will baseline screenshots across the page families
  before/after each change.
- Deploy is a manual `git pull && docker compose up -d --build` on the prod CPX41; no staging
  box. So changes ship behind CI + screenshot diffs, family-by-family.

---

*Generated by Claude Code as input for Claude Design. Counts and mappings verified against the
codebase at commit-time; the live site is the visual source of truth.*
