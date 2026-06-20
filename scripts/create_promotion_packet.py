#!/usr/bin/env python3
"""Create an append-only project-brain promotion packet."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_project_brain_dir
from src.lib.vault_promotion import PromotionPacketRequest, create_promotion_packet


def _parse_packet_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a project-brain promotion packet.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--contributor", required=True)

    synthesis = parser.add_mutually_exclusive_group(required=True)
    synthesis.add_argument("--synthesis")
    synthesis.add_argument("--synthesis-file")

    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--action", action="append", default=[])
    parser.add_argument("--link", action="append", default=[])
    parser.add_argument("--role", action="append", default=[])
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--sensitivity", default="internal")
    parser.add_argument("--date", dest="packet_date", type=_parse_packet_date)
    return parser


def _read_synthesis(args: argparse.Namespace) -> str:
    if args.synthesis_file:
        return Path(args.synthesis_file).read_text(encoding="utf-8")
    return args.synthesis or ""


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    packet = create_promotion_packet(
        get_project_brain_dir(),
        PromotionPacketRequest(
            topic=args.topic,
            contributor=args.contributor,
            synthesis=_read_synthesis(args),
            source_paths=[Path(source) for source in args.source],
            proposed_actions=list(args.action),
            proposed_links=list(args.link),
            roles=list(args.role),
            domains=list(args.domain),
            sensitivity=args.sensitivity,
            packet_date=args.packet_date,
        ),
    )
    print(packet.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
