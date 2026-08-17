#!/usr/bin/env python3

"""
Report on EKF3 status (XKF4.SS and XKFS.SS fields).

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

import datetime
from argparse import ArgumentParser

import pymavlink.dialects.v20.ardupilotmega as apm
from pymavlink import mavutil

import util

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


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-r", "--recurse", help="enter directories looking for BIN files", action="store_true")
    parser.add_argument("path", nargs="+")
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, ".BIN")
    print(f"Processing {len(files)} files")

    for file in files:
        print("-------------------")
        reader = FilterStatusReport(file)
        reader.read_and_report()


if __name__ == "__main__":
    main()
