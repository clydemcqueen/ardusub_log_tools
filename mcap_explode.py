#!/usr/bin/env python3

"""
Read MAVLink messages from an mcap file and write a csv file for each message type.

We only look at the "mavlink/out" channel, which contains MAVLink telemetry from BlueOS.
"""

import argparse
import json

from mcap.reader import make_reader
from pymavlink.dialects.v20 import ardupilotmega as mavlink

import table_types
import util
from log_merger import LogMerger

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
    ):
        super().__init__(filename, max_msgs, 500000, verbose)
        self.filename = filename
        self.types = types
        self.sysid = sysid
        self.compid = compid
        self.system_time = system_time
        self.split_source = split_source
        self.raw = raw
        self.time_delta_s = None

    def read_mcap(self):
        self.tables = {}
        msg_count = 0

        try:
            with open(self.filename, "rb") as f:
                reader = make_reader(f)
                for schema, channel, message in reader.iter_messages(topics=["mavlink/out"]):
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

                    # Filter by sysid and compid
                    if self.sysid is not None and self.sysid != sysid:
                        continue
                    if self.compid is not None and self.compid != compid:
                        continue

                    log_s = message.log_time / 1e9

                    if self.system_time:
                        # Merge on time_boot_ms (time since ArduSub boot in ms) instead of log time
                        if msg_type == "SYSTEM_TIME" and sysid == 1 and compid == 1 and self.time_delta_s is None:
                            self.time_delta_s = log_s - msg_data.get("time_boot_ms", 0) / 1000.0
                            print(f"Time synchronized, delta is {self.time_delta_s} seconds")

                        if self.time_delta_s is None:
                            continue

                        clean_data = {"timestamp": int((log_s - self.time_delta_s) * 1000.0)}
                    else:
                        clean_data = {"timestamp": log_s}

                    # Save sysid and compid in the table name or in the data
                    if self.split_source:
                        table_name = f"{msg_type}_{sysid}_{compid}"
                    else:
                        table_name = msg_type
                        clean_data[f"{msg_type}.sysid"] = sysid
                        clean_data[f"{msg_type}.compid"] = compid

                    # Resolve fields
                    for k, v in msg_data.items():
                        resolved_k, resolved_v = resolve_field_value(k, v)
                        clean_data[f"{table_name}.{resolved_k}"] = resolved_v

                    # Make sure the table exists
                    if table_name not in self.tables:
                        self.tables[table_name] = table_types.Table.create_table(
                            msg_type, table_name=table_name, filter_bad=not self.raw
                        )

                    # Append the message to the table
                    self.tables[table_name].append(clean_data)

                    msg_count += 1
                    if msg_count > self.max_msgs:
                        print("Too many messages, stopping")
                        break
                    if self.verbose and msg_count % 20000 == 0:
                        print(f"{msg_count} messages")

        except Exception as e:
            print(f'CRASH WITH ERROR "{e}", SHOWING PARTIAL RESULTS')

        print(f"{msg_count} messages")

    def add_rate_field(self, half_n=10, field_name="rate"):
        for table_name in self.tables:
            self.tables[table_name].add_rate_field(half_n, field_name)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for mcap files")
    parser.add_argument("-v", "--verbose", action="store_true", help="print a lot more information")
    parser.add_argument("--types", default=None, help="comma separated list of message types")
    parser.add_argument("--max-msgs", type=int, default=500000, help="stop after N messages (default 500K)")
    parser.add_argument("--rate", action="store_true", help="calculate rate for each message type")
    parser.add_argument("--sysid", type=int, default=None, help="select source system id (default is all)")
    parser.add_argument("--compid", type=int, default=None, help="select source component id (default is all)")
    parser.add_argument("--split-source", action="store_true", help="split messages by source (sysid, compid)")
    parser.add_argument("--system-time", action="store_true", help="use ArduSub SYSTEM_TIME.time_boot_ms vs log time")
    parser.add_argument("--raw", action="store_true", help="show all GPS messages; default is to drop bad GPS messages")
    args = parser.parse_args()

    if args.types:
        msg_types = args.types.split(",")
    else:
        msg_types = PERHAPS_USEFUL_MSG_TYPES

    if args.system_time:
        print("Use SYSTEM_TIME.time_boot_ms instead of log timestamp")
        if "SYSTEM_TIME" not in msg_types:
            print("Adding SYSTEM_TIME to message types")
            msg_types.append("SYSTEM_TIME")

    print(f"Looking for these types: {msg_types}")

    files = util.expand_path(args.paths, args.recurse, ".mcap")
    print(f"Processing {len(files)} files")

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
        )

        reader.read_mcap()

        if args.rate:
            reader.add_rate_field()

        reader.write_msg_csv_files()


if __name__ == "__main__":
    main()
