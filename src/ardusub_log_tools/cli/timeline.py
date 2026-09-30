"""
ASL 2.0: 'timeline' verb implementation.
"""

from __future__ import annotations

import argparse
import datetime
import io
import os
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pymavlink.dialects.v20.ardupilotmega as apm

import table_types
import util
from ardusub_log_tools.core.mcap_events import resolve_enum_value
from ardusub_log_tools.core.output import resolve_outfile_name
from tlog_timeline import ANSI_CODES, IGNORE_CMDS, ColorMap, mav_cmd_name, mav_result_name


class GenericTimelineWriter:
    """Format chronological event stream with optional ANSI colors and custom timezone."""

    def __init__(self, out_file: io.TextIOBase, ansi: bool, tz: ZoneInfo):
        self.out = out_file
        self.ansi = ansi
        self.tz = tz
        self.colors = ColorMap()
        self.first_ts: float | None = None

        # Autopilot state
        self.base_mode = apm.MAV_MODE_PREFLIGHT
        self.custom_mode = table_types.Mode.UNKNOWN
        self.system_status = apm.MAV_STATE_UNINIT
        self.ekf_status_flags = apm.EKF_UNINITIALIZED

        self.out.write("Time                |   Since epoch | Elapsed : Message\n")

    def format_prefix(self, ts: float) -> str:
        if self.first_ts is None:
            self.first_ts = ts
        dt = datetime.datetime.fromtimestamp(ts, tz=self.tz)
        dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        elapsed = ts - self.first_ts
        return f"{dt_str} | {ts:.2f} | {elapsed:7.2f} : "

    def report(self, ts: float, msg_str: str, color_name: str | None = None) -> None:
        prefix = self.format_prefix(ts)
        if self.ansi and color_name and color_name in ANSI_CODES:
            line = f"{prefix}{ANSI_CODES[color_name]}{msg_str}{ANSI_CODES['END']}\n"
        else:
            line = f"{prefix}{msg_str}\n"
        self.out.write(line)

    def process_heartbeat(self, ts: float, base_mode: int, custom_mode: int, system_status: int) -> None:
        if base_mode != self.base_mode or custom_mode != self.custom_mode or system_status != self.system_status:
            armed_str = "ARMED" if table_types.is_armed(base_mode) else "DISARMED"
            mode_str = f"{table_types.mode_name(custom_mode)} ({custom_mode})"
            state_str = "CRITICAL" if system_status == apm.MAV_STATE_CRITICAL else ""
            msg = f"{armed_str} {mode_str} {state_str}".strip()
            self.report(ts, msg, self.colors.heartbeat)
            self.base_mode = base_mode
            self.custom_mode = custom_mode
            self.system_status = system_status

    def process_statustext(self, ts: float, severity: int, text: str) -> None:
        sev_name = table_types.status_severity_name(severity)
        self.report(ts, f"{sev_name}: {text}", self.colors.status_text)

    def process_command_long(self, ts: float, command: int, param1: float = 0.0) -> None:
        if command not in IGNORE_CMDS:
            self.report(ts, f"Command:  {mav_cmd_name(command)}, param1 {param1}", self.colors.command_long)

    def process_command_ack(self, ts: float, command: int, result: int) -> None:
        if command not in IGNORE_CMDS:
            self.report(ts, f"Response: {mav_cmd_name(command)}, {mav_result_name(result)}", self.colors.command_ack)

    def process_param_set(self, ts: float, param_id: str, param_value: float) -> None:
        from ardusub_log_tools.core.mcap_events import McapParam

        p = McapParam(param_id, param_value)
        comment = p.comment()
        if comment:
            self.report(ts, f"Set param {param_id} to {comment} ({p.value_str()})", self.colors.param_set)
        else:
            self.report(ts, f"Set param {param_id} to {p.value_str()}", self.colors.param_set)

    def process_gps_global_origin(self, ts: float, lat: float, lon: float, alt: float) -> None:
        self.report(
            ts,
            f"Global origin set to ({lat:.7f}, {lon:.7f}), altitude {alt:.1f} above mean sea level",
            self.colors.gps_global_origin,
        )

    def process_ekf_status(self, ts: float, flags: int) -> None:
        if flags != self.ekf_status_flags:
            if flags & apm.EKF_UNINITIALIZED:
                self.report(ts, "EKF uninitialized", self.colors.ekf_status_report)
            elif flags == 0:
                self.report(ts, "EKF initialized", self.colors.ekf_status_report)
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
                self.report(ts, s, self.colors.ekf_status_report)
            self.ekf_status_flags = flags


