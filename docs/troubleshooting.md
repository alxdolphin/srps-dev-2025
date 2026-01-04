# Troubleshooting

## `srps: command not found`

You likely installed without editable mode, or your environment isn't active.

```bash
python -m pip install -e ".[dev]"
```

## DonorPerfect tool says `DP_API_URL and DP_API_KEY must be set`

Set them in `.env` (preferred) or your shell environment:

- `DP_API_URL`
- `DP_API_KEY`

## Dry-run still makes network calls

`donorperfect tag-running-leaders` needs to **read** DonorPerfect to find donor records and flags.
Dry-run guarantees **no writes**, but it still performs API requests.

