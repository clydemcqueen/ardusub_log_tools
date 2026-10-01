#!/usr/bin/env python3

"""
MCAP backend for ardusub_log_tools.

Supports:
- McapLogReader (for merge, explode, and reading MAVLink messages + extensions)
- BlueOS extension parsing: WlUgpsExternalParser, WaterlinkedUgpsParser, WaterlinkedDvlParser
- Video processing: strip_video_from_mcap, extract_video_from_mcap
- Channel counting: count_mcap_messages
- Format conversion: mcap_to_tlog, diff_tlog
- Log extraction: dump_logs, dump_extension_logs
- Diagnostics: AcousticLogInfo
"""

import argparse
import ast
import csv
import difflib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone

from mcap.reader import make_reader
from mcap.writer import CompressionType, Writer
from pymavlink import mavutil
from pymavlink.dialects.v20 import ardupilotmega as mavlink

from ardusub_log_tools.core import table_types, util
from ardusub_log_tools.core.log_merger import LogMerger
from ardusub_log_tools.core.segment_reader import Segment, add_segment_args, build_segment_name, parse_segment_args

# Tables that look generally interesting (matching tlog_merge / tlog_explode)
PERHAPS_USEFUL_MSG_TYPES = [
    "AHRS",
    "AHRS2",
    "ATTITUDE",
    # "AUTOPILOT_VERSION",
    # "BATTERY_STATUS",
    # "COMMAND_ACK",
    # "COMMAND_LONG",
    "DISTANCE_SENSOR",
    "EKF_STATUS_REPORT",
    "GLOBAL_POSITION_INT",
    "GLOBAL_VISION_POSITION_ESTIMATE",
    # "GPS2_RAW",
    "GPS_GLOBAL_ORIGIN",
    "GPS_INPUT",
    "GPS_RAW_INT",
    "HEARTBEAT",
    "HOME_POSITION",
    # "HWSTATUS",
    "LOCAL_POSITION_NED",
    # "MANUAL_CONTROL",
    # "MEMINFO",
    # "MISSION_ACK",
    # "MISSION_COUNT",
    # "MISSION_CURRENT",
    # "MISSION_REQUEST_LIST",
    # "MOUNT_STATUS",
    # "NAMED_VALUE_FLOAT",
    # "NAV_CONTROLLER_OUTPUT",
    # "PARAM_REQUEST_LIST",
    # "PARAM_VALUE",
    # "POWER_STATUS",
    "RANGEFINDER",
    # "RAW_IMU",
    # "RC_CHANNELS",
    # "REQUEST_DATA_STREAM",
    # "SCALED_IMU2",
    # "SCALED_PRESSURE",
    "SCALED_PRESSURE2",
    # "SENSOR_OFFSETS",
    "SERVO_OUTPUT_RAW",
    "SET_GPS_GLOBAL_ORIGIN",
    # "STATUSTEXT",
    "SYS_STATUS",
    "SYSTEM_TIME",
    "TIMESYNC",
    "VFR_HUD",
    # "VIBRATION",
    "VISION_POSITION_DELTA",
    "VISION_POSITION_ESTIMATE",
]

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

WATERLINKED_DVL_FIELDS = [
    "timestamp",
    "status",
]

BLUEROBOTICS_WATER_LINKED_DVL_FIELDS = WATERLINKED_DVL_FIELDS

TRANSDUCER_DESCRIPTIONS = [
    "Transducer 0 (R1, -x, aft)",
    "Transducer 1 (R2, +y, starboard)",
    "Transducer 2 (R3, +x, forward)",
    "Transducer 3 (R4, +z, down)",
]

FOXGLOVE_LOG_SCHEMA = "foxglove.Log"
EXTENSION_LOG_PREFIX = "extensions/logs/"

RE_LOGURU_TIMESTAMP = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)")
RE_HTTP_TIMESTAMP = re.compile(r"\[(\d{2})/([A-Za-z]{3})/(\d{4}) (\d{2}):(\d{2}):(\d{2})\]")
MONTH_MAP = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def normalize_types(type_list: list[str]) -> list[str]:
    """Normalize message type list, recognizing pseudo-MAVLink extension table names."""
    normalized = []
    for t in type_list:
        t_clean = t.strip()
        t_lower = t_clean.lower()
        if t_lower in ("wl_ugps", "waterlinked.ugps"):
            normalized.append("wl_ugps")
        elif t_lower == "wl_ugps_external":
            normalized.append("wl_ugps_external")
        elif t_lower in (
            "wl_dvl",
            "wl-dvl",
            "waterlinked.dvl",
            "waterlinked_dvl",
            "bluerobotics.water-linked-dvl",
            "water-linked-dvl",
        ):
            normalized.append("wl_dvl")
        else:
            normalized.append(t_clean.upper())
    return normalized


def resolve_field_value(k: str, v):
    """
    Convert JSON values to pymavlink-compatible / table-friendly values:
    - Map 'mavtype' key to 'type'.
    - If a field is a dictionary containing a 'type' key (e.g. enum objects), extract the 'type' value.
    - If a string contains a bitwise-OR combination (e.g., 'A|B'), resolve each constant against the dialect.
    - If a string is a named enum constant in pymavlink dialect, resolve it to its integer value.
    - If a string is empty (''), default to 0.
    - Otherwise, preserve strings, numbers, lists, etc.
    """
    if k == "mavtype":
        k = "type"

    if isinstance(v, dict) and "type" in v:
        v = v["type"]

    if isinstance(v, str):
        if "|" in v:
            parts = [p.strip() for p in v.split("|")]
            result = 0
            for p in parts:
                enum_v = getattr(mavlink, p, None)
                if enum_v is not None:
                    result |= enum_v
            v = result
        else:
            enum_v = getattr(mavlink, v, None)
            if enum_v is not None:
                v = enum_v
            elif v == "":
                v = 0

    return k, v


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


