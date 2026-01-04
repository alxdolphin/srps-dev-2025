from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def load_dotenv(path: Path) -> dict[str, str]:
    """
    Minimal .env parser (KEY=VALUE, supports # comments).
    Values are treated as raw strings; quotes are stripped if present.
    """
    if not path.exists():
        return {}

    out: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        out[key] = value
    return out


def apply_env(env: dict[str, str], *, override: bool = False) -> None:
    for k, v in env.items():
        if override or k not in os.environ:
            os.environ[k] = v


def load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    import tomllib  # py311+

    return tomllib.loads(path.read_text(encoding="utf-8"))


def get_str(d: dict[str, Any], key: str, default: str = "") -> str:
    v = d.get(key, default)
    return default if v is None else str(v)


def get_int(d: dict[str, Any], key: str, default: int) -> int:
    v = d.get(key, default)
    try:
        return int(v)
    except Exception:
        return default


@dataclass(frozen=True)
class CoursemapConfig:
    api_url: str
    api_token: str


@dataclass(frozen=True)
class DonorPerfectConfig:
    api_url: str
    api_key: str
    active_flag_code: str = "RL"
    former_flag_code: str = "FRL"

