#!/usr/bin/env python3
"""
Telemetry (tlog / MAVLink) backend parsers, readers, and diagnostics.
"""

from __future__ import annotations

import argparse
import datetime
import os
import time

import numpy as np
import pymavlink.dialects.v20.ardupilotmega as apm
import pymavlink.dialects.v20.common as mav_common
from pymavlink import mavutil

from ardusub_log_tools.core import table_types, util
from ardusub_log_tools.core.log_merger import LogMerger

# Force MAVLink 2.0
os.environ["MAVLINK20"] = "1"

# ---------------------------------------------------------------------------
# Useful MAVLink Message Types
# ---------------------------------------------------------------------------
PERHAPS_USEFUL_MSG_TYPES = [
    "AHRS",
    "AHRS2",
    "ATTITUDE",
    "DISTANCE_SENSOR",
    "EKF_STATUS_REPORT",
    "GLOBAL_POSITION_INT",
    "GLOBAL_VISION_POSITION_ESTIMATE",
    "GPS_GLOBAL_ORIGIN",
    "GPS_INPUT",
    "GPS_RAW_INT",
    "HEARTBEAT",
    "HOME_POSITION",
    "LOCAL_POSITION_NED",
    "RANGEFINDER",
    "SCALED_PRESSURE2",
    "SERVO_OUTPUT_RAW",
    "SET_GPS_GLOBAL_ORIGIN",
    "SYS_STATUS",
    "SYSTEM_TIME",
    "TIMESYNC",
    "VFR_HUD",
    "VISION_POSITION_DELTA",
    "VISION_POSITION_ESTIMATE",
]


# ---------------------------------------------------------------------------
# TelemetryLogReader (Time-aligned message merging and export)
# ---------------------------------------------------------------------------
class TelemetryLogReader(LogMerger):
    def __init__(
        self,
        reader,
        max_msgs: int,
        max_rows: int,
        verbose: bool,
        sysid: int | None,
        compid: int | None,
        system_time: bool,
        split_source: bool,
        raw: bool,
    ):
        super().__init__(reader.name, max_msgs, max_rows, verbose)
        self.reader = reader
        self.sysid = sysid
        self.compid = compid
        self.system_time = system_time
        self.split_source = split_source
        self.raw = raw
        self.time_delta_s = None

    def read_tlog(self):
        self.tables = {}
        msg_count = 0

        for msg in self.reader:
            sysid = msg.get_srcSystem()
            compid = msg.get_srcComponent()

            if self.sysid is not None and self.sysid != sysid:
                continue
            if self.compid is not None and self.compid != compid:
                continue

            msg_type = msg.get_type()
            raw_data = msg.to_dict()
            qgc_s = getattr(msg, "_timestamp", 0.0)

            if self.system_time:
                if msg_type == "SYSTEM_TIME" and sysid == 1 and compid == 1 and self.time_delta_s is None:
                    self.time_delta_s = qgc_s - raw_data["time_boot_ms"] / 1000.0
                    if self.verbose:
                        print(f"Time synchronized, delta is {self.time_delta_s} seconds")

                if self.time_delta_s is None:
                    continue

                clean_data = {"timestamp": int((qgc_s - self.time_delta_s) * 1000.0)}
            else:
                clean_data = {"timestamp": qgc_s}

            if self.split_source:
                table_name = f"{msg_type}_{sysid}_{compid}"
            else:
                table_name = msg_type
                clean_data[f"{msg_type}.sysid"] = sysid
                clean_data[f"{msg_type}.compid"] = compid

            for key in raw_data.keys():
                if key != "mavpackettype":
                    clean_data[f"{table_name}.{key}"] = raw_data[key]

            if table_name not in self.tables:
                self.tables[table_name] = table_types.Table.create_table(
                    msg_type, table_name=table_name, filter_bad=not self.raw
                )

            self.tables[table_name].append(clean_data)

            msg_count += 1
            if msg_count > self.max_msgs:
                if self.verbose:
                    print("Too many messages, stopping")
                break
            if self.verbose and msg_count % 20000 == 0:
                print(f"{msg_count} messages")

        if self.verbose:
            print(f"{msg_count} messages")

    def add_rate_field(self, half_n=10, field_name="rate"):
        for table_name in self.tables:
            self.tables[table_name].add_rate_field(half_n, field_name)


