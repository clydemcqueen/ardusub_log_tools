#!/usr/bin/env python3

"""
Read ArduSub dataflash messages from a BIN file and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.

BIN_merge.py can also write multiple csv files, one per type, using the --explode option.

You can examine the contents of a single table using the --explode, --no-merge and --types options:
BIN_merge.py --explode --no-merge --types GPS 000011.BIN
"""

import argparse
import datetime
import os
import re
from enum import Enum
from operator import attrgetter

import pandas as pd
import pymavlink.dialects.v20.ardupilotmega as apm
from pymavlink import mavutil

from ardusub_log_tools.backends.telemetry import (
    NOISY_PARAMS,
    EK3_SRCn_POSXY,
    EK3_SRCn_POSZ,
    EK3_SRCn_VELXY,
    EK3_SRCn_VELZ,
    EK3_SRCn_YAW,
)
from ardusub_log_tools.core import table_types, util
from ardusub_log_tools.core.log_merger import LogMerger

# Basically everything I've seen in an ArduSub dataflash (BIN) file
ALL_MSG_TYPES = [
    "AHR2",
    "ARM",
    "ATT",
    "BARO",
    "BAT",
    "CTRL",
    "CTUN",
    "DSF",
    "DU32",
    "EV",
    "FMT",
    "FMTU",
    "FTN",
    "GPA",
    "GPS",
    "IMU",
    "MAG",
    "MAV",
    "MAVC",
    "MODE",
    "MOTB",
    "MSG",
    "MULT",
    "PARM",
    "PM",
    "PSCD",
    "RATE",
    "RCI2",
    "RCIN",
    "RCOU",
    "RFND",
    "UNIT",
    "VIBE",
    "XKF1",
    "XKF2",
    "XKF3",
    "XKF4",
    "XKF5",
    "XKFS",
    "XKQ",
    "XKT",
    "XKV1",
    "XKV2",
    "XKFD",  # Not on by default for ArduSub, need to add a compiler flag
]

# Stuff that looks kinda interesting
PERHAPS_USEFUL_MSG_TYPES = [
    "AHR2",
    "ARM",
    "ATT",
    "BARO",
    "BAT",
    "CTRL",
    "CTUN",
    "DSF",
    "DU32",
    "EV",
    "FMT",
    "FMTU",
    "FTN",
    "GPS",
    "IMU",
    "MAG",
    "MAV",
    "MAVC",
    "MODE",
    "MOTB",
    "MSG",
    "MULT",
    "PARM",
    "PM",
    "PSCD",
    "PSOT",
    "RATE",
    "RCI2",
    "RCIN",
    "RCOU",
    "RFND",
    "XKFD",  # Not on by default for ArduSub, need to add a compiler flag
]

# Messages types that can be split by the 'C' field
SPLIT_CORE_MSG_TYPES = [
    "XKF1",  # EKF3 estimator outputs
    "XKF2",  # EKF3 estimator secondary outputs
    "XKF3",  # EKF3 innovations
    "XKF4",  # EKF3 variances
    "XKFS",  # EKF3 sensor selection
    "XKQ",  # EKF3 quaternion defining the rotation from NED to XYZ (autopilot) axes
    "XKT",  # EKF3 timing information
    "XKTV",  # EKF3 Yaw Estimator States
]

# Messages types that can be split by the 'I' field
SPLIT_INSTANCE_MSG_TYPES = [
    "BARO",  # Barometer data
    "IMU",  # IMU data
    "MAG",  # Compass data
]

# Messages types that can be split by the 'chan' field
SPLIT_CHANNEL_MSG_TYPES = [
    "MAV",  # MAVLink link statistics
]

EKF_MSG_TYPES = [
    *SPLIT_CORE_MSG_TYPES,
    "XKF5",  # EKF3 Sensor innovations (primary core) and general dumping ground
    "XKV1",  # EKF3 State variances (primary core)
    "XKV2",  # more EKF3 State Variances (primary core)
]


class DataflashTable:
    @staticmethod
    def create_table(msg_type: str):
        if msg_type == "RCIN":
            return RCINTable()
        elif msg_type == "PSCN":
            return PSCxTable(msg_type, "N", flip=False)
        elif msg_type == "PSCE":
            return PSCxTable(msg_type, "E", flip=False)
        elif msg_type == "PSCD":
            return PSCxTable(msg_type, "D", flip=False)
        elif msg_type == "PSCU":
            return PSCxTable(msg_type, "D", flip=True)
        elif msg_type == "PSOT":
            return PSOTTable(msg_type)
        elif msg_type == "XKV1":
            return XKV1Table(msg_type)
        elif msg_type == "XKV2":
            return XKV2Table(msg_type)
        elif msg_type.startswith("XKF1"):
            return XKF1Table(msg_type)
        elif msg_type.startswith("XKF4"):
            return XKF4Table(msg_type)
        elif msg_type.startswith("XKF5"):
            return XKF5Table(msg_type)
        else:
            return DataflashTable(msg_type)

    def __init__(self, msg_type: str):
        self._msg_type = msg_type
        self._rows = []
        self._df = None

    def append(self, row: dict):
        self._rows.append(row)

    def get_dataframe(self, verbose):
        if self._df is None:
            self._df = pd.DataFrame(self._rows)
            if not self._df.empty and "timestamp" in self._df.columns:
                self._df[f"{self._msg_type}._dt"] = self._df["timestamp"].diff().fillna(0.0)
            if verbose:
                print("-----------------")
                if self._df.empty:
                    print(f"{self._msg_type} is empty")
                else:
                    print(f"{self._msg_type} has {len(self._df)} rows:")
                    print(self._df.head())

        return self._df


