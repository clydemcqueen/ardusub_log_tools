#!/usr/bin/env python3

"""
Read MCAP files and build Leaflet (interactive HTML) maps from GPS coordinates.

Plots global positions for both the ROV and the vessel across all available sources
so viewers can see discrepancies between sensors, acoustic solutions, and the EKF.

Sources drawn bottom-to-top:
    wl_ugps_external -- vessel position from satellite compass (input to G2), orange line
    ugps_master -- vessel position polled from G2, red line
    ugps_global -- ROV position from G2 acoustic solution, cyan line
    ugps_gps_input -- ROV position sent to ArduSub by G2 extension, magenta line
    GPS_INPUT -- ROV sensor data sent to ArduSub via MAVLink, light grey line
    GPS_RAW_INT -- ROV sensor data sent from ArduSub to QGC via MAVLink, dark grey line
    GLOBAL_POSITION_INT -- ROV filtered position estimate from ArduSub EKF, blue line

Supports segments.
"""

import argparse
import json

import pandas as pd
from branca.element import Element
from mcap.reader import make_reader

import util
from map_maker import MapMaker, add_map_maker_args
from mcap_explode import resolve_field_value
from mcap_explode_extension_logs import WaterlinkedUgpsParser, WlUgpsExternalParser
from segment_reader import Segment, add_segment_args, build_segment_name, parse_segment_args

# Sources ordered by drawing z-order (bottom to top).
# Vessel tracks first, then raw/acoustic ROV tracks, then MAVLink raw, then EKF filtered output on top.
SOURCES = [
    # (key, display_name, color_name, hex_color, description)
    (
        "wl_ugps_external",
        "wl_ugps_external",
        "orange",
        "#FF8C00",
        "vessel position from satellite compass, input to G2",
    ),
    (
        "ugps_master",
        "ugps_master",
        "red",
        "#E02020",
        "vessel position polled from G2",
    ),
    (
        "ugps_global",
        "ugps_global",
        "cyan",
        "#00CED1",
        "ROV position from G2 acoustic solution",
    ),
    (
        "ugps_gps_input",
        "ugps_gps_input",
        "magenta",
        "#BA55D3",
        "ROV position sent to ArduSub by G2 extension",
    ),
    (
        "GPS_INPUT",
        "GPS_INPUT",
        "light grey",
        "#999999",
        "sensor data sent to ArduSub",
    ),
    (
        "GPS_RAW_INT",
        "GPS_RAW_INT",
        "dark grey",
        "#777777",
        "sensor data sent from ArduSub to QGC",
    ),
    (
        "GLOBAL_POSITION_INT",
        "GLOBAL_POSITION_INT",
        "blue",
        "#0000AA",
        "filtered position estimate from ArduSub EKF",
    ),
]


def print_legend(active_sources: list[tuple[str, str, str, str, str]]):
    """Print the color legend to remind the viewer of what the colors mean."""
    print("Global position sources (drawn bottom-to-top):")
    for _, name, color_name, _, desc in active_sources:
        print(f"  {color_name:10s}: {name} -- {desc}")