class WaterlinkedDvlParser:
    """Parse status records from bluerobotics.water-linked-dvl."""

    def __init__(self):
        self.last_time = 0.0

    @staticmethod
    def extract_timestamp(text: str) -> float | None:
        m = RE_LOGURU_TIMESTAMP.search(text)
        if m:
            try:
                return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                pass

        m = RE_HTTP_TIMESTAMP.search(text)
        if m:
            day, mon_str, year, hour, minute, second = m.groups()
            mon = MONTH_MAP.get(mon_str)
            if mon:
                try:
                    return datetime(
                        int(year), mon, int(day), int(hour), int(minute), int(second), tzinfo=timezone.utc
                    ).timestamp()
                except ValueError:
                    pass

        print(f"Could not parse timestamp in '{text}', dropping record")
        return None

    def parse_message(self, message) -> list[dict]:
        try:
            payload = json.loads(message.data.decode("utf-8"))
            if isinstance(payload, dict):
                text = payload.get("message", "")
            else:
                text = str(payload)
        except Exception:
            text = message.data.decode("utf-8", errors="replace")

        return self.parse_line(text)

    def parse_line(self, text: str) -> list[dict]:
        if "GET /get_status" in text and re.search(r"\s200\b", text):
            status = 0
        elif re.search(r"invalid\s+dvl\s+reading", text, re.IGNORECASE):
            status = 1
        else:
            return []

        ts = self.extract_timestamp(text)
        if ts is None:
            return []
        if ts < self.last_time:
            print(f"Time went backwards: {self.last_time} -> {ts}, dropping record")
            return []
        self.last_time = ts
        return [{"timestamp": ts, "status": status}]

    def finish(self) -> list[dict]:
        return []


BlueroboticsWaterLinkedDvlParser = WaterlinkedDvlParser


class McapLogReader(LogMerger):
    def __init__(
        self,
        filename: str,
        types: list[str] | None,
        max_msgs: int,
        verbose: bool,
        sysid: int | None,
        compid: int | None,
        system_time: bool,
        split_source: bool,
        raw: bool,
        segment: Segment | None = None,
        max_rows: int = 500000,
    ):
        super().__init__(filename, max_msgs, max_rows, verbose)
        self.filename = filename
        self.types = types
        self.sysid = sysid
        self.compid = compid
        self.system_time = system_time
        self.split_source = split_source
        self.raw = raw
        self.segment = segment
        self.time_delta_s = None

    def read_mcap(self, filename: str | None = None):
        if not hasattr(self, "tables") or self.tables is None:
            self.tables = {}
        file_to_read = filename if filename is not None else self.filename
        msg_count = 0

        want_wl_dvl = self.types is not None and "wl_dvl" in self.types
        want_wl_ugps = self.types is not None and "wl_ugps" in self.types
        want_wl_external = self.types is not None and "wl_ugps_external" in self.types
        want_mavlink = self.types is None or any(t not in ("wl_ugps", "wl_ugps_external", "wl_dvl") for t in self.types)

        try:
            with open(file_to_read, "rb") as f:
                reader = make_reader(f)
                summary = reader.get_summary()

                topics = []
                if summary and summary.channels:
                    if want_mavlink:
                        for c in summary.channels.values():
                            if c.topic == "mavlink/out":
                                topics.append(c.topic)
                    if want_wl_dvl:
                        for c in summary.channels.values():
                            if "water-linked-dvl" in c.topic or "water-linked-dev" in c.topic or "wl_dvl" in c.topic:
                                topics.append(c.topic)
                    if want_wl_external:
                        for c in summary.channels.values():
                            if "wl_ugps_external" in c.topic:
                                topics.append(c.topic)
                    if want_wl_ugps:
                        for c in summary.channels.values():
                            if "waterlinked.ugps" in c.topic:
                                topics.append(c.topic)
                    topics = list(dict.fromkeys(topics))
                    iter_kwargs = {"topics": topics}
                else:
                    iter_kwargs = {}

                wl_dvl_parser = WaterlinkedDvlParser() if want_wl_dvl else None
                wl_external_parser = WlUgpsExternalParser() if want_wl_external else None
                wl_ugps_parser = WaterlinkedUgpsParser() if want_wl_ugps else None

                def append_wl_dvl_rows(rows):
                    nonlocal msg_count
                    for r in rows:
                        r_ts = r["timestamp"]
                        if self.system_time:
                            if self.time_delta_s is None:
                                continue
                            ts = int((r_ts - self.time_delta_s) * 1000.0)
                        else:
                            ts = r_ts

                        if self.segment is not None:
                            if r_ts < self.segment.start or r_ts > self.segment.end:
                                continue

                        table_name = "wl_dvl"
                        clean_data = {"timestamp": ts}
                        for k, v in r.items():
                            if k != "timestamp":
                                clean_data[f"{table_name}.{k}"] = v

                        if table_name not in self.tables:
                            self.tables[table_name] = table_types.Table.create_table(
                                table_name, table_name=table_name, filter_bad=not self.raw
                            )
                        self.tables[table_name].append(clean_data)
                        msg_count += 1

                def append_wl_external_rows(rows):
                    nonlocal msg_count
                    for r in rows:
                        r_ts = r["timestamp"]
                        if self.system_time:
                            if self.time_delta_s is None:
                                continue
                            ts = int((r_ts - self.time_delta_s) * 1000.0)
                        else:
                            ts = r_ts

                        if self.segment is not None:
                            if r_ts < self.segment.start or r_ts > self.segment.end:
                                continue

                        table_name = "wl_ugps_external"
                        clean_data = {"timestamp": ts}
                        for k, v in r.items():
                            if k != "timestamp":
                                clean_data[f"{table_name}.{k}"] = v

                        if table_name not in self.tables:
                            self.tables[table_name] = table_types.Table.create_table(
                                table_name, table_name=table_name, filter_bad=not self.raw
                            )
                        self.tables[table_name].append(clean_data)
                        msg_count += 1

                def append_wl_ugps_rows(passes):
                    nonlocal msg_count
                    for p in passes:
                        p_ts = p["timestamp"]
                        if self.system_time:
                            if self.time_delta_s is None:
                                continue
                            ts = int((p_ts - self.time_delta_s) * 1000.0)
                        else:
                            ts = p_ts

                        if self.segment is not None:
                            if p_ts < self.segment.start or p_ts > self.segment.end:
                                continue

                        table_name = "wl_ugps"
                        clean_data = {"timestamp": ts}
                        for k, v in p.items():
                            if k != "timestamp":
                                clean_data[f"{table_name}.{k}"] = v

                        if table_name not in self.tables:
                            self.tables[table_name] = table_types.Table.create_table(
                                table_name, table_name=table_name, filter_bad=not self.raw
                            )
                        self.tables[table_name].append(clean_data)
                        msg_count += 1

                for schema, channel, message in reader.iter_messages(**iter_kwargs):
                    log_s = message.log_time / 1e9

                    if channel.topic == "mavlink/out" and want_mavlink:
                        data = json.loads(message.data)
                        header = data.get("header", {})
                        msg_data = data.get("message", {})
                        msg_type = msg_data.pop("type", None)

                        if not msg_type:
                            continue

                        if self.types is not None and msg_type not in self.types:
                            continue

                        sysid = header.get("system_id", 1)
                        compid = header.get("component_id", 1)

                        if self.sysid is not None and self.sysid != sysid:
                            continue
                        if self.compid is not None and self.compid != compid:
                            continue

                        if self.system_time:
                            if msg_type == "SYSTEM_TIME" and sysid == 1 and compid == 1 and self.time_delta_s is None:
                                self.time_delta_s = log_s - msg_data.get("time_boot_ms", 0) / 1000.0
                                print(f"Time synchronized, delta is {self.time_delta_s} seconds")

                            if self.time_delta_s is None:
                                continue

                            clean_data = {"timestamp": int((log_s - self.time_delta_s) * 1000.0)}
                        else:
                            clean_data = {"timestamp": log_s}

                        if self.segment is not None:
                            if log_s < self.segment.start or log_s > self.segment.end:
                                continue

                        if self.split_source:
                            table_name = f"{msg_type}_{sysid}_{compid}"
                        else:
                            table_name = msg_type
                            clean_data[f"{msg_type}.sysid"] = sysid
                            clean_data[f"{msg_type}.compid"] = compid

                        for k, v in msg_data.items():
                            resolved_k, resolved_v = resolve_field_value(k, v)
                            clean_data[f"{table_name}.{resolved_k}"] = resolved_v

                        if table_name not in self.tables:
                            self.tables[table_name] = table_types.Table.create_table(
                                msg_type, table_name=table_name, filter_bad=not self.raw
                            )

                        self.tables[table_name].append(clean_data)
                        msg_count += 1

                    elif wl_dvl_parser is not None and (
                        "water-linked-dvl" in channel.topic
                        or "water-linked-dev" in channel.topic
                        or "wl_dvl" in channel.topic
                    ):
                        append_wl_dvl_rows(wl_dvl_parser.parse_message(message))

                    elif wl_external_parser is not None and "wl_ugps_external" in channel.topic:
                        append_wl_external_rows(wl_external_parser.parse_message(message))

                    elif wl_ugps_parser is not None and "waterlinked.ugps" in channel.topic:
                        append_wl_ugps_rows(wl_ugps_parser.parse_message(message))

                    if msg_count > self.max_msgs:
                        print("Too many messages, stopping")
                        break
                    if self.verbose and msg_count % 20000 == 0:
                        print(f"{msg_count} messages")

                if wl_dvl_parser is not None:
                    append_wl_dvl_rows(wl_dvl_parser.finish())
                if wl_external_parser is not None:
                    append_wl_external_rows(wl_external_parser.finish())
                if wl_ugps_parser is not None:
                    append_wl_ugps_rows(wl_ugps_parser.finish())

        except Exception as e:
            print(f'CRASH WITH ERROR "{e}", SHOWING PARTIAL RESULTS')

        print(f"{msg_count} messages")

    def add_rate_field(self, half_n=10, field_name="rate"):
        for table_name in self.tables:
            self.tables[table_name].add_rate_field(half_n, field_name)


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


