"""
ASL 2.0: 'info' verb implementation.
"""

from __future__ import annotations

import argparse
import os
import sys

from mcap.reader import make_reader

import util
from ardusub_log_tools.core.mcap_events import resolve_enum_value


class McapLogInfo:
    """Extract and display high-level summary and health metadata from an MCAP file."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def read_and_report(self) -> None:
        print(f"Results for {self.file_path}")
        with open(self.file_path, "rb") as f:
            reader = make_reader(f)
            summary = reader.get_summary()
            if not summary:
                print("  No MCAP summary available.")
                return

            stats = summary.statistics
            if stats:
                start_s = stats.message_start_time / 1e9 if stats.message_start_time else 0.0
                end_s = stats.message_end_time / 1e9 if stats.message_end_time else 0.0
                duration_s = end_s - start_s if end_s >= start_s else 0.0
                print(f"  Log span: {util.time_str(start_s)} to {util.time_str(end_s)} ({duration_s:.1f} s)")
                print(f"  Total messages: {stats.message_count}")
                print(f"  Total channels: {stats.channel_count}")
                print(f"  Total schemas:  {stats.schema_count}")

            # Inspect mavlink/out if available
            heartbeat_count = 0
            modes_seen = set()
            critical_events = []

            for _, _, msg in util.iter_mcap_messages(
                self.file_path,
                message_types=["HEARTBEAT", "STATUSTEXT"],
                sys_id=1,
                comp_id=1,
            ):
                m = msg.json.get("message", {})
                mtype = m.get("type")
                if mtype == "HEARTBEAT":
                    heartbeat_count += 1
                    c_mode = m.get("custom_mode")
                    if c_mode is not None:
                        modes_seen.add(c_mode)
                elif mtype == "STATUSTEXT":
                    sev = resolve_enum_value(m.get("severity", 0))
                    text = str(m.get("text", "")).strip()
                    if sev <= 3 and text:  # ERROR, CRITICAL, ALERT, EMERGENCY
                        critical_events.append(text)

            if heartbeat_count > 0:
                print("\n  MAVLink Telemetry (Autopilot 1:1):")
                print(f"    Heartbeats: {heartbeat_count}")
                print(f"    Flight modes: {sorted(list(modes_seen))}")
                if critical_events:
                    print(f"    Warnings/Errors: {len(critical_events)} events logged")
                    for ce in critical_events[:5]:
                        print(f"      - {ce}")
                    if len(critical_events) > 5:
                        print(f"      ... and {len(critical_events) - 5} more")


def run_info(args: argparse.Namespace) -> int:
    """Display high-level log metadata, duration, and hardware health across supported logs."""
    files = util.expand_path(args.paths, getattr(args, "recurse", False), [".tlog", ".BIN", ".mcap"])
    if not files:
        print("No matching log files found (.BIN, .tlog, .mcap).")
        return 1

    print(f"Inspecting {len(files)} file(s) for 'info'")

    for file_path in files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        print("------------------------------------------------------------")

        try:
            if ext_lower == ".bin":
                from BIN_info import DataflashLogInfo

                info = DataflashLogInfo(file_path)
                info.read_and_report()

            elif ext_lower == ".tlog":
                from file_reader import FileReader
                from tlog_info import MSG_TYPES as TLOG_MSG_TYPES
                from tlog_info import TelemetryLogInfo

                reader = FileReader(file_path, TLOG_MSG_TYPES)
                info = TelemetryLogInfo(reader)
                info.read_and_report()

            elif ext_lower == ".mcap":
                info = McapLogInfo(file_path)
                info.read_and_report()

            else:
                print(f"Unsupported format: {ext}")

        except Exception as e:
            print(f"Error inspecting {file_path}: {e}", file=sys.stderr)
            if getattr(args, "verbose", False):
                import traceback

                traceback.print_exc()
            return 1

    return 0
