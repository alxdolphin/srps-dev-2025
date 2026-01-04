from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from srps_toolkit.common.io import ensure_parent
from srps_toolkit.coursemap.client import CoursemapClient


@dataclass(frozen=True)
class LeaderRow:
    id: str
    first_name: str
    last_name: str
    email: str
    status: str  # active|inactive


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    s = str(v).strip().lower()
    return s in ("true", "1", "active", "yes", "y")


def derive_status(user: dict[str, Any]) -> str:
    if "is_active" in user and user.get("is_active") is not None:
        return "active" if _as_bool(user.get("is_active")) else "inactive"
    if "status" in user and user.get("status") is not None:
        return "active" if str(user.get("status")).strip().lower() == "active" else "inactive"
    if "active" in user and user.get("active") is not None:
        return "active" if _as_bool(user.get("active")) else "inactive"
    return "inactive"


def extract_users(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Coursemap APIs vary a bit; accept common response shapes.
    """
    candidates = (
        payload.get("data", {}).get("users")
        if isinstance(payload.get("data"), dict)
        else None
    )
    if isinstance(candidates, list):
        return candidates

    for key in ("users",):
        if isinstance(payload.get(key), list):
            return payload[key]

    data = payload.get("data")
    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data.get("users"), list):
            return data["users"]
    if isinstance(data, list):
        return data
    return []


def users_to_leaders(users: list[dict[str, Any]], *, limit: int | None = None) -> list[LeaderRow]:
    out: list[LeaderRow] = []
    for u in users:
        out.append(
            LeaderRow(
                id=str(u.get("id") or "").strip(),
                first_name=str(u.get("first_name") or "").strip(),
                last_name=str(u.get("last_name") or "").strip(),
                email=str(u.get("email") or "").strip(),
                status=derive_status(u),
            )
        )
        if limit is not None and len(out) >= limit:
            break
    return out


def write_leaders_csv(path: Path, leaders: list[LeaderRow]) -> None:
    ensure_parent(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "first_name", "last_name", "email", "status"])
        for r in leaders:
            w.writerow([r.id, r.first_name, r.last_name, r.email, r.status])


def _handler(args: argparse.Namespace, config: dict[str, Any]) -> int:
    cm_cfg = dict(config.get("coursemap", {})) if isinstance(config.get("coursemap"), dict) else {}
    api_url = os.environ.get("COURSEMAP_API_URL") or str(cm_cfg.get("api_url") or "")
    api_token = os.environ.get("COURSEMAP_API_TOKEN") or str(cm_cfg.get("api_token") or "")
    if not api_url or not api_token:
        raise SystemExit("COURSEMAP_API_URL and COURSEMAP_API_TOKEN must be set (env or config.toml)")

    active = args.active
    out_path = Path(args.out)
    limit = int(args.limit) if args.limit is not None else None
    dry_run = bool(args.dry_run)

    client = CoursemapClient(api_url=api_url, api_token=api_token)

    params: dict[str, str] = {"page": "all"}
    if active is not None:
        params["active"] = str(active)

    status, payload = client.get_json("/users/get-leaders", params=params)
    if status != 200:
        raise SystemExit(f"coursemap request failed: status={status}")

    users = extract_users(payload)
    leaders = users_to_leaders(users, limit=limit)
    print(f"loaded {len(leaders)} leaders")

    if dry_run:
        print("dry-run: no files written; showing first 3 rows")
        for r in leaders[:3]:
            print({"id": r.id, "first_name": r.first_name, "last_name": r.last_name, "email": r.email, "status": r.status})
        return 0

    write_leaders_csv(out_path, leaders)
    print(f"wrote leaders csv: {out_path}")
    return 0


def cmd_coursemap_pull_leaders(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", default="output/coursemap/leaders.csv", help="Output CSV path")
    p.add_argument("--dry-run", action="store_true", help="No writes; print a small preview")
    p.add_argument("--limit", type=int, default=None, help="Limit leaders processed (for testing)")
    p.add_argument(
        "--active",
        default=None,
        help="Optional active filter passed through to API (e.g. 1/0/true/false).",
    )
    p.set_defaults(_handler=_handler)

