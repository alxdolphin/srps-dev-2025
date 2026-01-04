from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from srps_toolkit.common.io import ensure_parent
from srps_toolkit.donorperfect.client import DonorPerfectClient, escape_sql, parse_result_records

logger = logging.getLogger(__name__)

AMBIGUOUS = "AMBIGUOUS"
FILTERED = "FILTERED"


def named_params(**pairs: Any) -> str:
    segments: list[str] = []
    for key, value in pairs.items():
        if value is None:
            segments.append(f"@{key}=null")
        elif isinstance(value, bool):
            segments.append(f"@{key}={'1' if value else '0'}")
        elif isinstance(value, (int, float)):
            segments.append(f"@{key}={value}")
        else:
            s = str(value).replace("'", "''")
            segments.append(f"@{key}='{s}'")
    return ",".join(segments)


@dataclass(frozen=True)
class Leader:
    coursemap_id: str
    first_name: str
    last_name: str
    email: str
    status: str


def load_leaders_csv(path: Path, *, limit: int | None = None) -> list[Leader]:
    items: list[Leader] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if (row[0] or "").strip().lower() == "id":
                continue
            coursemap_id = (row[0] or "").strip()
            first_name = (row[1] or "").strip()
            last_name = (row[2] or "").strip()
            email = (row[3] or "").strip()
            status = (row[4] or "").strip().lower() if len(row) > 4 else ""
            if status not in ("active", "inactive"):
                status = "inactive"
            items.append(Leader(coursemap_id, first_name, last_name, email, status))
            if limit is not None and len(items) >= limit:
                break
    return items