def parse_bluerobotics_water_linked_dvl(mcap_file: str) -> list[dict]:
    """Parse status records from bluerobotics.water-linked-dvl."""
    parser = WaterlinkedDvlParser()
    rows = []
    with open(mcap_file, "rb") as f:
        reader = make_reader(f)
        summary = reader.get_summary()
        topic = None
        if summary and summary.channels:
            for c in summary.channels.values():
                if "water-linked-dvl" in c.topic or "water-linked-dev" in c.topic:
                    topic = c.topic
                    break

        iter_kwargs = {"topics": [topic]} if topic else {}

        for schema, channel, message in reader.iter_messages(**iter_kwargs):
            if "water-linked-dvl" not in channel.topic and "water-linked-dev" not in channel.topic:
                continue
            rows.extend(parser.parse_message(message))

    rows.extend(parser.finish())
    return rows


parse_waterlinked_dvl = parse_bluerobotics_water_linked_dvl


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

    dvl_rows = parse_bluerobotics_water_linked_dvl(mcap_file)
    if segment is not None:
        dvl_rows = [r for r in dvl_rows if segment.start <= r["timestamp"] <= segment.end]

    if dvl_rows:
        out_path = util.get_outfile_name(target_prefix, suffix="_bluerobotics.water-linked-dvl", ext=ext)
        if use_json:
            write_json(out_path, dvl_rows)
        else:
            write_csv(out_path, dvl_rows, WATERLINKED_DVL_FIELDS)
        counts["bluerobotics.water-linked-dvl"] = len(dvl_rows)
        print(f"  Wrote {len(dvl_rows):5d} records to {out_path}")

    if not counts:
        print(f"  No extension data found in {mcap_file}")

    return counts


def is_video_channel(topic: str, schema_name: str | None) -> bool:
    """Determine if a channel contains video data based on its topic name or schema."""
    if topic.startswith("video/") or topic.startswith("/video/"):
        return True
    if schema_name:
        schema_lower = schema_name.lower()
        if "compressedvideo" in schema_lower or "compressedimage" in schema_lower or "rawimage" in schema_lower:
            return True
    return False


