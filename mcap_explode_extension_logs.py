#!/usr/bin/env python3

"""
Extract structured telemetry and diagnostic data from BlueOS extension logs in MCAP files.

Writes data to CSV (default) or JSON files for interesting extensions:
- wl_ugps_external: vessel location, heading, and HTTP response
- waterlinked.ugps: depth/orientation, global locator, acoustic solution, GPS_INPUT, and master position per pass
"""

import argparse
import ast
import csv
import json

from mcap.reader import make_reader

import util
from segment_reader import Segment, add_segment_args, build_segment_name, parse_segment_args

WL_UGPS_EXTERNAL_FIELDS = [
    "timestamp",
    "lat",
    "lon",
    "orientation",
    "cog",
    "sog",
    "hdop",
    "numsats",
    "fix_quality",
    "response",
]

WATERLINKED_UGPS_FIELDS = [
    "timestamp",
    "mav_alt",
    "mav_temp_raw",
    "depth_sent",
    "temp_sent",
    "depth_resp",
    "mav_heading",
    "orientation_sent",
    "orientation_resp",
    "global_lat",
    "global_lon",
    "global_orientation",
    "global_numsats",
    "global_hdop",
    "global_fix_quality",
    "global_sog",
    "global_cog",
    "acoustic_valid",
    "acoustic_x",
    "acoustic_y",
    "acoustic_z",
    "acoustic_std",
    "receiver_valid_0",
    "receiver_valid_1",
    "receiver_valid_2",
    "receiver_valid_3",
    "receiver_distance_0",
    "receiver_distance_1",
    "receiver_distance_2",
    "receiver_distance_3",
    "receiver_rssi_0",
    "receiver_rssi_1",
    "receiver_rssi_2",
    "receiver_rssi_3",
    "receiver_nsd_0",
    "receiver_nsd_1",
    "receiver_nsd_2",
    "receiver_nsd_3",
    "gps_input_lat",
    "gps_input_lon",
    "gps_input_fix_type",
    "gps_input_hdop",
    "gps_input_vdop",
    "gps_input_horiz_accuracy",
    "gps_input_satellites_visible",
    "gps_input_yaw",
    "gps_input_resp",
    "master_lat",
    "master_lon",
    "master_orientation",
    "master_numsats",
    "master_hdop",
    "master_fix_quality",
    "master_sog",
    "master_cog",
    "nmea_gpgga",
    "nmea_gprmc",
    "nmea_gpvtg",
]


class WlUgpsExternalParser:
    """Incrementally parse vessel position and heading requests sent by wl_ugps_external."""

    def __init__(self):
        self.current_req = None

    def parse_message(self, message) -> list[dict]:
        try:
            payload = json.loads(message.data.decode("utf-8"))
            text = payload.get("message", "")
        except Exception:
            text = message.data.decode("utf-8", errors="replace")

        log_time = message.log_time / 1e9
        return self.parse_line(text, log_time)

    def parse_line(self, text: str, log_time: float) -> list[dict]:
        rows = []
        if "/api/v1/external/master" in text and "json:" in text:
            try:
                json_str = text.split("json:", 1)[1].strip()
                try:
                    req_data = json.loads(json_str)
                except Exception:
                    req_data = ast.literal_eval(json_str)

                self.current_req = {
                    "timestamp": log_time,
                    "lat": req_data.get("lat"),
                    "lon": req_data.get("lon"),
                    "orientation": req_data.get("orientation"),
                    "cog": req_data.get("cog"),
                    "sog": req_data.get("sog"),
                    "hdop": req_data.get("hdop"),
                    "numsats": req_data.get("numsats"),
                    "fix_quality": req_data.get("fix_quality"),
                    "response": None,
                }
            except Exception:
                pass
        elif self.current_req is not None:
            if "Got response:" in text:
                resp = text.split("Got response:", 1)[1].strip()
                self.current_req["response"] = resp
                rows.append(self.current_req)
                self.current_req = None
            elif "Got HTTP Error:" in text or "Got exception:" in text:
                resp = text.split("-", 1)[1].strip() if "-" in text else text
                self.current_req["response"] = resp
                rows.append(self.current_req)
                self.current_req = None

        return rows

    def finish(self) -> list[dict]:
        return []


