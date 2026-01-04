# SRPS Toolkit (SRPS-DEV-2025)

A small, privacy-conscious toolkit for automating common fundraising/admin data workflows using **DonorPerfect** and **Venmo exports**.

## Why it matters

Nonprofits often lose time to repetitive, error-prone “spreadsheet glue”. This repo packages a few small tools into a clean, runnable toolkit with audit logs and dry-run support.

## Tools included (headline)

- **DonorPerfect: tag running leaders** — read a leaders roster CSV, match donors, and (optionally) set a flag, producing audit CSV logs.
- **Venmo: ingest + normalize export** — normalize a Venmo export into a conservative, import-friendly CSV (no DP writes).

## Quickstart (60 seconds)

```bash
python -m pip install -e ".[dev]"
srps venmo ingest --input examples/venmo_sample.csv --dry-run
```

## Configuration

- **Environment**: copy `/.env.example` to `/.env` and fill in values (never commit `.env`).
- **Optional TOML**: copy `/config.example.toml` to `/config.toml`.

Environment variables take precedence over `config.toml`.

## Usage

### Coursemap pull leaders roster

This tool **reads Coursemap** to export a leaders roster CSV. In dry-run mode it performs **no writes**, but still makes API calls.

```bash
srps coursemap pull-leaders --dry-run --limit 5
```

### Venmo normalize

Dry-run preview:

```bash
srps venmo ingest --input examples/venmo_sample.csv --dry-run
```

Sample output (dry-run):

```text
loaded 2 venmo rows from examples/venmo_sample.csv
dry-run: no files written; showing first 3 normalized rows
{'date': '2025-01-01T12:00:00Z', 'amount': '10.00', 'transaction_id': 'txn_001', 'payer': 'alex_runner', 'note': 'Donation'}
```

Write an output CSV:

```bash
srps venmo ingest --input examples/venmo_sample.csv --output output/venmo/venmo_normalized.csv
```

### DonorPerfect tag running leaders

This tool **reads DonorPerfect** to match donors and check gifts. In dry-run mode it performs **no writes**, but still makes API calls.

```bash
srps donorperfect tag-running-leaders --input examples/leaders_sample.csv --dry-run --limit 5
```

To apply updates:

```bash
srps donorperfect tag-running-leaders --input path/to/leaders.csv --apply
```

## Data privacy

- **No real org data** should be committed (donor/student exports, emails, addresses, etc.).
- The `examples/` inputs are **synthetic**.
- `.gitignore` blocks common sensitive artifacts (`.env`, `data/`, `output/`, `*.csv`, `*.xlsx`, `*.db`, etc.).

## Repo notes

Legacy / exploratory scripts are kept under `archive/` and are intentionally not featured.

## Docs

- `docs/setup.md`
- `docs/troubleshooting.md`
