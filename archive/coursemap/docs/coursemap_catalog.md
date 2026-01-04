### Coursemap: Data Catalog and How to Regenerate Leader Exports

This documents the existing Coursemap scripts in the repo and how leader data is produced and consumed by DonorPerfect automation.

#### Scripts

- `coursemap/scripts/pullRunLeads.sh`
  - *Purpose*: Pull all leaders from Coursemap API and write a CSV at `data/export/run_leads_ids_names.csv`. Also prints JSON/CSV to stdout depending on mode.
  - *Env required*: `COURSEMAP_API_URL`, `COURSEMAP_API_TOKEN` (Bearer).
  - *Usage examples*:
    - *CSV (default), all leaders*:
      ```bash
      ./coursemap/scripts/pullRunLeads.sh
      ```
    - *JSON output to stdout*:
      ```bash
      ./coursemap/scripts/pullRunLeads.sh json
      ```
    - *Filter active only (server accepts various truthy strings)*:
      ```bash
      ./coursemap/scripts/pullRunLeads.sh csv true
      ```
  - *Output file*: `data/export/run_leads_ids_names.csv` with columns:
    - `id,first_name,last_name,email,status`
    - *`status`*: is derived from several possible fields (`is_active`, `status`, `active`) and normalized to `active|inactive` matching server semantics.

- `coursemap/scripts/scrapeStudentv1`
  - *Purpose*: Simple lookup/inspection script to view student records via the API (demo/testing).
  - *Env required*: `COURSEMAP_API_URL`, `COURSEMAP_API_TOKEN`.
  - *Usage*:
    ```bash
    ./coursemap/scripts/scrapeStudentv1
    ```

#### *API references used*

- `GET {COURSEMAP_API_URL}/users/get-leaders?page=all[&active={0|1|true|false}]`
  - Bearer auth via `COURSEMAP_API_TOKEN`.
  - Response shapes observed vary; the automation tolerates these keys: `.data.users`, `.users`, `.data.data`, `.data`.
  - Fields consumed by DP automation: `id`, `first_name`, `last_name`, `email`, plus derived `status` (`active|inactive`).

#### *How DonorPerfect automation uses this*

- Apps Script (`donorperfect/scripts/dpMonthlyReport.gs`) fetches leaders directly from Coursemap using the same endpoint as above.
- It resolves Coursemap leaders to DP donors (email first, then name), checks if they have any gifts, and sets a DP `FLAG` code:
  - Active leaders → `DP_FLAG_ACTIVE` (e.g., `RUN_LEADER_ACTIVE`)
  - Inactive leaders → `DP_FLAG_FORMER` (e.g., `RUN_LEADER_FORMER`)
- Logs are written to sheets: `dp_leader_updates`, `dp_leader_unmatched`, `dp_leader_ambiguous` in the configured report spreadsheet.

#### *Environment variables (.env / Script Properties)*

- `COURSEMAP_API_URL`: Base URL (e.g., `https://api.studentsrunphilly.org/api/v2`)
- `COURSEMAP_API_TOKEN`: Bearer token for API

Optional (for DP automation; configured as Script Properties):

- `DP_FLAG_ACTIVE`, `DP_FLAG_FORMER`
- `DP_REPORT_SPREADSHEET_ID`

#### *Regenerating leader CSV locally (optional)*

If you want a local CSV snapshot for audit or dry-runs:

```bash
COURSEMAP_API_URL="https://api.studentsrunphilly.org/api/v2" \
COURSEMAP_API_TOKEN="..." \
./coursemap/scripts/pullRunLeads.sh csv
```

The DP Apps Script can run without the local CSV since it reads from Coursemap directly, but the CSV can be useful for point-in-time reviews.