class RCINTable(DataflashTable):
    def __init__(self):
        super().__init__("RCIN")

    RC_MAP = [(1, "pitch"), (2, "roll"), (3, "throttle"), (4, "yaw"), (5, "forward"), (6, "lateral")]

    def append(self, row: dict):
        # Rename a few fields for ease-of-use
        for item in RCINTable.RC_MAP:
            row[f"RCIN.C{item[0]}_{item[1]}"] = row.pop(f"RCIN.C{item[0]}")
        super().append(row)


class PSCxTable(DataflashTable):
    """
    Works with PosControl tables PSCN (north), PSCE (east), PSCD (down) and the made-up table PSCU (up)
    Suffix should be 'N', 'E', 'D'; this is used to change field names from short codes to log_PSCx struct field names
    Flip means flip the sign, e.g., from down to up

    Key and source of data:
    Short  Long             Method                              Variable
    TP     pos_target       get_pos_target_cm().z               _pos_target.z
    P      pos              _inav.get_position_z_up_cm()        _relpos_cm.z
    DV     vel_desired      get_vel_desired_cms().z             _vel_desired.z
    TV     vel_target       get_vel_target_cms().z              _vel_target.z
    V      vel              _inav.get_velocity_z_up_cms()       _velocity_cm.z
    DA     accel_desired    _accel_desired.z                    _accel_desired.z
    TA     accel_target     get_accel_target_cmss().z           _accel_target.z
    A      accel            get_z_accel_cmss()                  -(_ahrs.get_accel_ef().z + GRAVITY_MSS) * 100.0
    """

    def __init__(self, table_name: str, suffix: str, flip: bool):
        super().__init__(table_name)
        self._suffix = suffix
        self._flip = flip

    MAP = [
        ("TP", "pos_target"),
        ("P", "pos"),
        ("DV", "vel_desired"),
        ("TV", "vel_target"),
        ("V", "vel"),
        ("DA", "accel_desired"),
        ("TA", "accel_target"),
        ("A", "accel"),
    ]

    def append(self, row: dict):
        for item in PSCxTable.MAP:
            field = row.pop(f"{self._msg_type}.{item[0]}{self._suffix}")
            row[f"{self._msg_type}.{item[1]}"] = -field if self._flip else field
        super().append(row)


class PSOTTable(DataflashTable):
    """
    Add U (up) fields to the PSOT "Position Control Offsets Terrain (Down)" table

    Key and source of data as of AP 4.7:
    Short   log_PSOx struct field   Underlying PosControl variable
    TPOT    pos_target_offset       -_pos_terrain_target_u_m
    POT     pos_offset              -_pos_terrain_u_m
    TVOT    vel_target_offset       0 (always)
    VOT     vel_offset              -_vel_terrain_u_ms
    TAOT    accel_target_offset     0 (always)
    AOT     accel_offset            -_accel_terrain_u_mss

    Might be interesting to do this for PSOx similar to PSCx, but start here
    """

    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        for field in ["AOT", "POT", "TAOT", "TPOT", "TVOT", "VOT"]:
            d_field = f"{self._msg_type}.{field}"
            if d_field in row:
                row[f"{self._msg_type}.{field}_U"] = -row[d_field]
        super().append(row)


def rename_fields(row: dict, map: list[tuple], msg_type: str) -> dict:
    for item in map:
        field = row.pop(f"{msg_type}.{item[0]}")
        row[f"{msg_type}.{item[1]}"] = field
    return row


class XKV1Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    MAP = [
        ("V00", "q0"),
        ("V01", "q1"),
        ("V02", "q2"),
        ("V03", "q3"),
        ("V04", "vel_N"),
        ("V05", "vel_E"),
        ("V06", "vel_D"),
        ("V07", "pos_N"),
        ("V08", "pos_E"),
        ("V09", "pos_D"),
        ("V10", "gyro_bias_X"),
        ("V11", "gyro_bias_Y"),
    ]

    def append(self, row: dict):
        rename_fields(row, XKV1Table.MAP, self._msg_type)
        super().append(row)


class XKF1Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        # Add a PU (position up) field = -PD (position down)
        pd_field = f"{self._msg_type}.PD"
        if pd_field in row:
            row[f"{self._msg_type}.PU"] = -row[pd_field]
        super().append(row)


class XKV2Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    MAP = [
        ("V12", "gyro_bias_Z"),
        ("V13", "accel_bias_X"),
        ("V14", "accel_bias_Y"),
        ("V15", "accel_bias_Z"),
        ("V16", "earth_mag_N"),
        ("V17", "earth_mag_E"),
        ("V18", "earth_mag_D"),
        ("V19", "body_mag_X"),
        ("V20", "body_mag_Y"),
        ("V21", "body_mag_Z"),
        ("V22", "wind_vel_N"),
        ("V23", "wind_vel_E"),
    ]

    def append(self, row: dict):
        rename_fields(row, XKV2Table.MAP, self._msg_type)
        super().append(row)


class XKF4Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        ss_field = f"{self._msg_type}.SS"
        row[f"{self._msg_type}.const_pos"] = 1 if row[ss_field] & (1 << 7) else 0
        row[f"{self._msg_type}.horiz_rel"] = 1 if row[ss_field] & (1 << 3) else 0
        super().append(row)


class XKF5Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        # Add offset_up field as negative of offset (terrainState)
        offset_field = f"{self._msg_type}.offset"
        if offset_field in row:
            row[f"{self._msg_type}.offset_up"] = -row[offset_field]
        super().append(row)


