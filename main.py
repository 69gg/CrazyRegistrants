#!/usr/bin/env python3
"""疯狂注册人 — CLI 入口"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from platforms import discover


def main() -> None:
    parser = argparse.ArgumentParser(description="疯狂注册人：注册机大合集")
    sub = parser.add_subparsers(dest="platform", required=True, metavar="PLATFORM")

    registrants = discover()
    for name, r in registrants.items():
        p = sub.add_parser(name, help=r.meta.description)
        r.add_args(p)

    args = parser.parse_args()
    registrants[args.platform].run(args)


if __name__ == "__main__":
    mp.freeze_support()
    main()