#!/usr/bin/env python3

"""
Time synchronization, RTC, and timestamp stability diagnostics for tlog and BIN files.
"""

import os
import time

import numpy as np
from pymavlink import mavutil


def check_offset_stability(tlog_path: str):
    """Check stability of time_boot_ms offset against Unix timestamp in a tlog."""
    print(f"Analyzing {tlog_path}")
    mlog = mavutil.mavlink_connection(tlog_path, robust_parsing=False)

    offsets = []
    first_offset = None

    while True:
        msg = mlog.recv_match(blocking=False)
        if msg is None:
            break

        if hasattr(msg, "time_boot_ms"):
            offset = getattr(msg, "_timestamp", 0) - msg.time_boot_ms / 1e3
            offsets.append(offset)

            if first_offset is None:
                first_offset = offset

    if not offsets:
        print("No messages with time_boot_ms found.")
        return

    offsets = np.array(offsets)

    print(f"Count: {len(offsets)}")
    print(f"First offset: {first_offset:.6f}")
    print(f"Min offset:   {offsets.min():.6f}")
    print(f"Max offset:   {offsets.max():.6f}")
    print(f"Mean offset:  {offsets.mean():.6f}")
    print(f"Std dev:      {offsets.std():.6f}")
    print(f"Range:        {offsets.max() - offsets.min():.6f}")

    diff = first_offset - offsets.min()
    print(f"First - Min:  {diff:.6f}")


def check_bin_gps_time(filename: str, verbose: bool = False) -> bool:
    """Check if a BIN file has GPS time."""
    try:
        mlog = mavutil.mavlink_connection(filename)
    except Exception:
        return False

    if hasattr(mlog, "clock") and hasattr(mlog.clock, "timebase"):
        if mlog.clock.timebase > 1:
            return True

    return False


def check_tlog_gps_or_unix_time(filename: str, verbose: bool = False) -> tuple[bool, bool, bool]:
    """Check if a tlog file has GPS time, or Unix time in general."""
    try:
        mlog = mavutil.mavlink_connection(filename)
    except Exception:
        return False, False, False

    gps_time = 0
    unix_time_1_1 = 0
    unix_time_x_x = 0

    while True:
        m = mlog.recv_match(type=["GPS_INPUT", "SYSTEM_TIME"], blocking=False)
        if m is None:
            break

        sysid = m.get_srcSystem()
        compid = m.get_srcComponent()
        msg_type = m.get_type()

        if msg_type == "GPS_INPUT":
            if m.time_week > 0:
                gps_time += 1
        elif msg_type == "SYSTEM_TIME":
            if m.time_unix_usec > 0:
                if sysid == 1 and compid == 1:
                    unix_time_1_1 += 1
                else:
                    unix_time_x_x += 1

    if verbose:
        if gps_time > 0:
            print(f"GPS time in {gps_time} messages")
        if unix_time_1_1 > 0:
            print(f"Unix time from ArduSub (1,1) in {unix_time_1_1} messages")
        if unix_time_x_x > 0:
            print(f"Unix time from somewhere (x,x) in {unix_time_x_x} messages")

    return gps_time > 0, unix_time_1_1 > 0, unix_time_x_x > 0


def process_rtc_file(filename: str, verbose: bool = False):
    """Check and display time source type for a log file (.BIN or .tlog)."""
    _, ext = os.path.splitext(filename)

    gps_time = False
    unix_time_1_1 = False
    unix_time_x_x = False

    if ext == ".BIN":
        gps_time = check_bin_gps_time(filename, verbose)
    elif ext == ".tlog":
        gps_time, unix_time_1_1, unix_time_x_x = check_tlog_gps_or_unix_time(filename, verbose)

    if gps_time:
        prefix = "GPS"
    elif unix_time_1_1:
        prefix = "UNIX (ArduSub)"
    elif unix_time_x_x:
        prefix = "UNIX (other)"
    else:
        prefix = ""

    print(f"{prefix:14s} {filename}")


def check_timestamps(reader):
    """Scan reader for future or backwards timestamps."""
    count = 0
    prev_timestamp = None
    tomorrow = time.time() + 24 * 60 * 60

    for msg in reader:
        sysid = msg.get_srcSystem()
        compid = msg.get_srcComponent()
        msg_type = msg.get_type()
        timestamp = getattr(msg, "_timestamp", 0.0)

        if timestamp > tomorrow:
            print(
                f"  Time {timestamp} is in the future; message num={count}, type={msg_type}, sysid={sysid}, compid={compid}"
            )

        if prev_timestamp is not None and timestamp < prev_timestamp:
            print(
                f"  Time went backwards from {prev_timestamp} to {timestamp}; message num={count}, sysid={sysid}, compid={compid}"
            )

        count += 1
        prev_timestamp = timestamp