def parse_mcap_sources(
    mcap_file: str,
    wanted_keys: set[str],
    hdop_max: float = 100.0,
    segment: Segment | None = None,
    raw: bool = False,
) -> dict[str, list[tuple[float, float]]]:
    """
    Extract GPS coordinate series from an MCAP file for the requested sources.
    Returns a dictionary mapping source key to a list of (latitude, longitude) tuples.
    """
    points: dict[str, list[tuple[float, float]]] = {k: [] for k in wanted_keys}

    want_external = "wl_ugps_external" in wanted_keys
    want_ugps = any(k in wanted_keys for k in ("ugps_master", "ugps_global", "ugps_gps_input"))
    want_mavlink = any(k in wanted_keys for k in ("GPS_INPUT", "GPS_RAW_INT", "GLOBAL_POSITION_INT", "GPS2_RAW"))

    wl_external_parser = WlUgpsExternalParser() if want_external else None
    wl_ugps_parser = WaterlinkedUgpsParser() if want_ugps else None

    def add_external_rows(rows: list[dict]):
        for r in rows:
            ts = r.get("timestamp")
            if segment is not None and ts is not None and (ts < segment.start or ts > segment.end):
                continue
            lat = r.get("lat")
            lon = r.get("lon")
            if lat is None or lon is None or (lat == 0 and lon == 0):
                continue
            if not raw:
                fix_quality = r.get("fix_quality")
                if fix_quality is not None and fix_quality < 1:
                    continue
                hdop = r.get("hdop")
                if hdop is not None and hdop > 0 and hdop > hdop_max:
                    continue
            points["wl_ugps_external"].append((lat, lon))

    def add_ugps_passes(passes: list[dict]):
        for p in passes:
            ts = p.get("timestamp")
            if segment is not None and ts is not None and (ts < segment.start or ts > segment.end):
                continue

            if "ugps_master" in wanted_keys:
                mlat = p.get("master_lat")
                mlon = p.get("master_lon")
                if mlat is not None and mlon is not None and (mlat != 0 or mlon != 0):
                    mhdop = p.get("master_hdop")
                    if raw or not (mhdop is not None and mhdop > 0 and mhdop > hdop_max):
                        points["ugps_master"].append((mlat, mlon))

            if "ugps_global" in wanted_keys:
                glat = p.get("global_lat")
                glon = p.get("global_lon")
                if glat is not None and glon is not None and (glat != 0 or glon != 0):
                    ghdop = p.get("global_hdop")
                    if raw or not (ghdop is not None and ghdop > 0 and ghdop > hdop_max):
                        points["ugps_global"].append((glat, glon))

            if "ugps_gps_input" in wanted_keys:
                ilat = p.get("gps_input_lat")
                ilon = p.get("gps_input_lon")
                if ilat is not None and ilon is not None and (ilat != 0 or ilon != 0):
                    if not raw:
                        fix_type = p.get("gps_input_fix_type")
                        if fix_type is not None and fix_type < 3:
                            continue
                        ihdop = p.get("gps_input_hdop")
                        if ihdop is not None and ihdop > 0 and ihdop > hdop_max:
                            continue
                    points["ugps_gps_input"].append((ilat, ilon))

    try:
        with open(mcap_file, "rb") as f:
            reader = make_reader(f)
            summary = reader.get_summary()

            topics = []
            if summary and summary.channels:
                for c in summary.channels.values():
                    if want_mavlink and c.topic == "mavlink/out":
                        topics.append(c.topic)
                    if want_external and "wl_ugps_external" in c.topic:
                        topics.append(c.topic)
                    if want_ugps and "waterlinked.ugps" in c.topic:
                        topics.append(c.topic)
                topics = list(dict.fromkeys(topics))
                iter_kwargs = {"topics": topics}
            else:
                iter_kwargs = {}

            for schema, channel, message in reader.iter_messages(**iter_kwargs):
                log_s = message.log_time / 1e9

                if segment is not None and (log_s < segment.start or log_s > segment.end):
                    continue

                if wl_external_parser is not None and "wl_ugps_external" in channel.topic:
                    add_external_rows(wl_external_parser.parse_message(message))

                elif wl_ugps_parser is not None and "waterlinked.ugps" in channel.topic:
                    add_ugps_passes(wl_ugps_parser.parse_message(message))

                elif want_mavlink and channel.topic == "mavlink/out":
                    data = json.loads(message.data)
                    msg_data = data.get("message", {})
                    mtype = msg_data.pop("type", None)
                    if mtype in wanted_keys:
                        lat = msg_data.get("lat", 0) / 1e7
                        lon = msg_data.get("lon", 0) / 1e7
                        if lat == 0 and lon == 0:
                            continue
                        if not raw:
                            if mtype == "GPS_INPUT":
                                _, ft = resolve_field_value("fix_type", msg_data.get("fix_type"))
                                if ft < 3:
                                    continue
                                if msg_data.get("hdop", 0) > hdop_max:
                                    continue
                            elif mtype in ("GPS_RAW_INT", "GPS2_RAW"):
                                _, ft = resolve_field_value("fix_type", msg_data.get("fix_type"))
                                if ft < 3:
                                    continue
                                if msg_data.get("eph", 0) / 100.0 > hdop_max:
                                    continue
                        points[mtype].append((lat, lon))

            if wl_external_parser is not None:
                add_external_rows(wl_external_parser.finish())
            if wl_ugps_parser is not None:
                add_ugps_passes(wl_ugps_parser.finish())

    except Exception as e:
        print(f'Error reading {mcap_file}: "{e}"')

    return points