# ---------------------------------------------------------------------------
# Telemetry Parameters
# ---------------------------------------------------------------------------
NOISY_PARAMS: list[str] = ["BARO1_GND_PRESS", "BARO2_GND_PRESS", "STAT_FLTTIME", "STAT_RUNTIME"]

EK3_SRCn_POSXY = {
    0: "None",
    3: "GPS",
    4: "Beacon",
    6: "ExternalNav",
}

EK3_SRCn_VELXY = {
    0: "None",
    3: "GPS",
    4: "Beacon",
    5: "OpticalFlow",
    6: "ExternalNav",
    7: "WheelEncoder",
}

EK3_SRCn_POSZ = {
    0: "None",
    1: "Baro",
    2: "RangeFinder",
    3: "GPS",
    4: "Beacon",
    6: "ExternalNav",
}

EK3_SRCn_VELZ = {
    0: "None",
    3: "GPS",
    4: "Beacon",
    5: "ExternalNav",
}

EK3_SRCn_YAW = {
    0: "None",
    1: "Compass",
    2: "GPS",
    3: "GPS with Compass Fallback",
    6: "ExternalNav",
    8: "GSF",
}


def firmware_version_type_str(firmware_version_type: int) -> str:
    try:
        return mav_common.enums["FIRMWARE_VERSION_TYPE"][firmware_version_type].description
    except KeyError:
        return ""


def is_int(param_type: int) -> bool:
    return mav_common.MAV_PARAM_TYPE_UINT8 <= param_type <= mav_common.MAV_PARAM_TYPE_INT64


class Param:
    def __init__(self, msg: mav_common.MAVLink_param_value_message):
        self.id = msg.param_id if hasattr(msg, "param_id") else getattr(msg, "Name", "")
        self.value = msg.param_value if hasattr(msg, "param_value") else getattr(msg, "Value", 0)
        self.type = getattr(msg, "param_type", 0)
        timestamp = getattr(msg, "_timestamp", 0.0)
        self.when = f"[{timestamp:.3f}] {time.asctime(time.localtime(timestamp))}"

    def is_int(self) -> bool:
        return is_int(self.type)

    def value_int(self) -> int:
        if self.is_int():
            return int(self.value)
        else:
            try:
                return int(self.value)
            except Exception:
                return 0

    def value_str(self) -> str:
        if self.type is mav_common.MAV_PARAM_TYPE_REAL32:
            return str(np.float32(self.value))
        elif self.type is mav_common.MAV_PARAM_TYPE_REAL64:
            return str(self.value)
        else:
            return str(int(self.value))

    def comment(self) -> str | None:
        if self.id.startswith("EK3_SRC"):
            val = self.value_int()
            if self.id.endswith("POSXY"):
                return EK3_SRCn_POSXY.get(val)
            elif self.id.endswith("VELXY"):
                return EK3_SRCn_VELXY.get(val)
            elif self.id.endswith("POSZ"):
                return EK3_SRCn_POSZ.get(val)
            elif self.id.endswith("VELZ"):
                return EK3_SRCn_VELZ.get(val)
            elif self.id.endswith("YAW"):
                return EK3_SRCn_YAW.get(val)
            elif self.id == "EK3_SRC_OPTIONS":
                return "FuseAllVelocities" if val == 1 else "None"
        return None


def print_change(old_param: Param | None, new_param: Param | None):
    param_id = new_param.id if new_param else old_param.id
    if param_id in NOISY_PARAMS:
        return

    param_type = new_param.type if new_param else old_param.type
    param_when = new_param.when if new_param else "REMOVED"

    if is_int(param_type):
        old_param_str = f"{old_param.value_int()}" if old_param else "ADDED"
        new_param_str = f"{new_param.value_int()}" if new_param else ""
    else:
        old_param_str = f"{old_param.value:.6f}" if old_param else "ADDED"
        new_param_str = f"{new_param.value:.6f}" if new_param else ""

    print(f"{param_when} {param_id:18s} {old_param_str} -> {new_param_str}")


