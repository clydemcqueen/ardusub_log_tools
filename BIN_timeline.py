#!/usr/bin/env python3

"""
Read Dataflash messages from a BIN file and generate a timeline.

Supports segments.

EKF status bits:
  const             EKF_CONST_POS_MODE      Not enough information to estimate xy position
  att               EKF_ATTITUDE            Good estimate for attitude (roll, pitch yaw)
  pos_xy rel        EKF_POS_HORIZ_REL       Good estimate for relative xy position
  pos_xy abs        EKF_POS_HORIZ_ABS       Good estimate for absolute xy position
  pos_xy pred_rel   EKF_PRED_POS_HORIZ_REL  Good prediction for relative xy position
  pos_xy pred_abs   EKF_PRED_POS_HORIZ_ABS  Good prediction for absolute xy position
  pos_z abs         EKF_POS_VERT_ABS        Good estimate for absolute z position
  pos_z agl         EKF_POS_VERT_AGL        Good estimate for z position "above ground level"
  vel xy            EKF_VELOCITY_HORIZ      Good estimate for xy velocity
  vel z             EKF_VELOCITY_VERT       Good estimate for z velocity

Example EKF status reports:

SITL (GPS):                           att pos_xy: [rel abs pred_rel pred_abs] pos_z: [abs agl] vel: [xy z]
Sub with just a barometer:      const att pos_xy: [                         ] pos_z: [abs agl] vel: [xy z]
Sub with a DVL:                       att pos_xy: [rel     pred_rel         ] pos_z: [abs agl] vel: [xy z]
"""

import argparse
import datetime

import pymavlink.dialects.v20.ardupilotmega as apm

import table_types
from BIN_messages import LogErrorSubsystem, LogEvent, log_error_code
from BIN_param import DataflashParam
from segment_reader import add_segment_args, choose_reader_list
from tlog_param import NOISY_PARAMS

# Process these messages to build the timeline
MSG_TYPES = [
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

# Ignore these commands
IGNORE_CMDS = [511, 512, 521, 522, 525, 527, 2504, 2505]

# Highlight these modes
AUTO_MODES = [
    table_types.Mode.ACRO,
    table_types.Mode.AUTO,
    table_types.Mode.GUIDED,
    table_types.Mode.CIRCLE,
    table_types.Mode.SURFACE,
    table_types.Mode.POS_HOLD,
    table_types.Mode.MOTOR_DETECT,
]

SOURCE_SETS = [
    "primary (0)",
    "secondary (1)",
    "tertiary (2)",
]

# A few ANSI codes
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
    else:
        return f"unknown command {cmd}"


def mav_result_name(result: int) -> str:
    if result in apm.enums["MAV_RESULT"]:
        return f"{apm.enums['MAV_RESULT'][result].name} ({result})"
    else:
        return f"unknown result {result}"


def format_param_value(val: float) -> str:
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    elif isinstance(val, float):
        return f"{val:g}"
    return str(val)


class Timeline:
    def __init__(self, reader, ansi: bool = True):
        # Enable / disable ansi codes
        self.ansi = ansi
        self.colors = ColorMap()

        # Track mode and arm state
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
                # Catch all
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
        try:
            subsys = LogErrorSubsystem(subsys_id)
            ecode_names = [name for name, code in log_error_code.items() if code == ecode]
            ecode_str = ",".join(ecode_names) if ecode_names else str(ecode)
            self.report(f"Error: Subsys {subsys.name}, ECode {ecode_str}", self.colors.status_text)
        except ValueError:
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


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser, ext=".BIN")
    parser.add_argument(
        "--ansi", default=True, action=argparse.BooleanOptionalAction, help="add ANSI colors, use --no-ansi to disable"
    )
    args = parser.parse_args()

    readers = choose_reader_list(args, MSG_TYPES, ext=".BIN")
    for reader in readers:
        print(f"Results for {reader.name}")
        Timeline(reader, args.ansi)


if __name__ == "__main__":
    main()