def _normalize_name(value: str) -> str:
    if not value:
        return ""
    s = value.strip().lower()
    s = re.sub(r"[^a-z]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _dp_record_is_malformed(rec: dict[str, str]) -> str | None:
    donor_id = (rec.get("donor_id") or "").strip()
    if not donor_id.isdigit():
        return "missing-or-non-numeric-donor_id"
    # A defensive check: DP occasionally returns placeholders or blank names.
    if not (rec.get("first_name") or "").strip() and not (rec.get("last_name") or "").strip():
        return "missing-name"
    return None


def flag_code_exists(dp: DonorPerfectClient, flag_code: str) -> bool:
    safe = escape_sql(flag_code)
    sql = f"SELECT TOP 1 code, inactive FROM dpcodes WHERE field_name='FLAG' AND code='{safe}'"
    status, body = dp.call(sql)
    if status != 200:
        logger.warning("failed to verify flag code existence for %s, status=%s", flag_code, status)
        return False
    for rec in parse_result_records(body):
        if rec.get("code") == flag_code:
            inactive = (rec.get("inactive") or "").strip().upper()
            return inactive != "Y"
    return False


def get_existing_flags(dp: DonorPerfectClient, donor_id: str) -> list[str]:
    sql = f"SELECT flag FROM dpflags WHERE donor_id={int(donor_id)}"
    status, body = dp.call(sql)
    if status != 200:
        return []
    records = parse_result_records(body)
    return [r.get("flag") for r in records if r.get("flag")]


def set_flag_saveflag(dp: DonorPerfectClient, donor_id: str, flag_code: str) -> tuple[bool, str]:
    params = named_params(donor_id=int(donor_id), flag=flag_code, user_id="srps-toolkit")
    status, body = dp.call("dp_saveflag_xml", params)
    if status != 200:
        return False, "failed"
    if "<result" in body:
        return True, "updated"
    lower_body = body.lower()
    if "violation of primary key constraint" in lower_body or "duplicate key" in lower_body:
        return True, "already-set"
    return False, "failed"


def find_donor_by_email(dp: DonorPerfectClient, email: str) -> dict[str, str] | None:
    if not email:
        return None
    raw = email
    lower = raw.lower()
    upper = raw.upper()
    safe_raw = escape_sql(raw)
    safe_lower = escape_sql(lower)
    safe_upper = escape_sql(upper)
    sql = (
        "SELECT TOP 1 donor_id, first_name, last_name, email FROM dp WHERE "
        f"email='{safe_raw}' OR email='{safe_lower}' OR email='{safe_upper}'"
    )
    status, body = dp.call(sql)
    if status != 200:
        return None
    records = parse_result_records(body)
    return records[0] if records else None


def find_donor_by_name(
    dp: DonorPerfectClient, first_name: str, last_name: str, expected_email: str | None = None
) -> dict[str, str] | str | None:
    if not first_name or not last_name:
        return None

    params = named_params(
        donor_id=None,
        last_name=f"{last_name}%",
        first_name=f"{first_name}%",
        opt_line=None,
        address=None,
        city=None,
        state=None,
        zip=None,
        country=None,
        filter_id=None,
        user_id=None,
    )
    status, body = dp.call("dp_donorsearch", params)
    if status == 200:
        records = parse_result_records(body)
        target_fn = _normalize_name(first_name)
        target_ln = _normalize_name(last_name)
        good: list[dict[str, str]] = []
        malformed: list[dict[str, str]] = []
        for rec in records:
            rec_fn = _normalize_name(rec.get("first_name", ""))
            rec_ln = _normalize_name(rec.get("last_name", ""))
            if rec_fn == target_fn and rec_ln == target_ln:
                reason = _dp_record_is_malformed(rec)
                if reason:
                    malformed.append(rec)
                else:
                    good.append(rec)
        if len(good) == 1:
            return good[0]
        if len(good) > 1:
            if expected_email:
                by_email = [
                    r
                    for r in good
                    if (r.get("email") or "").strip().lower() == expected_email.strip().lower()
                ]
                if len(by_email) == 1:
                    return by_email[0]
            return AMBIGUOUS
        if not good and malformed:
            return FILTERED

    safe_first = escape_sql(first_name)
    safe_last = escape_sql(last_name)
    sql = (
        "SELECT TOP 2 donor_id, first_name, last_name, email "
        f"FROM dp WHERE first_name='{safe_first}' AND last_name='{safe_last}'"
    )
    status, body = dp.call(sql)
    if status != 200:
        return None
    records = parse_result_records(body)
    if not records:
        return None
    good = [r for r in records if not _dp_record_is_malformed(r)]
    if len(good) == 1:
        return good[0]
    if len(good) > 1:
        if expected_email:
            by_email = [
                r
                for r in good
                if (r.get("email") or "").strip().lower() == expected_email.strip().lower()
            ]
            if len(by_email) == 1:
                return by_email[0]
        return AMBIGUOUS
    return None


def has_any_gifts(dp: DonorPerfectClient, donor_id: str) -> bool:
    params = named_params(donor_id=int(donor_id))
    status, body = dp.call("dp_gifts", params)
    if status != 200:
        return False
    return len(parse_result_records(body)) > 0


def choose_flag(status: str, active_flag: str, former_flag: str) -> str:
    return active_flag if (status or "").strip().lower() == "active" else former_flag


def resolve_donor_id(
    dp: DonorPerfectClient,
    leader: Leader,
    ambiguous_writer: csv.writer,
    unmatched_writer: csv.writer,
) -> tuple[str | None, str | None, bool, bool]:
    leader_name = (leader.first_name + " " + leader.last_name).strip()

    donor = find_donor_by_email(dp, leader.email)
    if donor:
        donor_id = donor.get("donor_id")
        if donor_id:
            return donor_id, "email", False, False
        unmatched_writer.writerow([leader.coursemap_id, leader_name, leader.email, "matched donor missing donor_id"])
        return None, None, False, True

    donor_by_name = find_donor_by_name(dp, leader.first_name, leader.last_name, leader.email)
    if donor_by_name == AMBIGUOUS:
        ambiguous_writer.writerow([leader.coursemap_id, leader_name, leader.email, "multiple donors matched by name"])
        return None, None, True, False
    if donor_by_name == FILTERED:
        unmatched_writer.writerow([leader.coursemap_id, leader_name, leader.email, "name matches found but malformed"])
        return None, None, False, True
    if not donor_by_name:
        unmatched_writer.writerow([leader.coursemap_id, leader_name, leader.email, "no donor matched by email or name"])
        return None, None, False, True

    donor_id = str(donor_by_name.get("donor_id") or "").strip()
    if not donor_id:
        unmatched_writer.writerow(
            [leader.coursemap_id, leader_name, leader.email, "matched donor missing donor_id (name match)"]
        )
        return None, None, False, True
    return donor_id, "name", False, False


def run(
    *,
    dp: DonorPerfectClient,
    input_path: Path,
    logs_dir: Path,
    apply: bool,
    active_flag: str,
    former_flag: str,
    limit: int | None = None,
    sleep_sec: float = 0.2,
) -> int:
    if not flag_code_exists(dp, active_flag):
        raise ValueError(f"active flag code '{active_flag}' not found or inactive")
    if not flag_code_exists(dp, former_flag):
        raise ValueError(f"former flag code '{former_flag}' not found or inactive")

    leaders = load_leaders_csv(input_path, limit=limit)
    ensure_parent(logs_dir / "_touch")

    updates_log = logs_dir / "dp_leader_updates.csv"
    unmatched_log = logs_dir / "dp_leader_unmatched.csv"
    ambiguous_log = logs_dir / "dp_leader_ambiguous.csv"

    for p in (updates_log, unmatched_log, ambiguous_log):
        ensure_parent(p)

    with (
        updates_log.open("w", newline="", encoding="utf-8") as u,
        unmatched_log.open("w", newline="", encoding="utf-8") as um,
        ambiguous_log.open("w", newline="", encoding="utf-8") as am,
    ):
        u_writer = csv.writer(u)
        um_writer = csv.writer(um)
        am_writer = csv.writer(am)
        u_writer.writerow(
            ["donor_id", "email", "coursemap_id", "leader_name", "target", "old_value", "new_value", "status"]
        )
        um_writer.writerow(["coursemap_id", "leader_name", "email", "reason"])
        am_writer.writerow(["coursemap_id", "leader_name", "email", "reason"])

        processed = 0
        updated = 0
        matched_by_email = 0
        matched_by_name = 0
        ambiguous_count = 0
        unmatched_count = 0
        donors_with_gifts = 0
        gift_cache: dict[str, bool] = {}

        for idx, leader in enumerate(leaders, 1):
            leader_name = (leader.first_name + " " + leader.last_name).strip()
            logger.info("[%s/%s] Processing leader: %s <%s>", idx, len(leaders), leader_name, leader.email)

            donor_id, matched_via, was_ambiguous, was_unmatched = resolve_donor_id(dp, leader, am_writer, um_writer)
            if was_ambiguous:
                ambiguous_count += 1
                continue
            if was_unmatched or not donor_id:
                unmatched_count += 1
                continue

            if matched_via == "email":
                matched_by_email += 1
            elif matched_via == "name":
                matched_by_name += 1

            if donor_id in gift_cache:
                has_gifts = gift_cache[donor_id]
            else:
                has_gifts = has_any_gifts(dp, donor_id)
                gift_cache[donor_id] = has_gifts

            if not has_gifts:
                um_writer.writerow([leader.coursemap_id, leader_name, leader.email, "no gifts found"])
                continue
            donors_with_gifts += 1

            chosen_flag = choose_flag(leader.status, active_flag, former_flag)
            target = f"FLAG:{chosen_flag}"

            existing_flags = get_existing_flags(dp, donor_id)
            old_value = ",".join(existing_flags) if existing_flags else "NONE"
            new_value = chosen_flag
            status_text = "dry-run"
            did_update = False

            if apply:
                if chosen_flag in existing_flags:
                    status_text = "already-set"
                else:
                    ok, status_text = set_flag_saveflag(dp, donor_id, chosen_flag)
                    if ok:
                        verify_flags = get_existing_flags(dp, donor_id)
                        if chosen_flag in verify_flags:
                            status_text = "updated-verified"
                            did_update = True
                        else:
                            status_text = "verify-failed"

            u_writer.writerow([donor_id, leader.email, leader.coursemap_id, leader_name, target, old_value, new_value, status_text])
            processed += 1
            if apply and did_update:
                updated += 1

            if sleep_sec > 0:
                time.sleep(sleep_sec)

        summary_target = f"FLAG:{active_flag}/{former_flag}"
        summary_text = (
            f"processed_total={len(leaders)} "
            f"matched_by_email={matched_by_email} matched_by_name={matched_by_name} "
            f"donors_with_gifts={donors_with_gifts} ambiguous={ambiguous_count} "
            f"unmatched={unmatched_count} updated={updated} of {processed}"
        )
        u_writer.writerow(["", "", "", "SUMMARY", summary_target, "", "", summary_text])

    return 0


def _handler(args: argparse.Namespace, config: dict[str, Any]) -> int:
    # Environment variables are the single source of truth; config.toml is optional convenience.
    dp_cfg = dict(config.get("donorperfect", {})) if isinstance(config.get("donorperfect"), dict) else {}

    api_url = os.environ.get("DP_API_URL") or str(dp_cfg.get("api_url") or "")
    api_key = os.environ.get("DP_API_KEY") or str(dp_cfg.get("api_key") or "")
    if not api_url or not api_key:
        raise SystemExit("DP_API_URL and DP_API_KEY must be set (env or config.toml)")

    active_flag = os.environ.get("DP_ACTIVE_FLAG_CODE") or str(dp_cfg.get("active_flag_code") or "RL")
    former_flag = os.environ.get("DP_FORMER_FLAG_CODE") or str(dp_cfg.get("former_flag_code") or "FRL")

    dp = DonorPerfectClient(api_url=api_url, api_key=api_key)

    apply_flag = bool(getattr(args, "apply", False))
    input_path = Path(args.input)
    logs_dir = Path(args.logs_dir)
    limit = int(args.limit) if getattr(args, "limit", None) is not None else None
    sleep_sec = float(args.sleep_sec)

    mode = "APPLY" if apply_flag else "DRY-RUN"
    print(f"{mode} – tagging leaders who donated → FLAG:{active_flag}/{former_flag}")
    print(f"input: {input_path}")
    print(f"logs_dir: {logs_dir}")

    return run(
        dp=dp,
        input_path=input_path,
        logs_dir=logs_dir,
        apply=apply_flag,
        active_flag=active_flag,
        former_flag=former_flag,
        limit=limit,
        sleep_sec=sleep_sec,
    )


def cmd_tag_running_leaders(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--input",
        required=True,
        help="Path to leaders CSV (id,first_name,last_name,email,status)",
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true", help="Apply updates (writes to DonorPerfect)")
    group.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Run without making changes (default)",
    )
    p.set_defaults(dry_run=True)
    p.add_argument("--limit", type=int, default=None, help="Limit leaders processed (for testing)")
    p.add_argument("--sleep-sec", type=float, default=0.2, help="Delay between requests (default: 0.2)")
    p.add_argument("--logs-dir", default="output/donorperfect", help="Directory for output audit logs")
    p.set_defaults(_handler=_handler)