def _generate_mcap_timeline(file_path: str, writer: GenericTimelineWriter) -> None:
    types = [
        "HEARTBEAT",
        "STATUSTEXT",
        "COMMAND_LONG",
        "COMMAND_ACK",
        "PARAM_SET",
        "GPS_GLOBAL_ORIGIN",
        "EKF_STATUS_REPORT",
    ]
    for _, _, msg in util.iter_mcap_messages(file_path, message_types=types, sys_id=None, comp_id=None):
        ts = msg.log_time_s
        d = msg.json
        header = d.get("header", {})
        m = d.get("message", {})
        mtype = m.get("type")
        sys_id = header.get("system_id", 1)
        comp_id = header.get("component_id", 1)

        if mtype == "HEARTBEAT" and sys_id == 1 and comp_id == 1:
            base_mode = resolve_enum_value(m.get("base_mode", 0))
            custom_mode = m.get("custom_mode", 0)
            system_status = resolve_enum_value(m.get("system_status", 0))
            writer.process_heartbeat(ts, base_mode, custom_mode, system_status)

        elif mtype == "STATUSTEXT":
            sev = resolve_enum_value(m.get("severity", 0))
            text = str(m.get("text", "")).rstrip("\x00").strip()
            writer.process_statustext(ts, sev, text)

        elif mtype == "COMMAND_LONG":
            cmd = m.get("command", 0)
            p1 = m.get("param1", 0.0)
            writer.process_command_long(ts, cmd, p1)

        elif mtype == "COMMAND_ACK":
            cmd = m.get("command", 0)
            res = resolve_enum_value(m.get("result", 0))
            writer.process_command_ack(ts, cmd, res)

        elif mtype == "PARAM_SET":
            p_id = str(m.get("param_id", "")).rstrip("\x00").strip()
            p_val = m.get("param_value", 0.0)
            writer.process_param_set(ts, p_id, p_val)

        elif mtype == "GPS_GLOBAL_ORIGIN":
            lat = m.get("latitude", 0) / 1e7
            lon = m.get("longitude", 0) / 1e7
            alt = m.get("altitude", 0) / 1000.0
            writer.process_gps_global_origin(ts, lat, lon, alt)

        elif mtype == "EKF_STATUS_REPORT":
            flags = resolve_enum_value(m.get("flags", 0))
            writer.process_ekf_status(ts, flags)


def _generate_tlog_timeline(reader, writer: GenericTimelineWriter) -> None:
    for msg in reader:
        ts = getattr(msg, "_timestamp", 0.0)
        mtype = msg.get_type()

        if mtype == "HEARTBEAT" and msg.get_srcSystem() == 1 and msg.get_srcComponent() == 1:
            writer.process_heartbeat(ts, msg.base_mode, msg.custom_mode, msg.system_status)
        elif mtype == "STATUSTEXT":
            writer.process_statustext(ts, msg.severity, msg.text)
        elif mtype == "COMMAND_LONG":
            writer.process_command_long(ts, msg.command, getattr(msg, "param1", 0.0))
        elif mtype == "COMMAND_ACK":
            writer.process_command_ack(ts, msg.command, msg.result)
        elif mtype == "PARAM_SET":
            writer.process_param_set(ts, msg.param_id, msg.param_value)
        elif mtype == "GPS_GLOBAL_ORIGIN":
            writer.process_gps_global_origin(ts, msg.latitude / 1e7, msg.longitude / 1e7, msg.altitude / 1000.0)
        elif mtype == "EKF_STATUS_REPORT":
            writer.process_ekf_status(ts, msg.flags)


def _generate_bin_timeline(reader, writer: GenericTimelineWriter) -> None:
    from BIN_messages import LogEvent, decode_error

    for msg in reader:
        mtype = msg.get_type()
        data = msg.to_dict()
        ts = getattr(msg, "_timestamp", data.get("TimeUS", 0) * 1e-6)

        if mtype == "MODE":
            mode_num = data.get("Mode", 0)
            writer.report(ts, f"MODE {table_types.mode_name(mode_num)} ({mode_num})", writer.colors.heartbeat)
        elif mtype == "ARM":
            armed = data.get("ArmState", 0) == 1
            writer.report(ts, "ARMED" if armed else "DISARMED", writer.colors.heartbeat)
        elif mtype == "MSG":
            writer.report(ts, str(data.get("Message", "")), writer.colors.status_text)
        elif mtype == "EV":
            try:
                ev = LogEvent(data.get("Id", 0))
                writer.report(ts, f"Event: {ev.name}", writer.colors.status_text)
            except ValueError:
                writer.report(ts, f"Event: {data.get('Id', 0)}", writer.colors.status_text)
        elif mtype == "ERR":
            subsys, ecode = decode_error(data.get("Subsys", 0), data.get("ECode", 0))
            writer.report(ts, f"Error: Subsys {subsys}, ECode {ecode}", writer.colors.status_text)
        elif mtype == "CMD":
            cmd = data.get("CId", 0)
            p1 = data.get("Prm1", 0.0)
            writer.process_command_long(ts, cmd, p1)
        elif mtype == "MAVC":
            cmd = data.get("Cmd", 0)
            res = data.get("Res", 0)
            writer.process_command_ack(ts, cmd, res)
        elif mtype == "PARM":
            p_name = str(data.get("Name", "")).rstrip("\x00").strip()
            p_val = data.get("Value", 0.0)
            writer.process_param_set(ts, p_name, p_val)
        elif mtype == "ORGN":
            lat = data.get("Lat", 0) / 1e7
            lon = data.get("Lng", 0) / 1e7
            alt = data.get("Alt", 0) / 100.0
            writer.process_gps_global_origin(ts, lat, lon, alt)
        elif mtype == "XKF4":
            flags = data.get("SS", 0)
            writer.process_ekf_status(ts, flags)