class DataflashTableSTATUS(DataflashTable):
    def __init__(self, tables: dict, verbose: bool):
        super().__init__("STATUS")

        print("Generating STATUS table")

        frames = []

        if "MODE" in tables:
            df = tables["MODE"].get_dataframe(verbose)[["timestamp", "MODE.TimeUS", "MODE.Mode"]].copy()
            df.rename(columns={"MODE.TimeUS": "STATUS.TimeUS", "MODE.Mode": "STATUS.Mode"}, inplace=True)
            df["STATUS.Source"] = 0
            frames.append(df)

        if "ARM" in tables:
            df = tables["ARM"].get_dataframe(verbose)[["timestamp", "ARM.TimeUS", "ARM.ArmState"]].copy()
            df.rename(columns={"ARM.TimeUS": "STATUS.TimeUS", "ARM.ArmState": "STATUS.ArmState"}, inplace=True)
            df["STATUS.Source"] = 1
            frames.append(df)

        if "ERR" in tables:
            df = tables["ERR"].get_dataframe(verbose)[["timestamp", "ERR.TimeUS", "ERR.Subsys", "ERR.ECode"]].copy()
            df.rename(
                columns={
                    "ERR.TimeUS": "STATUS.TimeUS",
                    "ERR.Subsys": "STATUS.ERR_Subsys",
                    "ERR.ECode": "STATUS.ERR_ECode",
                },
                inplace=True,
            )
            df["STATUS.Source"] = 2
            frames.append(df)

        if "EV" in tables:
            df = tables["EV"].get_dataframe(verbose)[["timestamp", "EV.TimeUS", "EV.Id"]].copy()
            df.rename(columns={"EV.TimeUS": "STATUS.TimeUS", "EV.Id": "STATUS.EV_Id"}, inplace=True)
            df["STATUS.Source"] = 3
            frames.append(df)

        if frames:
            status_df: pd.DataFrame = pd.concat(frames)
            status_df.sort_values(by=["timestamp"], inplace=True)
            self._rows = status_df.to_dict("records")


class DataflashLogReader(LogMerger):
    def __init__(
        self,
        infile: str,
        msg_types: list[str],
        max_msgs: int,
        max_rows: int,
        verbose: bool,
        raw: bool,
        start: float,
        stop: float,
        rtc_shift: float = 0.0,
    ):
        super().__init__(infile, max_msgs, max_rows, verbose)
        self.msg_types = msg_types
        self.raw = raw
        self.start = start
        self.stop = stop
        self.rtc_shift = rtc_shift

        # Make up the PSCU (position control 'up') table, a flipped version of PSCD
        self.pscu = "PSCU" in msg_types
        if self.pscu:
            if "PSCD" in msg_types:
                print("PSCD and PSCU both requested, dropping PSCD")
            else:
                msg_types.append("PSCD")

        # Make up the STATUS table from MODE, ARM, ERR and EV
        self.status = "STATUS" in msg_types
        if self.status:
            msg_types.remove("STATUS")
            print("STATUS is a synthetic table and requires MODE, ARM, ERR and EV")
            if "MODE" not in msg_types:
                msg_types.append("MODE")
            if "ARM" not in msg_types:
                msg_types.append("ARM")
            if "ERR" not in msg_types:
                msg_types.append("ERR")
            if "EV" not in msg_types:
                msg_types.append("EV")

    def read(self):
        self.tables = {}

        print(f"Reading {self.infile}")
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=False, dialect="ardupilotmega")

        print("Parsing messages")
        msg_count = 0
        while (msg := mlog.recv_match(blocking=False, type=self.msg_types)) is not None:
            msg_type = msg.get_type()
            raw_data = msg.to_dict()

            # Hack: drop readings from the barometer inside the electronics tube
            if not self.raw and msg_type == "BARO" and raw_data["I"] == 0:
                continue

            # Hack: drop GPS and AHR2 readings where Lat/Lng are 0
            if not self.raw and (msg_type == "AHR2" or msg_type == "GPS") and raw_data["Lat"] == 0:
                continue

            table_name = msg_type

            # Hack: split some tables into _core0, ... and _instance0, ...
            if msg_type in SPLIT_CORE_MSG_TYPES:
                table_name = f"{msg_type}_core{msg.C}"
            elif msg_type in SPLIT_INSTANCE_MSG_TYPES:
                table_name = f"{msg_type}_instance{msg.I}"
            elif msg_type in SPLIT_CHANNEL_MSG_TYPES:
                table_name = f"{msg_type}_chan{msg.chan}"

            # Hack: make up the PSCU table
            if msg_type == "PSCD" and self.pscu:
                table_name = "PSCU"

            # This will pull from TimeUS, which is present in nearly all records
            timestamp = getattr(msg, "_timestamp", 0.0) + self.rtc_shift

            # Hack: process just a segment
            if self.start >= 0 and timestamp < self.start:
                continue
            if 0 < self.stop < timestamp:
                continue

            # Clean up the data: add the timestamp, remove mavpackettype, and rename the keys
            clean_data = {"timestamp": timestamp}
            for key in raw_data.keys():
                if key != "mavpackettype":
                    clean_data[f"{table_name}.{key}"] = raw_data[key]

            if table_name not in self.tables:
                print(f"adding {table_name}")
                self.tables[table_name] = DataflashTable.create_table(table_name)

            self.tables[table_name].append(clean_data)

            msg_count += 1
            if msg_count > self.max_msgs:
                print("Too many messages, stopping")
                break
            if self.verbose and msg_count % 20000 == 0:
                print(f"{msg_count} messages")

        print(f"{msg_count} messages")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for BIN files")
    parser.add_argument("-v", "--verbose", action="store_true", help="print a lot more information")
    parser.add_argument("--explode", action="store_true", help="write a csv file for each message type")
    parser.add_argument("--no-merge", action="store_true", help="do not merge, useful if you also select --explode")
    parser.add_argument("--types", default=None, help="comma separated list of message types")
    parser.add_argument("--ekf", action="store_true", help="add all EKF message types to the list of types")
    parser.add_argument("--max-msgs", type=int, default=500000, help="stop after N messages (default 500K)")
    parser.add_argument("--max-rows", type=int, default=500000, help="stop if the merge exceeds N rows (default 500K)")
    parser.add_argument("--raw", action="store_true", help="do not drop BARO records where id==0")
    parser.add_argument("--start", type=float, default=-1.0, help="experiment: segment start")
    parser.add_argument("--stop", type=float, default=-1.0, help="experiment: segment stop")
    parser.add_argument("--sync", default=None, help="experiment: provide a tlog file to establish an rtc_shift")
    parser.add_argument("path", nargs="+")
    args = parser.parse_args()

    if args.types:
        args.types = args.types.upper()

    files = util.expand_path(args.path, args.recurse, ".BIN")
    print(f"Processing {len(files)} files")

    if args.types:
        msg_types = args.types.split(",")
        if args.ekf:
            msg_types.extend(EKF_MSG_TYPES)
    elif args.ekf:
        msg_types = EKF_MSG_TYPES
    else:
        msg_types = PERHAPS_USEFUL_MSG_TYPES
    print(f"Looking for {len(msg_types)} types: {msg_types}")

    if args.sync:
        print(f"Experiment: adjust timestamps using an RTC shift from {args.sync}")
        tlog_conn = mavutil.mavlink_connection(args.sync, robust_parsing=False)
        rtc_shift = util.get_rtc_shift(tlog_conn)
        if rtc_shift is None:
            print("Failed to get RTC shift")
            rtc_shift = 0
        else:
            print(f"RTC shift is {rtc_shift}")
    else:
        rtc_shift = 0

    for file in files:
        print("===================")
        reader = DataflashLogReader(
            file, msg_types, args.max_msgs, args.max_rows, args.verbose, args.raw, args.start, args.stop, rtc_shift
        )
        reader.read()
        if reader.status:
            reader.tables["STATUS"] = DataflashTableSTATUS(reader.tables, args.verbose)
        if args.explode:
            reader.write_msg_csv_files()
        if not args.no_merge:
            reader.write_merged_csv_file()


