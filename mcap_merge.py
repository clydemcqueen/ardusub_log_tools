#!/usr/bin/env python3

"""
Read MAVLink messages and BlueOS extension logs from an MCAP file and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.

Supports MAVLink telemetry from the "mavlink/out" channel as well as first-class extension
tables such as wl_ugps and wl_ugps_external.

Supports segments.
"""

import argparse
import json

from mcap.reader import make_reader
from pymavlink.dialects.v20 import ardupilotmega as mavlink

import table_types
import util
from log_merger import LogMerger
from mcap_explode_extension_logs import WaterlinkedUgpsParser, WlUgpsExternalParser
from segment_reader import Segment, add_segment_args, build_segment_name, parse_segment_args

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

        want_wl_ugps = self.types is not None and "wl_ugps" in self.types
        want_wl_external = self.types is not None and "wl_ugps_external" in self.types
        want_mavlink = self.types is None or any(t not in ("wl_ugps", "wl_ugps_external") for t in self.types)

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

                wl_external_parser = WlUgpsExternalParser() if want_wl_external else None
                wl_ugps_parser = WaterlinkedUgpsParser() if want_wl_ugps else None

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

                    elif wl_external_parser is not None and "wl_ugps_external" in channel.topic:
                        append_wl_external_rows(wl_external_parser.parse_message(message))

                    elif wl_ugps_parser is not None and "waterlinked.ugps" in channel.topic:
                        append_wl_ugps_rows(wl_ugps_parser.parse_message(message))

                    if msg_count > self.max_msgs:
                        print("Too many messages, stopping")
                        break
                    if self.verbose and msg_count % 20000 == 0:
                        print(f"{msg_count} messages")

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
