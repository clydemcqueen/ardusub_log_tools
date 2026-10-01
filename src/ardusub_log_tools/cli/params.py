"""
ASL 2.0: 'params' verb implementation.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys

from pymavlink import mavutil

from ardusub_log_tools.backends.dataflash import DataFlashParams
from ardusub_log_tools.backends.dataflash import print_changes as print_bin_changes
from ardusub_log_tools.backends.telemetry import TelemetryLogParam
from ardusub_log_tools.backends.telemetry import print_changes as print_tlog_changes
from ardusub_log_tools.core import util
from ardusub_log_tools.core.mcap_events import extract_mcap_params
from ardusub_log_tools.core.output import resolve_outfile_name


def _matches_patterns(param_name: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatch(param_name, pat) for pat in patterns)


def _process_bin_params(file_path: str, patterns: list[str] | None, changes_mode: bool, outfile: str):
    mlog = mavutil.mavlink_connection(file_path, robust_parsing=False, dialect="ardupilotmega")
    current_file = DataFlashParams(None)

    while (msg := mlog.recv_match(blocking=False, type=["PARM"])) is not None:
        p_name = msg.Name
        if _matches_patterns(p_name, patterns):
            current_file.add(msg)

    if not changes_mode:
        current_file.write_params_file(outfile)
    return current_file


def _process_tlog_params(file_path: str, patterns: list[str] | None, changes_mode: bool, outfile: str):
    param_reader = TelemetryLogParam(file_path, print_intra_file_changes=changes_mode, params=patterns)
    if patterns:
        param_reader.params = {k: v for k, v in param_reader.params.items() if _matches_patterns(k, patterns)}

    if not changes_mode:
        param_reader.write_params_file(outfile)
    return param_reader


def _process_mcap_params(file_path: str, patterns: list[str] | None, changes_mode: bool, outfile: str):
    params, changes = extract_mcap_params(file_path, patterns=patterns)
    if changes_mode:
        for ts, old_p, new_p in changes:
            print(f"[{ts:10.2f}] {old_p.id}: {old_p.value_str()} -> {new_p.value_str()}")
    else:
        if not params:
            print(f"No matching parameters found in {file_path}")
            return None

        with open(outfile, "w", encoding="utf-8") as f:
            f.write("# Onboard parameters for Vehicle 1\n#\n# Stack: ArduPilot\n# Vehicle: Sub\n#\n")
            f.write("# Vehicle-Id\tComponent-Id\tName\tValue\tType\n")
            for _, p in sorted(params.items()):
                cmt = p.comment()
                if cmt:
                    f.write(f"1\t1\t{p.id}\t{p.value_str()}\t{p.type}\t# {cmt}\n")
                else:
                    f.write(f"1\t1\t{p.id}\t{p.value_str()}\t{p.type}\n")
        print(f"Wrote {len(params)} parameters to {outfile}")
    return params


def run_params(args: argparse.Namespace) -> int:
    """Extract vehicle parameters and track parameter modifications across supported log files."""
    files = util.expand_path(args.paths, getattr(args, "recurse", False), [".tlog", ".BIN", ".mcap"])
    if not files:
        print("No matching log files found (.BIN, .tlog, .mcap).")
        return 1

    patterns = [p.strip() for p in args.names.split(",")] if getattr(args, "names", None) else None
    changes_mode = getattr(args, "changes", False)

    print(f"Processing {len(files)} file(s) for 'params'")

    prev_obj = None
    for file_path in files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        outfile = resolve_outfile_name(file_path, suffix="_params", ext=".params", output_dir=args.output_dir)
        print("------------------------------------------------------------")
        print(f"Reading parameters from {file_path}")

        try:
            if ext_lower == ".bin":
                curr_obj = _process_bin_params(file_path, patterns, changes_mode, outfile)
                if changes_mode and prev_obj is not None:
                    print_bin_changes(prev_obj, curr_obj)
                prev_obj = curr_obj

            elif ext_lower == ".tlog":
                curr_obj = _process_tlog_params(file_path, patterns, changes_mode, outfile)
                if changes_mode and prev_obj is not None:
                    print_tlog_changes(prev_obj, curr_obj)
                prev_obj = curr_obj

            elif ext_lower == ".mcap":
                _process_mcap_params(file_path, patterns, changes_mode, outfile)

            else:
                print(f"Unsupported format: {ext}")
                continue

            if not changes_mode and os.path.exists(outfile):
                print(f"Wrote {outfile}")

        except Exception as e:
            print(f"Error processing parameters for {file_path}: {e}", file=sys.stderr)
            if getattr(args, "verbose", False):
                import traceback

                traceback.print_exc()
            return 1

    return 0
