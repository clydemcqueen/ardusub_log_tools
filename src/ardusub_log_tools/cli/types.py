"""
ASL 2.0: 'types' verb implementation.
"""

from __future__ import annotations

import argparse
import os
import sys

import util


def run_types(args: argparse.Namespace) -> int:
    """Scan logs and report message types, counts, and rates across .BIN, .tlog, and .mcap."""
    files = util.expand_path(args.paths, args.recurse, [".tlog", ".BIN", ".mcap"])
    if not files:
        print("No matching log files found (.BIN, .tlog, .mcap).")
        return 1

    print(f"Processing {len(files)} file(s) for 'types'")

    for file_path in files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        print("------------------------------------------------------------")
        print(f"Reading {file_path}")

        try:
            if ext_lower in (".bin", ".tlog"):
                import show_types

                scanner = show_types.TypeFinder(file_path)
                scanner.read()
            elif ext_lower == ".mcap":
                import mcap_types

                scanner = mcap_types.TypeFinder(file_path)
                scanner.read()
            else:
                print(f"Unsupported format: {ext}")
        except Exception as e:
            print(f"Error reading types from {file_path}: {e}", file=sys.stderr)
            if args.verbose:
                import traceback

                traceback.print_exc()

    return 0
