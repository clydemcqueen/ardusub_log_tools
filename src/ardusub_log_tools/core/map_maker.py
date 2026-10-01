#!/usr/bin/env python3

"""
Build Leaflet (interactive HTML) maps from GPS coordinates across CSV, TXT, TLOG, and MCAP files.

For csv files:
    Latitude column header should be 'gps.lat' or 'lat'
    Longitude column header should be 'gps.lon' or 'lon'

For txt files:
    Look for NMEA 0183 GGA messages of the form $[A-Z]+ at the end of a line of text

For tlog files:
    GPS_INPUT, GPS_RAW_INT, GLOBAL_POSITION_INT

For mcap files:
    wl_ugps_external, ugps_master, ugps_global, ugps_gps_input, GPS_INPUT, GPS_RAW_INT, GLOBAL_POSITION_INT
"""

import argparse
import json
import os
import re
from datetime import datetime
from statistics import fmean

import folium
import pandas as pd
import pynmea2
from branca.element import Element
from mcap.reader import make_reader

from ardusub_log_tools.backends.mcap import WaterlinkedUgpsParser, WlUgpsExternalParser, resolve_field_value
from ardusub_log_tools.core import table_types, util
from ardusub_log_tools.core.segment_reader import Segment

GPS_MSG_TYPES = ["GPS_INPUT", "GPS_RAW_INT", "GLOBAL_POSITION_INT"]
GPS_MSG_COLORS = ["#999999", "#777777", "#0000AA"]

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


class MapMaker:
    @staticmethod
    def build_map_from_df(df, lat_col, lon_col, outfile, verbose, center, zoom):
        mm = MapMaker(verbose, center, zoom)
        mm.add_df(df, lat_col, lon_col, "blue")
        mm.write(outfile)

    @staticmethod
    def build_map_from_txt(locations, outfile, verbose, center, zoom):
        mm = MapMaker(verbose, center, zoom)
        mm.add_locations(locations, "blue")
        mm.write(outfile)

    def __init__(self, verbose, center, zoom):
        self.m = None
        self.verbose = verbose
        self.center = center
        self.zoom = zoom

    def _build_empty_map(self):
        self.m = folium.Map(location=self.center, zoom_start=self.zoom, max_zoom=24)

    def add_df(self, df, lat_col, lon_col, color, marker_function=None):
        if self.m is None:
            if self.center[0] is None:
                self.center[0] = df[lat_col].mean()
            if self.center[1] is None:
                self.center[1] = df[lon_col].mean()
            self._build_empty_map()

        if self.verbose:
            print(df.head())
            print(len(df))

        # smooth_factor=1 (default) seems to mean "do not remove points", which is what we want
        folium.PolyLine(df[[lat_col, lon_col]].values, color=color, weight=1).add_to(self.m)

        if marker_function is not None:
            for index, row in df.iterrows():
                marker = marker_function(row)
                if marker is not None:
                    marker.add_to(self.m)

    def add_table(self, table, lat_col, lon_col, color):
        self.add_df(table.get_dataframe(self.verbose), lat_col, lon_col, color)

    def add_locations(self, locations: list[tuple[float, float]], color):
        if self.m is None:
            lats, lons = zip(*locations)
            if self.center[0] is None:
                self.center[0] = fmean(lats)
            if self.center[1] is None:
                self.center[1] = fmean(lons)
            self._build_empty_map()

        # smooth_factor=1 (default) seems to mean "do not remove points", which is what we want
        folium.PolyLine(locations, color=color, weight=1).add_to(self.m)

    def write(self, outfile):
        if self.m:
            print(f"Writing {outfile}")
            self.m.save(outfile)
        else:
            print("Nothing to write")


def build_map_from_csv(infile, outfile, verbose, center, zoom):
    try:
        df = pd.read_csv(infile)
    except Exception as e:
        print(f"exception parsing csv file: {e}")
        return

    if "gps.lat" in df.columns and "gps.lat" in df.columns:
        if verbose:
            print("QGC csv file")
        df = pd.read_csv(infile, usecols=["gps.lat", "gps.lon"])
        MapMaker.build_map_from_df(df, "gps.lat", "gps.lon", outfile, verbose, center, zoom)
    elif "lat" in df.columns and "lon" in df.columns:
        if verbose:
            print("cleaned csv file")
        df = pd.read_csv(infile, usecols=["lat", "lon"])
        MapMaker.build_map_from_df(df, "lat", "lon", outfile, verbose, center, zoom)
    else:
        print("GPS information not found")


def get_timestamp(line: str):
    match = re.search(r"^[^|]+", line)
    return datetime.strptime(match[0], "%Y-%m-%d %H:%M:%S.%f ")