# ---------------------------------------------------------------------------
# DataflashLogInfo
# ---------------------------------------------------------------------------
class DataflashLogInfo:
    def __init__(self, infile: str):
        self.infile = infile
        self.message_counts = {}

    def read_and_report(self):
        print(f"Results for {self.infile}")
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=False, dialect="ardupilotmega")

        count_gps_records = 0
        gps_week = 0
        gps_week_ms = 0
        count_orgn_records = 0
        count_file_records = 0
        embedded_files = {}

        while (msg := mlog.recv_match(blocking=False, type=["MSG", "GPS", "ORGN", "FILE"])) is not None:
            mtype = msg.get_type()
            if mtype == "MSG":
                message = msg.Message
                self.message_counts[message] = self.message_counts.get(message, 0) + 1
            elif mtype == "GPS" and gps_week == 0:
                count_gps_records += 1
                if msg.GWk > 0:
                    gps_week = msg.GWk
                    gps_week_ms = msg.GMS
            elif mtype == "ORGN":
                count_orgn_records += 1
                origin_type = "EKF origin" if msg.Type == 0 else "AHRS home"
                print(f"{origin_type} set after {msg.TimeUS / 1e6:.1f} seconds: ({msg.Lat}, {msg.Lng}, {msg.Alt})")
            elif mtype == "FILE":
                count_file_records += 1
                name = getattr(msg, "FileName", "")
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="replace")
                name = name.rstrip("\x00").strip()
                if name:
                    offset = getattr(msg, "Offset", 0)
                    length = getattr(msg, "Length", 0)
                    embedded_files[name] = max(embedded_files.get(name, 0), offset + length)

        if count_orgn_records == 0:
            print("No ORGN records, origin was not set")

        if count_gps_records == 0:
            print("No GPS records, no datetime information")
        elif gps_week == 0:
            print(f"{count_gps_records} GPS records, gps_week is always 0, no datetime information")
        else:
            print(f"{count_gps_records} GPS records, last record gps_week {gps_week}, gps_week_ms {gps_week_ms}")

        if count_file_records == 0:
            print("No FILE records, no embedded files")
        elif not embedded_files:
            print(f"{count_file_records} FILE records, no file names found")
        else:
            print(f"{count_file_records} FILE records, embedded files:")
            for name, size in sorted(embedded_files.items()):
                print(f"    {name} ({size} bytes)")

        print("List of messages, with counts:")
        for item in sorted(self.message_counts.items()):
            print(f"{item[1]:8d}  {item[0]}")


# ---------------------------------------------------------------------------
# DataflashFileExtractor
# ---------------------------------------------------------------------------
def sanitize_filename(name: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return safe_name.strip("_")


class DataflashFileExtractor:
    def __init__(self, infile: str):
        self.infile = infile

    def extract(self):
        print(f"Extracting from {self.infile}")
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=False, dialect="ardupilotmega")
        files = {}

        while (msg := mlog.recv_match(blocking=False, type="FILE")) is not None:
            name = getattr(msg, "FileName", "")
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            name = name.rstrip("\x00").strip()
            if not name:
                continue

            offset = getattr(msg, "Offset", 0)
            length = getattr(msg, "Length", 0)
            data = getattr(msg, "Data", [])
            if not isinstance(data, (bytes, bytearray)):
                data = bytes(data[:length])
            else:
                data = data[:length]

            safe_name = sanitize_filename(name)
            if safe_name not in files:
                files[safe_name] = bytearray()

            end_pos = offset + length
            if len(files[safe_name]) < end_pos:
                files[safe_name].extend(b"\x00" * (end_pos - len(files[safe_name])))
            files[safe_name][offset:end_pos] = data

        if not files:
            print("  No embedded files found.")
            return

        base_name = os.path.splitext(os.path.basename(self.infile))[0]
        out_dir = os.path.join(os.path.dirname(self.infile), f"{base_name}_asl_extracted")
        os.makedirs(out_dir, exist_ok=True)
        print(f"  Found {len(files)} files. Writing to {out_dir}/")

        for name, data in files.items():
            out_path = os.path.join(out_dir, name)
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"    Wrote {name} ({len(data)} bytes)")


