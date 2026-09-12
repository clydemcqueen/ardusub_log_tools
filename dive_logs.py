#!/usr/bin/env python3
"""
Dive Logs Correspondence & Alignment Tool
=========================================

Analyzes ArduSub Dataflash (.BIN) logs and BlueOS MAVLink recordings (.mcap)
in a dive directory to establish exact boot cycles, time alignment (rtc_shift_s),
file correspondences, and depth-signal optimization.

Conforms to schemas/dive_logs.schema.json.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import util

# Auto-fallback to project .venv if dependencies are not in current interpreter
# TODO: remove this, it is an artifact of how the agent manages Python in a multi-project folder
try:
    import numpy as np
    from pymavlink import mavutil
except ImportError:
    venv_python = os.path.abspath(os.path.join(os.path.dirname(__file__), ".venv", "bin", "python3"))
    if os.path.exists(venv_python) and sys.executable != venv_python:
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        raise

# GPS epoch (1980-01-06) and leap seconds
_GPS_EPOCH = 315964800
_GPS_LEAP = 18

# ArduSub Flight Modes
SUB_MODES = {
    0: "STABILIZE",
    1: "ACRO",
    2: "ALT_HOLD",
    3: "AUTO",
    4: "GUIDED",
    7: "CIRCLE",
    9: "SURFACE",
    16: "POS_HOLD",
    19: "MANUAL",
    20: "MOTOR_DETECT",
    21: "SURFTRAK",
}


def get_sub_mode(mode_num: int | str | None) -> str:
    """Return standard flight mode name for integer mode number."""
    if mode_num is None:
        return "UNKNOWN"
    try:
        mn = int(mode_num)
        return SUB_MODES.get(mn, f"MODE_{mn}")
    except (ValueError, TypeError):
        return str(mode_num)


def format_iso(timestamp_s: float | None) -> str | None:
    """Format Unix timestamp in seconds to ISO-8601 UTC string."""
    if timestamp_s is None:
        return None
    dt = datetime.fromtimestamp(timestamp_s, tz=timezone.utc)
    return dt.isoformat()


def parse_iso(iso_str: str | None) -> float | None:
    """Parse ISO-8601 string to Unix timestamp in seconds."""
    if not iso_str:
        return None
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.timestamp()


@dataclass
class BinFile:
    name: str
    boot_id: int | None
    uptime_start_s: float
    uptime_end_s: float
    duration_s: float
    start_iso: str | None = None
    end_iso: str | None = None
    log_disarmed: int | None = None
    ardusub_version: str | None = None
    has_rtc_message: bool = False
    has_gps_fix: bool = False
    mcap_files: list[str] = field(default_factory=list)
    _dive_logs: DiveLogs | None = field(default=None, repr=False)

    def timeus_to_utc_s(self, time_us: int | float) -> float | None:
        """Convert a TimeUS value in this BIN log to a UTC Unix epoch timestamp."""
        if self._dive_logs and self.boot_id is not None:
            boot = self._dive_logs.get_boot(self.boot_id)
            if boot and boot.rtc_shift_s is not None:
                return (time_us / 1e6) + boot.rtc_shift_s
        return None

    def timeus_to_iso(self, time_us: int | float) -> str | None:
        """Convert a TimeUS value in this BIN log to an ISO-8601 UTC string."""
        utc_s = self.timeus_to_utc_s(time_us)
        return format_iso(utc_s)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "boot_id": self.boot_id,
            "log_disarmed": self.log_disarmed,
            "ardusub_version": self.ardusub_version,
            "uptime_start_s": round(self.uptime_start_s, 6),
            "uptime_end_s": round(self.uptime_end_s, 6),
            "duration_s": round(self.duration_s, 3),
            "start_iso": self.start_iso,
            "end_iso": self.end_iso,
            "has_rtc_message": self.has_rtc_message,
            "has_gps_fix": self.has_gps_fix,
            "mcap_files": self.mcap_files,
        }


@dataclass
class McapFile:
    name: str
    boot_id: int | None
    start_iso: str
    end_iso: str
    duration_s: float
    uptime_start_s: float | None = None
    uptime_end_s: float | None = None
    sample_rtc_shift_s: float | None = None
    flight_modes: list[str] = field(default_factory=list)
    bin_files: list[str] = field(default_factory=list)
    _dive_logs: DiveLogs | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "boot_id": self.boot_id,
            "start_iso": self.start_iso,
            "end_iso": self.end_iso,
            "duration_s": round(self.duration_s, 3),
            "uptime_start_s": round(self.uptime_start_s, 6) if self.uptime_start_s is not None else None,
            "uptime_end_s": round(self.uptime_end_s, 6) if self.uptime_end_s is not None else None,
            "sample_rtc_shift_s": round(self.sample_rtc_shift_s, 6) if self.sample_rtc_shift_s is not None else None,
            "flight_modes": self.flight_modes,
            "bin_files": self.bin_files,
        }


@dataclass
class Boot:
    boot_id: int
    rtc_shift_s: float | None
    start_iso: str | None
    end_iso: str | None
    duration_s: float | None
    alignment_method: str
    signal_optimized: bool = False
    depth_correlation_r: float | None = None
    bin_files: list[str] = field(default_factory=list)
    mcap_files: list[str] = field(default_factory=list)
    _dive_logs: DiveLogs | None = field(default=None, repr=False)

    @property
    def bins(self) -> list[BinFile]:
        """Convenience property returning resolved BinFile objects."""
        if not self._dive_logs:
            return []
        return [self._dive_logs.get_bin(name) for name in self.bin_files if self._dive_logs.get_bin(name)]

    @property
    def mcaps(self) -> list[McapFile]:
        """Convenience property returning resolved McapFile objects."""
        if not self._dive_logs:
            return []
        return [self._dive_logs.get_mcap(name) for name in self.mcap_files if self._dive_logs.get_mcap(name)]

    def to_dict(self) -> dict:
        return {
            "boot_id": self.boot_id,
            "rtc_shift_s": round(self.rtc_shift_s, 6) if self.rtc_shift_s is not None else None,
            "start_iso": self.start_iso,
            "end_iso": self.end_iso,
            "duration_s": round(self.duration_s, 3) if self.duration_s is not None else None,
            "alignment_method": self.alignment_method,
            "signal_optimized": self.signal_optimized,
            "depth_correlation_r": round(self.depth_correlation_r, 4) if self.depth_correlation_r is not None else None,
            "bin_files": self.bin_files,
            "mcap_files": self.mcap_files,
        }


class DiveLogs:
    """
    Top-level representation of dive logs and their time-alignments for a directory.
    """

    def __init__(
        self,
        directory: str | Path,
        boots: list[Boot],
        bin_files: list[BinFile],
        mcap_files: list[McapFile],
        schema_version: str = "1.0.0",
        created_iso: str | None = None,
    ):
        self.directory = Path(directory).resolve()
        self.schema_version = schema_version
        self.created_iso = created_iso or datetime.now(timezone.utc).isoformat()
        self.boots = boots
        self.bin_files = bin_files
        self.mcap_files = mcap_files
        self._index()

    def _index(self):
        self._boot_map: dict[int, Boot] = {b.boot_id: b for b in self.boots}
        self._bin_map: dict[str, BinFile] = {b.name: b for b in self.bin_files}
        self._mcap_map: dict[str, McapFile] = {m.name: m for m in self.mcap_files}

        for b in self.boots:
            b._dive_logs = self
        for f in self.bin_files:
            f._dive_logs = self
        for m in self.mcap_files:
            m._dive_logs = self

    def get_boot(self, boot_id: int | None) -> Boot | None:
        """Lookup a Boot object by its 1-based boot_id."""
        return self._boot_map.get(boot_id) if boot_id is not None else None

    def get_bin(self, name: str) -> BinFile | None:
        """Lookup a BinFile object by filename."""
        return self._bin_map.get(name)

    def get_mcap(self, name: str) -> McapFile | None:
        """Lookup an McapFile object by filename."""
        return self._mcap_map.get(name)

    def find_overlapping(
        self,
        start_utc: float | str,
        end_utc: float | str,
    ) -> tuple[list[BinFile], list[McapFile]]:
        """
        Find all BIN and MCAP logs that overlap a given UTC time window.
        Input timestamps can be float epoch seconds or ISO strings.
        """
        t_start = parse_iso(start_utc) if isinstance(start_utc, str) else float(start_utc)
        t_end = parse_iso(end_utc) if isinstance(end_utc, str) else float(end_utc)

        matched_bins = []
        for b in self.bin_files:
            if b.start_iso and b.end_iso:
                b_start = parse_iso(b.start_iso)
                b_end = parse_iso(b.end_iso)
                if b_start and b_end and max(b_start, t_start) <= min(b_end, t_end):
                    matched_bins.append(b)

        matched_mcaps = []
        for m in self.mcap_files:
            m_start = parse_iso(m.start_iso)
            m_end = parse_iso(m.end_iso)
            if m_start and m_end and max(m_start, t_start) <= min(m_end, t_end):
                matched_mcaps.append(m)

        return matched_bins, matched_mcaps

    def to_dict(self) -> dict:
        """Serialize data to JSON-compatible dictionary conforming to schema."""
        return {
            "schema_version": self.schema_version,
            "directory": str(self.directory),
            "created_iso": self.created_iso,
            "boots": [b.to_dict() for b in self.boots],
            "bin_files": [b.to_dict() for b in self.bin_files],
            "mcap_files": [m.to_dict() for m in self.mcap_files],
        }

    def save(self, dest: str | Path | None = None) -> Path:
        """
        Save dive logs alignment metadata to dive_logs.json in directory or target path.
        """
        if dest is None:
            dest_path = self.directory / "dive_logs.json"
        else:
            dest_path = Path(dest)
            if dest_path.is_dir():
                dest_path = dest_path / "dive_logs.json"

        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

        return dest_path

    @classmethod
    def from_dict(cls, data: dict, directory: str | Path) -> DiveLogs:
        """Construct DiveLogs instance from parsed JSON dictionary."""
        boots = [
            Boot(
                boot_id=b["boot_id"],
                rtc_shift_s=b.get("rtc_shift_s"),
                start_iso=b.get("start_iso"),
                end_iso=b.get("end_iso"),
                duration_s=b.get("duration_s"),
                alignment_method=b["alignment_method"],
                signal_optimized=b.get("signal_optimized", False),
                depth_correlation_r=b.get("depth_correlation_r"),
                bin_files=b.get("bin_files", []),
                mcap_files=b.get("mcap_files", []),
            )
            for b in data.get("boots", [])
        ]

        bin_files = [
            BinFile(
                name=bf["name"],
                boot_id=bf.get("boot_id"),
                uptime_start_s=bf["uptime_start_s"],
                uptime_end_s=bf["uptime_end_s"],
                duration_s=bf["duration_s"],
                start_iso=bf.get("start_iso"),
                end_iso=bf.get("end_iso"),
                log_disarmed=bf.get("log_disarmed"),
                ardusub_version=bf.get("ardusub_version"),
                has_rtc_message=bf.get("has_rtc_message", False),
                has_gps_fix=bf.get("has_gps_fix", False),
                mcap_files=bf.get("mcap_files", []),
            )
            for bf in data.get("bin_files", [])
        ]

        mcap_files = [
            McapFile(
                name=mf["name"],
                boot_id=mf.get("boot_id"),
                start_iso=mf["start_iso"],
                end_iso=mf["end_iso"],
                duration_s=mf["duration_s"],
                uptime_start_s=mf.get("uptime_start_s"),
                uptime_end_s=mf.get("uptime_end_s"),
                sample_rtc_shift_s=mf.get("sample_rtc_shift_s"),
                flight_modes=mf.get("flight_modes", []),
                bin_files=mf.get("bin_files", []),
            )
            for mf in data.get("mcap_files", [])
        ]

        return cls(
            directory=directory,
            boots=boots,
            bin_files=bin_files,
            mcap_files=mcap_files,
            schema_version=data.get("schema_version", "1.0.0"),
            created_iso=data.get("created_iso"),
        )

    @classmethod
    def load(cls, path_or_dir: str | Path) -> DiveLogs:
        """Load DiveLogs from a dive_logs.json file or dated dive directory."""
        p = Path(path_or_dir).resolve()
        if p.is_dir():
            target = p / "dive_logs.json"
        else:
            target = p
            p = p.parent

        if not target.is_file():
            raise FileNotFoundError(f"Dive logs file not found: {target}")

        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data, directory=p)

    @classmethod
    def build(
        cls,
        directory: str | Path,
        optimize: bool = True,
        verbose: bool = False,
    ) -> DiveLogs:
        """
        Scan a directory, align all BIN and MCAP logs, optimize depth signals,
        and return a populated DiveLogs instance.
        """
        target_dir = Path(directory).resolve()
        return _build_alignment(target_dir, optimize=optimize, verbose=verbose)


# ---------------------------------------------------------------------------
#  Log Scanners & Extraction
# ---------------------------------------------------------------------------


@dataclass
class McapScan:
    path: Path
    first_log_time_s: float
    last_log_time_s: float
    uptime_start_s: float | None = None
    uptime_end_s: float | None = None
    sample_rtc_shift_s: float | None = None
    system_time_shift_s: float | None = None
    flight_modes: list[str] = field(default_factory=list)
    depth_track: list[tuple[float, float]] = field(default_factory=list)  # (uptime_s, depth_m)
    armed_spans: list[tuple[float, float]] = field(default_factory=list)  # (uptime_s, uptime_s)


@dataclass
class BinScan:
    path: Path
    uptime_start_s: float
    uptime_end_s: float
    duration_s: float
    log_disarmed: int | None = None
    ardusub_version: str | None = None
    rtc_shift_from_rtc: float | None = None
    rtc_shift_from_gps: float | None = None
    has_rtc_message: bool = False
    has_gps_fix: bool = False
    flight_modes: list[str] = field(default_factory=list)
    depth_track: list[tuple[float, float]] = field(default_factory=list)  # (uptime_s, depth_m)
    armed_spans: list[tuple[float, float]] = field(default_factory=list)  # (uptime_s, uptime_s)


def scan_mcap_file(path: Path, verbose: bool = False) -> McapScan | None:
    """Scan a BlueOS MCAP file extracting timestamps, ArduSub uptime, and depth track."""
    if verbose:
        print(f"  [MCAP] Scanning {path.name}...")

    info = util.get_mcap_summary_info(path)
    first_log_time = info.start_time_s if info else None
    last_log_time = info.end_time_s if info else None
    first_uptime = None
    last_uptime = None
    shift_samples: list[float] = []
    sys_time_shifts: list[float] = []
    depth_track: list[tuple[float, float]] = []
    flight_modes: list[str] = []
    arm_events: list[tuple[float, int]] = []
    prev_armed: bool | None = None

    try:
        for schema, channel, message in util.iter_mcap_messages(
            path,
            message_types=["HEARTBEAT", "GLOBAL_POSITION_INT", "SYSTEM_TIME"],
            sys_id=1,
            comp_id=1,
        ):
            log_t = message.log_time_s
            if first_log_time is None:
                first_log_time = log_t
            last_log_time = log_t

            try:
                data = message.json
            except Exception:
                continue

            header = data.get("header", {})
            sys_id = header.get("system_id", 1)
            comp_id = header.get("component_id", 1)

            # Focus on vehicle autopilot messages (sysid=1, compid=1)
            if sys_id != 1 or comp_id != 1:
                continue

            msg = data.get("message", {})
            mtype = msg.get("type")

            # Extract flight modes and arm state from HEARTBEAT
            if mtype == "HEARTBEAT":
                custom_mode = msg.get("custom_mode", 0)
                if isinstance(custom_mode, dict):
                    custom_mode = custom_mode.get("type", 0)
                mname = get_sub_mode(custom_mode)
                if not flight_modes or flight_modes[-1] != mname:
                    flight_modes.append(mname)

                base_mode = msg.get("base_mode", 0)
                is_armed = (
                    "SAFETY_ARMED" in str(base_mode)
                    if isinstance(base_mode, (str, dict))
                    else bool(int(base_mode or 0) & 128)
                )
                if is_armed != prev_armed:
                    t_now = last_uptime or (log_t - shift_samples[0] if shift_samples else None)
                    if t_now is not None:
                        arm_events.append((t_now, 1 if is_armed else 0))
                    prev_armed = is_armed

            # Extract ArduSub uptime (time_boot_ms)
            bms = msg.get("time_boot_ms")
            if bms is not None and isinstance(bms, (int, float)) and bms > 0:
                uptime_s = bms / 1000.0
                if first_uptime is None:
                    first_uptime = uptime_s
                last_uptime = uptime_s

                # Candidate rtc_shift
                shift_samples.append(log_t - uptime_s)

                # Extract depth from GLOBAL_POSITION_INT relative_alt (in mm)
                if mtype == "GLOBAL_POSITION_INT" and "relative_alt" in msg:
                    rel_alt = msg.get("relative_alt")
                    if rel_alt is not None:
                        depth_m = -float(rel_alt) / 1000.0
                        depth_track.append((uptime_s, depth_m))

            # Extract MAVLink SYSTEM_TIME (time_unix_usec) from autopilot
            if mtype == "SYSTEM_TIME":
                time_unix_usec = msg.get("time_unix_usec")
                bms_st = msg.get("time_boot_ms")
                if (
                    time_unix_usec
                    and isinstance(time_unix_usec, (int, float))
                    and time_unix_usec > 1_000_000_000_000_000
                ):
                    up_ref = (bms_st / 1000.0) if (bms_st and bms_st > 0) else last_uptime
                    if up_ref is not None:
                        sys_time_shifts.append((time_unix_usec / 1e6) - up_ref)

    except Exception as ex:
        if verbose:
            print(f"  [MCAP] Warning reading {path.name}: {ex}", file=sys.stderr)
        return None

    if first_log_time is None or last_log_time is None:
        return None

    sample_shift = None
    if shift_samples:
        # Take 1st percentile of shifts to eliminate positive transport latency
        sample_shift = float(np.percentile(shift_samples, 1.0))

    sys_shift = float(np.median(sys_time_shifts)) if sys_time_shifts else None

    # Construct armed spans
    armed_spans: list[tuple[float, float]] = []
    curr_arm = None
    for t_up, st in arm_events:
        if st == 1 and curr_arm is None:
            curr_arm = t_up
        elif st == 0 and curr_arm is not None:
            armed_spans.append((curr_arm, t_up))
            curr_arm = None
    if curr_arm is not None and last_uptime is not None:
        armed_spans.append((curr_arm, last_uptime))

    return McapScan(
        path=path,
        first_log_time_s=first_log_time,
        last_log_time_s=last_log_time,
        uptime_start_s=first_uptime,
        uptime_end_s=last_uptime,
        sample_rtc_shift_s=sample_shift,
        system_time_shift_s=sys_shift,
        flight_modes=flight_modes,
        depth_track=depth_track,
        armed_spans=armed_spans,
    )


def scan_bin_file(path: Path, verbose: bool = False) -> BinScan | None:
    """Scan an ArduSub Dataflash (.BIN) log extracting TimeUS bounds, RTC, GPS, and CTUN depth."""
    if verbose:
        print(f"  [BIN] Scanning {path.name}...")

    try:
        conn = mavutil.mavlink_connection(str(path))
    except Exception as ex:
        if verbose:
            print(f"  [BIN] Error opening {path.name}: {ex}", file=sys.stderr)
        return None

    first_us = None
    last_us = None
    log_disarmed = None
    ardusub_version = None
    rtc_shifts: list[float] = []
    gps_shifts: list[float] = []
    flight_modes: list[str] = []
    depth_track: list[tuple[float, float]] = []
    arm_events: list[tuple[float, int]] = []

    wanted_types = ["PARM", "MSG", "MODE", "ARM", "RTC", "GPS", "CTUN"]

    while True:
        msg = conn.recv_match(type=wanted_types, blocking=False)
        if msg is None:
            break

        us = getattr(msg, "TimeUS", None)
        if us is not None:
            if first_us is None:
                first_us = us
            last_us = us

        mtype = msg.get_type()

        if mtype == "PARM":
            pname = getattr(msg, "Name", "")
            if pname == "LOG_DISARMED":
                log_disarmed = int(getattr(msg, "Value", 1))

        elif mtype == "MSG":
            txt = getattr(msg, "Message", "").strip()
            if "ArduSub" in txt:
                if "V4.7" in txt or "4.7." in txt:
                    ardusub_version = "4.7.0"  # TODO: get full version string
                elif "V4.5" in txt or "4.5." in txt:
                    ardusub_version = "4.5.0"  # TODO: get full version string
                else:
                    ardusub_version = txt.replace("ArduSub", "").strip()

        elif mtype == "MODE":
            mnum = getattr(msg, "Mode", getattr(msg, "ModeNum", None))
            if mnum is not None:
                mname = get_sub_mode(mnum)
                if not flight_modes or flight_modes[-1] != mname:
                    flight_modes.append(mname)

        elif mtype == "ARM":
            astate = getattr(msg, "ArmState", None)
            if astate is not None and us is not None:
                arm_events.append((us / 1e6, int(astate)))

        elif mtype == "RTC":
            epoch_us = getattr(msg, "Epoch", 0)
            source_type = getattr(msg, "SourceType", 3)
            # SourceType: 0=GPS, 1=SYSTEM_TIME, 2=HW, 3=NONE
            if source_type in (0, 1) and epoch_us > 0 and us is not None:
                shift = (epoch_us - us) / 1e6
                rtc_shifts.append(shift)

        elif mtype == "GPS":
            status = getattr(msg, "Status", 0)
            gwk = getattr(msg, "GWk", 0)
            gms = getattr(msg, "GMS", 0)
            if status >= 3 and gwk > 0 and us is not None:
                wall_utc = _GPS_EPOCH + (gwk * 604800) + (gms / 1000.0) - _GPS_LEAP
                gps_shifts.append(wall_utc - (us / 1e6))

        elif mtype == "CTUN":
            # Prefer BAlt (barometer altitude) as Alt is 0.0 before EKF origin initialization
            balt = getattr(msg, "BAlt", None)
            alt = getattr(msg, "Alt", None)
            depth_val = balt if balt is not None else alt
            if depth_val is not None and us is not None:
                depth_track.append((us / 1e6, -float(depth_val)))

    if first_us is None or last_us is None:
        return None

    up_start = first_us / 1e6
    up_end = last_us / 1e6
    dur = max(0.0, up_end - up_start)

    rtc_shift_rtc = float(np.median(rtc_shifts)) if rtc_shifts else None
    rtc_shift_gps = float(np.median(gps_shifts)) if gps_shifts else None

    # Construct armed spans
    armed_spans: list[tuple[float, float]] = []
    starts_armed = (arm_events and arm_events[0][1] == 0) or (log_disarmed is not None and int(log_disarmed) == 0)
    curr_arm = up_start if starts_armed else None
    for t_s, st in arm_events:
        if st == 1 and curr_arm is None:
            curr_arm = t_s
        elif st == 0 and curr_arm is not None:
            armed_spans.append((curr_arm, t_s))
            curr_arm = None
    if curr_arm is not None and up_end is not None:
        armed_spans.append((curr_arm, up_end))
    elif not armed_spans and starts_armed and up_start is not None and up_end is not None:
        armed_spans.append((up_start, up_end))

    return BinScan(
        path=path,
        uptime_start_s=up_start,
        uptime_end_s=up_end,
        duration_s=dur,
        log_disarmed=log_disarmed,
        ardusub_version=ardusub_version,
        rtc_shift_from_rtc=rtc_shift_rtc,
        rtc_shift_from_gps=rtc_shift_gps,
        has_rtc_message=bool(rtc_shifts),
        has_gps_fix=bool(gps_shifts),
        flight_modes=flight_modes,
        depth_track=depth_track,
        armed_spans=armed_spans,
    )


# ---------------------------------------------------------------------------
#  Depth Signal Optimization
# ---------------------------------------------------------------------------


def optimize_depth_shift(
    bin_track: list[tuple[float, float]],
    mcap_track: list[tuple[float, float]],
    search_window_s: float = 0.2,
    resolution_ms: float = 0.2,
) -> tuple[float, float] | None:
    """
    Fine-tune alignment by cross-correlating depth profiles on the shared uptime axis.
    Returns (optimal_delta_s, pearson_r) or None if insufficient movement/data.
    """
    if len(bin_track) < 30 or len(mcap_track) < 30:
        return None

    bt = np.asarray([p[0] for p in bin_track])
    bd = np.asarray([p[1] for p in bin_track])
    mt = np.asarray([p[0] for p in mcap_track])
    md = np.asarray([p[1] for p in mcap_track])

    # Check that vehicle moved vertically (barometer variance > threshold)
    if float(np.std(md)) < 0.05 or float(np.std(bd)) < 0.05:
        return None

    # Overlapping uptime window
    overlap_min = max(float(bt[0]), float(mt[0]))
    overlap_max = min(float(bt[-1]), float(mt[-1]))
    if overlap_max - overlap_min < 5.0:
        return None

    mask = (mt >= overlap_min) & (mt <= overlap_max)
    mt_sub = mt[mask]
    md_sub = md[mask]
    if len(mt_sub) < 30:
        return None

    # Search fine shifts
    step_s = resolution_ms / 1000.0
    num_steps = int((2 * search_window_s) / step_s) + 1
    shifts = np.linspace(-search_window_s, search_window_s, num_steps)

    mses = []
    for s in shifts:
        interp_bd = np.interp(mt_sub + s, bt, bd)
        mse = float(np.mean((md_sub - interp_bd) ** 2))
        mses.append(mse)

    best_idx = int(np.argmin(mses))
    best_delta = float(shifts[best_idx])

    # Compute Pearson correlation at best shift
    interp_best = np.interp(mt_sub + best_delta, bt, bd)
    if float(np.std(interp_best)) < 1e-6:
        return None

    r = float(np.corrcoef(interp_best, md_sub)[0, 1])
    return best_delta, r


# ---------------------------------------------------------------------------
#  Clustering & Alignment Pipeline
# ---------------------------------------------------------------------------


def _build_alignment(directory: Path, optimize: bool = True, verbose: bool = False) -> DiveLogs:
    """Core orchestration engine scanning files, resolving boots, and performing alignment."""
    if verbose:
        print(f"Scanning dive directory: {directory}")

    # Discover logs
    bin_paths = sorted(glob.glob(os.path.join(directory, "*.BIN")))
    mcap_paths = sorted(glob.glob(os.path.join(directory, "*.mcap")))

    bin_scans: list[BinScan] = []
    for bp in bin_paths:
        s = scan_bin_file(Path(bp), verbose=verbose)
        if s:
            bin_scans.append(s)

    mcap_scans: list[McapScan] = []
    for mp in mcap_paths:
        s = scan_mcap_file(Path(mp), verbose=verbose)
        if s:
            mcap_scans.append(s)

    if verbose:
        print(f"Discovered {len(bin_scans)} valid BIN log(s) and {len(mcap_scans)} valid MCAP recording(s).")

    # Group files into Boot cycles.
    # An ArduSub power cycle (boot) has a unique continuous uptime starting at 0.
    # Under standard operation (LOG_FILE_DSRMROT=0), each BIN corresponds to exactly one boot.
    # If LOG_FILE_DSRMROT=1, multiple BIN files might share the same boot session if uptimes are strictly increasing.

    # 1. Cluster BIN files into boots
    boot_groups: list[dict] = []  # list of {'bin_scans': [...], 'mcap_scans': [...]}

    curr_boot_bins: list[BinScan] = []
    for b in bin_scans:
        if not curr_boot_bins:
            curr_boot_bins.append(b)
        else:
            prev = curr_boot_bins[-1]
            # If uptime restarts from near 0 (or goes backwards), it is a new boot!
            if b.uptime_start_s < prev.uptime_end_s - 1.0 or b.uptime_start_s < 10.0:
                boot_groups.append({"bin_scans": curr_boot_bins, "mcap_scans": []})
                curr_boot_bins = [b]
            else:
                curr_boot_bins.append(b)
    if curr_boot_bins:
        boot_groups.append({"bin_scans": curr_boot_bins, "mcap_scans": []})

    # 1b. Cluster MCAP files into boot sessions by uptime monotonicity and reasonable time gaps
    mcap_clusters: list[list[McapScan]] = []
    curr_cluster: list[McapScan] = []

    for m in mcap_scans:
        if not curr_cluster:
            curr_cluster.append(m)
        else:
            prev = curr_cluster[-1]
            p_up = prev.uptime_end_s or 0.0
            m_up = m.uptime_start_s or 0.0
            delta_up = m_up - p_up
            delta_log = m.first_log_time_s - prev.last_log_time_s

            # Two consecutive MCAPs belong to the same autopilot boot if:
            # - Uptime did not go backwards by more than 1 second (delta_up >= -1.0)
            # - Start uptime did not reset near zero while previous was high
            # - Wall-clock elapsed matches ArduSub uptime elapsed within tolerance (< 60s)
            same_boot = (delta_up >= -1.0) and not (m_up < 30.0 and p_up > 60.0) and (abs(delta_log - delta_up) < 60.0)

            if same_boot:
                curr_cluster.append(m)
            else:
                mcap_clusters.append(curr_cluster)
                curr_cluster = [m]
    if curr_cluster:
        mcap_clusters.append(curr_cluster)

    # 2. Match MCAP clusters to BIN boot groups based on positive evidence
    matched_group_indices: set[int] = set()

    for cluster in mcap_clusters:
        cluster_min_up = min((m.uptime_start_s for m in cluster if m.uptime_start_s is not None), default=0.0)
        cluster_max_up = max((m.uptime_end_s for m in cluster if m.uptime_end_s is not None), default=0.0)
        cluster_shifts = [
            (m.system_time_shift_s or m.sample_rtc_shift_s)
            for m in cluster
            if (m.system_time_shift_s or m.sample_rtc_shift_s) is not None
        ]
        cluster_shift = float(np.median(cluster_shifts)) if cluster_shifts else None

        best_group_idx = None
        best_score = 0.0

        for g_idx, group in enumerate(boot_groups):
            if g_idx in matched_group_indices:
                continue

            bins = group["bin_scans"]
            if not bins:
                continue

            b_up_start = bins[0].uptime_start_s
            b_up_end = bins[-1].uptime_end_s

            # BIN file must span long enough to contain the cluster
            if b_up_end < cluster_max_up - 5.0 or b_up_start > cluster_min_up + 5.0:
                continue

            score = 0.0
            best_r = 0.0

            # Evidence A: Test depth correlation across all combinations in cluster/group
            for b in bins:
                for m in cluster:
                    opt = optimize_depth_shift(b.depth_track, m.depth_track)
                    if opt and opt[1] > best_r:
                        best_r = opt[1]

            if best_r >= 0.8:
                score += 1000.0 * best_r

            # Evidence B: If BIN has RTC or GPS shift, check shift difference
            b_shift = bins[0].rtc_shift_from_rtc or bins[0].rtc_shift_from_gps
            if b_shift is not None and cluster_shift is not None:
                diff = abs(b_shift - cluster_shift)
                if diff < 2.0:
                    score += 500.0 - diff
                else:
                    # Incompatible shifts
                    continue

            # Evidence C: When depth correlation is inconclusive/flat (e.g. deck/surface tests)
            # Match by uptime interval containment and armed duration
            if best_r < 0.8:
                bin_arm_durs = [(sp[1] - sp[0]) for b in bins for sp in getattr(b, "armed_spans", [])]
                mcap_arm_durs = [(sp[1] - sp[0]) for m in cluster for sp in getattr(m, "armed_spans", [])]
                if bin_arm_durs and mcap_arm_durs:
                    for b_dur in bin_arm_durs:
                        for m_dur in mcap_arm_durs:
                            d_diff = abs(b_dur - m_dur)
                            if d_diff <= max(3.0, 0.15 * b_dur):
                                score += 600.0 - d_diff
                                break
                elif not bin_arm_durs and not mcap_arm_durs:
                    # Both unarmed, fully contained in uptime
                    score += 300.0

            if score > best_score:
                best_score = score
                best_group_idx = g_idx

        # Only match if there is confirmed evidence (score >= 100.0)
        if best_group_idx is not None and best_score >= 100.0:
            boot_groups[best_group_idx]["mcap_scans"].extend(cluster)
            matched_group_indices.add(best_group_idx)
        else:
            # Standalone boot for this MCAP cluster
            boot_groups.append({"bin_scans": [], "mcap_scans": cluster})

    # Sort boot_groups chronologically
    def group_sort_key(g):
        if g["bin_scans"]:
            return (0, g["bin_scans"][0].path.name)
        elif g["mcap_scans"]:
            return (1, g["mcap_scans"][0].path.name)
        return (2, "")

    boot_groups.sort(key=group_sort_key)

    # 3. Process each boot group into a Boot object and assign rtc_shift_s via Priority Cascade
    boots_out: list[Boot] = []
    bin_files_out: list[BinFile] = []
    mcap_files_out: list[McapFile] = []

    for boot_idx, group in enumerate(boot_groups, start=1):
        g_bins: list[BinScan] = group["bin_scans"]
        g_mcaps: list[McapScan] = group["mcap_scans"]

        shift = None
        method = "unaligned"
        signal_optimized = False
        depth_r = None

        # Priority 1: bin_rtc_message (from ArduSub 4.7 internal RTC message)
        for b in g_bins:
            if b.rtc_shift_from_rtc is not None:
                shift = b.rtc_shift_from_rtc
                method = "bin_rtc_message"
                break

        # Priority 2: bin_gps_fix (direct satellite ground truth)
        if shift is None:
            for b in g_bins:
                if b.rtc_shift_from_gps is not None:
                    shift = b.rtc_shift_from_gps
                    method = "bin_gps_fix"
                    break

        # Priority 3: mcap_system_time (internal ArduSub RTC from MAVLink SYSTEM_TIME in MCAP)
        if shift is None and g_mcaps:
            sys_shifts = [m.system_time_shift_s for m in g_mcaps if getattr(m, "system_time_shift_s", None) is not None]
            if sys_shifts:
                shift = float(np.median(sys_shifts))
                method = "mcap_rtc_shift"

        # Priority 4: mcap_rtc_shift (1st percentile floor from MCAP telemetry)
        if shift is None and g_mcaps:
            mcap_shifts = [m.sample_rtc_shift_s for m in g_mcaps if m.sample_rtc_shift_s is not None]
            if mcap_shifts:
                shift = mcap_shifts[0]
                method = "mcap_rtc_shift"

        # Signal Optimization using Depth Cross-Correlation (opt_rtc_shift)
        if optimize and g_bins and g_mcaps:
            best_opt = None
            best_mcap_shift = None
            for b in g_bins:
                for m in g_mcaps:
                    opt_res = optimize_depth_shift(b.depth_track, m.depth_track)
                    if opt_res:
                        delta_s, r_val = opt_res
                        if best_opt is None or r_val > best_opt[1]:
                            best_opt = (delta_s, r_val)
                            best_mcap_shift = m.system_time_shift_s or m.sample_rtc_shift_s

            if best_opt and best_opt[1] >= 0.8:
                delta_s, r_val = best_opt
                anchor = (
                    best_mcap_shift if (best_mcap_shift is not None and shift is None) else (shift or best_mcap_shift)
                )
                if anchor is not None:
                    shift = anchor + delta_s
                    method = "mcap_rtc_shift" if method == "unaligned" else method
                    signal_optimized = True
                    depth_r = r_val
            elif best_opt:
                depth_r = best_opt[1]

        # Enforce causality: boot start must not be later than the earliest MCAP recording in this boot
        if shift is not None and g_mcaps and g_bins:
            boot_up_start = min(b.uptime_start_s for b in g_bins)
            earliest_mcap = min(g_mcaps, key=lambda m: m.first_log_time_s)
            if earliest_mcap.uptime_start_s is not None:
                earliest_est = earliest_mcap.system_time_shift_s or earliest_mcap.sample_rtc_shift_s
                if (boot_up_start + shift) > (earliest_mcap.first_log_time_s + 0.5) and earliest_est:
                    shift = earliest_est

        # Calculate Boot start_iso, end_iso, duration
        boot_start_s = None
        boot_end_s = None

        if g_bins:
            boot_up_start = min(b.uptime_start_s for b in g_bins)
            boot_up_end = max(b.uptime_end_s for b in g_bins)
            duration_s = max(0.0, boot_up_end - boot_up_start)
            if shift is not None:
                boot_start_s = boot_up_start + shift
                boot_end_s = boot_up_end + shift
        elif g_mcaps:
            boot_start_s = min(m.first_log_time_s for m in g_mcaps)
            boot_end_s = max(m.last_log_time_s for m in g_mcaps)
            duration_s = max(0.0, boot_end_s - boot_start_s)
        else:
            duration_s = 0.0

        b_obj = Boot(
            boot_id=boot_idx,
            rtc_shift_s=shift,
            start_iso=format_iso(boot_start_s),
            end_iso=format_iso(boot_end_s),
            duration_s=duration_s,
            alignment_method=method,
            signal_optimized=signal_optimized,
            depth_correlation_r=depth_r,
            bin_files=[b.path.name for b in g_bins],
            mcap_files=[m.path.name for m in g_mcaps],
        )
        boots_out.append(b_obj)

        # Build BinFile records
        for b in g_bins:
            b_start_iso = format_iso(b.uptime_start_s + shift) if shift is not None else None
            b_end_iso = format_iso(b.uptime_end_s + shift) if shift is not None else None

            overlapping_mcaps = [
                m.path.name
                for m in g_mcaps
                if m.uptime_start_s is not None
                and m.uptime_end_s is not None
                and max(b.uptime_start_s, m.uptime_start_s) <= min(b.uptime_end_s, m.uptime_end_s)
            ]

            bin_files_out.append(
                BinFile(
                    name=b.path.name,
                    boot_id=boot_idx,
                    uptime_start_s=b.uptime_start_s,
                    uptime_end_s=b.uptime_end_s,
                    duration_s=b.duration_s,
                    start_iso=b_start_iso,
                    end_iso=b_end_iso,
                    log_disarmed=b.log_disarmed,
                    ardusub_version=b.ardusub_version,
                    has_rtc_message=b.has_rtc_message,
                    has_gps_fix=b.has_gps_fix,
                    mcap_files=overlapping_mcaps,
                )
            )

        # Build McapFile records
        for m in g_mcaps:
            dur_mcap = max(0.0, m.last_log_time_s - m.first_log_time_s)
            overlapping_bins = [
                b.path.name
                for b in g_bins
                if m.uptime_start_s is not None
                and m.uptime_end_s is not None
                and max(b.uptime_start_s, m.uptime_start_s) <= min(b.uptime_end_s, m.uptime_end_s)
            ]

            mcap_files_out.append(
                McapFile(
                    name=m.path.name,
                    boot_id=boot_idx,
                    start_iso=format_iso(m.first_log_time_s),
                    end_iso=format_iso(m.last_log_time_s),
                    duration_s=dur_mcap,
                    uptime_start_s=m.uptime_start_s,
                    uptime_end_s=m.uptime_end_s,
                    sample_rtc_shift_s=m.sample_rtc_shift_s,
                    flight_modes=m.flight_modes,
                    bin_files=overlapping_bins,
                )
            )

    # 4. Bidirectional interpolation of unaligned boots until convergence
    changed = True
    while changed:
        changed = False
        for i, b in enumerate(boots_out):
            if b.rtc_shift_s is not None:
                continue

            prev_boot = boots_out[i - 1] if i > 0 else None
            next_boot = boots_out[i + 1] if i + 1 < len(boots_out) else None

            est_shift = None
            # Backward propagation from next boot:
            if next_boot and next_boot.rtc_shift_s is not None and next_boot.start_iso:
                next_start = parse_iso(next_boot.start_iso)
                if next_start is not None:
                    end_est = next_start - 30.0
                    g_bins = [bf for bf in bin_files_out if bf.boot_id == b.boot_id]
                    up_end = max((bf.uptime_end_s for bf in g_bins), default=b.duration_s or 0.0)
                    est_shift = end_est - up_end
            # Forward propagation from prev boot:
            elif prev_boot and prev_boot.rtc_shift_s is not None and prev_boot.end_iso:
                prev_end = parse_iso(prev_boot.end_iso)
                if prev_end is not None:
                    g_bins = [bf for bf in bin_files_out if bf.boot_id == b.boot_id]
                    up_start = min((bf.uptime_start_s for bf in g_bins), default=0.0)
                    est_shift = prev_end + 30.0 - up_start

            if est_shift is not None:
                b.rtc_shift_s = est_shift
                b.alignment_method = "interpolated"
                g_bins = [bf for bf in bin_files_out if bf.boot_id == b.boot_id]
                if g_bins:
                    boot_up_start = min(bf.uptime_start_s for bf in g_bins)
                    boot_up_end = max(bf.uptime_end_s for bf in g_bins)
                    b.start_iso = format_iso(boot_up_start + est_shift)
                    b.end_iso = format_iso(boot_up_end + est_shift)
                    b.duration_s = max(0.0, boot_up_end - boot_up_start)
                elif b.duration_s is not None:
                    b.start_iso = format_iso(est_shift)
                    b.end_iso = format_iso(est_shift + b.duration_s)

                for bf in bin_files_out:
                    if bf.boot_id == b.boot_id:
                        bf.start_iso = format_iso(bf.uptime_start_s + est_shift)
                        bf.end_iso = format_iso(bf.uptime_end_s + est_shift)

                changed = True

    return DiveLogs(
        directory=directory,
        boots=boots_out,
        bin_files=bin_files_out,
        mcap_files=mcap_files_out,
    )


# ---------------------------------------------------------------------------
#  CLI Presentation
# ---------------------------------------------------------------------------


def print_summary(dive_logs: DiveLogs):
    """Print human-readable summary of alignment to stdout."""
    print("=" * 78)
    print(f"Dive Logs Alignment Report: {dive_logs.directory.name}")
    print("=" * 78)
    print(f"Directory:    {dive_logs.directory}")
    print(f"Total Boots:  {len(dive_logs.boots)}")
    print(f"BIN Logs:     {len(dive_logs.bin_files)}")
    print(f"MCAP Logs:    {len(dive_logs.mcap_files)}")
    print("-" * 78)

    print("\n[BOOT CYCLES]")
    for b in dive_logs.boots:
        shift_str = f"{b.rtc_shift_s:.3f} s" if b.rtc_shift_s is not None else "UNALIGNED"
        opt_str = " (signal optimized)" if b.signal_optimized else ""
        r_str = f" [depth r={b.depth_correlation_r:.4f}]" if b.depth_correlation_r is not None else ""
        print(f"  Boot #{b.boot_id}:")
        print(f"    Method:       {b.alignment_method}{opt_str}{r_str}")
        print(f"    rtc_shift_s:  {shift_str}")
        print(f"    Window (UTC): {b.start_iso or 'Unknown'} -> {b.end_iso or 'Unknown'}")
        print(f"    Duration:     {b.duration_s:.1f} s" if b.duration_s is not None else "    Duration:     Unknown")
        print(f"    BIN Files:    {', '.join(b.bin_files) if b.bin_files else '(none)'}")
        print(f"    MCAP Files:   {', '.join(b.mcap_files) if b.mcap_files else '(none)'}")

    print("\n[BIN FILES]")
    for bf in dive_logs.bin_files:
        ver = f" ({bf.ardusub_version})" if bf.ardusub_version else ""
        rtc_tag = " [RTC]" if bf.has_rtc_message else ""
        gps_tag = " [GPS]" if bf.has_gps_fix else ""
        print(f"  {bf.name}{ver}{rtc_tag}{gps_tag}:")
        print(f"    Boot ID:      #{bf.boot_id}")
        print(f"    Uptime Span:  {bf.uptime_start_s:.1f} s -> {bf.uptime_end_s:.1f} s ({bf.duration_s:.1f} s)")
        print(f"    UTC Window:   {bf.start_iso or 'Unanchored'} -> {bf.end_iso or 'Unanchored'}")
        print(f"    MCAP Matches: {', '.join(bf.mcap_files) if bf.mcap_files else '(none)'}")

    print("\n[MCAP RECORDINGS]")
    for mf in dive_logs.mcap_files:
        modes = f" [{', '.join(mf.flight_modes)}]" if mf.flight_modes else ""
        print(f"  {mf.name}{modes}:")
        print(f"    Boot ID:      #{mf.boot_id}")
        print(f"    UTC Window:   {mf.start_iso} -> {mf.end_iso} ({mf.duration_s:.1f} s)")
        up_span = (
            f"{mf.uptime_start_s:.1f} s -> {mf.uptime_end_s:.1f} s" if mf.uptime_start_s is not None else "Unknown"
        )
        print(f"    Uptime Span:  {up_span}")
        print(f"    BIN Matches:  {', '.join(mf.bin_files) if mf.bin_files else '(none)'}")

    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(
        description="Align ArduSub Dataflash (.BIN) and BlueOS (.mcap) logs for a dive directory."
    )
    parser.add_argument("directory", nargs="?", default=".", help="Target dive directory (default: current directory)")
    parser.add_argument(
        "-o",
        "--output",
        help="Custom output file destination (default: <directory>/dive_logs.json)",
    )
    parser.add_argument(
        "--no-opt",
        action="store_true",
        help="Disable depth-signal cross-correlation optimization",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print verbose scanning and matching logs",
    )

    args = parser.parse_args()

    dive_logs = DiveLogs.build(args.directory, optimize=not args.no_opt, verbose=args.verbose)
    out_path = dive_logs.save(args.output)
    print_summary(dive_logs)
    print(f"Saved alignment metadata to: {out_path}\n")


if __name__ == "__main__":
    main()