def build_map_from_txt(infile, outfile, verbose, center, zoom):
    with open(infile, "r") as file:
        line = file.readline()
        if line == "":
            print("Empty file")
            return

        total_nmea = 0
        locations = []
        start = get_timestamp(line)
        prev_line = line
        pattern = re.compile(r"(\$[A-Z]+),.*$")

        while line := file.readline():
            m = re.search(pattern, line)
            if m is not None:
                total_nmea += 1
                if m.group(1).endswith("GGA"):
                    sentence = pynmea2.parse(m.group(0))
                    locations.append((sentence.latitude, sentence.longitude))
            prev_line = line

    duration = get_timestamp(prev_line) - start
    print(f"{total_nmea} sentences received in {duration.seconds} seconds, {len(locations)} were GGA")

    if len(locations) > 0:
        MapMaker.build_map_from_txt(locations, outfile, verbose, center, zoom)
    else:
        print("No GGA messages found")


BIN_GPS_MSG_TYPES = ["GPS", "POS"]
BIN_GPS_MSG_COLORS = ["#999999", "#0000AA"]


def build_map_from_BIN(reader, outfile, verbose, center, zoom, hdop_max):
    tables: dict[str, list[dict]] = {}

    for msg in reader:
        msg_type = msg.get_type()
        data = msg.to_dict()

        if msg_type == "GPS":
            if data["HDop"] > hdop_max:
                continue
            if data["Lat"] == 0 or data["Lng"] == 0:
                continue
        elif msg_type == "POS":
            if data["Lat"] == 0 or data["Lng"] == 0:
                continue
        else:
            continue

        if msg_type not in tables:
            if verbose:
                print(f"Good {msg_type} messages in {reader.name}")
            tables[msg_type] = []

        tables[msg_type].append(data)

    mm = MapMaker(verbose, center, zoom)

    for msg_type, msg_color in zip(BIN_GPS_MSG_TYPES, BIN_GPS_MSG_COLORS):
        if msg_type in tables and len(tables[msg_type]):
            df = pd.DataFrame(tables[msg_type])
            df = df[["Lat", "Lng"]]
            mm.add_df(df, "Lat", "Lng", msg_color)

    mm.write(outfile)


def build_map_from_tlog(reader, outfile, verbose, center, zoom, hdop_max):
    tables: dict[str, table_types.Table] = {}

    for msg in reader:
        msg_type = msg.get_type()
        raw_data = msg.to_dict()
        timestamp = getattr(msg, "_timestamp", 0.0)

        clean_data = {"timestamp": timestamp}
        for key in raw_data.keys():
            if key != "mavpackettype":
                clean_data[f"{msg_type}.{key}"] = raw_data[key]

        if msg_type not in tables:
            tables[msg_type] = table_types.Table.create_table(msg_type, hdop_max=hdop_max, filter_bad=True)

        tables[msg_type].append(clean_data)

    mm = MapMaker(verbose, center, zoom)

    for msg_type, msg_color in zip(GPS_MSG_TYPES, GPS_MSG_COLORS):
        if msg_type in tables and len(tables[msg_type]):
            mm.add_table(tables[msg_type], f"{msg_type}.lat_deg", f"{msg_type}.lon_deg", msg_color)

    mm.write(outfile)


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


def build_map_from_mcap(
    file_path: str,
    outfile: str,
    verbose: bool = False,
    center: list[float | None] | None = None,
    zoom: int = 18,
    hdop_max: float = 2.0,
    selected_sources: list[str] | None = None,
    segment: Segment | None = None,
    raw: bool = False,
):
    """Build an interactive Leaflet HTML map from an MCAP file."""
    if center is None:
        center = [None, None]
    if selected_sources:
        types_set = {s.strip().lower() for s in selected_sources}
        active_sources = [s for s in SOURCES if s[0].lower() in types_set]
    else:
        active_sources = SOURCES

    wanted_keys = {s[0] for s in active_sources}
    file_data = parse_mcap_sources(file_path, wanted_keys, hdop_max=hdop_max, segment=segment, raw=raw)
    build_map_from_points(file_data, outfile, verbose, center, zoom, active_sources)


def add_map_maker_args(parser: argparse.ArgumentParser):
    parser.add_argument("-v", "--verbose", action="store_true", help="print a lot more information")
    parser.add_argument(
        "--lat", default=None, type=float_or_none, help="center the map at this latitude, default is mean of all points"
    )
    parser.add_argument(
        "--lon",
        default=None,
        type=float_or_none,
        help="center the map at this longitude, default is mean of all points",
    )
    parser.add_argument("--zoom", default=18, type=int, help="initial zoom, default is 18")


def float_or_none(x):
    if x is None:
        return None

    try:
        return float(x)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{x} is not a floating-point literal")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for csv and txt files")
    parser.add_argument("path", nargs="+")
    add_map_maker_args(parser)
    args = parser.parse_args()

    files = util.expand_path(args.path, args.recurse, [".csv", ".txt"])
    print(f"Processing {len(files)} files")

    for infile in files:
        print("-------------------")
        print(infile)
        outfile = util.get_outfile_name(infile, suffix="_map", ext=".html")
        _, ext = os.path.splitext(infile)

        if ext == ".csv":
            build_map_from_csv(infile, outfile, args.verbose, [args.lat, args.lon], args.zoom)
        else:
            build_map_from_txt(infile, outfile, args.verbose, [args.lat, args.lon], args.zoom)


if __name__ == "__main__":
    main()