# ---------------------------------------------------------------------------
# DataflashParam & DataFlashParams
# ---------------------------------------------------------------------------
class DataflashParam:
    def __init__(self, msg):
        self.time_us = msg.TimeUS
        self.id = msg.Name
        self.value = msg.Value
        self.when = f"[{self.time_us:12d}]"

    def is_int(self) -> bool:
        return isinstance(self.value, (int, float)) and float(self.value).is_integer()

    def value_int(self) -> int:
        return int(self.value)

    def value_str(self) -> str:
        if self.is_int():
            return str(int(self.value))
        return f"{self.value:.6f}"

    def comment(self) -> str | None:
        if self.id.startswith("EK3_SRC"):
            val = self.value_int()
            if self.id.endswith("POSXY"):
                return EK3_SRCn_POSXY.get(val, None)
            elif self.id.endswith("VELXY"):
                return EK3_SRCn_VELXY.get(val, None)
            elif self.id.endswith("POSZ"):
                return EK3_SRCn_POSZ.get(val, None)
            elif self.id.endswith("VELZ"):
                return EK3_SRCn_VELZ.get(val, None)
            elif self.id.endswith("YAW"):
                return EK3_SRCn_YAW.get(val, None)
            elif self.id == "EK3_SRC_OPTIONS":
                return "FuseAllVelocities" if val == 1 else "None"
        return None


def print_change(old_param: DataflashParam | None, new_param: DataflashParam | None):
    param_id = new_param.id if new_param else old_param.id
    if param_id in NOISY_PARAMS:
        return

    param_when = new_param.when if new_param else "REMOVED"
    if old_param:
        old_param_str = f"{old_param.value_int()}" if old_param.is_int() else f"{old_param.value:.6f}"
    else:
        old_param_str = "ADDED"

    if new_param:
        new_param_str = f"{new_param.value_int()}" if new_param.is_int() else f"{new_param.value:.6f}"
    else:
        new_param_str = ""

    print(f"{param_when} {param_id:18s} {old_param_str} -> {new_param_str}")


def print_changes(previous_file: "DataFlashParams", current_file: "DataFlashParams"):
    if not len(previous_file.params) and not len(current_file.params):
        print("Nothing to compare")
        return

    for _, param in sorted(current_file.params.items()):
        if param.id not in previous_file.params:
            print_change(None, param)
        elif param.value != previous_file.params[param.id].value:
            print_change(previous_file.params[param.id], param)

    for _, param in sorted(previous_file.params.items()):
        if param.id not in current_file.params:
            print_change(param, None)


class DataFlashParams:
    def __init__(self, interesting: list[str] | None = None):
        self.interesting = interesting
        self.param_list: list[DataflashParam] = []
        self.params: dict[str, DataflashParam] = {}

    def add(self, msg):
        if self.interesting is None or msg.Name in self.interesting:
            param = DataflashParam(msg)
            self.param_list.append(param)
            self.params[param.id] = param

    def get_value(self, name: str, default=None):
        if name in self.params:
            return self.params[name].value
        return default

    def write_params_file(self, outfile: str):
        if not len(self.param_list):
            print("Nothing to write")
            return

        print(f"Writing {outfile}")
        with open(outfile, "w") as f:
            previous_id = None
            for param in sorted(self.param_list, key=attrgetter("id", "time_us")):
                s = f"{param.id:20s}{param.time_us:12}"
                s = s + (" >>>" if param.id == previous_id else "    ")
                s = s + f"{param.value:30}"
                comment = param.comment()
                if comment is not None:
                    s = s + f"  # {comment}"
                f.write(s + "\n")
                previous_id = param.id


# ---------------------------------------------------------------------------
# Dataflash Error and Event Codes
# ---------------------------------------------------------------------------
class LogErrorSubsystem(Enum):
    MAIN = 1
    RADIO = 2
    COMPASS = 3
    OPTFLOW = 4
    FAILSAFE_RADIO = 5
    FAILSAFE_BATT = 6
    FAILSAFE_GPS = 7
    FAILSAFE_GCS = 8
    FAILSAFE_FENCE = 9
    FLIGHT_MODE = 10
    GPS = 11
    CRASH_CHECK = 12
    FLIP = 13
    AUTOTUNE = 14
    PARACHUTES = 15
    EKFCHECK = 16
    FAILSAFE_EKFINAV = 17
    BARO = 18
    CPU = 19
    FAILSAFE_ADSB = 20
    TERRAIN = 21
    NAVIGATION = 22
    FAILSAFE_TERRAIN = 23
    EKF_PRIMARY = 24
    THRUST_LOSS_CHECK = 25
    FAILSAFE_SENSORS = 26
    FAILSAFE_LEAK = 27
    PILOT_INPUT = 28
    FAILSAFE_VIBE = 29
    INTERNAL_ERROR = 30
    FAILSAFE_DEADRECKON = 31


log_error_code = {
    "ERROR_RESOLVED": 0,
    "FAILED_TO_INITIALISE": 1,
    "UNHEALTHY": 4,
    "RADIO_LATE_FRAME": 2,
    "FAILSAFE_RESOLVED": 0,
    "FAILSAFE_OCCURRED": 1,
    "MAIN_INS_DELAY": 1,
    "CRASH_CHECK_CRASH": 1,
    "CRASH_CHECK_LOSS_OF_CONTROL": 2,
    "FLIP_ABANDONED": 2,
    "MISSING_TERRAIN_DATA": 2,
    "FAILED_TO_SET_DESTINATION": 2,
    "RESTARTED_RTL": 3,
    "FAILED_CIRCLE_INIT": 4,
    "DEST_OUTSIDE_FENCE": 5,
    "RTL_MISSING_RNGFND": 6,
    "INTERNAL_ERRORS_DETECTED": 1,
    "PARACHUTE_TOO_LOW": 2,
    "PARACHUTE_LANDED": 3,
    "EKFCHECK_BAD_VARIANCE": 2,
    "EKFCHECK_VARIANCE_CLEARED": 0,
    "BARO_GLITCH": 2,
    "BAD_DEPTH": 3,
    "GPS_GLITCH": 2,
}

