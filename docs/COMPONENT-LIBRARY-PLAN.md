# Databook Component Library — Scoping Plan

> Status (2026-07-09): **All three phases complete.** **Phase A** (theme hardening —
> docs/THEMING.md) and **Phase B** (Blade `<x-db.*>` components — docs/BLADE-COMPONENTS.md,
> live at `/styleguide/components`) shipped to prod. **Phase C shipped**: React library
> **`@wegovnyc/databook-ui`** (repo `github.com/wegovnyc/databook-ui`, sibling checkout
> `../databook-ui`) — `<x-db.*>` twins, vendored CSS as single source of truth (+ `check:css`
> drift guard), tsup ESM/CJS/d.ts build, Storybook, SSR fidelity smoke. **Design-synced** into
> the claude.ai/design project **"Databook Design System"** via the `/design-sync` skill
> (storybook shape): 14 storied components verified against the reference storybook, bundle
> ships Bootstrap 5.3.3 + Public Sans/Roboto Mono via `styles.css`'s `@import` closure so the
> design agent composes real Databook parts that map 1:1 to Blade. Owner: Devin. Remaining is
> v2 composites (profile headers, facet rails, org chart, jobs grid, Analysis surface) — see
> "Explicitly deferred".

## Purpose

**Make it easier to design and build pages for databook.nyc.** Secondary: give sibling
properties (WeGovNYC, UNNYC) **compatible — but not identical — branding**: they share the
design system's structure and token schema while carrying their own brand values.

## Current state (verified)

- The design system is a hand-authored CSS layer — `.db-*` classes over Bootstrap 5.3.3
  (CDN, no build step): `app/public/css/databook-tokens.css` (160 lines of tokens) +
  `app/public/css/databook-components.css` (~743 lines, ~211 classes) +
  `app/public/js/db-charts.js` (Chart.js theming). Living reference: `/styleguide`.
  Portable summary for integrators: `docs/DATABOOK-STYLE.md`.
- **Highly token-driven already:** components.css references `var(--db-*)` **884 times**
  vs **68 hardcoded colors** (nearly all `#fff` / white-alpha on navy surfaces).
- The frontend is **Laravel `^7.29` server-rendered Blade**. Blade component tags
  (`<x-...>`) are supported by the framework but **unused** (0 files; only 8 `sub.*`
  partials). Every new page hand-copies `.db-*` markup from existing pages or `/styleguide`.
- Claude Design's `/design-sync` requires a **compiled React component library**
  (TS types + `dist/` + Storybook or package build). No such library exists.
- UNNY is **Vite + vanilla JS** (not React) — it can consume CSS/tokens, not React.

## The key architectural insight

The three consumers want three different surfaces, but they can all sit on **one source
of truth — the existing CSS**:

| Consumer | Stack | Surface they consume |
|---|---|---|
| databook.nyc (build) | Laravel/Blade, no JS build | **Blade components** emitting `.db-*` markup |
| Claude Design (design) | React runtime | **React library** emitting the same `.db-*` markup |
| WeGov / UNNYC (branding) | Vite/vanilla, anything | **Token schema** — same slots, their values |

**Rule: wrap the CSS, never rebuild it.** Components in either stack emit `db-*` classes
and load the canonical stylesheet. No CSS-in-JS, no Tailwind port, no second styling
implementation — that road guarantees drift from the live Blade app.

"Compatible but not the same" branding is achieved by the token layer, not by sharing
Databook's skin: a sibling brand = the same `databook-components.css` + **its own token
sheet** (its palette/type in the same `--db-*` slots). Databook's exact values stay
Databook's.

## Phases

### Phase A — Theme hardening (small; ~a day)

Make the token layer the complete brand interface.

1. Tokenize the ~68 hardcoded colors in `databook-components.css` — mostly introduce
   `--db-text-on-dark`, `--db-surface-overlay`-type tokens for the white/white-alpha
   values on navy surfaces, then sweep.
2. Document the **token schema** (the contract a sibling brand implements): every slot,
   its role, and which are "brand" (palette, type, wordmark) vs "structural" (spacing,
   radius, z-index — siblings should generally keep these for compatibility).
3. Ship a proof-of-concept `wegov-theme.css` (or `unny-theme.css`): a token sheet with a
   different palette applied to `/styleguide`, demonstrating compatible-not-same.
4. Acceptance: `/styleguide` renders correctly with (a) the Databook token sheet and
   (b) the PoC sibling sheet swapped in, with zero component-CSS edits.

Deliverable value: unblocks UNNYC/WeGov branding immediately, independent of B/C.

### Phase B — Blade component layer (moderate; days)

The direct "build databook pages faster" win.

1. Create `app/resources/views/components/db/` with the v1 inventory (below) as
   anonymous Blade components: `<x-db.card>`, `<x-db.stat-grid>`, `<x-db.tabs>`, etc.
   Each emits exactly the canonical `.db-*` markup pattern (crib from `/styleguide`).
2. Props mirror the CSS variants (`variant="primary|outline|ghost"`, `size="sm|lg"`,
   badge tones, etc.). Slots for content. **Data hooks pass through** — components must
   accept arbitrary attributes/ids so DataTables/`fapireq()`/`gs_*` hooks keep working.
