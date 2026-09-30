"""
ASL 2.0: 'split' verb implementation.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys

from pymavlink import mavutil

import util
from ardusub_log_tools.core.output import resolve_outfile_name


def _split_by_mode(args: argparse.Namespace, files: list[str]) -> int:
    from split_by_mode import get_mode_mapping, process_bin, process_tlog

    mapping = get_mode_mapping()
    requested_modes = None

    if args.mode:
        requested_modes = set()
        for m in args.mode:
            m_clean = m.strip()
            if m_clean.upper() in mapping:
                requested_modes.add(mapping[m_clean.upper()])
            else:
                try:
                    requested_modes.add(int(m_clean))
                except ValueError:
                    print(f"Warning: Unknown mode '{m_clean}', ignoring.", file=sys.stderr)

    for file_path in files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        if ext_lower == ".bin":
            process_bin(file_path, requested_modes, output_dir=args.output_dir)
        elif ext_lower == ".tlog":
            process_tlog(file_path, requested_modes, output_dir=args.output_dir)
        else:
            print(f"Skipping {file_path}: unsupported format {ext}")

    return 0


def _split_by_segments(args: argparse.Namespace, files: list[str]) -> int:
    from segment_reader import parse_segment_args

    try:
        segments = parse_segment_args(args)
    except Exception as e:
        print(f"Error parsing segment arguments: {e}", file=sys.stderr)
        return 1

    if not segments:
        print("No segments defined to split.", file=sys.stderr)
        return 1

    print(f"Splitting {len(files)} file(s) across {len(segments)} segment(s)")

    for file_path in files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        print("------------------------------------------------------------")
        print(f"Splitting {file_path} into segments")

        for seg in segments:
            seg_suffix = f"_seg_{seg.name}"
            outfile_name = resolve_outfile_name(file_path, suffix=seg_suffix, ext=ext, output_dir=args.output_dir)
            print(f"Extracting segment '{seg.name}' ({seg.start:.1f} -> {seg.end:.1f}) -> {outfile_name}")

            mlog = mavutil.mavlink_connection(file_path, robust_parsing=False, dialect="ardupilotmega")
            count = 0

            if ext_lower == ".bin":
                fmt_msgs = []
                with open(outfile_name, "wb") as outfile:
                    while True:
                        msg = mlog.recv_match(blocking=False)
                        if msg is None:
                            break
                        msg_type = msg.get_type()
                        if msg_type == "FMT":
                            fmt_msgs.append(msg)
                            outfile.write(msg.get_msgbuf())
                            continue

                        ts = getattr(msg, "_timestamp", 0.0)
                        if seg.start <= ts <= seg.end:
                            outfile.write(msg.get_msgbuf())
                            count += 1
                        elif ts > seg.end:
                            # In chronological logs, can stop early
                            pass

                print(f"Wrote {count} messages to {outfile_name}")

            elif ext_lower == ".tlog":
                with open(outfile_name, "wb") as outfile:
                    while True:
                        msg = mlog.recv_match(blocking=False)
                        if msg is None:
                            break

                        ts = getattr(msg, "_timestamp", 0.0)
                        if seg.start <= ts <= seg.end:
                            header = struct.pack(">Q", int(ts * 1e6))
                            outfile.write(header)
                            outfile.write(msg.get_msgbuf())
                            count += 1
                        elif ts > seg.end:
                            pass

                print(f"Wrote {count} messages to {outfile_name}")

            else:
                print(f"Unsupported format for segment splitting: {ext}")
                break

    return 0


def run_split(args: argparse.Namespace) -> int:
    """Execute the 'split' command across supported log files."""
    files = util.expand_path(args.paths, getattr(args, "recurse", False), [".tlog", ".BIN"])
    if not files:
        print("No matching log files found (.BIN, .tlog).")
        return 1

    if args.mode is not None:
        return _split_by_mode(args, files)
    elif args.segments or args.keep:
        return _split_by_segments(args, files)
    else:
        print("Error: Either --mode or --segments/--keep must be specified.", file=sys.stderr)
        return 1