class WaterlinkedUgpsParser:
    """Incrementally parse telemetry, acoustic fixes, and GPS_INPUT data per pass in waterlinked.ugps."""

    def __init__(self):
        self.passes = []
        self.current_pass = {}
        self.last_req = None

    def _flush_pass(self):
        if self.current_pass and any(k != "timestamp" for k in self.current_pass):
            self.passes.append(self.current_pass)
        self.current_pass = {}

    def parse_message(self, message) -> list[dict]:
        try:
            payload = json.loads(message.data.decode("utf-8"))
            text = payload.get("message", "")
        except Exception:
            text = message.data.decode("utf-8", errors="replace")

        log_time = message.log_time / 1e9
        return self.parse_line(text, log_time)

    def parse_line(self, text: str, log_time: float) -> list[dict]:
        start_count = len(self.passes)

        if "Forwarding depth, temperature and orientation" in text:
            self._flush_pass()
            self.current_pass["timestamp"] = log_time

        if "timestamp" not in self.current_pass:
            self.current_pass["timestamp"] = log_time

        if "Request url:" in text:
            parts = text.split("Request url:", 1)[1].strip()
            if " json:" in parts:
                url, json_str = parts.split(" json:", 1)
                url = url.strip()
                json_str = json_str.strip()
                try:
                    req_json = json.loads(json_str)
                except Exception:
                    try:
                        req_json = ast.literal_eval(json_str)
                    except Exception:
                        req_json = {}
            else:
                url = parts
                req_json = None

            self.last_req = url

            if "/api/v1/external/depth" in url and req_json:
                self.current_pass["depth_sent"] = req_json.get("depth")
                self.current_pass["temp_sent"] = req_json.get("temp")
            elif "/api/v1/external/orientation" in url and req_json:
                self.current_pass["orientation_sent"] = req_json.get("orientation")
            elif "/mavlink" in url and req_json and req_json.get("message", {}).get("type") == "GPS_INPUT":
                msg = req_json["message"]
                self.current_pass["gps_input_lat"] = msg.get("lat", 0) / 1e7 if msg.get("lat") else None
                self.current_pass["gps_input_lon"] = msg.get("lon", 0) / 1e7 if msg.get("lon") else None
                self.current_pass["gps_input_fix_type"] = msg.get("fix_type")
                self.current_pass["gps_input_hdop"] = msg.get("hdop")
                self.current_pass["gps_input_vdop"] = msg.get("vdop")
                self.current_pass["gps_input_horiz_accuracy"] = msg.get("horiz_accuracy")
                self.current_pass["gps_input_satellites_visible"] = msg.get("satellites_visible")
                self.current_pass["gps_input_yaw"] = msg.get("yaw", 0) / 100.0 if msg.get("yaw") is not None else None

        elif "Got response:" in text and self.last_req:
            resp_text = text.split("Got response:", 1)[1].strip()
            if "/messages/VFR_HUD/message/alt" in self.last_req:
                try:
                    self.current_pass["mav_alt"] = float(resp_text)
                except Exception:
                    pass
            elif "/messages/SCALED_PRESSURE2/message/temperature" in self.last_req:
                try:
                    self.current_pass["mav_temp_raw"] = float(resp_text)
                except Exception:
                    pass
            elif "/messages/VFR_HUD/message/heading" in self.last_req:
                try:
                    self.current_pass["mav_heading"] = float(resp_text)
                except Exception:
                    pass
            elif "/api/v1/external/depth" in self.last_req:
                self.current_pass["depth_resp"] = resp_text
            elif "/api/v1/external/orientation" in self.last_req:
                self.current_pass["orientation_resp"] = resp_text
            elif "/api/v1/position/global" in self.last_req:
                try:
                    data = json.loads(resp_text)
                    self.current_pass["global_lat"] = data.get("lat")
                    self.current_pass["global_lon"] = data.get("lon")
                    self.current_pass["global_orientation"] = data.get("orientation")
                    self.current_pass["global_numsats"] = data.get("numsats")
                    self.current_pass["global_hdop"] = data.get("hdop")
                    self.current_pass["global_fix_quality"] = data.get("fix_quality")
                    self.current_pass["global_sog"] = data.get("sog")
                    self.current_pass["global_cog"] = data.get("cog")
                except Exception:
                    pass
            elif "/api/v1/position/acoustic/filtered" in self.last_req:
                try:
                    data = json.loads(resp_text)
                    self.current_pass["acoustic_valid"] = data.get("position_valid")
                    self.current_pass["acoustic_x"] = data.get("x")
                    self.current_pass["acoustic_y"] = data.get("y")
                    self.current_pass["acoustic_z"] = data.get("z")
                    self.current_pass["acoustic_std"] = data.get("std")

                    valid_list = data.get("receiver_valid") or []
                    for idx in range(4):
                        self.current_pass[f"receiver_valid_{idx}"] = valid_list[idx] if idx < len(valid_list) else None

                    dist_list = data.get("receiver_distance") or []
                    for idx in range(4):
                        self.current_pass[f"receiver_distance_{idx}"] = dist_list[idx] if idx < len(dist_list) else None

                    rssi_list = data.get("receiver_rssi") or []
                    for idx in range(4):
                        self.current_pass[f"receiver_rssi_{idx}"] = rssi_list[idx] if idx < len(rssi_list) else None

                    nsd_list = data.get("receiver_nsd") or []
                    for idx in range(4):
                        self.current_pass[f"receiver_nsd_{idx}"] = nsd_list[idx] if idx < len(nsd_list) else None
                except Exception:
                    pass
            elif "/mavlink" in self.last_req:
                self.current_pass["gps_input_resp"] = resp_text
            elif "/api/v1/position/master" in self.last_req:
                try:
                    data = json.loads(resp_text)
                    self.current_pass["master_lat"] = data.get("lat")
                    self.current_pass["master_lon"] = data.get("lon")
                    self.current_pass["master_orientation"] = data.get("orientation")
                    self.current_pass["master_numsats"] = data.get("numsats")
                    self.current_pass["master_hdop"] = data.get("hdop")
                    self.current_pass["master_fix_quality"] = data.get("fix_quality")
                    self.current_pass["master_sog"] = data.get("sog")
                    self.current_pass["master_cog"] = data.get("cog")
                except Exception:
                    pass

            self.last_req = None

        elif "Sending UDP" in text:
            nmea = text.split("Sending UDP", 1)[1].strip()
            if nmea.startswith("$GPGGA"):
                self.current_pass["nmea_gpgga"] = nmea
            elif nmea.startswith("$GPRMC"):
                self.current_pass["nmea_gprmc"] = nmea
            elif nmea.startswith("$GPVTG"):
                self.current_pass["nmea_gpvtg"] = nmea

        elif "Got HTTP Error:" in text and self.last_req:
            err_text = text.split("Got HTTP Error:", 1)[1].strip()
            if "/api/v1/external/depth" in self.last_req:
                self.current_pass["depth_resp"] = f"HTTP Error: {err_text}"
            elif "/api/v1/external/orientation" in self.last_req:
                self.current_pass["orientation_resp"] = f"HTTP Error: {err_text}"
            elif "/mavlink" in self.last_req:
                self.current_pass["gps_input_resp"] = f"HTTP Error: {err_text}"
            self.last_req = None

        new_passes = self.passes[start_count:]
        return new_passes

    def finish(self) -> list[dict]:
        start_count = len(self.passes)
        self._flush_pass()
        return self.passes[start_count:]


