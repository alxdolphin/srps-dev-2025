from __future__ import annotations

from pathlib import Path

from srps_toolkit.donorperfect.client import parse_result_records
from srps_toolkit.venmo.ingest import normalize_venmo_csv


def test_parse_result_records_smoke():
    xml = """<result>
    <record>
      <field name='donor_id' value='123' />
      <field name='email' value='alex@example.org' />
    </record>
    </result>"""
    recs = parse_result_records(xml)
    assert recs and recs[0]["donor_id"] == "123"


def test_venmo_normalize_smoke(tmp_path: Path):
    p = tmp_path / "venmo.csv"
    p.write_text(
        "ID,Datetime,Amount (total),From,Note\n"
        "txn_1,2025-01-01T12:00:00Z,10.00,ALEX,Donation\n",
        encoding="utf-8",
    )
    rows = normalize_venmo_csv(input_csv=p, limit=10)
    assert len(rows) == 1
    assert rows[0].transaction_id == "txn_1"