class TelemetryLogParam:
    def __init__(self, infile: str, print_intra_file_changes: bool, params: list[str] | None = None):
        self.infile = infile
        self.params: dict[str, Param] = {}
        self.params_to_track = params
        self.autopilot_version: str = ""
        self.git_hash: str = ""
        mlog = mavutil.mavlink_connection(infile, robust_parsing=False, dialect="ardupilotmega")

        while (
            msg := mlog.recv_match(blocking=False, type=["PARAM_VALUE", "PARAM_SET", "AUTOPILOT_VERSION"])
        ) is not None:
            if msg.get_type() == "PARAM_VALUE":
                self.handle_param_value(msg, print_intra_file_changes)
            elif msg.get_type() == "PARAM_SET":
                self.handle_param_set(msg)
            else:
                self.handle_version(msg)

    def handle_param_value(self, msg: mav_common.MAVLink_param_value_message, print_intra_file_changes: bool):
        new_param = Param(msg)

        if self.params_to_track is not None and new_param.id not in self.params_to_track:
            return

        if new_param.id in self.params:
            old_param = self.params[new_param.id]

            if print_intra_file_changes and new_param.type != old_param.type:
                print(f"ERROR: {old_param.id} type changed from {old_param.type} to {new_param.type}")

            if new_param.value != old_param.value:
                if print_intra_file_changes:
                    print_change(old_param, new_param)
                old_param.value = new_param.value
        else:
            self.params[new_param.id] = new_param

    def handle_param_set(self, msg: mav_common.MAVLink_param_set_message):
        if self.params_to_track is None or msg.param_id in self.params_to_track:
            print(
                f"PARAM_SET ({msg.get_srcSystem()}, {msg.get_srcComponent()}) -> ({msg.target_system}, {msg.target_component}), param {msg.param_id}, new value {msg.param_value}"
            )

    def handle_version(self, msg: mav_common.MAVLink_autopilot_version_message):
        flight_sw_version = msg.flight_sw_version
        major = (flight_sw_version >> (8 * 3)) & 0xFF
        minor = (flight_sw_version >> (8 * 2)) & 0xFF
        path = (flight_sw_version >> (8 * 1)) & 0xFF
        version_type = (flight_sw_version >> (8 * 0)) & 0xFF

        self.autopilot_version = f"{major}.{minor}.{path} {firmware_version_type_str(version_type)}"
        self.git_hash = bytes(msg.flight_custom_version).decode("utf-8")

    def get_value(self, name: str, default=None):
        if name in self.params:
            return self.params[name].value
        return default

    def write_params_file(self, outfile: str):
        if not len(self.params):
            print("Nothing to write")
            return

        print(f"Writing {outfile}")
        with open(outfile, "w") as f:
            f.write("# Onboard parameters for Vehicle 1\n")
            f.write("#\n")
            f.write("# Stack: ArduPilot\n")
            f.write("# Vehicle: Sub\n")
            f.write(f"# Version: {self.autopilot_version}\n")
            f.write(f"# Git Revision: {self.git_hash}\n")
            f.write("#\n")
            f.write("# Vehicle-Id\tComponent-Id\tName\tValue\tType\n")

            for _, param in sorted(self.params.items()):
                comment = param.comment()
                if comment is not None:
                    f.write(f"1\t1\t{param.id}\t{param.value_str()}\t{param.type}\t# {comment}\n")
                else:
                    f.write(f"1\t1\t{param.id}\t{param.value_str()}\t{param.type}\n")


def print_changes(previous_file: TelemetryLogParam, current_file: TelemetryLogParam):
    if not len(previous_file.params) and not len(current_file.params):
        print("Nothing to compare")
        return

    for _, param in sorted(current_file.params.items()):
        if param.id not in previous_file.params:
            print_change(None, param)
        elif param.value != previous_file.params[param.id].value:
            print_change(previous_file.params[param.id], param)


