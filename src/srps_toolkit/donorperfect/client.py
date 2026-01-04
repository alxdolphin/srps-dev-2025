from __future__ import annotations

import time
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any


_DEFAULT_TIMEOUT_SEC = 15.0
_DEFAULT_MAX_RETRIES = 3


def _extract_between(text: str, start_token: str, end_token: str) -> str | None:
    start = text.find(start_token)
    if start == -1:
        return None
    start += len(start_token)
    end = text.find(end_token, start)
    if end == -1:
        return None
    return text[start:end]


def parse_result_records(xml_text: str) -> list[dict[str, str]]:
    """
    Very small DonorPerfect XML response parser for <result><record><field .../></record></result>.
    """
    if not xml_text or "<result" not in xml_text:
        return []
    records: list[dict[str, str]] = []
    cursor = 0
    while True:
        rec_start = xml_text.find("<record>", cursor)
        if rec_start == -1:
            break
        rec_end = xml_text.find("</record>", rec_start)
        if rec_end == -1:
            break
        rec_xml = xml_text[rec_start:rec_end]
        cursor = rec_end + len("</record>")

        record: dict[str, str] = {}
        field_cursor = 0
        while True:
            field_start = rec_xml.find("<field", field_cursor)
            if field_start == -1:
                break
            tag_close = rec_xml.find(">", field_start)
            if tag_close == -1:
                break
            field_tag = rec_xml[field_start : tag_close + 1]
            name = _extract_between(field_tag, "name='", "'")
            value_attr = _extract_between(field_tag, "value='", "'")
            is_self_closing = field_tag.endswith("/>")
            value_text = ""
            if not is_self_closing:
                close_tag = rec_xml.find("</field>", tag_close)
                if close_tag != -1:
                    value_text = rec_xml[tag_close + 1 : close_tag]
                    field_cursor = close_tag + len("</field>")
                else:
                    field_cursor = tag_close + 1
            else:
                field_cursor = tag_close + 1
            if name:
                record[name] = value_attr if value_attr is not None else value_text
        records.append(record)
    return records


def escape_sql(value: str) -> str:
    return str(value).replace("'", "''")


@dataclass(frozen=True)
class DonorPerfectClient:
    api_url: str
    api_key: str
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC
    max_retries: int = _DEFAULT_MAX_RETRIES
    user_agent: str = "srps-toolkit/0.1"

    def call(self, action: str, params: str | None = None) -> tuple[int, str]:
        query: dict[str, Any] = {"apikey": self.api_key, "action": action}
        if params is not None:
            query["params"] = params
        url = self.api_url + "?" + urllib.parse.urlencode(query)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/xml, text/xml, */*",
            "Connection": "close",
        }

        attempt = 0
        while True:
            attempt += 1
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    return resp.getcode(), resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                status = getattr(e, "code", 0) or 0
                body_bytes = getattr(e, "fp", None).read() if getattr(e, "fp", None) else None
                body_text = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""
                if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    time.sleep(min(backoff, 8.0))
                    continue
                return status, body_text
            except urllib.error.URLError as e:
                if attempt < self.max_retries:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    time.sleep(min(backoff, 8.0))
                    continue
                reason = getattr(e, "reason", "")
                return 0, str(reason) if reason else str(e)