3. Adoption is incremental: new pages use components; existing pages migrate
   opportunistically when touched. No big-bang rewrite.
4. Rebuild `/styleguide` sections onto the components as they land — the styleguide
   becomes both the visual reference and the component usage reference.
5. Acceptance: one real new-or-touched page built entirely from `<x-db.*>` components,
   pixel-equal to the handwritten version; view:cache compiles clean.

Laravel 7 constraints to respect: no `@class` directive (8.x+); anonymous components
and `$attributes` merging ARE available in 7.x.

### Phase C — React library for Claude Design (larger; ~1–2 weeks)

The "design databook pages faster" win.

1. New repo (suggested: `wegovnyc/databook-ui`): TypeScript + Vite/tsup build to
   `dist/`, **Storybook** for previews, one React component per v1 inventory entry.
2. Components import the canonical CSS (see open decision 1) and render the same
   `.db-*` markup as their Blade twins — same names, same variant props, so a Claude
   Design mockup maps 1:1 onto Blade components at implementation time.
3. Run `/design-sync` to upload it to a Claude Design project; from then on the design
   agent composes real Databook parts, and handoffs name components instead of
   describing markup (fixes the spec-vs-reality mismatches from the 2026-06 passes).
4. Acceptance: `/design-sync` completes with all v1 components verified; a test design
   produced in Claude Design uses `db-*` components and translates to Blade 1:1.

### Explicitly deferred

- **Web Components** for UNNY — CSS classes + tokens cover the need today.
- Publishing an npm package of Databook's skin for third parties (superseded by the
  compatible-branding token approach).
- v2 composites: profile headers, facet rails, map overlay controls, org chart, jobs
  grid, analysis (orange) components.

## v1 component inventory (~12)

Shared inventory and naming across Blade (Phase B) and React (Phase C):

| Component | Canonical classes | Variants/props |
|---|---|---|
| Button | `db-btn` | `primary / outline / ghost / icon`, `sm / lg` |
| Card | `db-card`, `db-card-body`, `db-card-title` | `hoverable` |
| Badge | `db-badge`, `db-dot` | `navy / neutral / success / warning / danger / info`, `dot` |
| StatGrid / StatTile | `db-stat-grid`, `db-stat`, `db-stat-label`, `db-stat-value` | `accent` |
| Table | `db-table`, `db-table-wrap` | (skin; DataTables passthrough) |
| Tabs | `db-tabs`, `db-tab`, `db-tabs-wrap`, `db-tab-dd` | `scroll`, dropdown tab |
| Alert | `db-alert`, `db-alert-body`, `db-alert-close` | `info / success / warning / danger` |
| Eyebrow | `db-eyebrow` | — |
| Hero | `db-hero`, `db-hero-inner`, `db-hero-copy` | — |
| SearchInput | `db-search` | — |
| EmptyState | `db-empty`, `db-empty-icon/-title/-text` | — |
| Icon | Bootstrap Icons `bi-*` | name |
| ChartCard | `db-chart-card`, `db-chart-head/-title/-body` | (fixed-height body — see gotcha) |

## Open decisions

1. **Where the canonical CSS lives.** Default for v1: **the databook repo stays the
   source**; the React package vendors/syncs the two CSS files at build time (a copy
   step + a checksum check in CI to catch drift). Alternative (later): invert ownership
   — the UI package publishes the CSS and the Blade app loads the published file.
   Deferred until C proves out; inverting touches the prod deploy for little v1 gain.
2. **Blade component style**: anonymous components (view-only, fastest) vs class-based
   (logic, slots API). Default: anonymous; promote individual components to class-based
   only when they need logic.
3. **React repo location**: separate repo (clean for /design-sync + npm later) vs a
   `ui/` workspace in the databook repo. Default: separate repo.
4. **Sibling theme ownership**: does the WeGov/UNNY token sheet live in this repo
   (examples/) or in each consumer's repo? Default: PoC lives here; real sheets live
   with their consumers.

## Risks & gotchas (carry-overs from the design-system work)

- **Drift is the failure mode.** Every layer must emit/load the same CSS. CI check in
  Phase C: hash the vendored CSS against the databook repo's copy.
- `.db-*` are **additive skins** — preserve data hooks (`.prj_stat`, `gs_*`, DataTable
  element IDs + `dom`/colVis, `fapireq()` targets, form `name`s) in any componentization.
- **Bootstrap Icons only** (`bi-*`); Font Awesome is not loaded and renders nothing.
- Money renders **navy**; green is for status only; orange (`--db-brand`) is reserved
  for the wordmark + Analysis surface.
- Chart.js: `maintainAspectRatio:false` canvases MUST sit in a fixed-height
  `.db-chart-body` wrapper (page grows unboundedly otherwise).
- Laravel 7: no `@class` directive; edit `app/public/css/*` (live), never
  `resources/sass` (dead).
- The `*A`-view orphan trap: verify the controller's `return view()` before editing
  any `*A` Blade file.

## Suggested sequence & effort

A (≈1 day) → B (≈3–5 days, incremental adoption ongoing) → C (≈1–2 weeks incl.
/design-sync verification). Each phase ships standalone value; stop-points after each
are safe.
