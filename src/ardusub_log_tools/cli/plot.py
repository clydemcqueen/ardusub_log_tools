"""
ASL 2.0: 'plot' verb implementation.
"""

from __future__ import annotations

import argparse
import os
import sys

import util
from ardusub_log_tools.core.output import resolve_outfile_name


def run_plot(args: argparse.Namespace) -> int:
    """Generate 2D trajectory or sensor profile visualization plots."""
    plot_type = getattr(args, "plot_type", None)
    if not plot_type:
        print("Error: No plot type specified (e.g. local, altitude, transect).", file=sys.stderr)
        return 1

    fmt = getattr(args, "format", "pdf")
    ext_out = f".{fmt}"
    show = getattr(args, "show", False)
    dvl = getattr(args, "dvl", False)

    if plot_type == "local":
        files = util.expand_path(args.paths, getattr(args, "recurse", False), [".tlog", ".BIN", ".mcap"])
        if not files:
            print("No matching log files found (.BIN, .tlog, .mcap).")
            return 1

        print(f"Processing {len(files)} file(s) for 'plot local'")
        for file_path in files:
            _, ext = os.path.splitext(file_path)
            ext_lower = ext.lower()
            print("------------------------------------------------------------")
            print(f"Plotting local trajectory for {file_path}")

            try:
                if ext_lower == ".bin":
                    from BIN_plot_local import MSG_TYPES as BIN_MSG_TYPES
                    from BIN_plot_local import plot_bin_local
                    from segment_reader import choose_reader_list

                    # has_segments = bool(getattr(args, "keep", None) or getattr(args, "segments", None))
                    sub_args = argparse.Namespace(
                        path=[file_path],
                        recurse=False,
                        keep=getattr(args, "keep", None),
                        segments=getattr(args, "segments", None),
                        all=False,
                    )
                    readers = choose_reader_list(sub_args, BIN_MSG_TYPES, ext=".BIN")
                    for reader in readers:
                        seg_label = f"_{reader._segment.name}" if hasattr(reader, "_segment") else ""
                        outfile = (
                            None
                            if show
                            else resolve_outfile_name(
                                file_path, suffix=f"{seg_label}_local", ext=ext_out, output_dir=args.output_dir
                            )
                        )
                        plot_bin_local(reader, outfile=outfile, dvl=dvl, show=show)

                elif ext_lower == ".tlog":
                    from segment_reader import choose_reader_list
                    from tlog_plot_local import MSG_TYPES as TLOG_MSG_TYPES
                    from tlog_plot_local import plot_local_position

                    # has_segments = bool(getattr(args, "keep", None) or getattr(args, "segments", None))
                    sub_args = argparse.Namespace(
                        path=[file_path],
                        recurse=False,
                        keep=getattr(args, "keep", None),
                        segments=getattr(args, "segments", None),
                        all=False,
                        blueos=False,
                        qgc=False,
                    )
                    readers = choose_reader_list(sub_args, TLOG_MSG_TYPES, ext=".tlog")
                    for reader in readers:
                        seg_label = f"_{reader._segment.name}" if hasattr(reader, "_segment") else ""
                        outfile = (
                            None
                            if show
                            else resolve_outfile_name(
                                file_path, suffix=f"{seg_label}_local", ext=ext_out, output_dir=args.output_dir
                            )
                        )
                        plot_local_position(reader, outfile=outfile, dvl=dvl, show=show)

                elif ext_lower == ".mcap":
                    from mcap_plot_local import plot_mcap_local

                    outfile = (
                        None
                        if show
                        else resolve_outfile_name(file_path, suffix="_local", ext=ext_out, output_dir=args.output_dir)
                    )
                    plot_mcap_local(file_path, outfile=outfile, dvl=dvl, show=show)

                else:
                    print(f"Unsupported file format for plot local: {ext}")
                    continue

            except Exception as e:
                print(f"Error plotting {file_path}: {e}", file=sys.stderr)
                if getattr(args, "verbose", False):
                    import traceback

                    traceback.print_exc()
                return 1

    elif plot_type == "altitude":
        files = util.expand_path(args.paths, getattr(args, "recurse", False), [".BIN"])
        if not files:
            print("No matching .BIN files found for 'plot altitude'.")
            return 1

        print(f"Processing {len(files)} file(s) for 'plot altitude'")
        for file_path in files:
            print("------------------------------------------------------------")
            print(f"Plotting altitude for {file_path}")

            try:
                from BIN_graph_alt import process_reader
                from file_reader import FileReader

                reader = FileReader(file_path, ["AHR2", "XKF1", "BARO", "ORGN", "POS"])
                outfile = (
                    None
                    if show
                    else resolve_outfile_name(file_path, suffix="_altitude", ext=ext_out, output_dir=args.output_dir)
                )
                process_reader(reader, outfile=outfile, show=show)

            except Exception as e:
                print(f"Error plotting altitude for {file_path}: {e}", file=sys.stderr)
                if getattr(args, "verbose", False):
                    import traceback

                    traceback.print_exc()
                return 1

    elif plot_type == "transect":
        files = util.expand_path(args.paths, getattr(args, "recurse", False), [".BIN"])
        if not files:
            print("No matching .BIN files found for 'plot transect'.")
            return 1

        print(f"Processing {len(files)} file(s) for 'plot transect'")
        for file_path in files:
            print("------------------------------------------------------------")
            print(f"Plotting transect for {file_path}")

            try:
                from BIN_plot_transect import load_data, plot_transect
                from segment_reader import choose_reader_list

                sub_args = argparse.Namespace(
                    path=[file_path],
                    recurse=False,
                    keep=getattr(args, "keep", None),
                    segments=getattr(args, "segments", None),
                    all=False,
                )
                readers = choose_reader_list(sub_args, None, ext=".BIN")
                for reader in readers:
                    dfs = load_data(reader)
                    if dfs["TRNS"].empty:
                        print(f"[{reader.name}] No TRNS table found in log.")
                        continue

                    seg_label = f"_{reader._segment.name}" if hasattr(reader, "_segment") else ""
                    outfile = (
                        None
                        if show
                        else resolve_outfile_name(
                            file_path, suffix=f"{seg_label}_transect", ext=ext_out, output_dir=args.output_dir
                        )
                    )
                    plot_transect(dfs, pdf_outfile=outfile, show_plot=show, reader_name=reader.name)

            except Exception as e:
                print(f"Error plotting transect for {file_path}: {e}", file=sys.stderr)
                if getattr(args, "verbose", False):
                    import traceback

                    traceback.print_exc()
                return 1

    else:
        print(f"Unknown plot subcommand: {plot_type}", file=sys.stderr)
        return 1

    return 0