SUB_MODES = {
    0: "STABILIZE",
    1: "ACRO",
    2: "ALT_HOLD",
    3: "AUTO",
    4: "GUIDED",
    7: "CIRCLE",
    9: "SURFACE",
    16: "POSHOLD",
    19: "MANUAL",
    20: "MOTOR_DETECT",
    21: "SURFTRAK",
}


def decode_error(subsys_id: int, ecode: int) -> tuple[str, str]:
    try:
        subsys = LogErrorSubsystem(subsys_id)
        subsys_name = subsys.name
    except ValueError:
        subsys_name = f"UNKNOWN_{subsys_id}"

    if subsys_name == "FLIGHT_MODE":
        return subsys_name, SUB_MODES.get(ecode, f"MODE_{ecode}")
    if subsys_name == "EKF_PRIMARY":
        return subsys_name, f"CORE_{ecode}"
    if subsys_name == "FAILSAFE_FENCE":
        if ecode == 0:
            return subsys_name, "FAILSAFE_RESOLVED"
        breaches = []
        if ecode & 1:
            breaches.append("ALT_MAX")
        if ecode & 2:
            breaches.append("CIRCLE")
        if ecode & 4:
            breaches.append("POLYGON")
        if ecode & 8:
            breaches.append("ALT_MIN")
        return subsys_name, "|".join(breaches) if breaches else f"BREACH_{ecode}"
    if subsys_name.startswith("FAILSAFE_") or subsys_name in ("PILOT_INPUT", "CPU", "THRUST_LOSS_CHECK"):
        if subsys_name == "FAILSAFE_SENSORS" and ecode == 3:
            return subsys_name, "BAD_DEPTH"
        if ecode == 0:
            return subsys_name, "FAILSAFE_RESOLVED"
        if ecode == 1:
            return subsys_name, "FAILSAFE_OCCURRED"
    if subsys_name == "EKFCHECK":
        if ecode == 0:
            return subsys_name, "EKFCHECK_VARIANCE_CLEARED"
        if ecode == 2:
            return subsys_name, "EKFCHECK_BAD_VARIANCE"
    if subsys_name == "BARO":
        baro_codes = {0: "ERROR_RESOLVED", 1: "FAILED_TO_INITIALISE", 2: "BARO_GLITCH", 3: "BAD_DEPTH", 4: "UNHEALTHY"}
        if ecode in baro_codes:
            return subsys_name, baro_codes[ecode]
    if subsys_name == "GPS":
        gps_codes = {0: "ERROR_RESOLVED", 1: "FAILED_TO_INITIALISE", 2: "GPS_GLITCH", 4: "UNHEALTHY"}
        if ecode in gps_codes:
            return subsys_name, gps_codes[ecode]
    if subsys_name == "COMPASS":
        compass_codes = {0: "ERROR_RESOLVED", 1: "FAILED_TO_INITIALISE", 4: "UNHEALTHY"}
        if ecode in compass_codes:
            return subsys_name, compass_codes[ecode]
    if subsys_name == "NAVIGATION":
        nav_codes = {
            0: "ERROR_RESOLVED",
            2: "FAILED_TO_SET_DESTINATION",
            3: "RESTARTED_RTL",
            4: "FAILED_CIRCLE_INIT",
            5: "DEST_OUTSIDE_FENCE",
            6: "RTL_MISSING_RNGFND",
        }
        if ecode in nav_codes:
            return subsys_name, nav_codes[ecode]

    general_codes = {0: "ERROR_RESOLVED", 1: "FAILED_TO_INITIALISE", 4: "UNHEALTHY"}
    return subsys_name, general_codes.get(ecode, str(ecode))


class LogEvent(Enum):
    ARMED = 10
    DISARMED = 11
    AUTO_ARMED = 15
    LAND_COMPLETE_MAYBE = 17
    LAND_COMPLETE = 18
    LOST_GPS = 19
    FLIP_START = 21
    FLIP_END = 22
    SET_HOME = 25
    SET_SIMPLE_ON = 26
    SET_SIMPLE_OFF = 27
    NOT_LANDED = 28
    SET_SUPERSIMPLE_ON = 29
    AUTOTUNE_INITIALISED = 30
    AUTOTUNE_OFF = 31
    AUTOTUNE_RESTART = 32
    AUTOTUNE_SUCCESS = 33
    AUTOTUNE_FAILED = 34
    AUTOTUNE_REACHED_LIMIT = 35
    AUTOTUNE_PILOT_TESTING = 36
    AUTOTUNE_SAVEDGAINS = 37
    SAVE_TRIM = 38
    SAVEWP_ADD_WP = 39
    FENCE_ENABLE = 41
    FENCE_DISABLE = 42
    ACRO_TRAINER_OFF = 43
    ACRO_TRAINER_LEVELING = 44
    ACRO_TRAINER_LIMITED = 45
    GRIPPER_GRAB = 46
    GRIPPER_RELEASE = 47
    PARACHUTE_DISABLED = 49
    PARACHUTE_ENABLED = 50
    PARACHUTE_RELEASED = 51
    LANDING_GEAR_DEPLOYED = 52
    LANDING_GEAR_RETRACTED = 53
    MOTORS_EMERGENCY_STOPPED = 54
    MOTORS_EMERGENCY_STOP_CLEARED = 55
    MOTORS_INTERLOCK_DISABLED = 56
    MOTORS_INTERLOCK_ENABLED = 57
    ROTOR_RUNUP_COMPLETE = 58
    ROTOR_SPEED_BELOW_CRITICAL = 59
    EKF_ALT_RESET = 60
    LAND_CANCELLED_BY_PILOT = 61
    EKF_YAW_RESET = 62
    AVOIDANCE_ADSB_ENABLE = 63
    AVOIDANCE_ADSB_DISABLE = 64
    AVOIDANCE_PROXIMITY_ENABLE = 65
    AVOIDANCE_PROXIMITY_DISABLE = 66
    GPS_PRIMARY_CHANGED = 67
    ZIGZAG_STORE_A = 71
    ZIGZAG_STORE_B = 72
    LAND_REPO_ACTIVE = 73
    STANDBY_ENABLE = 74
    STANDBY_DISABLE = 75
    FENCE_ALT_MAX_ENABLE = 76
    FENCE_ALT_MAX_DISABLE = 77
    FENCE_CIRCLE_ENABLE = 78
    FENCE_CIRCLE_DISABLE = 79
    FENCE_ALT_MIN_ENABLE = 80
    FENCE_ALT_MIN_DISABLE = 81
    FENCE_POLYGON_ENABLE = 82
    FENCE_POLYGON_DISABLE = 83
    EK3_SOURCES_SET_TO_PRIMARY = 85
    EK3_SOURCES_SET_TO_SECONDARY = 86
    EK3_SOURCES_SET_TO_TERTIARY = 87
    AIRSPEED_PRIMARY_CHANGED = 90
    SURFACED = 163
    NOT_SURFACED = 164
    BOTTOMED = 165
    NOT_BOTTOMED = 166


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------
TIMELINE_MSG_TYPES = [
    "MODE",
    "EV",
    "ARM",
    "ERR",
    "MSG",
    "ORGN",
    "MAVC",
    "CMD",
    "PARM",
    "XKF4",
    "XKFS",
]
MSG_TYPES = TIMELINE_MSG_TYPES

