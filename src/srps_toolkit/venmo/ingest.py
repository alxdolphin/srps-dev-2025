from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from srps_toolkit.common.io import ensure_parent


@dataclass(frozen=True)
class VenmoRow:
    date: str
    amount: str
    transaction_id: str
    payer: str
    note: str


def _parse_venmo_export_row(row: dict[str, str]) -> VenmoRow:
    # Venmo exports vary; we support a small common subset via fallbacks.
    date = (row.get("Datetime") or row.get("Date") or row.get("Time") or "").strip()
    amount = (row.get("Amount (total)") or row.get("Amount") or row.get("Total") or "").strip()
    transaction_id = (row.get("ID") or row.get("Transaction ID") or row.get("TransactionId") or "").strip()
    payer = (row.get("From") or row.get("Username") or row.get("Payer") or "").strip()
    note = (row.get("Note") or row.get("Description") or "").strip()
    return VenmoRow(date=date, amount=amount, transaction_id=transaction_id, payer=payer, note=note)


def normalize_venmo_csv(*, input_csv: Path, limit: int | None = None) -> list[VenmoRow]:
    out: list[VenmoRow] = []
    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append(_parse_venmo_export_row(row))
            if limit is not None and len(out) >= limit:
                break
    return out


def write_dp_ready_csv(*, rows: list[VenmoRow], output_csv: Path) -> None:
    """
    Produce a conservative, import-friendly CSV. This does NOT write to DonorPerfect.

    Columns are intentionally minimal; downstream mapping/matching is org-specific.
    """
    ensure_parent(output_csv)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "amount", "transaction_id", "payer", "note", "reference"])
        for r in rows:
            reference = f"VENMO:{r.transaction_id}" if r.transaction_id else ""
            w.writerow([r.date, r.amount, r.transaction_id, r.payer, r.note, reference])


def _handler(args: argparse.Namespace, _config: dict[str, Any]) -> int:
    inp = Path(args.input)
    out = Path(args.output)
    limit = int(args.limit) if args.limit is not None else None
    dry_run = bool(args.dry_run)

    rows = normalize_venmo_csv(input_csv=inp, limit=limit)
    print(f"loaded {len(rows)} venmo rows from {inp}")
    if dry_run:
        print("dry-run: no files written; showing first 3 normalized rows")
        for r in rows[:3]:
            print({"date": r.date, "amount": r.amount, "transaction_id": r.transaction_id, "payer": r.payer, "note": r.note})
        return 0

    write_dp_ready_csv(rows=rows, output_csv=out)
    print(f"wrote dp-ready csv: {out}")
    return 0


def cmd_venmo_ingest(p: argparse.ArgumentParser) -> None:
    p.add_argument("--input", required=True, help="Path to Venmo CSV export")
    p.add_argument("--output", default="output/venmo/venmo_normalized.csv", help="Output CSV path")
    p.add_argument("--dry-run", action="store_true", help="No writes; print a small preview")
    p.add_argument("--limit", type=int, default=None, help="Limit rows processed (for testing)")
    p.set_defaults(_handler=_handler)

