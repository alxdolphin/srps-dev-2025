from __future__ import annotations

import argparse
from pathlib import Path

from srps_toolkit.common.config import apply_env, load_dotenv, load_toml
from srps_toolkit.common.logging import configure_logging
from srps_toolkit.donorperfect.tag_running_leaders import cmd_tag_running_leaders
from srps_toolkit.venmo.ingest import cmd_venmo_ingest


def _add_common_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--env-file", default=".env", help="Path to .env file (default: .env)")
    p.add_argument(
        "--config",
        default="config.toml",
        help="Path to config TOML (default: config.toml). Optional; env vars still apply.",
    )
    p.add_argument("--verbose", action="store_true", help="Enable INFO logs")
    p.add_argument("--debug", action="store_true", help="Enable DEBUG logs")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="srps", description="SRPS toolkit CLI")
    sub = p.add_subparsers(dest="product", required=True)

    # donorperfect
    dp = sub.add_parser("donorperfect", help="DonorPerfect helpers")
    dp_sub = dp.add_subparsers(dest="dp_cmd", required=True)
    dp_tag = dp_sub.add_parser("tag-running-leaders", help="Tag running leaders in DonorPerfect")
    _add_common_flags(dp_tag)
    cmd_tag_running_leaders(dp_tag)

    # venmo
    vn = sub.add_parser("venmo", help="Venmo helpers")
    vn_sub = vn.add_subparsers(dest="venmo_cmd", required=True)
    vn_ingest = vn_sub.add_parser("ingest", help="Normalize Venmo CSV exports")
    _add_common_flags(vn_ingest)
    cmd_venmo_ingest(vn_ingest)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(verbose=bool(getattr(args, "verbose", False)), debug=bool(getattr(args, "debug", False)))

    env_file = Path(getattr(args, "env_file", ".env"))
    apply_env(load_dotenv(env_file), override=False)

    config_path = Path(getattr(args, "config", "config.toml"))
    config = load_toml(config_path) if config_path.exists() else {}

    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.error("internal error: missing handler")
    return int(handler(args, config) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