IGNORE_CMDS = [511, 512, 521, 522, 525, 527, 2504, 2505]

SOURCE_SETS = [
    "primary (0)",
    "secondary (1)",
    "tertiary (2)",
]

ANSI_CODES = {
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
    "END": "\033[0m",
    "WHITE": "\033[37m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
    "CYAN": "\033[36m",
    "MAGENTA": "\033[35m",
    "BLUE": "\033[34m",
    "RED": "\033[31m",
}


class ColorMap:
    def __init__(self):
        self.heartbeat = "GREEN"
        self.status_text = "WHITE"
        self.command_long = "MAGENTA"
        self.command_ack = "MAGENTA"
        self.param_set = "CYAN"
        self.gps_global_origin = "BLUE"
        self.ekf_status_report = "YELLOW"


def mav_cmd_name(cmd: int) -> str:
    if cmd in apm.enums["MAV_CMD"]:
        return f"{apm.enums['MAV_CMD'][cmd].name} ({cmd})"
    return f"unknown command {cmd}"


def mav_result_name(result: int) -> str:
    if result in apm.enums["MAV_RESULT"]:
        return f"{apm.enums['MAV_RESULT'][result].name} ({result})"
    return f"unknown result {result}"


def format_param_value(val: float) -> str:
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    elif isinstance(val, float):
        return f"{val:g}"
    return str(val)