def build_map_from_points(
    sources_data: dict[str, list[tuple[float, float]]],
    outfile: str,
    verbose: bool,
    center: list[float | None],
    zoom: int,
    active_sources: list[tuple[str, str, str, str, str]],
):
    """Generate and save an interactive HTML map from the collected source points."""
    mm = MapMaker(verbose, center, zoom)
    plotted = []

    for key, name, color_name, hex_color, desc in active_sources:
        pts = sources_data.get(key, [])
        if pts:
            print(f"  {name:20s}: {len(pts):5d} points ({color_name})")
            df = pd.DataFrame(pts, columns=["lat", "lon"])
            mm.add_df(df, "lat", "lon", hex_color)
            plotted.append((key, name, color_name, hex_color, desc))

    if mm.m is not None and plotted:
        legend_items = "".join(
            [
                f'<div style="margin: 3px 0;">'
                f'<span style="display:inline-block; width:12px; height:12px; background:{hex_c}; '
                f'margin-right:6px; border-radius:2px; vertical-align:middle;"></span>'
                f'<b>{n}</b> ({col}): <span style="color:#555;">{desc}</span>'
                f"</div>"
                for _, n, col, hex_c, desc in plotted
            ]
        )
        legend_html = f"""
        <div style="
            position: fixed; 
            bottom: 30px; left: 30px; max-width: 420px;
            background-color: rgba(255, 255, 255, 0.92);
            z-index: 9999; font-size: 12px; font-family: sans-serif;
            border: 1px solid #bbb; padding: 10px 14px; border-radius: 6px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.25);
            line-height: 1.4;
        ">
            <div style="font-weight: bold; margin-bottom: 6px; border-bottom: 1px solid #ddd; padding-bottom: 4px; font-size: 13px;">
                Global Position Sources
            </div>
            {legend_items}
        </div>
        """
        mm.m.get_root().html.add_child(Element(legend_html))

    mm.write(outfile)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser, ext=".mcap")
    add_map_maker_args(parser)
    parser.add_argument("--types", default=None, help="comma separated list of message types / sources")
    parser.add_argument(
        "--hdop-max",
        default=100.0,
        type=float,
        help="reject GPS messages where hdop exceeds this limit, default 100.0 (no limit)",
    )
    parser.add_argument("--raw", action="store_true", help="plot raw coordinates without filtering by fix_type or hdop")
    args = parser.parse_args()

    # Active sources from --types
    if args.types:
        types_set = {t.strip().lower() for t in args.types.split(",")}
        active_sources = [s for s in SOURCES if s[0].lower() in types_set]
        if not active_sources:
            print(f"Error: none of the specified types match known sources: {[s[0] for s in SOURCES]}")
            return
    else:
        active_sources = SOURCES

    print_legend(active_sources)

    files = util.expand_path(args.path, args.recurse, ".mcap")
    print(f"Processing {len(files)} file(s)")

    wanted_keys = {s[0] for s in active_sources}

    segments = parse_segment_args(args)
    if segments:
        for segment in segments:
            seg_prefix = build_segment_name(files[0], segment.name)
            outfile = util.get_outfile_name(seg_prefix, suffix="_map", ext=".html")
            print("-------------------")
            print(f"Reading {len(files)} file(s) for segment {segment.name}")
            combined_data: dict[str, list[tuple[float, float]]] = {k: [] for k in wanted_keys}
            for file in files:
                if args.verbose:
                    print(f"  Reading {file}")
                file_data = parse_mcap_sources(file, wanted_keys, hdop_max=args.hdop_max, segment=segment, raw=args.raw)
                for k in wanted_keys:
                    combined_data[k].extend(file_data.get(k, []))

            build_map_from_points(combined_data, outfile, args.verbose, [args.lat, args.lon], args.zoom, active_sources)
    else:
        for file in files:
            print("-------------------")
            print(f"Reading {file}")
            outfile = util.get_outfile_name(file, suffix="_map", ext=".html")
            file_data = parse_mcap_sources(file, wanted_keys, hdop_max=args.hdop_max, segment=None, raw=args.raw)
            build_map_from_points(file_data, outfile, args.verbose, [args.lat, args.lon], args.zoom, active_sources)


if __name__ == "__main__":
    main()
