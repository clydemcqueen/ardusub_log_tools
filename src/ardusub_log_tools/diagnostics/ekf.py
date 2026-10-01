#!/usr/bin/env python3

"""
Report on EKF3 status (XKF4.SS and XKFS.SS fields).
"""

import datetime

import pymavlink.dialects.v20.ardupilotmega as apm
from pymavlink import mavutil

SOURCE_SETS = [
    "primary (0)",
    "secondary (1)",
    "tertiary (2)",
]


def format_ekf_status(flags: int) -> str:
    if flags == 0:
        return "EKF uninitialized"

    s = f"EKF status: {flags:6}"
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
    return s


class FilterStatusReport:
    def __init__(self, infile: str):
        self.infile = infile

    def read_and_report(self):
        print(f"Results for {self.infile}")
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=False, dialect="ardupilotmega")

        print("Time                | Elapsed : Message")

        first_ts = None
        prev_status = None
        prev_ss = None

        while (msg := mlog.recv_match(blocking=False, type=["XKF4", "XKFS"])) is not None:
            ts = getattr(msg, "_timestamp", msg.TimeUS * 1e-6)
            if first_ts is None:
                first_ts = ts

            prefix = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") + f" | {ts - first_ts:7.2f} : "

            msg_type = msg.get_type()
            if msg_type == "XKF4":
                if msg.SS != prev_status:
                    print(f"{prefix}{format_ekf_status(msg.SS)}")
                    prev_status = msg.SS
            elif msg_type == "XKFS":
                if msg.SS != prev_ss:
                    ss_str = SOURCE_SETS[msg.SS] if 0 <= msg.SS < len(SOURCE_SETS) else f"unknown ({msg.SS})"
                    print(f"{prefix}Source set: {ss_str}")
                    prev_ss = msg.SS