def parse_wl_ugps_external(mcap_file: str) -> list[dict]:
    """Parse vessel position and heading requests sent by wl_ugps_external."""
    parser = WlUgpsExternalParser()
    rows = []
    with open(mcap_file, "rb") as f:
        reader = make_reader(f)
        summary = reader.get_summary()
        topic = None
        if summary and summary.channels:
            for c in summary.channels.values():
                if "wl_ugps_external" in c.topic:
                    topic = c.topic
                    break

        iter_kwargs = {"topics": [topic]} if topic else {}

        for schema, channel, message in reader.iter_messages(**iter_kwargs):
            if "wl_ugps_external" not in channel.topic:
                continue
            rows.extend(parser.parse_message(message))

    rows.extend(parser.finish())
    return rows


def parse_waterlinked_ugps(mcap_file: str) -> list[dict]:
    """Parse telemetry, acoustic fixes, and GPS_INPUT data per pass in waterlinked.ugps."""
    parser = WaterlinkedUgpsParser()
    passes = []
    with open(mcap_file, "rb") as f:
        reader = make_reader(f)
        summary = reader.get_summary()
        topic = None
        if summary and summary.channels:
            for c in summary.channels.values():
                if "waterlinked.ugps" in c.topic:
                    topic = c.topic
                    break

        iter_kwargs = {"topics": [topic]} if topic else {}

        for schema, channel, message in reader.iter_messages(**iter_kwargs):
            if "waterlinked.ugps" not in channel.topic:
                continue
            passes.extend(parser.parse_message(message))

    passes.extend(parser.finish())
    return passes


