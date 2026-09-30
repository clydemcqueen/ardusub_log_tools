"""
ASL 2.0: 'map' verb implementation.
"""

from __future__ import annotations

import argparse
import os
import sys

import util
from ardusub_log_tools.core.output import resolve_outfile_name


def run_map(args: argparse.Namespace) -> int:
    """Build interactive Leaflet HTML maps from GPS coordinates across .BIN, .tlog, and .mcap."""
    files = util.expand_path(args.paths, args.recurse, [".tlog", ".BIN", ".mcap"])
    if not files:
        print("No matching log files found (.BIN, .tlog, .mcap).")
        return 1

    print(f"Processing {len(files)} file(s) for 'map'")

    center = [args.lat, args.lon]
    zoom = args.zoom
    hdop_max = args.max_hdop
    selected_sources = [s.strip() for s in args.sources.split(",")] if args.sources else None

    for file_path in files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        outfile = resolve_outfile_name(file_path, suffix="_map", ext=".html", output_dir=args.output_dir)

        print("------------------------------------------------------------")
        print(f"Generating map for {file_path} -> {outfile}")

        try:
            if ext_lower == ".bin":
                from BIN_map_maker import GPS_MSG_TYPES, build_map_from_BIN
                from segment_reader import choose_reader_list

                # Temporary args namespace for choose_reader_list
                sub_args = argparse.Namespace(
                    path=[file_path],
                    recurse=False,
                    keep=args.keep,
                    segments=args.segments,
                    all=True,
                )
                readers = choose_reader_list(sub_args, GPS_MSG_TYPES, ext=".BIN")
                for reader in readers:
                    build_map_from_BIN(reader, outfile, args.verbose, center, zoom, hdop_max)

            elif ext_lower == ".tlog":
                from segment_reader import choose_reader_list
                from tlog_map_maker import GPS_MSG_TYPES, build_map_from_tlog

                sub_args = argparse.Namespace(
                    path=[file_path],
                    recurse=False,
                    keep=args.keep,
                    segments=args.segments,
                    all=True,
                    blueos=False,
                    qgc=False,
                )
                readers = choose_reader_list(sub_args, GPS_MSG_TYPES, ext=".tlog")
                for reader in readers:
                    build_map_from_tlog(reader, outfile, args.verbose, center, zoom, hdop_max)

            elif ext_lower == ".mcap":
                from mcap_map_maker import build_map_from_mcap

                build_map_from_mcap(
                    file_path,
                    outfile,
                    verbose=args.verbose,
                    center=center,
                    zoom=zoom,
                    hdop_max=hdop_max,
                    selected_sources=selected_sources,
                )

            else:
                print(f"Unsupported format for map: {ext}")
                continue

            print(f"Wrote {outfile}")

        except Exception as e:
            print(f"Error generating map for {file_path}: {e}", file=sys.stderr)
            if args.verbose:
                import traceback

                traceback.print_exc()
            return 1

    return 0
