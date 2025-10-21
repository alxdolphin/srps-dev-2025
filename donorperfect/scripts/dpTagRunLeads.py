#!/usr/bin/env python3
import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import urllib.parse
import urllib.request
import urllib.error

import logging
import re

# Set up logging (level adjusted later based on flags)
logging.basicConfig(
    level=logging.WARNING,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

AMBIGUOUS = "AMBIGUOUS"
FILTERED = "FILTERED"
_DEFAULT_TIMEOUT_SEC = 15.0
_DEFAULT_MAX_RETRIES = 3
_USER_AGENT = 'srps-dpTagRunLeads/2025.10'

def _extract_between(text: str, start_token: str, end_token: str) -> Optional[str]:
    start = text.find(start_token)
    if start == -1:
        return None
    start += len(start_token)
    end = text.find(end_token, start)
    if end == -1:
        return None
    return text[start:end]

def parse_result_records(xml_text: str) -> List[Dict[str, str]]:
    if not xml_text or '<result' not in xml_text:
        return []
    records: List[Dict[str, str]] = []
    cursor = 0
    while True:
        rec_start = xml_text.find('<record>', cursor)
        if rec_start == -1:
            break
        rec_end = xml_text.find('</record>', rec_start)
        if rec_end == -1:
            break
        rec_xml = xml_text[rec_start:rec_end]
        cursor = rec_end + len('</record>')
        record: Dict[str, str] = {}
        field_cursor = 0
        while True:
            field_start = rec_xml.find('<field', field_cursor)
            if field_start == -1:
                break
            tag_close = rec_xml.find('>', field_start)
            if tag_close == -1:
                break
            field_tag = rec_xml[field_start:tag_close + 1]
            name = _extract_between(field_tag, "name='", "'")
            value_attr = _extract_between(field_tag, "value='", "'")
            is_self_closing = field_tag.endswith('/>')
            value_text = ''
            if not is_self_closing:
                close_tag = rec_xml.find('</field>', tag_close)
                if close_tag != -1:
                    value_text = rec_xml[tag_close + 1:close_tag]
                    field_cursor = close_tag + len('</field>')
                else:
                    field_cursor = tag_close + 1
            else:
                field_cursor = tag_close + 1
            if name:
                record[name] = value_attr if value_attr is not None else value_text
        records.append(record)
    return records

def dp_call(api_url: str, api_key: str, action: str, params: Optional[str] = None) -> Tuple[int, str]:
    query = {
        'apikey': api_key,
        'action': action,
    }
    if params is not None:
        query['params'] = params
    url = api_url + '?' + urllib.parse.urlencode(query)
    debug(f"API call: {action}, params: {params}")

    try:
        max_retries = int(os.environ.get('DP_HTTP_RETRIES', str(_DEFAULT_MAX_RETRIES)))
    except ValueError:
        max_retries = _DEFAULT_MAX_RETRIES
    try:
        timeout_sec = float(os.environ.get('DP_HTTP_TIMEOUT', str(_DEFAULT_TIMEOUT_SEC)))
    except ValueError:
        timeout_sec = _DEFAULT_TIMEOUT_SEC

    headers = {
        'User-Agent': _USER_AGENT,
        'Accept': 'application/xml, text/xml, */*',
        'Connection': 'close',
    }

    attempt = 0
    while True:
        attempt += 1
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                status = resp.getcode()
                body = resp.read().decode('utf-8', errors='replace')
                debug(f"API call result ({action}): status={status}")
                return status, body
        except urllib.error.HTTPError as e:
            status = getattr(e, 'code', 0) or 0
            body_bytes = getattr(e, 'fp', None).read() if getattr(e, 'fp', None) else None
            body_text = (body_bytes.decode('utf-8', errors='replace') if body_bytes else '')
            if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                retry_after = 0.0
                try:
                    retry_after = float(e.headers.get('Retry-After')) if e.headers and e.headers.get('Retry-After') else 0.0
                except Exception:
                    retry_after = 0.0
                backoff = retry_after if retry_after > 0 else 0.5 * (2 ** (attempt - 1))
                time.sleep(min(backoff, 8.0))
                continue
            return status, body_text
        except urllib.error.URLError as e:
            if attempt < max_retries:
                time.sleep(min(0.5 * (2 ** (attempt - 1)), 8.0))
                continue
            reason = getattr(e, 'reason', '')
            return 0, str(reason) if reason else str(e)

def named_params(**pairs) -> str:
    segments = []
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
    return ','.join(segments)

def ensure_dirs(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

def escape_sql(value: str) -> str:
    return str(value).replace("'", "''")

def flag_code_exists(api_url: str, api_key: str, flag_code: str) -> bool:
    safe = escape_sql(flag_code)
    sql = f"SELECT TOP 1 code, inactive FROM dpcodes WHERE field_name='FLAG' AND code='{safe}'"
    status, body = dp_call(api_url, api_key, sql)
    if status != 200:
        logger.warning(f"failed to verify flag code existence for {flag_code}, status={status}")
        return False
    records = parse_result_records(body)
    for rec in records:
        if rec.get('code') == flag_code:
            inactive = (rec.get('inactive') or '').strip().upper()
            return inactive != 'Y'
    return False

def donor_has_flag(api_url: str, api_key: str, donor_id: str, flag_code: str) -> bool:
    safe_flag = escape_sql(flag_code)
    sql = f"SELECT TOP 1 flag FROM dpflags WHERE donor_id={int(donor_id)} AND flag='{safe_flag}'"
    status, body = dp_call(api_url, api_key, sql)
    if status != 200:
        return False
    records = parse_result_records(body)
    return len(records) > 0

def get_existing_flags(api_url: str, api_key: str, donor_id: str) -> List[str]:
    sql = f"SELECT flag FROM dpflags WHERE donor_id={int(donor_id)}"
    status, body = dp_call(api_url, api_key, sql)
    if status != 200:
        return []
    records = parse_result_records(body)
    return [rec.get("flag") for rec in records if "flag" in rec and rec.get("flag")]

def set_flag_saveflag(api_url: str, api_key: str, donor_id: str, flag_code: str) -> Tuple[bool, str]:
    params = named_params(donor_id=int(donor_id), flag=flag_code, user_id='srps-script')
    status, body = dp_call(api_url, api_key, 'dp_saveflag_xml', params)
    if status != 200:
        return False, 'failed'
    if '<result' in body:
        return True, 'updated'
    lower_body = body.lower()
    if 'violation of primary key constraint' in lower_body or 'duplicate key' in lower_body:
        return True, 'already-set'
    return False, 'failed'

def choose_flag(status: str, active_flag: str, former_flag: str) -> str:
    return active_flag if (status or '').strip().lower() == 'active' else former_flag

def donor_has_any_gifts_cached(api_url: str, api_key: str, donor_id: str, gift_cache: Dict[str, bool]) -> bool:
    cached = gift_cache.get(donor_id)
    if cached is not None:
        return cached
    has = has_any_gifts(api_url, api_key, donor_id)
    gift_cache[donor_id] = has
    return has

def log_ambiguous(am_writer: csv.writer, leader: 'Leader', leader_name: str, reason: str):
    am_writer.writerow([leader.coursemap_id, leader_name, leader.email, reason])

def log_unmatched(um_writer: csv.writer, leader: 'Leader', leader_name: str, reason: str):
    um_writer.writerow([leader.coursemap_id, leader_name, leader.email, reason])

def resolve_donor_id(api_url: str, api_key: str, leader: 'Leader', am_writer: csv.writer, um_writer: csv.writer) -> Tuple[Optional[str], Optional[str], bool, bool]:
    leader_name = (leader.first_name + ' ' + leader.last_name).strip()
    donor = find_donor_by_email(api_url, api_key, leader.email)
    if donor:
        donor_id = donor.get('donor_id')
        if donor_id:
            return donor_id, 'email', False, False
        log_unmatched(um_writer, leader, leader_name, 'matched donor missing donor_id')
        return None, None, False, True
    donor_by_name = find_donor_by_name(api_url, api_key, leader.first_name, leader.last_name, leader.email)
    if donor_by_name == AMBIGUOUS:
        log_ambiguous(am_writer, leader, leader_name, 'multiple donors matched by name')
        return None, None, True, False
    if donor_by_name == FILTERED:
        log_unmatched(um_writer, leader, leader_name, 'name matches found but all malformed in DP')
        return None, None, False, True
    if not donor_by_name:
        log_unmatched(um_writer, leader, leader_name, 'no donor matched by email or name')
        return None, None, False, True
    donor_id = donor_by_name.get('donor_id')
    if not donor_id:
        log_unmatched(um_writer, leader, leader_name, 'matched donor missing donor_id (name match)')
        return None, None, False, True
    return donor_id, 'name', False, False

@dataclass
class Leader:
    coursemap_id: str
    first_name: str
    last_name: str
    email: str
    status: str

def load_leaders_csv(path: Path) -> List[Leader]:
    items: List[Leader] = []
    with path.open('r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if row[0].lower() == 'id':
                continue
            coursemap_id = (row[0] or '').strip()
            first_name = (row[1] or '').strip()
            last_name = (row[2] or '').strip()
            email = (row[3] or '').strip()
            status = (row[4] or '').strip().lower() if len(row) > 4 else ''
            if status not in ('active', 'inactive'):
                status = 'inactive'
            items.append(Leader(coursemap_id, first_name, last_name, email, status))
    logger.info(f"Loaded {len(items)} leader records from CSV {path}")
    return items

def find_donor_by_email(api_url: str, api_key: str, email: str) -> Optional[Dict[str, str]]:
    if not email:
        logger.debug(f"Skipped empty email")
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
    debug(f"Looking up donor by email variants: {raw} | {lower} | {upper}")
    status, body = dp_call(api_url, api_key, sql)
    if status != 200:
        logger.warning(f"DP lookup failed for {email}, status={status}")
        return None
    records = parse_result_records(body)
    if records:
        logger.debug(f"Match found for {email}: donor_id={records[0].get('donor_id')}")
    else:
        logger.info(f"No match found for {email}")
    return records[0] if records else None

def _normalize_name(value: str) -> str:
    if not value:
        return ''
    s = value.strip().lower()
    s = re.sub(r"[^a-z]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def find_donor_by_name(api_url: str, api_key: str, first_name: str, last_name: str, expected_email: Optional[str] = None) -> Optional[Dict[str, str]]:
    if not first_name or not last_name:
        logger.debug(f"Skipped empty first or last name for donor lookup")
        return None
    debug(f"Looking up donor by name via dp_donorsearch (wildcards): {first_name} {last_name}")
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
    status, body = dp_call(api_url, api_key, 'dp_donorsearch', params)
    if status == 200:
        records = parse_result_records(body)
        target_fn = _normalize_name(first_name)
        target_ln = _normalize_name(last_name)
        good: List[Dict[str, str]] = []
        malformed: List[Dict[str, str]] = []
        for rec in records:
            rec_fn = _normalize_name(rec.get('first_name', ''))
            rec_ln = _normalize_name(rec.get('last_name', ''))
            if rec_fn == target_fn and rec_ln == target_ln:
                reason = _dp_record_is_malformed(rec)
                if reason:
                    logger.debug(f"Filtered malformed dp record donor_id={rec.get('donor_id')} reason={reason}")
                    malformed.append(rec)
                else:
                    good.append(rec)
        if len(good) == 1:
            logger.debug(f"Match found (dp_donorsearch filtered) for {first_name} {last_name}: donor_id={good[0].get('donor_id')}")
            return good[0]
        if len(good) > 1:
            if expected_email:
                by_email = [r for r in good if (r.get('email') or '').strip().lower() == expected_email.strip().lower()]
                if len(by_email) == 1:
                    return by_email[0]
            logger.info(f"Ambiguous donor match (dp_donorsearch filtered) for name: {first_name} {last_name}")
            return AMBIGUOUS
        if not good and malformed:
            logger.info(f"Only malformed donor matches for name: {first_name} {last_name}")
            return FILTERED
    else:
        logger.warning(f"dp_donorsearch failed for {first_name} {last_name}, status={status}")

    safe_first = escape_sql(first_name)
    safe_last = escape_sql(last_name)
    sql = (
        "SELECT TOP 2 donor_id, first_name, last_name, email "
        f"FROM dp WHERE first_name='{safe_first}' AND last_name='{safe_last}'"
    )
    debug(f"Fallback name lookup via SELECT for: {first_name} {last_name}")
    status, body = dp_call(api_url, api_key, sql)
    if status != 200:
        logger.warning(f"Fallback DP lookup failed for {first_name} {last_name}, status={status}")
        return None
    records = parse_result_records(body)
    if not records:
        logger.info(f"No match found for name: {first_name} {last_name}")
        return None
    good = [r for r in records if not _dp_record_is_malformed(r)]
    if len(good) == 1:
        logger.debug(f"Match found (fallback) for {first_name} {last_name}: donor_id={good[0].get('donor_id')}")
        return good[0]
    if len(good) > 1:
        if expected_email:
            by_email = [r for r in good if (r.get('email') or '').strip().lower() == expected_email.strip().lower()]
            if len(by_email) == 1:
                return by_email[0]
        logger.info(f"Ambiguous donor match (fallback) for name: {first_name} {last_name}")
        return AMBIGUOUS
    logger.info(f"Only malformed donor matches in fallback for name: {first_name} {last_name}")
    return None

def has_any_gifts(api_url: str, api_key: str, donor_id: str) -> bool:
    params = named_params(donor_id=int(donor_id))
    debug(f"Checking for gifts for donor_id: {donor_id}")
    status, body = dp_call(api_url, api_key, 'dp_gifts', params)
    if status != 200:
        logger.warning(f"Gift check failed for donor_id={donor_id}, status={status}")
        return False
    records = parse_result_records(body)
    if records:
        logger.debug(f"Donor {donor_id} has {len(records)} gifts")
    else:
        logger.info(f"Donor {donor_id} has no gifts")
    return len(records) > 0

def run(input_path: Path, apply: bool, logs_dir: Path) -> int:
    api_url = os.environ.get('DP_API_URL', '')
    api_key = os.environ.get('DP_API_KEY', '')
    if not api_url or not api_key:
        print('error: DP_API_URL and DP_API_KEY must be set in environment', file=sys.stderr)
        return 2
    active_flag = os.environ.get('DP_ACTIVE_FLAG_CODE', 'RL') or 'RL'
    former_flag = os.environ.get('DP_FORMER_FLAG_CODE', 'FRL') or 'FRL'
    if not flag_code_exists(api_url, api_key, active_flag):
        print(f"error: active flag code '{active_flag}' not found or is inactive in DonorPerfect Codes (FLAG)", file=sys.stderr)
        return 3
    if not flag_code_exists(api_url, api_key, former_flag):
        print(f"error: former flag code '{former_flag}' not found or is inactive in DonorPerfect Codes (FLAG)", file=sys.stderr)
        return 3

    mode = 'APPLY' if apply else 'DRY-RUN'
    target = f"FLAG:{active_flag}/{former_flag}"
    print(f"{mode} – tagging leaders who donated → {target}")
    print(f"input: {input_path}")
    leaders = load_leaders_csv(input_path)
    updates_log = logs_dir / 'dp_leader_updates.csv'
    unmatched_log = logs_dir / 'dp_leader_unmatched.csv'
    ambiguous_log = logs_dir / 'dp_leader_ambiguous.csv'
    ensure_dirs(updates_log)
    ensure_dirs(unmatched_log)
    ensure_dirs(ambiguous_log)

    with updates_log.open('w', newline='', encoding='utf-8') as u, \
         unmatched_log.open('w', newline='', encoding='utf-8') as um, \
         ambiguous_log.open('w', newline='', encoding='utf-8') as am:
        u_writer = csv.writer(u)
        um_writer = csv.writer(um)
        am_writer = csv.writer(am)
        u_writer.writerow(['donor_id', 'email', 'coursemap_id', 'leader_name', 'target', 'old_value', 'new_value', 'status'])
        um_writer.writerow(['coursemap_id', 'leader_name', 'email', 'reason'])
        am_writer.writerow(['coursemap_id', 'leader_name', 'email', 'reason'])

        processed = 0
        updated = 0
        matched_by_email = 0
        matched_by_name = 0
        ambiguous_count = 0
        unmatched_count = 0
        donors_with_gifts = 0
        gift_cache: Dict[str, bool] = {}
        total = len(leaders)
        for idx, leader in enumerate(leaders, 1):
            leader_name = (leader.first_name + ' ' + leader.last_name).strip()
            logger.info(f"[{idx}/{total}] Processing leader: {leader_name} <{leader.email}>")
            donor_id, matched_via, was_ambiguous, was_unmatched = resolve_donor_id(api_url, api_key, leader, am_writer, um_writer)
            if was_ambiguous:
                ambiguous_count += 1
                continue
            if was_unmatched or not donor_id:
                unmatched_count += 1
                continue
            if matched_via == 'email':
                matched_by_email += 1
            elif matched_via == 'name':
                matched_by_name += 1

            if donor_id and matched_via:
                print(f"matched ({matched_via}): {leader_name} <{leader.email}> -> donor_id {donor_id}")

            if not donor_has_any_gifts_cached(api_url, api_key, donor_id, gift_cache):
                logger.info(f"  - Donor {donor_id} found for {leader.email if leader.email else (leader.first_name + ' ' + leader.last_name)}, but no gifts")
                um_writer.writerow([leader.coursemap_id, leader_name, leader.email, 'no gifts found'])
                continue
            donors_with_gifts += 1

            chosen_flag = choose_flag(leader.status, active_flag, former_flag)
            target = f"FLAG:{chosen_flag}"

            existing_flags = get_existing_flags(api_url, api_key, donor_id)
            old_value = ",".join(existing_flags) if existing_flags else 'NONE'

            new_value = chosen_flag
            status_text = 'dry-run'
            ok = True
            did_update = False
            if apply:
                if chosen_flag in existing_flags:
                    status_text = 'already-set'
                else:
                    ok, status_text = set_flag_saveflag(api_url, api_key, donor_id, chosen_flag)
                    if ok:
                        verify_flags = get_existing_flags(api_url, api_key, donor_id)
                        if chosen_flag in verify_flags:
                            status_text = 'updated-verified'
                            did_update = True
                        else:
                            status_text = 'verify-failed'
                            ok = False
            logger.info(f"  - {'Setting' if apply else 'Would set'} flag {chosen_flag} for donor_id={donor_id}. Status: {status_text}")
            u_writer.writerow([donor_id, leader.email, leader.coursemap_id, leader_name, target, old_value, new_value, status_text])
            processed += 1
            if apply and did_update:
                updated += 1
            time.sleep(0.2)

        summary_target = f"FLAG:{active_flag}/{former_flag}"
        summary_text = (
            f"processed_total={len(leaders)} "
            f"matched_by_email={matched_by_email} matched_by_name={matched_by_name} "
            f"donors_with_gifts={donors_with_gifts} ambiguous={ambiguous_count} "
            f"unmatched={unmatched_count} updated={updated} of {processed}"
        )
        u_writer.writerow(['', '', '', 'SUMMARY', summary_target, '', '', summary_text])

    print("--- summary ---")
    print(f"processed: {len(leaders)}")
    print(f"matched_by_email: {matched_by_email}")
    print(f"matched_by_name: {matched_by_name}")
    print(f"donors_with_gifts: {donors_with_gifts}")
    print(f"ambiguous: {ambiguous_count}")
    print(f"unmatched: {unmatched_count}")
    print(f"updated: {updated} of {processed}")
    print(f"logs: {updates_log}")
    print(f"logs: {unmatched_log}")
    print(f"logs: {ambiguous_log}")
    return 0

def main():
    parser = argparse.ArgumentParser(description='Tag DonorPerfect donors who are Coursemap running leaders and have donated')
    parser.add_argument('--input', required=True, help='Path to Coursemap leaders CSV produced by pullRunLeads.sh (id,first_name,last_name,email,status)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--apply', action='store_true', help='Apply updates')
    group.add_argument('--dry-run', dest='dry_run', action='store_true', help='Run without making changes (default)')
    parser.add_argument('--logs-dir', default='data/donorperfect/logs', help='Directory for output logs')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose console output (INFO)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging (most verbose)')
    args = parser.parse_args()

    if getattr(args, 'debug', False):
        logger.setLevel(logging.DEBUG)
        logger.debug("debug logging enabled")
    elif getattr(args, 'verbose', False):
        logger.setLevel(logging.INFO)
        logger.info("verbose logging enabled")

    input_path = Path(args.input)
    logs_dir = Path(args.logs_dir)
    apply_flag = bool(getattr(args, 'apply', False) and not getattr(args, 'dry_run', False))
    if not apply_flag:
        logger.info('dry-run: no changes will be saved; use --apply to update donors')
        print('dry-run: no changes will be saved; use --apply to update donors', file=sys.stderr)
    rc = run(
        input_path,
        apply_flag,
        logs_dir,
    )
    sys.exit(rc)

if __name__ == '__main__':
    main()