class Timeline:
    def __init__(self, reader, ansi: bool = True):
        self.ansi = ansi
        self.colors = ColorMap()
        self.custom_mode = table_types.Mode.UNKNOWN
        self.armed = False
        self.ekf_status_flags = None
        self.ekf_source_set = None
        self.known_params = {}
        self.last_orgn = None
        self.first_ts = None
        print("Time                |   Since epoch | Elapsed : Message")

        for msg in reader:
            ts = getattr(msg, "_timestamp", 0.0)
            if self.first_ts is None:
                self.first_ts = ts

            self.prefix = (
                datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                + f" | {ts:.2f} | {ts - self.first_ts:7.2f} : "
            )

            msg_type = msg.get_type()
            if msg_type == "MODE":
                self.process_mode(msg)
            elif msg_type == "EV":
                self.process_ev(msg)
            elif msg_type == "ARM":
                self.process_arm(msg)
            elif msg_type == "MSG":
                self.process_msg(msg)
            elif msg_type == "ERR":
                self.process_err(msg)
            elif msg_type == "MAVC":
                self.process_mavc(msg)
            elif msg_type == "CMD":
                self.process_cmd(msg)
            elif msg_type == "PARM":
                self.process_parm(msg)
            elif msg_type == "ORGN":
                self.process_orgn(msg)
            elif msg_type == "XKF4":
                self.process_xkf4(msg)
            elif msg_type == "XKFS":
                self.process_xkfs(msg)
            else:
                self.report(msg_type)

    def report(self, msg_str: str, ansi_code: str | None = None):
        if self.ansi and ansi_code is not None:
            print(f"{self.prefix}{ANSI_CODES[ansi_code]}{msg_str}{ANSI_CODES['END']}")
        else:
            print(f"{self.prefix}{msg_str}")

    def process_mode(self, msg):
        mode_num = getattr(msg, "Mode", getattr(msg, "ModeNum", None))
        if mode_num is not None and mode_num != self.custom_mode:
            self.custom_mode = mode_num
            armed_str = "ARMED" if self.armed else "DISARMED"
            mode_str = f"{table_types.mode_name(self.custom_mode)} ({self.custom_mode})"
            self.report(f"{armed_str} {mode_str}", self.colors.heartbeat)

    def process_ev(self, msg):
        ev_id = getattr(msg, "Id", None)
        if ev_id is None:
            return

        if ev_id in (LogEvent.ARMED.value, LogEvent.AUTO_ARMED.value):
            if not self.armed:
                self.armed = True
                mode_str = f"{table_types.mode_name(self.custom_mode)} ({self.custom_mode})"
                self.report(f"ARMED {mode_str}", self.colors.heartbeat)
        elif ev_id == LogEvent.DISARMED.value:
            if self.armed:
                self.armed = False
                mode_str = f"{table_types.mode_name(self.custom_mode)} ({self.custom_mode})"
                self.report(f"DISARMED {mode_str}", self.colors.heartbeat)
        else:
            try:
                ev = LogEvent(ev_id)
                self.report(f"Event: {ev.name}", self.colors.heartbeat)
            except ValueError:
                self.report(f"Event: unknown ({ev_id})", self.colors.heartbeat)

    def process_arm(self, msg):
        arm_state = getattr(msg, "ArmState", None)
        if arm_state is not None:
            new_armed = bool(arm_state)
            if new_armed != self.armed:
                self.armed = new_armed
                armed_str = "ARMED" if self.armed else "DISARMED"
                mode_str = f"{table_types.mode_name(self.custom_mode)} ({self.custom_mode})"
                self.report(f"{armed_str} {mode_str}", self.colors.heartbeat)

    def process_msg(self, msg):
        text = getattr(msg, "Message", "")
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        text = text.rstrip("\x00").strip()
        if text:
            self.report(text, self.colors.status_text)

    def process_err(self, msg):
        subsys_id = getattr(msg, "Subsys", None)
        ecode = getattr(msg, "ECode", None)
        if subsys_id is not None and ecode is not None:
            subsys_name, ecode_name = decode_error(subsys_id, ecode)
            self.report(f"Error: Subsys {subsys_name}, ECode {ecode_name}", self.colors.status_text)
        else:
            self.report(f"Error: Subsys unknown ({subsys_id}), ECode {ecode}", self.colors.status_text)

    def process_mavc(self, msg):
        cmd = getattr(msg, "Cmd", 0)
        if cmd not in IGNORE_CMDS:
            p1 = getattr(msg, "P1", 0.0)
            res = getattr(msg, "Res", None)
            res_str = f", result {mav_result_name(res)}" if res is not None else ""
            self.report(f"Command: {mav_cmd_name(cmd)}, param1 {p1}{res_str}", self.colors.command_long)

    def process_cmd(self, msg):
        cid = getattr(msg, "CId", 0)
        if cid not in IGNORE_CMDS:
            cnum = getattr(msg, "CNum", 0)
            ctot = getattr(msg, "CTot", 0)
            p1 = getattr(msg, "Prm1", 0.0)
            self.report(f"Mission cmd: {mav_cmd_name(cid)} ({cnum}/{ctot}), param1 {p1}", self.colors.command_long)

    def process_parm(self, msg):
        name = getattr(msg, "Name", None)
        val = getattr(msg, "Value", None)
        if name is None or val is None:
            return

        if name in self.known_params:
            if self.known_params[name] != val:
                if name not in NOISY_PARAMS and not name.startswith("STAT_"):
                    param = DataflashParam(msg)
                    comment = param.comment()
                    val_str = format_param_value(param.value)
                    if comment is None:
                        self.report(f"Set param {param.id} to {val_str}", self.colors.param_set)
                    else:
                        self.report(f"Set param {param.id} to {comment} ({val_str})", self.colors.param_set)
                self.known_params[name] = val
        else:
            self.known_params[name] = val

    def process_orgn(self, msg):
        orgn_key = (
            getattr(msg, "Type", 0),
            getattr(msg, "Lat", 0.0),
            getattr(msg, "Lng", 0.0),
            getattr(msg, "Alt", 0.0),
        )
        if orgn_key == self.last_orgn:
            return
        self.last_orgn = orgn_key
        lat = getattr(msg, "Lat", 0.0)
        lon = getattr(msg, "Lng", 0.0)
        alt = getattr(msg, "Alt", 0.0)
        self.report(
            f"Global origin set to ({lat}, {lon}), altitude {alt} above mean sea level",
            self.colors.gps_global_origin,
        )

    def process_xkf4(self, msg):
        if getattr(msg, "C", 0) == 0:
            flags = getattr(msg, "SS", 0)
            if flags != self.ekf_status_flags:
                if flags & apm.EKF_UNINITIALIZED:
                    self.report("EKF uninitialized", self.colors.ekf_status_report)
                elif flags == 0:
                    self.report("EKF initialized", self.colors.ekf_status_report)
                else:
                    s = f"EKF status: {flags:4}"
                    s += f" {'const' if flags & apm.EKF_CONST_POS_MODE else '':5}"
                    s += f" {'att' if flags & apm.EKF_ATTITUDE else '':3}"
                    s += " pos_xy: ["
                    s += f"{'rel' if flags & apm.EKF_POS_HORIZ_REL else '':3}"
                    s += f" {'abs' if flags & apm.EKF_POS_HORIZ_ABS else '':3}"
                    s += f" {'pred_rel' if flags & apm.EKF_PRED_POS_HORIZ_REL else '':8}"
                    s += f" {'pred_abs' if flags & apm.EKF_PRED_POS_HORIZ_ABS else '':8}"
                    s += "] pos_z: ["
                    s += f"{'abs' if flags & apm.EKF_POS_VERT_ABS else '':3}"
                    s += f" {'agl' if flags & apm.EKF_POS_VERT_AGL else '':3}"
                    s += "] vel: ["
                    s += f"{'xy' if flags & apm.EKF_VELOCITY_HORIZ else '':2}"
                    s += f" {'z' if flags & apm.EKF_VELOCITY_VERT else '':1}"
                    s += "]"
                    self.report(s, self.colors.ekf_status_report)
                self.ekf_status_flags = flags

    def process_xkfs(self, msg):
        if getattr(msg, "C", 0) == 0:
            ss = getattr(msg, "SS", 0)
            if ss != self.ekf_source_set:
                ss_str = SOURCE_SETS[ss] if 0 <= ss < len(SOURCE_SETS) else f"unknown ({ss})"
                self.report(f"Source set: {ss_str}", self.colors.ekf_status_report)
                self.ekf_source_set = ss


if __name__ == "__main__":
    main()