# ---------------------------------------------------------------------------
# TelemetryLogInfo
# ---------------------------------------------------------------------------
INFO_MSG_TYPES = ["HEARTBEAT", "STATUSTEXT", "SYSTEM_TIME", "SYS_STATUS"]


class SensorInfo:
    def __init__(self, description: str):
        if description == "0x100 laser based position":
            description = "0x100 laser based position (down-facing sonar rangefinder)"
        self.description = description
        self.present = 0
        self.enabled = 0
        self.healthy = 0

    def count(self, enabled, healthy):
        self.present += 1
        if enabled:
            self.enabled += 1
        if healthy:
            self.healthy += 1

    def count_str(self, count: int) -> str:
        if count == 0:
            return "NEVER!"
        elif count == self.present:
            return "always"
        else:
            return f"{100.0 * count / self.present:.2f}%"

    def report(self) -> str:
        return f"{self.description}: enabled {self.count_str(self.enabled)}, healthy {self.count_str(self.healthy)}"


class CompInfo:
    def __init__(self, sys_id: int, comp_id: int):
        self._sys_id = sys_id
        self._comp_id = comp_id
        self._heartbeat_count = 0
        self._mode_counter = table_types.ModeCounter()
        self._status_severities = {}
        self._status_messages = {}
        self._sensors = {}

    def heartbeat(self, msg: apm.MAVLink_heartbeat_message):
        self._heartbeat_count += 1
        if self._sys_id == 1 and self._comp_id == 1:
            self._mode_counter.count(msg.base_mode, msg.custom_mode)

    def statustext(self, msg: apm.MAVLink_statustext_message):
        severity = msg.severity
        self._status_severities[severity] = self._status_severities.get(severity, 0) + 1
        text = msg.text
        self._status_messages[text] = self._status_messages.get(text, 0) + 1

    def sys_status(self, msg: apm.MAVLink_sys_status_message):
        present = msg.onboard_control_sensors_present
        enabled = msg.onboard_control_sensors_enabled
        health = msg.onboard_control_sensors_health
        for bit in range(32):
            mask = 1 << bit
            if present & mask:
                if mask not in self._sensors:
                    self._sensors[mask] = SensorInfo(table_types.sensor_name(mask))
                self._sensors[mask].count(enabled & mask, health & mask)

    def report(self):
        print(f"Component [{self._sys_id}, {self._comp_id}] {table_types.comp_name(self._comp_id)}")
        print(f"  {self._heartbeat_count} heartbeats")
        if self._sys_id == 1 and self._comp_id == 1:
            self._mode_counter.report()
        for severity in sorted(self._status_severities.keys()):
            print(
                f"  {self._status_severities[severity]} status messages with severity {table_types.status_severity_name(severity)}"
            )
        for text in sorted(self._status_messages.keys()):
            print(f"  {self._status_messages[text]} status messages: {text}")
        for mask in sorted(self._sensors.keys()):
            print(f"  {self._sensors[mask].report()}")


class TelemetryLogInfo:
    def __init__(self, reader):
        self.reader = reader
        self.components: dict[tuple[int, int], CompInfo] = {}

    def read_and_report(self):
        print(f"Results for {self.reader.name}")
        for msg in self.reader:
            key = (msg.get_srcSystem(), msg.get_srcComponent())
            if key not in self.components:
                self.components[key] = CompInfo(*key)
            comp_info = self.components[key]
            mtype = msg.get_type()
            if mtype == "HEARTBEAT":
                comp_info.heartbeat(msg)
            elif mtype == "STATUSTEXT":
                comp_info.statustext(msg)
            elif mtype == "SYS_STATUS":
                comp_info.sys_status(msg)

        for comp_info in self.components.values():
            print("-------------------")
            comp_info.report()


