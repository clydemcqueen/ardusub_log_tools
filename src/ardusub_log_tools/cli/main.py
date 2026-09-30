#!/usr/bin/env python3
"""
ASL: ArduSub Log Tools CLI
==========================
Unified command-line interface for analyzing ArduSub and BlueOS vehicle logs (.BIN, .tlog, .mcap).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repository root is on sys.path for Phase 1 bridges to existing modules
_REPO_ROOT = str(Path(__file__).resolve().parents[3])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ardusub_log_tools import __version__


def create_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser for the asl CLI."""
    parser = argparse.ArgumentParser(
        prog="asl",
        description="ASL: Unified command-line interface for ArduSub and BlueOS vehicle logs (.BIN, .tlog, .mcap).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Shared parent parsers for global flags
    common_parent = argparse.ArgumentParser(add_help=False)
    common_parent.add_argument(
        "-r", "--recurse", action="store_true", help="Recursively scan directories for log files"
    )
    common_parent.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging output")
    common_parent.add_argument(
        "-o", "--output-dir", help="Destination directory for generated files (default: alongside inputs)"
    )

    segment_parent = argparse.ArgumentParser(add_help=False)
    segment_parent.add_argument(
        "-s",
        "--segments",
        help="Process segments specified in a JSON file or inline string (compatible with utc_plan.json)",
    )
    segment_parent.add_argument(
        "-k",
        "--keep",
        action="append",
        help="Process specific time segment(s): 'start,end[,name]'",
    )

    subparsers = parser.add_subparsers(dest="verb", title="verbs", metavar="<verb>")

    # -------------------------------------------------------------------------
    # Core Verb: explode
    # -------------------------------------------------------------------------
    p_explode = subparsers.add_parser(
        "explode",
        parents=[common_parent, segment_parent],
        help="Extract message types or channels into separate CSV files",
        description="Extract individual message types/topics into per-type CSV files (<base>_asl_[<seg>_]<type>.csv).",
    )
    type_group_exp = p_explode.add_mutually_exclusive_group(required=True)
    type_group_exp.add_argument(
        "--types",
        help="Comma-separated list of message types or group presets (e.g., 'GPS,ATT', 'ekf', 'nav', 'wl_dvl')",
    )
    type_group_exp.add_argument(
        "--all",
        action="store_true",
        help="Extract all message types discovered in the log file",
    )
    p_explode.add_argument(
        "--rate",
        action="store_true",
        help="Append a '<type>.rate' column containing calculated message rate (Hz)",
    )
    p_explode.add_argument(
        "--filter-bad-gps",
        action="store_true",
        help="Filter out invalid GPS fixes (fix_type < 2 or (0,0)). Default is raw unfiltered output.",
    )
    p_explode.add_argument(
        "--sysid",
        type=int,
        help="Select MAVLink source system ID (MAVLink/MCAP; ignored for .BIN)",
    )
    p_explode.add_argument(
        "--compid",
        type=int,
        help="Select MAVLink source component ID (MAVLink/MCAP; ignored for .BIN)",
    )
    p_explode.add_argument(
        "--split-source",
        action="store_true",
        help="Split messages into separate CSVs by source (sysid, compid)",
    )
    p_explode.add_argument(
        "--system-time",
        action="store_true",
        help="Use vehicle time_boot_ms/time_unix_usec instead of transport/log time",
    )
    p_explode.add_argument(
        "--limit",
        "--max-rows",
        dest="limit",
        type=int,
        default=None,
        help="Optional row limit for quick inspection (default: full log, no arbitrary cap)",
    )
    p_explode.add_argument("paths", nargs="+", help="Log files or directories to process")

    # -------------------------------------------------------------------------
    # Core Verb: merge
    # -------------------------------------------------------------------------
    p_merge = subparsers.add_parser(
        "merge",
        parents=[common_parent, segment_parent],
        help="Stitch message types into a single wide time-aligned CSV",
        description="Merge and forward-fill multiple message types into a wide CSV (<base>_asl_[<seg>_]merged.csv).",
    )
    type_group_mrg = p_merge.add_mutually_exclusive_group(required=True)
    type_group_mrg.add_argument(
        "--types",
        help="Comma-separated list of message types or group presets (e.g., 'GPS,ATT', 'ekf', 'nav')",
    )
    type_group_mrg.add_argument(
        "--all",
        action="store_true",
        help="Merge all message types discovered in the log file",
    )
    p_merge.add_argument(
        "--rate",
        action="store_true",
        help="Append calculated message rate columns (<type>.rate)",
    )
    p_merge.add_argument(
        "--filter-bad-gps",
        action="store_true",
        help="Filter out invalid GPS fixes (fix_type < 2 or (0,0)). Default is raw unfiltered output.",
    )
    p_merge.add_argument(
        "--sysid",
        type=int,
        help="Select MAVLink source system ID (MAVLink/MCAP; ignored for .BIN)",
    )
    p_merge.add_argument(
        "--compid",
        type=int,
        help="Select MAVLink source component ID (MAVLink/MCAP; ignored for .BIN)",
    )
    p_merge.add_argument(
        "--split-source",
        action="store_true",
        help="Split messages by source (sysid, compid)",
    )
    p_merge.add_argument(
        "--system-time",
        action="store_true",
        help="Use vehicle time_boot_ms/time_unix_usec instead of transport/log time",
    )
    p_merge.add_argument(
        "--limit",
        "--max-rows",
        dest="limit",
        type=int,
        default=None,
        help="Optional row limit for quick inspection (default: full log, no arbitrary cap)",
    )
    p_merge.add_argument("paths", nargs="+", help="Log files or directories to process")

    # -------------------------------------------------------------------------
    # Core Verb: types
    # -------------------------------------------------------------------------
    p_types = subparsers.add_parser(
        "types",
        parents=[common_parent],
        help="Scan and report message types, counts, and delivery rates",
        description="Print an ASCII table to stdout detailing message types, counts, rates, and descriptions.",
    )
    p_types.add_argument("paths", nargs="+", help="Log files or directories to inspect")

    # -------------------------------------------------------------------------
    # Core Verb: timeline
    # -------------------------------------------------------------------------
    p_timeline = subparsers.add_parser(
        "timeline",
        parents=[common_parent, segment_parent],
        help="Generate a chronological mission and vehicle event timeline",
        description="Extract modes, arming, commands, failsafes, and EKF status into <base>_asl_timeline.txt.",
    )
    p_timeline.add_argument(
        "--no-ansi",
        action="store_true",
        help="Disable ANSI color codes in the generated report (enabled by default)",
    )
    p_timeline.add_argument(
        "--tz",
        default="UTC",
        help="Display event timestamps in the specified timezone (default: UTC)",
    )
    p_timeline.add_argument("paths", nargs="+", help="Log files or directories to process")

    # -------------------------------------------------------------------------
    # Core Verb: messages
    # -------------------------------------------------------------------------
    p_messages = subparsers.add_parser(
        "messages",
        parents=[common_parent],
        help="Extract operator text messages, event codes, and error definitions",
        description="Extract textual messages and error codes chronologically into <base>_asl_messages.txt.",
    )
    p_messages.add_argument(
        "--summary",
        action="store_true",
        help="Write a frequency count of unique messages instead of the chronological event stream",
    )
    p_messages.add_argument("paths", nargs="+", help="Log files or directories to process")

    # -------------------------------------------------------------------------
    # Core Verb: params
    # -------------------------------------------------------------------------
    p_params = subparsers.add_parser(
        "params",
        parents=[common_parent],
        help="Extract vehicle parameters and track parameter modifications",
        description="Export vehicle parameter state to <base>_asl_params.params or report modifications.",
    )
    p_params.add_argument(
        "--changes",
        action="store_true",
        help="Report parameter modifications that occurred mid-flight or across logs instead of dumping snapshot",
    )
    p_params.add_argument(
        "--names",
        help="Filter parameters by exact name or wildcard pattern (e.g. 'EK3_*' or 'SURF_DEPTH,BATT_CAPACITY')",
    )
    p_params.add_argument("paths", nargs="+", help="Log files or directories to process")

    # -------------------------------------------------------------------------
    # Core Verb: map
    # -------------------------------------------------------------------------
    p_map = subparsers.add_parser(
        "map",
        parents=[common_parent, segment_parent],
        help="Build interactive Leaflet HTML maps from GPS/position tracks",
        description="Generate an interactive Leaflet HTML map (<base>_asl_map.html) with vehicle trajectories.",
    )
    p_map.add_argument(
        "--sources",
        help="Comma-separated list of trajectory sources to include (default: all available GPS, EKF, UGPS)",
    )
    p_map.add_argument(
        "--max-hdop",
        type=float,
        default=2.0,
        help="Filter out GPS fixes with HDOP > max (default: 2.0)",
    )
    p_map.add_argument("--zoom", type=int, default=18, help="Initial Leaflet map zoom level (default: 18)")
    p_map.add_argument("--lat", type=float, help="Center latitude (default: mean of plotted coordinates)")
    p_map.add_argument("--lon", type=float, help="Center longitude (default: mean of plotted coordinates)")
    p_map.add_argument("paths", nargs="+", help="Log files or directories to process")

    # -------------------------------------------------------------------------
    # Core Verb: plot
    # -------------------------------------------------------------------------
    p_plot = subparsers.add_parser(
        "plot",
        help="Generate 2D trajectory or sensor profile visualization plots",
        description="Plot local NED, altitude, or transect profiles to PDF/PNG.",
    )
    plot_subparsers = p_plot.add_subparsers(dest="plot_type", title="plot types", metavar="<plot-type>", required=True)

    plot_common = argparse.ArgumentParser(add_help=False, parents=[common_parent, segment_parent])
    plot_common.add_argument(
        "--format",
        choices=["pdf", "png"],
        default="pdf",
        help="Output graphic format (default: pdf)",
    )
    plot_common.add_argument(
        "--show",
        action="store_true",
        help="Display plot interactively on screen instead of saving to file",
    )

    p_plot_local = plot_subparsers.add_parser(
        "local",
        parents=[plot_common],
        help="Plot local NED X/Y trajectory (<base>_asl_local.pdf)",
    )
    p_plot_local.add_argument(
        "--dvl",
        action="store_true",
        help="Include DVL dead-reckoning trajectory (VISO)",
    )
    p_plot_local.add_argument("paths", nargs="+", help="Log files or directories to plot")

    plot_subparsers.add_parser(
        "altitude",
        parents=[plot_common],
        help="Plot barometer vs depth vs rangefinder over time (<base>_asl_altitude.pdf)",
    ).add_argument("paths", nargs="+", help="Log files or directories to plot")

    plot_subparsers.add_parser(
        "transect",
        parents=[plot_common],
        help="Plot transect path, SURFTRAK consistency, and terrain tracking (<base>_asl_transect.pdf)",
    ).add_argument("paths", nargs="+", help="Log files or directories to plot")

    # -------------------------------------------------------------------------
    # Core Verb: info
    # -------------------------------------------------------------------------
    p_info = subparsers.add_parser(
        "info",
        parents=[common_parent],
        help="Display high-level log metadata, duration, and hardware health",
        description="Display vehicle firmware, time bounds, duration, and subsystem statistics.",
    )
    p_info.add_argument("paths", nargs="+", help="Log files or directories to inspect")

    # -------------------------------------------------------------------------
    # Core Verb: split
    # -------------------------------------------------------------------------
    p_split = subparsers.add_parser(
        "split",
        parents=[common_parent],
        help="Split log into separate sub-logs based on flight mode or time segments",
        description="Split a log file by flight mode or time windows into smaller log files.",
    )
    split_group = p_split.add_mutually_exclusive_group(required=True)
    split_group.add_argument(
        "--mode",
        nargs="*",
        metavar="MODE",
        help="Split log into sub-logs by flight mode (e.g. SURFTRAK MANUAL; default: all active modes)",
    )
    split_group.add_argument(
        "--segments",
        help="Split log by segments in a JSON file (utc_plan.json or segment list)",
    )
    split_group.add_argument(
        "--keep",
        action="append",
        help="Split log by time segment(s): 'start,end[,name]'",
    )
    p_split.add_argument("paths", nargs="+", help="Log files to split")

    # -------------------------------------------------------------------------
    # Core Verb: dive
    # -------------------------------------------------------------------------
    p_dive = subparsers.add_parser(
        "dive",
        help="Analyze dive directory, establish boot cycles, and generate dive_logs.json",
        description="Comprehensive dive correspondence tool; establishes boots, rtc_shift_s, and file pairings.",
    )
    p_dive.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Target dive directory (default: current directory '.')",
    )
    p_dive.add_argument(
        "-o",
        "--output",
        help="Custom output file destination (default: <directory>/dive_logs.json)",
    )
    p_dive.add_argument(
        "--no-opt",
        action="store_true",
        help="Disable depth-signal cross-correlation optimization",
    )
    p_dive.add_argument(
        "--force",
        action="store_true",
        help="Force re-generation even if dive_logs.json already exists",
    )
    p_dive.add_argument("-v", "--verbose", action="store_true", help="Print verbose scanning logs")

    # -------------------------------------------------------------------------
    # Top-Level Diagnostic Verbs
    # -------------------------------------------------------------------------
    p_batt = subparsers.add_parser(
        "battery",
        parents=[common_parent],
        help="Analyze battery usage, power consumption, and tether/outland usage",
        description="Inspect battery health and power profiles (<base>_asl_battery.pdf).",
    )
    p_batt.add_argument("--terse", action="store_true", help="Concise report comparing Outland power vs battery")
    p_batt.add_argument("--plot", action="store_true", help="Plot energy and power curves to PDF")
    p_batt.add_argument("paths", nargs="+", help="Log files or directories to inspect")

    p_mission = subparsers.add_parser(
        "mission",
        parents=[common_parent, segment_parent],
        help="Dump uploaded waypoints, geo-fences, and rally items",
        description="Parse and print MISSION_* messages from telemetry logs.",
    )
    p_mission.add_argument("paths", nargs="+", help="Log files or directories to inspect")

    p_ekf = subparsers.add_parser(
        "ekf",
        parents=[common_parent],
        help="Report on EKF3 internal status, innovation consistency, and source sets",
        description="Detailed EKF3 health and innovation consistency diagnostics.",
    )
    p_ekf.add_argument("paths", nargs="+", help="Log files or directories to inspect")

    p_compass = subparsers.add_parser(
        "compass",
        parents=[common_parent],
        help="Analyze 3D magnetic calibration, interference, and gyro bias stability",
        description="Diagnostics for compass offsets, mag interference, and gyro bias stats.",
    )
    p_compass.add_argument("paths", nargs="+", help="Log files or directories to inspect")

    p_ugps = subparsers.add_parser(
        "ugps",
        parents=[common_parent],
        help="Report WaterLinked acoustic locator diagnostics and positioning stats",
        description="Diagnostic report for WaterLinked UGPS acoustic telemetry.",
    )
    p_ugps.add_argument("paths", nargs="+", help="MCAP log files or directories to inspect")

    # -------------------------------------------------------------------------
    # Format-Specific Subcommands: asl mcap
    # -------------------------------------------------------------------------
    p_mcap = subparsers.add_parser(
        "mcap",
        help="Format-specific tools for BlueOS/Foxglove MCAP files",
        description="Operations specific to MCAP container files (video extraction, channel listing, tlog diff).",
    )
    mcap_subparsers = p_mcap.add_subparsers(dest="mcap_cmd", title="mcap commands", metavar="<mcap-cmd>", required=True)

    p_mc_chan = mcap_subparsers.add_parser("channels", help="List MCAP channels, schemas, and message rates")
    p_mc_chan.add_argument("paths", nargs="+", help="MCAP file(s) to inspect")

    p_mc_strip = mcap_subparsers.add_parser("strip-video", help="Strip H.264 video chunks to produce lightweight MCAPs")
    p_mc_strip.add_argument(
        "--in-place",
        action="store_true",
        help="Strip video in-place: original renamed to <stem>_video.mcap, stripped file written to <stem>.mcap",
    )
    p_mc_strip.add_argument("-r", "--recurse", action="store_true", help="Recursively scan directories")
    p_mc_strip.add_argument("paths", nargs="+", help="MCAP file(s) or directories to strip")

    p_mc_ext = mcap_subparsers.add_parser("extract-video", help="Extract video streams from MCAP to MP4")
    p_mc_ext.add_argument("-r", "--recurse", action="store_true", help="Recursively scan directories")
    p_mc_ext.add_argument("paths", nargs="+", help="MCAP file(s) or directories to process")

    p_mc_totlog = mcap_subparsers.add_parser("to-tlog", help="Convert mavlink/out messages from MCAP to raw .tlog")
    p_mc_totlog.add_argument("paths", nargs="+", help="MCAP file(s) to convert")

    p_mc_diff = mcap_subparsers.add_parser(
        "diff-tlog", help="Validate packet parity between paired MCAP and tlog files"
    )
    p_mc_diff.add_argument("mcap_path", help="Path to input MCAP file")
    p_mc_diff.add_argument("tlog_path", help="Path to input tlog file")

    # -------------------------------------------------------------------------
    # Format-Specific Subcommands: asl bin
    # -------------------------------------------------------------------------
    p_bin = subparsers.add_parser(
        "bin",
        help="Format-specific tools for ArduPilot Dataflash (.BIN) files",
        description="Operations specific to Dataflash container files.",
    )
    bin_subparsers = p_bin.add_subparsers(dest="bin_cmd", title="bin commands", metavar="<bin-cmd>", required=True)

    p_bin_ext = bin_subparsers.add_parser("extract-files", help="Extract embedded @SYS/ files from Dataflash log")
    p_bin_ext.add_argument("-r", "--recurse", action="store_true", help="Recursively scan directories")
    p_bin_ext.add_argument("paths", nargs="+", help="Dataflash BIN file(s) to process")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point for the asl command."""
    parser = create_parser()
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    # Phase 2 Core Verbs
    if args.verb == "explode":
        from ardusub_log_tools.cli.explode import run_explode

        return run_explode(args)

    elif args.verb == "merge":
        from ardusub_log_tools.cli.merge import run_merge

        return run_merge(args)

    elif args.verb == "types":
        from ardusub_log_tools.cli.types import run_types

        return run_types(args)

    elif args.verb == "map":
        from ardusub_log_tools.cli.map import run_map

        return run_map(args)

    elif args.verb == "plot":
        from ardusub_log_tools.cli.plot import run_plot

        return run_plot(args)

    elif args.verb == "split":
        from ardusub_log_tools.cli.split import run_split

        return run_split(args)

    elif args.verb == "dive":
        try:
            import dive_logs

            cmd_argv = ["dive_logs", args.directory]
            if args.output:
                cmd_argv.extend(["-o", args.output])
            if args.no_opt:
                cmd_argv.append("--no-opt")
            if args.verbose:
                cmd_argv.append("-v")
            sys.argv = cmd_argv
            dive_logs.main()
            return 0
        except Exception as e:
            print(f"Error running 'asl dive': {e}", file=sys.stderr)
            return 1

    elif args.verb == "battery":
        try:
            # Detect file type or run appropriate tool
            first_file = args.paths[0] if args.paths else ""
            if first_file.endswith(".BIN"):
                import BIN_battery as batt_mod
            else:
                import tlog_battery as batt_mod

            cmd_argv = (
                ["battery"] + (["--terse"] if args.terse else []) + (["--plot"] if args.plot else []) + args.paths
            )
            sys.argv = cmd_argv
            batt_mod.main()
            return 0
        except Exception as e:
            print(f"Error running 'asl battery': {e}", file=sys.stderr)
            return 1

    elif args.verb == "mission":
        try:
            import mission_dump

            cmd_argv = ["mission_dump"] + args.paths
            sys.argv = cmd_argv
            mission_dump.main()
            return 0
        except Exception as e:
            print(f"Error running 'asl mission': {e}", file=sys.stderr)
            return 1

    elif args.verb == "ekf":
        try:
            import BIN_ekf_status

            cmd_argv = ["BIN_ekf_status"] + (["-r"] if args.recurse else []) + args.paths
            sys.argv = cmd_argv
            BIN_ekf_status.main()
            return 0
        except Exception as e:
            print(f"Error running 'asl ekf': {e}", file=sys.stderr)
            return 1

    elif args.verb == "compass":
        try:
            import BIN_mag_stats

            cmd_argv = ["BIN_mag_stats"] + (["-r"] if args.recurse else []) + args.paths
            sys.argv = cmd_argv
            BIN_mag_stats.main()
            return 0
        except Exception as e:
            print(f"Error running 'asl compass': {e}", file=sys.stderr)
            return 1

    elif args.verb == "ugps":
        try:
            import mcap_wl_ugps_acoustic_info

            for path in args.paths:
                info = mcap_wl_ugps_acoustic_info.AcousticLogInfo(path)
                info.read()
                info.report()
            return 0
        except Exception as e:
            print(f"Error running 'asl ugps': {e}", file=sys.stderr)
            return 1

    elif args.verb == "mcap":
        if args.mcap_cmd == "strip-video":
            try:
                import mcap_strip_video

                cmd_argv = (
                    ["mcap_strip_video"]
                    + (["--in-place"] if args.in_place else [])
                    + (["-r"] if args.recurse else [])
                    + args.paths
                )
                sys.argv = cmd_argv
                mcap_strip_video.main()
                return 0
            except Exception as e:
                print(f"Error running 'asl mcap strip-video': {e}", file=sys.stderr)
                return 1

        elif args.mcap_cmd == "channels":
            try:
                import mcap_channels

                sys.argv = ["mcap_channels"] + args.paths
                mcap_channels.main()
                return 0
            except Exception as e:
                print(f"Error running 'asl mcap channels': {e}", file=sys.stderr)
                return 1

        elif args.mcap_cmd == "extract-video":
            try:
                import mcap_extract_video

                cmd_argv = ["mcap_extract_video"] + (["-r"] if args.recurse else []) + args.paths
                sys.argv = cmd_argv
                mcap_extract_video.main()
                return 0
            except Exception as e:
                print(f"Error running 'asl mcap extract-video': {e}", file=sys.stderr)
                return 1

        elif args.mcap_cmd == "to-tlog":
            try:
                import mcap_to_tlog

                cmd_argv = ["mcap_to_tlog"] + args.paths
                sys.argv = cmd_argv
                mcap_to_tlog.main()
                return 0
            except Exception as e:
                print(f"Error running 'asl mcap to-tlog': {e}", file=sys.stderr)
                return 1

        elif args.mcap_cmd == "diff-tlog":
            try:
                import mcap_tlog_diff

                cmd_argv = ["mcap_tlog_diff", args.mcap_path, args.tlog_path]
                sys.argv = cmd_argv
                mcap_tlog_diff.main()
                return 0
            except Exception as e:
                print(f"Error running 'asl mcap diff-tlog': {e}", file=sys.stderr)
                return 1

    elif args.verb == "bin":
        if args.bin_cmd == "extract-files":
            try:
                import BIN_extract_files

                cmd_argv = ["BIN_extract_files"] + (["-r"] if args.recurse else []) + args.paths
                sys.argv = cmd_argv
                BIN_extract_files.main()
                return 0
            except Exception as e:
                print(f"Error running 'asl bin extract-files': {e}", file=sys.stderr)
                return 1

    elif args.verb == "timeline":
        from ardusub_log_tools.cli.timeline import run_timeline

        return run_timeline(args)

    elif args.verb == "messages":
        from ardusub_log_tools.cli.messages import run_messages

        return run_messages(args)

    elif args.verb == "params":
        from ardusub_log_tools.cli.params import run_params

        return run_params(args)

    elif args.verb == "info":
        from ardusub_log_tools.cli.info import run_info

        return run_info(args)

    print(f"Unknown verb '{args.verb}'", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
