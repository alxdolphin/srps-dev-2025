# Setup

## Prereqs

- Python **3.11+**

## Install

```bash
python -m pip install -e ".[dev]"
```

## Configure

Create a local `.env` (never commit it):

```bash
cp .env.example .env
```

Optionally, you can also use a TOML config:

```bash
cp config.example.toml config.toml
```

Environment variables take precedence over `config.toml`.

## Quick checks

```bash
srps --help
srps venmo ingest --input examples/venmo_sample.csv --dry-run
```