def write_csv(outfile: str, rows: list[dict], fieldnames: list[str]):
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(outfile: str, rows: list[dict]):
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def explode_extension_logs(
    mcap_file: str,
    use_json: bool = False,
    verbose: bool = False,
    segment: Segment | None = None,
    outfile_prefix: str | None = None,
) -> dict[str, int]:
    """
    Extract structured extension data from an MCAP file and write CSV or JSON files.
    Returns a dictionary mapping extension name to record count.
    """
    ext = ".json" if use_json else ".csv"
    counts = {}
    target_prefix = outfile_prefix if outfile_prefix is not None else mcap_file

    # 1. Parse wl_ugps_external
    wl_rows = parse_wl_ugps_external(mcap_file)
    if segment is not None:
        wl_rows = [r for r in wl_rows if segment.start <= r["timestamp"] <= segment.end]

    if wl_rows:
        out_path = util.get_outfile_name(target_prefix, suffix="_wl_ugps_external", ext=ext)
        if use_json:
            write_json(out_path, wl_rows)
        else:
            write_csv(out_path, wl_rows, WL_UGPS_EXTERNAL_FIELDS)
        counts["wl_ugps_external"] = len(wl_rows)
        print(f"  Wrote {len(wl_rows):5d} records to {out_path}")

    # 2. Parse waterlinked.ugps
    ugps_passes = parse_waterlinked_ugps(mcap_file)
    if segment is not None:
        ugps_passes = [p for p in ugps_passes if segment.start <= p["timestamp"] <= segment.end]

    if ugps_passes:
        out_path = util.get_outfile_name(target_prefix, suffix="_waterlinked.ugps", ext=ext)
        if use_json:
            write_json(out_path, ugps_passes)
        else:
            write_csv(out_path, ugps_passes, WATERLINKED_UGPS_FIELDS)
        counts["waterlinked.ugps"] = len(ugps_passes)
        print(f"  Wrote {len(ugps_passes):5d} passes to {out_path}")

    if not counts:
        print(f"  No extension data found in {mcap_file}")

    return counts


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser, ext=".mcap")
    parser.add_argument("--json", action="store_true", help="write JSON files instead of CSV")
    parser.add_argument("-v", "--verbose", action="store_true", help="print extra progress details")
    args = parser.parse_args()

    files = util.expand_path(args.path, args.recurse, ".mcap")
    print(f"Processing {len(files)} files")

    segments = parse_segment_args(args)
    if segments:
        for segment in segments:
            seg_prefix = build_segment_name(files[0], segment.name)
            for file in files:
                print("-------------------")
                print(f"Reading {file} for segment {segment.name}")
                explode_extension_logs(
                    file, use_json=args.json, verbose=args.verbose, segment=segment, outfile_prefix=seg_prefix
                )
    else:
        for file in files:
            print("-------------------")
            print(f"Reading {file}")
            explode_extension_logs(file, use_json=args.json, verbose=args.verbose)


if __name__ == "__main__":
    main()