def strip_video_from_mcap(file_path: str, in_place: bool = False) -> bool:
    """
    Read an MCAP file, filter out video messages/channels, and save to an MCAP file.
    """
    if not os.path.isfile(file_path):
        print(f"Error: '{file_path}' is not a valid file.")
        return False

    dirname, basename = os.path.split(file_path)
    root, ext = os.path.splitext(basename)

    if ext.lower() != ".mcap":
        print(f"Error: '{file_path}' does not have a .mcap extension.")
        return False

    target_dir = dirname if dirname else "."

    if in_place:
        if not os.access(file_path, os.R_OK | os.W_OK):
            print(f"Error: '{file_path}' is not readable and writable.")
            return False

        if not os.access(target_dir, os.W_OK):
            print(f"Error: Directory '{target_dir}' is not writable.")
            return False

        if root.endswith("_video"):
            print(f"Skipping '{file_path}': filename already ends with '_video'.")
            return False

        video_path = os.path.join(dirname, f"{root}_video{ext}")
        if os.path.exists(video_path):
            print(f"Skipping '{file_path}': target '{video_path}' already exists; aborting to avoid overwriting data.")
            return False

        temp_fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix=f".{root}_strip_tmp_", suffix=ext)
        os.close(temp_fd)
        write_path = temp_path
        print(f"Processing {file_path} in-place:")
        print(f"  Stripped -> {file_path}")
        print(f"  Original (with video) -> {video_path}")
    else:
        if not os.access(file_path, os.R_OK):
            print(f"Error: '{file_path}' is not readable.")
            return False

        if not os.access(target_dir, os.W_OK):
            print(f"Error: Directory '{target_dir}' is not writable.")
            return False

        out_path = util.get_outfile_name(file_path, suffix="_no_video", ext=".mcap")
        if os.path.abspath(file_path) == os.path.abspath(out_path):
            print(f"Error: Output file '{out_path}' matches input file '{file_path}'.")
            return False

        write_path = out_path
        print(f"Reading {file_path}")
        print(f"Writing {out_path}")

    try:
        in_size = os.path.getsize(file_path)
    except OSError:
        in_size = 0

    message_count = 0
    stripped_count = 0
    schema_map = {}
    channel_map = {}

    try:
        with open(file_path, "rb") as f_in, open(write_path, "wb") as f_out:
            reader = make_reader(f_in)
            writer = Writer(f_out, compression=CompressionType.ZSTD)
            writer.start()

            for schema, channel, message in reader.iter_messages():
                schema_name = schema.name if schema else None
                if is_video_channel(channel.topic, schema_name):
                    stripped_count += 1
                    continue

                if schema:
                    if schema.id not in schema_map:
                        new_schema_id = writer.register_schema(
                            name=schema.name, encoding=schema.encoding, data=schema.data
                        )
                        schema_map[schema.id] = new_schema_id
                    dest_schema_id = schema_map[schema.id]
                else:
                    dest_schema_id = 0

                if channel.id not in channel_map:
                    new_channel_id = writer.register_channel(
                        topic=channel.topic, message_encoding=channel.message_encoding, schema_id=dest_schema_id
                    )
                    channel_map[channel.id] = new_channel_id

                writer.add_message(
                    channel_id=channel_map[channel.id],
                    log_time=message.log_time,
                    data=message.data,
                    publish_time=message.publish_time,
                    sequence=message.sequence,
                )
                message_count += 1

            writer.finish()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        if os.path.exists(write_path):
            try:
                os.remove(write_path)
            except OSError:
                pass
        return False

    if in_place:
        if stripped_count == 0:
            print(f"No video messages found in {file_path}; file left unchanged.")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return True

        if os.path.exists(video_path):
            print(f"Error: target '{video_path}' was created during processing; aborting rename.")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False

        try:
            os.replace(file_path, video_path)
            try:
                os.replace(temp_path, file_path)
            except Exception as e:
                if not os.path.exists(file_path) and os.path.exists(video_path):
                    try:
                        os.replace(video_path, file_path)
                    except Exception:
                        pass
                raise e
        except Exception as e:
            print(f"Error during in-place rename for {file_path}: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False

        final_path = file_path
    else:
        final_path = write_path

    try:
        out_size = os.path.getsize(final_path)
    except OSError:
        out_size = 0

    print(f"Done: {message_count:,} messages written, {stripped_count:,} video messages stripped.")
    if in_size > 0:
        reduction = ((in_size - out_size) / in_size) * 100
        print(f"Size: {in_size:,} bytes -> {out_size:,} bytes (reduced by {reduction:.1f}%)")
    else:
        print(f"Size: {out_size:,} bytes")

    return True


def count_mcap_messages(file_path: str, extract: bool = False, raw: bool = False):
    """Report message counts by channel/topic in an MCAP file."""
    if not extract and not raw:
        info = util.get_mcap_summary_info(file_path)
        if info and info.channel_counts:
            print(f"--- Message Counts for: {file_path} ---")
            for topic, count in sorted(info.channel_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"{count:5d} | {topic}")
            return

    message_counts = Counter()
    extract_files = {}

    try:
        with open(file_path, "rb") as f:
            reader = make_reader(f)

            for schema, channel, message in reader.iter_messages():
                identifier = channel.topic
                if schema and schema.name:
                    identifier = f"{channel.topic} ({schema.name})"

                message_counts[identifier] += 1

                is_service_log = channel.topic.startswith("services/") and channel.topic.endswith("/log")
                is_sys_info = channel.topic.startswith("system_information/")

                if extract and (is_service_log or is_sys_info):
                    parts = channel.topic.split("/")
                    if len(parts) >= 2:
                        service_name = parts[1]
                        if service_name not in extract_files:
                            out_path = util.get_outfile_name(file_path, suffix=f"_{service_name}", ext=".txt")
                            extract_files[service_name] = open(out_path, "w", encoding="utf-8")
                            print(f"Extracting {channel.topic} to {out_path}")

                        f_out = extract_files[service_name]
                        try:
                            data = json.loads(message.data.decode("utf-8"))
                            text = data.get("message", json.dumps(data))
                        except Exception:
                            text = message.data.decode("utf-8", errors="replace")

                        f_out.write(text + "\n")

        print(f"--- Message Counts for: {file_path} ---")
        if not message_counts:
            print("No messages found in the file.")

        for topic, count in message_counts.most_common():
            print(f"{count:5d} | {topic}")

    except Exception as e:
        print(f"Error reading MCAP file: {e}")
    finally:
        for f_out in extract_files.values():
            f_out.close()


def parse_compressed_video(
    payload: bytes, encoding: str, schema_name: str | None
) -> tuple[float | None, str, str, bytes]:
    """
    Parse a video message payload to extract (timestamp, frame_id, format, raw_video_bytes).
    Supports CDR-encoded foxglove.CompressedVideo, JSON, and raw Annex B bitstreams.
    """
    if encoding == "cdr" or (schema_name and "compressedvideo" in schema_name.lower() and len(payload) > 16):
        try:
            offset = 4  # Skip 4-byte CDR header
            sec, nsec = struct.unpack_from("<iI", payload, offset)
            offset += 8

            str_len = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            frame_id = payload[offset : offset + str_len - 1].decode("utf-8", errors="replace") if str_len > 1 else ""
            offset += str_len
            if offset % 4 != 0:
                offset += 4 - (offset % 4)

            data_len = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            data = payload[offset : offset + data_len]
            offset += data_len
            if offset % 4 != 0:
                offset += 4 - (offset % 4)

            vformat = "h264"
            if offset + 4 <= len(payload):
                format_len = struct.unpack_from("<I", payload, offset)[0]
                offset += 4
                if format_len > 1 and offset + format_len - 1 <= len(payload):
                    vformat = payload[offset : offset + format_len - 1].decode("utf-8", errors="replace")

            ts = sec + nsec * 1e-9 if (sec != 0 or nsec != 0) else None
            return ts, frame_id, vformat.lower(), data
        except Exception:
            pass

    if encoding == "json":
        try:
            obj = json.loads(payload.decode("utf-8"))
            if isinstance(obj, dict):
                vformat = obj.get("format", "h264").lower()
                data_field = obj.get("data", b"")
                if isinstance(data_field, str):
                    import base64

                    data = base64.b64decode(data_field)
                elif isinstance(data_field, list):
                    data = bytes(data_field)
                else:
                    data = bytes(data_field)
                ts_dict = obj.get("timestamp", {})
                ts = ts_dict.get("sec", 0) + ts_dict.get("nsec", 0) * 1e-9 if ts_dict else None
                return ts, obj.get("frame_id", ""), vformat, data
        except Exception:
            pass

    return None, "", "h264", payload


def clean_channel_suffix(topic: str) -> str:
    """Derive a concise file suffix from a video topic name."""
    clean = topic.strip("/").replace("/", "_")
    if clean.startswith("video_"):
        clean = clean[len("video_") :]
    if clean.endswith("_stream"):
        clean = clean[: -len("_stream")]
    return clean if clean else "video"


def extract_video_from_mcap(
    file_path: str,
    fps: float = 30.0,
    topic_filter: str | None = None,
    suffix: str | None = None,
    out_dir: str | None = None,
    verbose: bool = False,
) -> list[str]:
    """
    Extract video streams from an MCAP file and write to MP4 using ffmpeg.
    Returns a list of created MP4 file paths.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        print("Error: ffmpeg is required to extract video to MP4, but was not found in PATH.", file=sys.stderr)
        return []

    try:
        f_in = open(file_path, "rb")
    except OSError as e:
        print(f"Error opening {file_path}: {e}", file=sys.stderr)
        return []

    created_files = []
    with f_in:
        reader = make_reader(f_in)
        summary = reader.get_summary()

        video_channels = {}
        if summary and summary.channels:
            for ch_id, ch in summary.channels.items():
                schema = summary.schemas.get(ch.schema_id) if ch.schema_id else None
                schema_name = schema.name if schema else None
                if is_video_channel(ch.topic, schema_name):
                    if topic_filter and topic_filter not in ch.topic:
                        continue
                    video_channels[ch_id] = ch

        if summary and not video_channels:
            print(f"No matching video channels found in {file_path}")
            return []

        single_channel = len(video_channels) == 1
        writers = {}

        try:
            topics_to_read = [ch.topic for ch in video_channels.values()] if video_channels else None
            iter_kwargs = {"topics": topics_to_read} if topics_to_read else {}

            for schema, channel, message in reader.iter_messages(**iter_kwargs):
                schema_name = schema.name if schema else None
                if channel.id not in video_channels:
                    if not is_video_channel(channel.topic, schema_name):
                        continue
                    if topic_filter and topic_filter not in channel.topic:
                        continue
                    video_channels[channel.id] = channel

                if channel.id not in writers:
                    if single_channel:
                        file_suffix = f"_{suffix}" if suffix else "_video"
                    else:
                        stream_tag = clean_channel_suffix(channel.topic)
                        file_suffix = f"_{stream_tag}_{suffix}" if suffix else f"_{stream_tag}"

                    default_out_path = util.get_outfile_name(file_path, suffix=file_suffix, ext=".mp4")
                    if out_dir:
                        out_path = os.path.join(out_dir, os.path.basename(default_out_path))
                    else:
                        out_path = default_out_path

                    _, _, vformat, raw_data = parse_compressed_video(
                        message.data, channel.message_encoding, schema_name
                    )
                    fmt_flag = "hevc" if "h265" in vformat or "hevc" in vformat else "h264"

                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-r",
                        str(fps),
                        "-f",
                        fmt_flag,
                        "-i",
                        "-",
                        "-c",
                        "copy",
                        out_path,
                    ]

                    if verbose:
                        print(f"  Starting ffmpeg for {channel.topic} -> {out_path}")
                        print(f"  Command: {' '.join(cmd)}")

                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE if not verbose else None,
                        stderr=subprocess.PIPE if not verbose else None,
                    )

                    writers[channel.id] = {
                        "proc": proc,
                        "out_path": out_path,
                        "topic": channel.topic,
                        "schema_name": schema_name,
                        "encoding": channel.message_encoding,
                        "frames": 0,
                        "bytes": 0,
                    }
                    created_files.append(out_path)

                w = writers[channel.id]
                _, _, _, raw_data = parse_compressed_video(message.data, w["encoding"], w["schema_name"])

                try:
                    w["proc"].stdin.write(raw_data)
                    w["frames"] += 1
                    w["bytes"] += len(raw_data)
                except BrokenPipeError:
                    print(f"Warning: ffmpeg process exited prematurely for {w['topic']}", file=sys.stderr)
                    break

        finally:
            for w in writers.values():
                proc = w["proc"]
                try:
                    stdout, stderr = proc.communicate()
                    if proc.returncode != 0:
                        err_msg = stderr.decode(errors="replace") if stderr else "Unknown error"
                        print(
                            f"Error: ffmpeg failed for {w['topic']} (code {proc.returncode}):\n{err_msg}",
                            file=sys.stderr,
                        )
                    else:
                        file_sz = os.path.getsize(w["out_path"]) if os.path.exists(w["out_path"]) else 0
                        duration_sec = w["frames"] / fps if fps > 0 else 0
                        duration_str = f"{int(duration_sec // 60)}m {duration_sec % 60:04.1f}s"
                        print(
                            f"  Wrote {w['frames']:,} frames to {w['out_path']} "
                            f"({file_sz / (1024 * 1024):.1f} MB, {duration_str} @ {fps:.1f} fps)"
                        )
                except Exception as e:
                    print(f"Error finalizing video {w['out_path']}: {e}", file=sys.stderr)

    return created_files


def convert_json_to_pymavlink(msg_class, msg_data):
    """Convert JSON values to pymavlink-compatible values."""
    kwargs = {}
    for k, v in msg_data.items():
        if k == "mavtype":
            k = "type"

        expected_type = None
        if hasattr(msg_class, "fieldnames"):
            if k not in msg_class.fieldnames:
                continue
            idx = msg_class.fieldnames.index(k)
            expected_type = msg_class.fieldtypes[idx]

        if isinstance(v, dict) and "type" in v:
            v = v["type"]

        if isinstance(v, str):
            if expected_type == "char":
                v = v.encode("utf-8")
            else:
                if "|" in v:
                    parts = [p.strip() for p in v.split("|")]
                    result = 0
                    for p in parts:
                        enum_v = getattr(mavlink, p, None)
                        if enum_v is not None:
                            result |= enum_v
                    v = result
                else:
                    enum_v = getattr(mavlink, v, None)
                    if enum_v is not None:
                        v = enum_v
                    elif v == "":
                        v = 0

        kwargs[k] = v

    return kwargs


def mcap_to_tlog(mcap_file: str, msg_types: list[str] | None = None):
    """Convert MCAP files containing MAVLink messages to tlog format."""
    output_filename = util.get_outfile_name(mcap_file, ext=".tlog")
    print(f"Reading {mcap_file}")
    print(f"Writing {output_filename}")

    msg_count = 0

    try:
        with open(mcap_file, "rb") as f_in, open(output_filename, "wb") as f_out:
            reader = make_reader(f_in)
            mav = mavlink.MAVLink(None)

            for schema, channel, message in reader.iter_messages(topics=["mavlink/out"]):
                timestamp_us = int(message.log_time / 1000)

                data = json.loads(message.data)
                header = data["header"]
                msg_data = data["message"]
                msg_type = msg_data.pop("type")

                if msg_types is not None and msg_type not in msg_types:
                    continue

                sys_id = header.get("system_id", 1)
                comp_id = header.get("component_id", 1)
                seq = header.get("sequence", 0)

                msg_class = getattr(mavlink, f"MAVLink_{msg_type.lower()}_message", None)
                if msg_class:
                    kwargs = convert_json_to_pymavlink(msg_class, msg_data)
                    msg = msg_class(**kwargs)

                    mav.srcSystem = sys_id
                    mav.srcComponent = comp_id
                    mav.seq = seq

                    packed_bytes = msg.pack(mav)
                    tlog_header = struct.pack(">Q", timestamp_us)
                    f_out.write(tlog_header)
                    f_out.write(packed_bytes)

                    msg_count += 1

        print(f"Converted {msg_count} messages")

    except Exception as e:
        print(f"Error processing {mcap_file}: {e}")
        if os.path.exists(output_filename):
            try:
                os.remove(output_filename)
            except OSError:
                pass


def msg_to_string(msg):
    """Produce a canonical string version of the message for difflib."""
    d = msg.to_dict()
    d.pop("mavpackettype", None)

    for k, v in d.items():
        if isinstance(v, float) and v == 0.0:
            d[k] = 0.0

    fields = ", ".join(f"{k}={d[k]}" for k in sorted(d.keys()))
    sys_id = msg.get_srcSystem()
    comp_id = msg.get_srcComponent()
    seq = msg.get_header().seq
    msg_type = msg.get_type()

    return f"[{sys_id:03d}:{comp_id:03d}] SEQ:{seq:03d} {msg_type} {{{fields}}}\n"


def diff_tlog(qgc_path: str, blueos_path: str, types: list[str] | None = None, output_file: str = "diff.patch"):
    """Compare a QGC-generated tlog to a BlueOS-generated tlog."""
    mavutil.mavfile.auto_mavlink_version = lambda *args, **kwargs: None

    print(f"Reading {blueos_path} to establish time bounds...")
    blueos_mlog = mavutil.mavlink_connection(blueos_path, dialect="ardupilotmega")
    blueos_lines = []
    first_ts = None
    last_ts = None
    while True:
        msg = blueos_mlog.recv_match(blocking=False, type=types)
        if msg is None:
            break

        ts = getattr(msg, "_timestamp", 0.0)
        if first_ts is None:
            first_ts = ts
        last_ts = ts
        blueos_lines.append(msg_to_string(msg))

    if first_ts is None:
        print("Error: BlueOS tlog has no messages.")
        return

    print(f"Time bounds established: {first_ts:.3f} to {last_ts:.3f}")

    print(f"Reading {qgc_path}...")
    qgc_mlog = mavutil.mavlink_connection(qgc_path, dialect="ardupilotmega")
    qgc_lines = []
    while True:
        msg = qgc_mlog.recv_match(blocking=False, type=types)
        if msg is None:
            break

        ts = getattr(msg, "_timestamp", 0.0)
        if first_ts - 0.01 <= ts <= last_ts + 0.01:
            qgc_lines.append(msg_to_string(msg))

    print("Generating diff...")
    diff = difflib.unified_diff(qgc_lines, blueos_lines, fromfile=qgc_path, tofile=blueos_path, n=3)

    print(f"Writing diff to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as outfile:
        outfile.writelines(diff)


def topic_to_log_name(topic: str) -> str:
    """Derive a clean, safe output name/suffix from a channel topic."""
    if topic.startswith(EXTENSION_LOG_PREFIX):
        return topic[len(EXTENSION_LOG_PREFIX) :]
    if topic.startswith("services/") and topic.endswith("/log"):
        return topic[len("services/") : -len("/log")]
    if topic.startswith("services/"):
        return topic[len("services/") :].replace("/", "_")
    parts = topic.split("/")
    if len(parts) > 1 and parts[-1] in ("log", "logs"):
        parts = parts[:-1]
    return "_".join(parts)


def dump_logs(mcap_file: str, extensions_only: bool = False, verbose: bool = False) -> dict[str, int]:
    """
    Extract log messages from an MCAP file.
    Writes output files with the pattern: <path>/<basename>_<log_name>.txt
    Returns a dictionary mapping log name to message count.
    """
    out_files = {}
    counts = defaultdict(int)

    try:
        with open(mcap_file, "rb") as f:
            reader = make_reader(f)

            topics = None
            summary = reader.get_summary()
            if summary and summary.channels:
                log_schema_ids = (
                    {s_id for s_id, s in summary.schemas.items() if s.name == FOXGLOVE_LOG_SCHEMA}
                    if summary.schemas
                    else set()
                )

                matching_topics = []
                for c in summary.channels.values():
                    if extensions_only:
                        if not c.topic.startswith(EXTENSION_LOG_PREFIX):
                            continue
                        if log_schema_ids and c.schema_id not in log_schema_ids:
                            continue
                        matching_topics.append(c.topic)
                    else:
                        if log_schema_ids:
                            if c.schema_id in log_schema_ids:
                                matching_topics.append(c.topic)
                        else:
                            if (
                                c.topic.startswith(EXTENSION_LOG_PREFIX)
                                or c.topic.startswith("services/")
                                or "log" in c.topic
                            ):
                                matching_topics.append(c.topic)

                if not matching_topics:
                    label = "extension logs" if extensions_only else "logs"
                    print(f"No {label} found in {mcap_file}")
                    return {}
                topics = matching_topics

            iter_kwargs = {"topics": topics} if topics is not None else {}

            for schema, channel, message in reader.iter_messages(**iter_kwargs):
                if extensions_only and not channel.topic.startswith(EXTENSION_LOG_PREFIX):
                    continue

                if schema and schema.name and schema.name != FOXGLOVE_LOG_SCHEMA:
                    continue

                log_name = topic_to_log_name(channel.topic)

                if log_name not in out_files:
                    out_path = util.get_outfile_name(mcap_file, suffix=f"_{log_name}", ext=".txt")
                    out_files[log_name] = open(out_path, "w", encoding="utf-8")
                    if verbose:
                        print(f"  Extracting {channel.topic} -> {out_path}")

                try:
                    data = json.loads(message.data.decode("utf-8"))
                    if isinstance(data, dict):
                        msg = data.get("message")
                        text = str(msg) if msg is not None else json.dumps(data)
                    else:
                        text = str(data)
                except Exception:
                    text = message.data.decode("utf-8", errors="replace")

                out_files[log_name].write(text.rstrip("\r\n") + "\n")
                counts[log_name] += 1

    finally:
        for f_out in out_files.values():
            f_out.close()

    for log_name, count in counts.items():
        out_path = util.get_outfile_name(mcap_file, suffix=f"_{log_name}", ext=".txt")
        print(f"  Wrote {count:5d} messages to {out_path}")

    if not counts:
        label = "extension logs" if extensions_only else "logs"
        print(f"  No {label} found in {mcap_file}")

    return counts


def dump_extension_logs(mcap_file: str, verbose: bool = False) -> dict[str, int]:
    """Compatibility wrapper to dump only extension logs."""
    return dump_logs(mcap_file, extensions_only=True, verbose=verbose)


class AcousticLogInfo:
    def __init__(self, mcap_file: str):
        self.mcap_file = mcap_file
        self.passes = []

    def read(self):
        self.passes = parse_waterlinked_ugps(self.mcap_file)

    def report(self):
        print(f"Reading {self.mcap_file}")
        if not self.passes:
            print("  No waterlinked.ugps extension logs found.")
            return

        total_readings = len(self.passes)
        first_time = self.passes[0].get("timestamp")
        last_time = self.passes[-1].get("timestamp")

        if first_time is not None and last_time is not None:
            duration = last_time - first_time
            print(f"  Log span: {util.time_str(first_time)} to {util.time_str(last_time)} ({duration:.1f} s)")

        print(f"  Total readings: {total_readings}")

        # 1. Acoustic Fixes
        valid_fixes = [p for p in self.passes if p.get("acoustic_valid") is True]
        pct_fixes = (100.0 * len(valid_fixes) / total_readings) if total_readings > 0 else 0.0
        print("\n  Acoustic fixes:")
        print(f"    Valid acoustic fixes: {len(valid_fixes)} / {total_readings} ({pct_fixes:.2f}%)")

        if valid_fixes:
            first_fix_ts = valid_fixes[0].get("timestamp")
            print(
                f"    Time of first valid acoustic fix: {util.time_str(first_fix_ts)} (timestamp: {first_fix_ts:.3f})"
            )
        else:
            print("    Time of first valid acoustic fix: None")

        # 2. Transducer Readings
        print("\n  Transducer valid readings:")
        for idx in range(4):
            valid_count = sum(
                1 for p in self.passes if p.get(f"receiver_valid_{idx}") == 1 or p.get(f"receiver_valid_{idx}") is True
            )
            pct = (100.0 * valid_count / total_readings) if total_readings > 0 else 0.0
            print(f"    {TRANSDUCER_DESCRIPTIONS[idx]:35s}: {valid_count:5d} / {total_readings} ({pct:6.2f}%)")

        # 3. Simultaneous valid transducer count distribution
        simultaneous_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        for p in self.passes:
            count = sum(
                1 for idx in range(4) if p.get(f"receiver_valid_{idx}") == 1 or p.get(f"receiver_valid_{idx}") is True
            )
            simultaneous_counts[count] += 1

        print("\n  Simultaneous valid transducers distribution:")
        print(
            f"    4 valid (full 3D solution)   : {simultaneous_counts[4]:5d} / {total_readings} ({100.0 * simultaneous_counts[4] / total_readings:6.2f}%)"
        )
        print(
            f"    3 valid (minimum 3D solution): {simultaneous_counts[3]:5d} / {total_readings} ({100.0 * simultaneous_counts[3] / total_readings:6.2f}%)"
        )
        print(
            f"    2 valid (no 3D solution)     : {simultaneous_counts[2]:5d} / {total_readings} ({100.0 * simultaneous_counts[2] / total_readings:6.2f}%)"
        )
        print(
            f"    1 valid (no 3D solution)     : {simultaneous_counts[1]:5d} / {total_readings} ({100.0 * simultaneous_counts[1] / total_readings:6.2f}%)"
        )
        print(
            f"    0 valid (no signal)          : {simultaneous_counts[0]:5d} / {total_readings} ({100.0 * simultaneous_counts[0] / total_readings:6.2f}%)"
        )

        # 4. Transducer Signal Levels (mean RSSI and NSD)
        rssi_avgs = []
        nsd_avgs = []
        for idx in range(4):
            rssi_vals = [p[f"receiver_rssi_{idx}"] for p in self.passes if p.get(f"receiver_rssi_{idx}") is not None]
            nsd_vals = [p[f"receiver_nsd_{idx}"] for p in self.passes if p.get(f"receiver_nsd_{idx}") is not None]
            rssi_avg = sum(rssi_vals) / len(rssi_vals) if rssi_vals else None
            nsd_avg = sum(nsd_vals) / len(nsd_vals) if nsd_vals else None
            rssi_avgs.append(rssi_avg)
            nsd_avgs.append(nsd_avg)

        if any(r is not None for r in rssi_avgs) or any(n is not None for n in nsd_avgs):
            print("\n  Average transducer signal levels:")
            for idx in range(4):
                rssi_str = f"{rssi_avgs[idx]:6.1f} dBm" if rssi_avgs[idx] is not None else "   N/A    "
                nsd_str = f"{nsd_avgs[idx]:6.1f} dB" if nsd_avgs[idx] is not None else "   N/A  "
                print(f"    {TRANSDUCER_DESCRIPTIONS[idx]:35s}: mean RSSI = {rssi_str}, mean NSD = {nsd_str}")

    def read_and_report(self):
        self.read()
        self.report()


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser, ext=".mcap")
    parser.add_argument("-v", "--verbose", action="store_true", help="print a lot more information")
    parser.add_argument("--explode", action="store_true", help="write a csv file for each message type")
    parser.add_argument("--no-merge", action="store_true", help="do not merge, useful if you also select --explode")
    parser.add_argument("--types", default=None, help="comma separated list of message types")
    parser.add_argument("--max-msgs", type=int, default=500000, help="stop after N messages (default 500K)")
    parser.add_argument("--max-rows", type=int, default=500000, help="stop if the merge exceeds N rows (default 500K)")
    parser.add_argument("--rate", action="store_true", help="calculate rate for each message type")
    parser.add_argument("--sysid", type=int, default=None, help="select source system id (default is all)")
    parser.add_argument("--compid", type=int, default=None, help="select source component id (default is all)")
    parser.add_argument("--split-source", action="store_true", help="split messages by source (sysid, compid)")
    parser.add_argument("--system-time", action="store_true", help="use ArduSub SYSTEM_TIME.time_boot_ms vs log time")
    parser.add_argument("--raw", action="store_true", help="show all GPS messages; default is to drop bad GPS messages")
    args = parser.parse_args()

    if args.types:
        msg_types = normalize_types(args.types.split(","))
    else:
        msg_types = PERHAPS_USEFUL_MSG_TYPES

    if args.system_time:
        print("Use SYSTEM_TIME.time_boot_ms instead of log timestamp")
        if "SYSTEM_TIME" not in msg_types:
            print("Adding SYSTEM_TIME to message types")
            msg_types.append("SYSTEM_TIME")

    print(f"Looking for these types: {msg_types}")

    files = util.expand_path(args.path, args.recurse, ".mcap")
    print(f"Processing {len(files)} files")

    segments = parse_segment_args(args)
    if segments:
        for segment in segments:
            seg_prefix = build_segment_name(files[0], segment.name) + ".mcap"
            reader = McapLogReader(
                files[0],
                msg_types,
                args.max_msgs,
                args.verbose,
                args.sysid,
                args.compid,
                args.system_time,
                args.split_source,
                args.raw,
                segment=segment,
                max_rows=args.max_rows,
            )
            reader.infile = seg_prefix
            for file in files:
                print("-------------------")
                print(f"Reading {file} for segment {segment.name}")
                reader.read_mcap(file)

            if args.rate:
                reader.add_rate_field()

            if args.explode:
                reader.write_msg_csv_files()

            if not args.no_merge:
                reader.write_merged_csv_file()
    else:
        for file in files:
            print("-------------------")
            print(f"Reading {file}")
            reader = McapLogReader(
                file,
                msg_types,
                args.max_msgs,
                args.verbose,
                args.sysid,
                args.compid,
                args.system_time,
                args.split_source,
                args.raw,
                max_rows=args.max_rows,
            )

            reader.read_mcap()

            if args.rate:
                reader.add_rate_field()

            if args.explode:
                reader.write_msg_csv_files()

            if not args.no_merge:
                reader.write_merged_csv_file()


if __name__ == "__main__":
    main()
