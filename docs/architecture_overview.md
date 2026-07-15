# Databook2 Architecture Overview

## System Components

The Databook2 application is a microservices-based architecture composed of two primary services and supporting infrastructure, all containerized using Docker.

### 1. Frontend Service (`databook-app`)
-   **Technology:** Laravel (PHP)
-   **Directory:** `app`
-   **Role:** Handles HTTP requests, renders Blade templates (UI), and serves the public-facing application.
-   **Data Access:**
    -   Reads static JSON files (e.g., `dashboard_data.json`) for high-performance page loads.
    -   Connects to MySQL for application data.

### 2. Backend Service (`databook-api`)
-   **Technology:** Python (FastAPI / Scripts)
-   **Directory:** `api`
-   **Role:**
    -   Runs data generation scripts (e.g., `generate_dashboard.py`).
    -   Processes data from CSVs and databases.
    -   Serves API endpoints (FastAPI).
-   **Data Access:**
    -   Reads raw data files (`titles_analysis.csv`, `salaries.csv`).
    -   Connects to Postgres for data storage.

### 3. Infrastructure
-   **Nginx (`databook-nginx`):** Reverse proxy handling routing between the frontend and backend services.
-   **Databases:**
    -   **MySQL (`databook-mysql`):** Primary store for the Laravel application.
    -   **Postgres (`databook-postgres`):** Data store for the Python backend.
    -   **Redis (`databook-redis`):** Caching layer.

## Connector Pattern
The system uses a **Shared Volume Pattern** for data exchange.
-   **Generation:** Python scripts in `databook-api` write JSON files to a shared volume mapped to `/app/shared`.
-   **Consumption:** Laravel frontend reads these JSON files from the same shared volume mapped to `/var/shared`.
-   **Infrastructure:** Defined in `docker-compose.yml` as `shared_data`.

## Storage
-   **Databases:** Persistent volumes for MySQL, Postgres, Redis.
-   **Shared Data:** `shared_data` volume for exchanging files between `api` and `app` containers without manual copying.