# ---------------------------------------------------------------------------
# BadDataFinder
# ---------------------------------------------------------------------------
class BadDataInfo:
    def __init__(self, msg):
        self.reason = msg.reason
        self.crc_error = True if msg.reason.find("invalid MAVLink CRC") >= 0 else False
        b = bytes(msg.data)
        self.mavlink2 = True if b[0] == 0xFD else False

        if self.mavlink2:
            self.sysid = int(b[5])
            self.compid = int(b[6])
            self.msg_id = (b[9] << 16) + (b[8] << 8) + b[7]
        else:
            self.sysid = int(b[3])
            self.compid = int(b[4])
            self.msg_id = int(b[5])

    def __str__(self):
        return f"BadDataMsg mavlink2={self.mavlink2} sysid={self.sysid} compid={self.compid} msg_id={self.msg_id} reason: {self.reason}"


class BadDataFinder:
    def __init__(self, infile: str, verbose: bool):
        self.infile = infile
        self.verbose = verbose

    def read(self):
        print(f"Results for {self.infile}")
        mlog = mavutil.mavlink_connection(self.infile, dialect="ardupilotmega")
        total_count = 0
        crc_errors = 0
        counts = {}

        while True:
            try:
                msg = mlog.recv_match(blocking=False)
            except Exception as e:
                print(f'CRASH WITH ERROR "{e}" READING {self.infile}')
                return

            if msg is None:
                break

            if msg.get_type() == "BAD_DATA":
                msg_info = BadDataInfo(msg)
                total_count += 1
                crc_errors += 1 if msg_info.crc_error else 0
                counts[msg_info.msg_id] = counts.get(msg_info.msg_id, 0) + 1
                if self.verbose:
                    print(msg_info)

        for msg_id_item in sorted(counts.items()):
            print(f"msg_id {msg_id_item[0]} count {msg_id_item[1]}")
        print(f"{total_count} BAD_DATA messages, {crc_errors} of them were CRC errors")


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------
class Scanner:
    def __init__(self, filename: str, types: list[str] | None):
        self.filename = filename
        self.types = types

    def read(self):
        mlog = mavutil.mavlink_connection(self.filename, dialect="ardupilotmega")
        count = 0
        while True:
            try:
                msg = mlog.recv_match(blocking=False, type=self.types)
            except Exception as e:
                print(f'CRASH WITH ERROR "{e}" READING {self.filename}')
                return
            if msg is None:
                break
            count += 1
        print(f"Read {count} messages from {self.filename}")


def scan_main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for tlog files")
    parser.add_argument("--types", default=None, help="comma separated list of message types")
    parser.add_argument("path", nargs="+")
    args = parser.parse_args()

    if args.types:
        args.types = args.types.upper()

    files = util.expand_path(args.path, args.recurse, ".tlog")
    print(f"Processing {len(files)} files")

    types = args.types.split(",") if args.types else None

    for file in files:
        scanner = Scanner(file, types)
        scanner.read()


main = scan_main


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------
TIMELINE_MSG_TYPES = [
    "HEARTBEAT",
    "STATUSTEXT",
    "COMMAND_LONG",
    "COMMAND_ACK",
    "PARAM_SET",
    "GPS_GLOBAL_ORIGIN",
    "EKF_STATUS_REPORT",
    "MISSION_CLEAR_ALL",
]
MSG_TYPES = TIMELINE_MSG_TYPES

IGNORE_CMDS = [511, 512, 521, 522, 525, 527, 2504, 2505]

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


