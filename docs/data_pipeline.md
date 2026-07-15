# Data Pipeline: Title Dashboard

This document details the data flow for the "Civil Service Titles" dashboard (`/titles` page).

## Data Flow

1.  **Source Data**:
    -   `titles_analysis.csv`: Analyzing title metadata.
    -   `api/salaries.csv`: Salary ranges for title codes.

2.  **Processing**:
    -   **Script:** `api/generate_dashboard.py`
    -   **Execution:** Runs within the `databook-api` Python container.
    -   **Logic:**
        -   Merges `titles_analysis.csv` and `salaries.csv` on `Title Code`.
        -   Calculates aggregate statistics (counts, age, etc.).
        -   Generates lists for "Popular Titles", "Oldest Titles", etc.

3.  **Output**:
    -   **File:** `dashboard_data.json`
    -   **Location (Container):** `/app/shared/dashboard_data.json` (inside `databook-api`).
    -   **Mechanism:** Written to the `shared_data` Docker volume.

4.  **Consumption**:
    -   **Service:** `databook-app` (Laravel).
    -   **Controller:** `App\Http\Controllers\Titles::main()`
    -   **View:** `resources/views/titles.blade.php`
    -   **Input:** Reads `dashboard_data.json` from `/var/shared/dashboard_data.json`.

## Production Sync Strategy

**Implemented Pattern:** A shared Docker volume `shared_data` is mounted to both services.

-   **API:** `/app/shared`
-   **App:** `/var/shared`

**Automated Workflow:**
1.  Run the generation script in the API container:
    ```bash
    sudo docker exec databook-api python api/generate_dashboard.py
    ```
2.  The script writes to `/app/shared/dashboard_data.json`.
3.  The file is instantly available at `/var/shared/dashboard_data.json` in the App container.
4.  Clear cache to see changes immediately:
    ```bash
    sudo docker exec databook-app php artisan view:clear
    ```

*No manual file copying is required.*
