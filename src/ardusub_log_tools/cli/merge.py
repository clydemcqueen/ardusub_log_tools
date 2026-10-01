"""
ASL 2.0: 'merge' verb implementation.
"""

from __future__ import annotations

import argparse
import os
import sys

from ardusub_log_tools.backends.dataflash import ALL_MSG_TYPES, DataflashLogReader
from ardusub_log_tools.backends.mcap import McapLogReader
from ardusub_log_tools.backends.telemetry import TelemetryLogReader
from ardusub_log_tools.core import util
from ardusub_log_tools.core.file_reader import FileReader
from ardusub_log_tools.core.presets import resolve_types
from ardusub_log_tools.core.segment_reader import (
    SegmentReader,
    build_segment_name,
    parse_segment,
    parse_segment_json,
)


def run_merge(args: argparse.Namespace) -> int:
    """Execute the 'merge' command across supported log files."""
    files = util.expand_path(args.paths, args.recurse, [".tlog", ".BIN", ".mcap"])
    if not files:
        print("No matching log files found (.BIN, .tlog, .mcap).")
        return 1

    print(f"Processing {len(files)} file(s) for 'merge'")

    limit = args.limit if args.limit is not None else 100_000_000
    raw = not getattr(args, "filter_bad_gps", False)

    for file_path in files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        print("------------------------------------------------------------")
        print(f"Reading {file_path}")

        types = resolve_types(args.types, ext, args.all)
        target_path = file_path
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
            target_path = os.path.join(args.output_dir, os.path.basename(file_path))

        try:
            if ext_lower == ".bin":
                bin_types = types if types is not None else list(ALL_MSG_TYPES)
                reader = DataflashLogReader(
                    file_path,
                    bin_types,
                    max_msgs=limit,
                    max_rows=limit,
                    verbose=args.verbose,
                    raw=raw,
                    start=-1.0,
                    stop=-1.0,
                )
                reader.read()
                reader.infile = target_path
                reader.write_merged_csv_file()

            elif ext_lower == ".tlog":
                segments = []
                if getattr(args, "segments", None) is not None:
                    segments = parse_segment_json(args.segments)
                elif getattr(args, "keep", None) is not None:
                    segments = [parse_segment(k) for k in args.keep]

                if segments:
                    for segment in segments:
                        f_reader = FileReader(file_path, types)
                        s_reader = SegmentReader(segment, f_reader, types)
                        t_reader = TelemetryLogReader(
                            s_reader,
                            max_msgs=limit,
                            max_rows=limit,
                            verbose=args.verbose,
                            sysid=args.sysid,
                            compid=args.compid,
                            system_time=args.system_time,
                            split_source=args.split_source,
                            raw=raw,
                        )
                        if args.output_dir:
                            t_reader.infile = os.path.join(args.output_dir, os.path.basename(s_reader.name))
                        t_reader.read_tlog()
                        if args.rate:
                            t_reader.add_rate_field()
                        t_reader.write_merged_csv_file()
                else:
                    f_reader = FileReader(file_path, types)
                    t_reader = TelemetryLogReader(
                        f_reader,
                        max_msgs=limit,
                        max_rows=limit,
                        verbose=args.verbose,
                        sysid=args.sysid,
                        compid=args.compid,
                        system_time=args.system_time,
                        split_source=args.split_source,
                        raw=raw,
                    )
                    t_reader.infile = target_path
                    t_reader.read_tlog()
                    if args.rate:
                        t_reader.add_rate_field()
                    t_reader.write_merged_csv_file()

            elif ext_lower == ".mcap":
                segments = []
                if getattr(args, "segments", None) is not None:
                    segments = parse_segment_json(args.segments)
                elif getattr(args, "keep", None) is not None:
                    segments = [parse_segment(k) for k in args.keep]

                if segments:
                    for segment in segments:
                        seg_prefix = build_segment_name(target_path, segment.name) + ".mcap"
                        m_reader = McapLogReader(
                            file_path,
                            types=types,
                            max_msgs=limit,
                            verbose=args.verbose,
                            sysid=args.sysid,
                            compid=args.compid,
                            system_time=args.system_time,
                            split_source=args.split_source,
                            raw=raw,
                            segment=segment,
                            max_rows=limit,
                        )
                        m_reader.infile = seg_prefix
                        m_reader.read_mcap()
                        if args.rate:
                            for tbl in m_reader.tables.values():
                                if hasattr(tbl, "add_rate_field"):
                                    tbl.add_rate_field()
                        m_reader.write_merged_csv_file()
                else:
                    m_reader = McapLogReader(
                        file_path,
                        types=types,
                        max_msgs=limit,
                        verbose=args.verbose,
                        sysid=args.sysid,
                        compid=args.compid,
                        system_time=args.system_time,
                        split_source=args.split_source,
                        raw=raw,
                        max_rows=limit,
                    )
                    m_reader.infile = target_path
                    m_reader.read_mcap()
                    if args.rate:
                        for tbl in m_reader.tables.values():
                            if hasattr(tbl, "add_rate_field"):
                                tbl.add_rate_field()
                    m_reader.write_merged_csv_file()

            else:
                print(f"Unsupported file format: {ext}")
                continue

        except Exception as e:
            print(f"Error merging {file_path}: {e}", file=sys.stderr)
            if args.verbose:
                import traceback

                traceback.print_exc()
            return 1

    return 0
