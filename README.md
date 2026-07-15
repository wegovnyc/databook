# Databook

**An open data platform for New York City government** — agencies, people, jobs,
capital projects, procurement, budgets, and City Record notices, unified into one
navigable, cross-linked interface.

🌐 **Live site:** [databook.nyc](https://databook.nyc) · **Public API:** [api.databook.nyc/docs](https://api.databook.nyc/docs)

Databook is a nonprofit project of [WeGov.NYC](https://wegov.nyc). It normalizes
dozens of NYC open datasets into a common model and layers on things the official
sources don't provide: a notice ↔ procurement crosswalk, a normalized cross-agency
org model, actual-spending analysis over CheckbookNYC, and a public API + MCP server.

> **Status: source-visible.** This repository is published so the work is
> inspectable and reusable. We're not actively soliciting pull requests yet —
> issues and questions are welcome (see below). A fuller contribution guide will
> follow.

## What's in here

This is the main application monorepo. Two Docker services plus supporting infra:

| Service | Tech | Directory | Role |
|---------|------|-----------|------|
| `databook-app` | Laravel 7 + Blade + Bootstrap 5.3 (server-rendered, no build step) | [`app/`](app/) | Public web interface |
| `databook-api` | FastAPI + Postgres + DuckDB-over-Parquet | [`api/`](api/) | JSON API + data-generation scripts |
| `databook-nginx` | Nginx | [`nginx/`](nginx/) | Reverse proxy |
| Postgres / MySQL / Redis | — | — | Storage + cache |

The frontend is **server-rendered Blade** hydrated client-side via jQuery/DataTables/
Mapbox — **not** React. It runs on a `db-*` design-token + component layer over
Bootstrap; the living reference is at [`/styleguide`](https://databook.nyc/styleguide).

Some parts of the platform live in separate repositories and are **not yet open**
(housing/ACRIS API, the map tiler, the CSV normalizer, the React component library,
the newsletter generator). The application in this repo runs standalone without them.

## Architecture

See [`docs/architecture_overview.md`](docs/architecture_overview.md) and
[`docs/data_pipeline.md`](docs/data_pipeline.md). In brief:

- **Postgres** holds relational data (contracts, solicitations, vendors, people,
  titles, schools, capital projects, City Record notices).
- **DuckDB over a Parquet lake** powers the high-volume OCE spending / budget /
  revenue domains (sourced from CheckbookNYC).
- The frontend calls the API via a thin `DatabookAPI` client; heavy dashboard
  widgets lazy-load client-side.

## Quick start (local)

Requires Docker + Docker Compose.

```bash
git clone https://github.com/wegovnyc/databook.git
cd databook
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
docker exec databook-app php artisan config:clear   # image bakes a cached config
```

- **Frontend:** http://localhost:8580
- **API docs:** http://localhost:8581/docs
- Postgres `:15432` · MySQL `:13306` · Redis `:16379`

The database tables are created by the import pipeline (there are no migrations for
the data tables), so a fresh Postgres starts **empty** — the app chrome renders but
data-backed pages are sparse until you load data. Copy `app/.env.example` →
`app/.env` and `.env.example` → `.env` and fill in values as needed. See
[`docs/`](docs/) for the ingest and pipeline details.

> **Note on data:** the large OCE spending/budget/revenue domains read a DuckDB
> Parquet lake that is not bundled here. Without it, those specific pages report
> "not yet available" and the rest of the app works normally.

## Configuration

All secrets and environment-specific settings come from environment variables —
see `.env.example` and `app/.env.example`. Nothing sensitive is committed; you
supply your own database credentials, API keys (Mapbox, Carto, Gemini, etc.), and
data-lake paths.

## Contributing & contact

- **Bugs / ideas:** open a GitHub issue.
- **Security:** please report privately — see [`SECURITY.md`](SECURITY.md).
- **General:** [wegov.nyc](https://wegov.nyc)

## License

[MIT](LICENSE) © WeGov.NYC. NYC open datasets surfaced by Databook remain subject
to their respective source terms.
