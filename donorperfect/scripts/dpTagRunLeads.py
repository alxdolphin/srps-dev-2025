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


# minimal xml helpers for DP result parsing
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
    # split into <record>...</record>
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
        # fields like <field name='donor_id' value='123' /> or <field name='x'>text</field>
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
            # self-closing?
            is_self_closing = field_tag.endswith('/>')
            value_text = ''
            if not is_self_closing:
                # find closing
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
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        status = resp.getcode()
        body = resp.read().decode('utf-8', errors='replace')
        return status, body


def named_params(**pairs) -> str:
    segments = []
    for key, value in pairs.items():
        if value is None:
            segments.append(f"@{key}=null")
        elif isinstance(value, (int, float)):
            segments.append(f"@{key}={value}")
        elif isinstance(value, bool):
            segments.append(f"@{key}={'1' if value else '0'}")
        else:
            # quote and escape single quotes per DP doc
            s = str(value).replace("'", "''")
            segments.append(f"@{key}='{s}'")
    return ','.join(segments)


def ensure_dirs(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Leader:
    coursemap_id: str
    first_name: str
    last_name: str
    email: str


def load_leaders_csv(path: Path) -> List[Leader]:
    items: List[Leader] = []
    with path.open('r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            # expect: id,first_name,last_name,email (from updated pullRunLeads.sh)
            if row[0].lower() == 'id':
                # allow header if present later
                continue
            coursemap_id = (row[0] or '').strip()
            first_name = (row[1] or '').strip()
            last_name = (row[2] or '').strip()
            email = (row[3] or '').strip().lower()
            items.append(Leader(coursemap_id, first_name, last_name, email))
    return items


def find_donor_by_email(api_url: str, api_key: str, email: str) -> Optional[Dict[str, str]]:
    if not email:
        return None
    # dynamic query to dp table (safer exact match)
    sql = f"SELECT TOP 1 donor_id, first_name, last_name, email FROM dp WHERE email='{email.replace("'", "''")}'"
    status, body = dp_call(api_url, api_key, sql)
    if status != 200:
        return None
    records = parse_result_records(body)
    return records[0] if records else None


def has_any_gifts(api_url: str, api_key: str, donor_id: str) -> bool:
    params = named_params(donor_id=int(donor_id))
    status, body = dp_call(api_url, api_key, 'dp_gifts', params)
    if status != 200:
        return False
    records = parse_result_records(body)
    return len(records) > 0


def get_current_flag(api_url: str, api_key: str, donor_id: str, field: str) -> Optional[str]:
    safe_field = field.replace("'", "''")
    sql = f"SELECT TOP 1 {safe_field} FROM dp WHERE donor_id={int(donor_id)}"
    status, body = dp_call(api_url, api_key, sql)
    if status != 200:
        return None
    records = parse_result_records(body)
    if not records:
        return None
    return records[0].get(field)


def set_flag_savedonor(api_url: str, api_key: str, donor_id: str, field: str, value: str) -> bool:
    # updates donor main table fields via dp_savedonor using named params
    params = named_params(donor_id=int(donor_id), **{field: value, 'user_id': 'srps-script'})
    status, body = dp_call(api_url, api_key, 'dp_savedonor', params)
    if status != 200:
        return False
    # dp returns <result> with record_count or status; if not error, assume success
    return '<result' in body


def normalize_truth(value: Optional[str]) -> str:
    v = (value or '').strip().upper()
    if v in ('Y', 'YES', 'TRUE', '1'):
        return 'Y'
    if v == 'N':
        return 'N'
    return v


def run(input_path: Path, leader_field: str, apply: bool, logs_dir: Path) -> int:
    api_url = os.environ.get('DP_API_URL', '')
    api_key = os.environ.get('DP_API_KEY', '')
    if not api_url or not api_key:
        print('error: DP_API_URL and DP_API_KEY must be set in environment', file=sys.stderr)
        return 2

    leaders = load_leaders_csv(input_path)
    updates_log = logs_dir / 'dp_leader_updates.csv'
    unmatched_log = logs_dir / 'dp_leader_unmatched.csv'
    ambiguous_log = logs_dir / 'dp_leader_ambiguous.csv'
    ensure_dirs(updates_log)
    ensure_dirs(unmatched_log)
    ensure_dirs(ambiguous_log)

    with updates_log.open('w', newline='', encoding='utf-8') as u,
         unmatched_log.open('w', newline='', encoding='utf-8') as um,
         ambiguous_log.open('w', newline='', encoding='utf-8') as am:
        u_writer = csv.writer(u)
        um_writer = csv.writer(um)
        am_writer = csv.writer(am)
        u_writer.writerow(['donor_id', 'email', 'coursemap_id', 'leader_name', 'field', 'old_value', 'new_value', 'status'])
        um_writer.writerow(['coursemap_id', 'leader_name', 'email', 'reason'])
        am_writer.writerow(['coursemap_id', 'leader_name', 'email', 'reason'])

        processed = 0
        updated = 0
        for leader in leaders:
            leader_name = (leader.first_name + ' ' + leader.last_name).strip()
            donor = find_donor_by_email(api_url, api_key, leader.email)
            if not donor:
                um_writer.writerow([leader.coursemap_id, leader_name, leader.email, 'no donor matched by email'])
                continue
            donor_id = donor.get('donor_id')
            if not donor_id:
                um_writer.writerow([leader.coursemap_id, leader_name, leader.email, 'matched donor missing donor_id'])
                continue

            if not has_any_gifts(api_url, api_key, donor_id):
                um_writer.writerow([leader.coursemap_id, leader_name, leader.email, 'no gifts found'])
                continue

            old_value = normalize_truth(get_current_flag(api_url, api_key, donor_id, leader_field))
            new_value = 'Y'
            status_text = 'dry-run'
            ok = True
            if apply:
                ok = set_flag_savedonor(api_url, api_key, donor_id, leader_field, new_value)
                status_text = 'updated' if ok else 'failed'
            u_writer.writerow([donor_id, leader.email, leader.coursemap_id, leader_name, leader_field, old_value, new_value, status_text])
            processed += 1
            if apply and ok:
                updated += 1
            # be gentle to API
            time.sleep(0.2)

    print(f"processed leaders: {len(leaders)}")
    print(f"log: {updates_log}")
    print(f"log: {unmatched_log}")
    print(f"log: {ambiguous_log}")
    return 0


def main():
    parser = argparse.ArgumentParser(description='Tag DonorPerfect donors who are Coursemap running leaders and have donated')
    parser.add_argument('--input', required=True, help='Path to Coursemap leaders CSV produced by pullRunLeads.sh (id,first_name,last_name,email)')
    parser.add_argument('--leader-field', default=os.environ.get('DP_LEADER_FIELD', 'RUNNING_LEADER'), help='DP donor field to set to Y')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--apply', action='store_true', help='Apply updates')
    group.add_argument('--dry-run', dest='dry_run', action='store_true', help='Run without making changes (default)')
    parser.add_argument('--logs-dir', default='data/donorperfect/logs', help='Directory for output logs')
    args = parser.parse_args()

    input_path = Path(args.input)
    logs_dir = Path(args.logs_dir)
    apply_flag = bool(getattr(args, 'apply', False) and not getattr(args, 'dry_run', False))
    if not apply_flag:
        print('dry-run: no changes will be saved; use --apply to update donors', file=sys.stderr)
    rc = run(input_path, args.leader_field, apply_flag, logs_dir)
    sys.exit(rc)


if __name__ == '__main__':
    main()


