"""
ASL 2.0: 'messages' verb implementation.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

from pymavlink import mavutil

from ardusub_log_tools.backends.dataflash import LogEvent, decode_error
from ardusub_log_tools.core import util
from ardusub_log_tools.core.mcap_events import iter_mcap_statustext
from ardusub_log_tools.core.output import resolve_outfile_name


def _extract_bin_messages(bin_file: str) -> list[tuple[float, str]]:
    mlog = mavutil.mavlink_connection(bin_file, robust_parsing=False, dialect="ardupilotmega")
    items = []
    while (msg := mlog.recv_match(blocking=False, type=["MSG", "EV", "ERR"])) is not None:
        data = msg.to_dict()
        ts = getattr(msg, "_timestamp", data.get("TimeUS", 0) * 1e-6)
        mtype = msg.get_type()

        if mtype == "MSG":
            items.append((ts, str(data.get("Message", ""))))
        elif mtype == "EV":
            try:
                ev = LogEvent(data.get("Id", 0))
                items.append((ts, f"Event: {ev.name}"))
            except ValueError:
                items.append((ts, f"Event: {data.get('Id', 0)}"))
        elif mtype == "ERR":
            subsys, ecode = decode_error(data.get("Subsys", 0), data.get("ECode", 0))
            items.append((ts, f"Error: Subsys {subsys}, ECode {ecode}"))

    items.sort(key=lambda x: x[0])
    return items


def _extract_tlog_messages(tlog_file: str) -> list[tuple[float, str]]:
    mlog = mavutil.mavlink_connection(tlog_file, robust_parsing=False, dialect="ardupilotmega")
    items = []
    while (msg := mlog.recv_match(blocking=False, type=["STATUSTEXT"])) is not None:
        ts = getattr(msg, "_timestamp", 0.0)
        items.append((ts, str(msg.text)))
    items.sort(key=lambda x: x[0])
    return items


def _extract_mcap_messages(mcap_file: str) -> list[tuple[float, str]]:
    items = []
    for ts, _sev, text in iter_mcap_statustext(mcap_file):
        items.append((ts, text))
    items.sort(key=lambda x: x[0])
    return items


def run_messages(args: argparse.Namespace) -> int:
    """Extract textual logs, operator status announcements, and errors across supported log files."""
    files = util.expand_path(args.paths, getattr(args, "recurse", False), [".tlog", ".BIN", ".mcap"])
    if not files:
        print("No matching log files found (.BIN, .tlog, .mcap).")
        return 1

    summary_mode = getattr(args, "summary", False)

    print(f"Processing {len(files)} file(s) for 'messages'")

    for file_path in files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        outfile = resolve_outfile_name(file_path, suffix="_messages", ext=".txt", output_dir=args.output_dir)
        print("------------------------------------------------------------")
        print(f"Extracting messages from {file_path} -> {outfile}")

        try:
            if ext_lower == ".bin":
                msg_list = _extract_bin_messages(file_path)
            elif ext_lower == ".tlog":
                msg_list = _extract_tlog_messages(file_path)
            elif ext_lower == ".mcap":
                msg_list = _extract_mcap_messages(file_path)
            else:
                print(f"Unsupported format: {ext}")
                continue

            with open(outfile, "w", encoding="utf-8") as f:
                if summary_mode:
                    counts = Counter(m[1] for m in msg_list)
                    for text, count in sorted(counts.items()):
                        f.write(f"{text}: {count}\n")
                else:
                    for ts, text in msg_list:
                        f.write(f"  {ts:10.6f} {text}\n")

            print(f"Wrote {len(msg_list)} message entries to {outfile}")

        except Exception as e:
            print(f"Error extracting messages from {file_path}: {e}", file=sys.stderr)
            if getattr(args, "verbose", False):
                import traceback

                traceback.print_exc()
            return 1

    return 0
