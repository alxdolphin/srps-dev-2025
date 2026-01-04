### DonorPerfect Leader Tagging and Venmo Import – Operations Manual

This guide explains setup and monthly operations for the Apps Script automation in `donorperfect/scripts/dpMonthlyReport.gs`.

#### One-time setup

1) Script Properties (Apps Script → Project Settings → Script properties):
   - `DP_API_URL`
   - `DP_API_KEY`
   - `DP_REPORT_SPREADSHEET_ID` (spreadsheet that will hold logs and reports)
   - `DP_FLAG_ACTIVE` (e.g., `RUN_LEADER_ACTIVE`)
   - `DP_FLAG_FORMER` (e.g., `RUN_LEADER_FORMER`)
   - `COURSEMAP_API_URL` (e.g., `https://api.studentsrunphilly.org/api/v2`)
   - `COURSEMAP_API_TOKEN`
   - `VENMO_FOLDER_ID` = `1BUGlfa-uyCHTmSQtEhbr7NbPyx4Y8X5Z`
   - `VENMO_FILE_MATCH` = `Venmo` (filters to Venmo files inside that folder tree)
   - `DP_VENMO_FUND` = `GENERAL`
   - `DP_VENMO_CAMPAIGN` = `ANNUAL`
   - `DP_VENMO_SOLICITATION` = `VENMO`
   - `DRY_RUN` = `1` (start in dry run)

2) Advanced Services:
   - Enable Google Drive advanced service (Apps Script → Services → Drive API) for .xlsx → Google Sheet conversion.

3) Permissions:
   - Ensure the service account / user running the script has read access to the Drive folder and edit access to the report spreadsheet.

#### Monthly automation

- The entrypoint is `runMonthlyAutomation()` which will:
  1) Tag running leaders (active/former) based on Coursemap, only for donors who have at least one gift.
  2) Import Venmo .xlsx (from the configured Drive folder and subfolders), converting to Google Sheet, matching donors, and inserting gifts in DP.
  3) Update the monthly DP report.

- Logs written to the report spreadsheet:
  - Leader tagging:
    - `dp_leader_updates`
    - `dp_leader_unmatched`
    - `dp_leader_ambiguous`
  - Venmo import:
    - `venmo_updates`
    - `venmo_unmatched`
    - `venmo_imported` (idempotency keys)
    - `venmo_mapping` (payer label → donor_id/email mapping table)

#### Matching and idempotency

- Leader tagging donor match order: email → name. Requires at least one gift to apply flag.
- Venmo donor match order: email in note → `venmo_mapping` → name split from payer label.
- Gifts are prevented from duplicating by:
  - Storing `reference` in DP as `VENMO:{transaction_id}` (or a computed unique key when no transaction_id).
  - Recording imported keys in `venmo_imported` sheet.

#### Running a dry run and going live

1) Dry run:
   - Set `DRY_RUN=1` in Script Properties.
   - Run `runMonthlyAutomation()`; review `*_unmatched` and `venmo_updates` statuses.

2) Fix unmatched:
   - For Venmo, add rows to `venmo_mapping` with `payer_label` → `donor_id` (and optional email).
   - Re-run `runMonthlyAutomation()`.

3) Live run:
   - Set `DRY_RUN=0` and re-run `runMonthlyAutomation()`.
   - Confirm gifts in DP; re-run to confirm idempotency (no duplicates).

#### Scheduling

- Use `scheduleMonthlyAutomationTrigger(dayOfMonth, hour)` to create a monthly trigger, e.g., 1st at 6am.

#### Troubleshooting

- DP API errors: verify `DP_API_URL`, `DP_API_KEY`, and Dynamic Query access (for SELECTs) is enabled for the API user.
- Coursemap errors: verify `COURSEMAP_API_URL` and `COURSEMAP_API_TOKEN` are correct, and that the token has access to `/users/get-leaders`.
- Drive conversion errors: ensure Advanced Drive service is enabled and `VENMO_FOLDER_ID` is accessible.