class Timeline:
    def __init__(self, reader, ansi: bool = True):
        self.ansi = ansi
        self.colors = ColorMap()
        self.base_mode = apm.MAV_MODE_PREFLIGHT
        self.custom_mode = table_types.Mode.UNKNOWN
        self.system_status = apm.MAV_STATE_UNINIT
        self.ekf_status_flags = apm.EKF_UNINITIALIZED
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
            if msg_type == "HEARTBEAT":
                self.process_heartbeat(msg)
            elif msg_type == "STATUSTEXT":
                self.process_status_text(msg)
            elif msg_type == "COMMAND_LONG":
                self.process_command_long(msg)
            elif msg_type == "COMMAND_ACK":
                self.process_command_ack(msg)
            elif msg_type == "PARAM_SET":
                self.process_param_set(msg)
            elif msg_type == "GPS_GLOBAL_ORIGIN":
                self.process_gps_global_origin(msg)
            elif msg_type == "EKF_STATUS_REPORT":
                self.process_ekf_status_report(msg)
            else:
                self.report(msg_type)

    def report(self, msg_str, ansi_code=None):
        if self.ansi and ansi_code is not None:
            print(f"{self.prefix}{ANSI_CODES[ansi_code]}{msg_str}{ANSI_CODES['END']}")
        else:
            print(f"{self.prefix}{msg_str}")

    def process_heartbeat(self, msg):
        if msg.get_srcSystem() == 1 and msg.get_srcComponent() == 1:
            if (
                msg.base_mode != self.base_mode
                or msg.custom_mode != self.custom_mode
                or self.system_status != msg.system_status
            ):
                armed_str = "ARMED" if table_types.is_armed(msg.base_mode) else "DISARMED"
                mode_str = f"{table_types.mode_name(msg.custom_mode)} ({msg.custom_mode})"
                state_str = "CRITICAL" if msg.system_status == apm.MAV_STATE_CRITICAL else ""
                self.report(f"{armed_str} {mode_str} {state_str}", self.colors.heartbeat)
                self.base_mode = msg.base_mode
                self.custom_mode = msg.custom_mode
                self.system_status = msg.system_status

    def process_status_text(self, msg):
        self.report(f"{table_types.status_severity_name(msg.severity)}: {msg.text}", self.colors.status_text)

    def process_command_long(self, msg):
        if msg.command not in IGNORE_CMDS:
            self.report(f"Command:  {mav_cmd_name(msg.command)}, param1 {msg.param1}", self.colors.command_long)

    def process_command_ack(self, msg):
        if msg.command not in IGNORE_CMDS:
            self.report(
                f"Response: {mav_cmd_name(msg.command)}, {mav_result_name(msg.result)}", self.colors.command_ack
            )

    def process_param_set(self, msg):
        param = Param(msg)
        comment = param.comment()
        if comment is None:
            self.report(f"Set param {param.id} to {param.value_str()}", self.colors.param_set)
        else:
            self.report(f"Set param {param.id} to {comment} ({param.value_str()})", self.colors.param_set)

    def process_gps_global_origin(self, msg):
        lat = msg.latitude / 1.0e7
        lon = msg.longitude / 1.0e7
        alt = msg.altitude / 1000.0
        self.report(
            f"Global origin set to ({lat}, {lon}), altitude {alt} above mean sea level", self.colors.gps_global_origin
        )

    def process_ekf_status_report(self, msg):
        if msg.flags != self.ekf_status_flags:
            if msg.flags & apm.EKF_UNINITIALIZED:
                self.report("EKF uninitialized", self.colors.ekf_status_report)
            elif msg.flags == 0:
                self.report("EKF initialized", self.colors.ekf_status_report)
            else:
                s = f"EKF status: {msg.flags:4}"
                s += f" {'const' if msg.flags & apm.EKF_CONST_POS_MODE else '':5}"
                s += f" {'att' if msg.flags & apm.EKF_ATTITUDE else '':3}"
                s += " pos_xy: ["
                s += f"{'rel' if msg.flags & apm.EKF_POS_HORIZ_REL else '':3}"
                s += f" {'abs' if msg.flags & apm.EKF_POS_HORIZ_ABS else '':3}"
                s += f" {'pred_rel' if msg.flags & apm.EKF_PRED_POS_HORIZ_REL else '':8}"
                s += f" {'pred_abs' if msg.flags & apm.EKF_PRED_POS_HORIZ_ABS else '':8}"
                s += "] pos_z: ["
                s += f"{'abs' if msg.flags & apm.EKF_POS_VERT_ABS else '':3}"
                s += f" {'agl' if msg.flags & apm.EKF_POS_VERT_AGL else '':3}"
                s += "] vel: ["
                s += f"{'xy' if msg.flags & apm.EKF_VELOCITY_HORIZ else '':2}"
                s += f" {'z' if msg.flags & apm.EKF_VELOCITY_VERT else '':1}"
                s += "]"
                self.report(s, self.colors.ekf_status_report)
            self.ekf_status_flags = msg.flags
