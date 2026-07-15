# Theming Databook's design system (sibling brands)

> Phase A of the component-library plan ([COMPONENT-LIBRARY-PLAN.md](COMPONENT-LIBRARY-PLAN.md)).
> Goal: let sibling properties (WeGovNYC, UNNYC) carry **compatible — but not
> identical — branding** by overriding *only* the brand token slots, with zero
> changes to `databook-components.css`.

## How it works

`databook-components.css` is (now) fully token-driven: every brand color is a
`var(--db-*)`, so a brand = a token sheet. Load order:

```
bootstrap 5.3.3  ->  databook-tokens.css  ->  databook-components.css  ->  <brand>-theme.css
```

The `<brand>-theme.css` redeclares `:root { … }` for the brand slots below; the
later declaration wins, re-skinning every `.db-*` component. See the working
proof-of-concept: [`app/public/css/themes/wegov-theme.css`](../app/public/css/themes/wegov-theme.css)
and the live sampler at `app/public/themes/theme-preview.html`
(`…/themes/theme-preview.html` and `?theme=wegov` on any host serving `public/`).

## The contract: what a sibling brand overrides vs inherits

**Override (brand identity):**

| Slot(s) | Role |
|---|---|
| `--db-navy-900 … --db-navy-050`, `--db-primary` | the primary/brand ramp (header, section heads, bands, tints) |
| `--db-link`, `--db-link-hover`, `--db-link-visited` | link colors |
| `--db-accent`, `--db-accent-soft` | functional accent (active underline, focus ring) |
| `--db-brand`, `--db-brand-hover`, `--db-brand-bg`, `--db-brand-wash` | wordmark + editorial "Analysis" surface |
| `--db-on-dark-accent`, `--db-navy-gradient`, `--db-deadline-on-dark` | brand-derived tints used on dark surfaces |
| `--bs-primary*`, `--bs-link-color*` | Bootstrap bridge — repoint at the new primary/link |

**Inherit (shared skeleton — this is what makes brands "compatible"; changing
these breaks family resemblance):**

- Spacing (`--db-space-*`), radius (`--db-radius*`), type ramp + weights +
  tracking (`--db-text-*`, `--db-font-*`, …), elevation (`--db-shadow-*`),
  z-index, motion, layout (`--db-container-max`, header/submenu heights).
- Neutral gray scale (`--db-gray-*`) and semantic state colors
  (`--db-success|danger|warning|info` + their `-bg`/`-fg`/`-border`). Keeping
  status colors shared means "green = good / red = bad" reads the same everywhere.
- `--db-on-dark` / `--db-on-dark-muted` — pure/soft white on dark surfaces.
  Override **only** if the brand uses a light header (then set a dark value).

## Intentionally-literal values

The translucent-white glass fills/borders in `databook-components.css`
(`rgba(255,255,255,0.08…0.30)`) and the inline SVG chevron stroke
(`%23ffffff`) are left as literals on purpose: they are brand-agnostic — white
glass reads correctly on *any* dark header hue — so a sibling brand never needs
to touch them.

## Making a new sibling theme

1. Copy `wegov-theme.css`, rename (`<brand>-theme.css`).
2. Set the **Override** slots above to the brand's palette; leave everything
   else out (it inherits).
3. Load it last (after `databook-components.css`).
4. Verify against `theme-preview.html?theme=<brand>` (or the brand's own pages):
   components re-skin, semantic badges/alerts stay shared, layout unchanged.

Sibling theme sheets should live with their consumer (UNNY/WeGov repos), not
here; `wegov-theme.css` is the committed template/PoC.