def run_timeline(args: argparse.Namespace) -> int:
    """Execute the 'timeline' command across supported log files (.BIN, .tlog, .mcap)."""
    files = util.expand_path(args.paths, getattr(args, "recurse", False), [".tlog", ".BIN", ".mcap"])
    if not files:
        print("No matching log files found (.BIN, .tlog, .mcap).")
        return 1

    tz_str = getattr(args, "tz", "UTC") or "UTC"
    try:
        tz = ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        print(f"Warning: Unknown timezone '{tz_str}', falling back to UTC.", file=sys.stderr)
        tz = ZoneInfo("UTC")

    ansi = not getattr(args, "no_ansi", False)

    print(f"Processing {len(files)} file(s) for 'timeline'")

    for file_path in files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        print("------------------------------------------------------------")
        print(f"Generating timeline for {file_path}")

        try:
            if ext_lower == ".mcap":
                outfile = resolve_outfile_name(file_path, suffix="_timeline", ext=".txt", output_dir=args.output_dir)
                with open(outfile, "w", encoding="utf-8") as f:
                    writer = GenericTimelineWriter(f, ansi=ansi, tz=tz)
                    _generate_mcap_timeline(file_path, writer)
                print(f"Wrote {outfile}")

            elif ext_lower == ".tlog":
                from segment_reader import choose_reader_list
                from tlog_timeline import MSG_TYPES as TLOG_MSG_TYPES

                sub_args = argparse.Namespace(
                    path=[file_path],
                    recurse=False,
                    keep=getattr(args, "keep", None),
                    segments=getattr(args, "segments", None),
                    all=False,
                    blueos=False,
                    qgc=False,
                )
                readers = choose_reader_list(sub_args, TLOG_MSG_TYPES, ext=".tlog")
                for reader in readers:
                    seg_label = f"_{reader._segment.name}" if hasattr(reader, "_segment") else ""
                    outfile = resolve_outfile_name(
                        file_path, suffix=f"{seg_label}_timeline", ext=".txt", output_dir=args.output_dir
                    )
                    with open(outfile, "w", encoding="utf-8") as f:
                        writer = GenericTimelineWriter(f, ansi=ansi, tz=tz)
                        _generate_tlog_timeline(reader, writer)
                    print(f"Wrote {outfile}")

            elif ext_lower == ".bin":
                from BIN_timeline import MSG_TYPES as BIN_MSG_TYPES
                from segment_reader import choose_reader_list

                sub_args = argparse.Namespace(
                    path=[file_path],
                    recurse=False,
                    keep=getattr(args, "keep", None),
                    segments=getattr(args, "segments", None),
                    all=False,
                )
                readers = choose_reader_list(sub_args, BIN_MSG_TYPES, ext=".BIN")
                for reader in readers:
                    seg_label = f"_{reader._segment.name}" if hasattr(reader, "_segment") else ""
                    outfile = resolve_outfile_name(
                        file_path, suffix=f"{seg_label}_timeline", ext=".txt", output_dir=args.output_dir
                    )
                    with open(outfile, "w", encoding="utf-8") as f:
                        writer = GenericTimelineWriter(f, ansi=ansi, tz=tz)
                        _generate_bin_timeline(reader, writer)
                    print(f"Wrote {outfile}")

            else:
                print(f"Unsupported file format for timeline: {ext}")
                continue

        except Exception as e:
            print(f"Error generating timeline for {file_path}: {e}", file=sys.stderr)
            if getattr(args, "verbose", False):
                import traceback

                traceback.print_exc()
            return 1

    return 0
