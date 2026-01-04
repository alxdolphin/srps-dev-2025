from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CoursemapClient:
    """
    Minimal HTTP client for Coursemap-like APIs.
    """

    api_url: str
    api_token: str
    timeout_sec: float = 20.0
    max_retries: int = 3
    user_agent: str = "srps-toolkit/1.0"

    def get_json(self, path: str, *, params: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
        base = self.api_url.rstrip("/")
        path_clean = "/" + path.lstrip("/")
        url = base + path_clean
        if params:
            url = url + "?" + urllib.parse.urlencode(params)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
            "Connection": "close",
        }

        attempt = 0
        while True:
            attempt += 1
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    status = resp.getcode()
                    raw = resp.read().decode("utf-8", errors="replace")
                    return status, json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                status = getattr(e, "code", 0) or 0
                body_bytes = getattr(e, "fp", None).read() if getattr(e, "fp", None) else None
                raw = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""
                if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    time.sleep(min(0.5 * (2 ** (attempt - 1)), 8.0))
                    continue
                try:
                    return status, json.loads(raw) if raw else {}
                except Exception:
                    return status, {}
            except urllib.error.URLError:
                if attempt < self.max_retries:
                    time.sleep(min(0.5 * (2 ** (attempt - 1)), 8.0))
                    continue
                return 0, {}

