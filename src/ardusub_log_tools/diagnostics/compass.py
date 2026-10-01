#!/usr/bin/env python3

"""
Compass, magnetometer, and IMU sensor diagnostics for BIN files.
"""

from statistics import mean, stdev

from pymavlink import mavutil

from ardusub_log_tools.backends.dataflash import DataFlashParams
from ardusub_log_tools.core import util


def analyze_mag_stats(file: str):
    """Read dataflash logs and report on MAG stats."""
    mlog = mavutil.mavlink_connection(file, robust_parsing=False, dialect="ardupilotmega")

    mag_param_names = [
        "COMPASS_DEV_ID",
        "COMPASS_DEV_ID2",
        "COMPASS_DEV_ID3",
    ]

    params = DataFlashParams(mag_param_names)
    mag_readings = {}

    while (msg := mlog.recv_match(blocking=False, type=["MAG", "PARM"])) is not None:
        msg_type = msg.get_type()
        if msg_type == "MAG":
            if msg.I not in mag_readings:
                mag_readings[msg.I] = {"X": [], "Y": [], "Z": []}
            mag_readings[msg.I]["X"].append(msg.MagX)
            mag_readings[msg.I]["Y"].append(msg.MagY)
            mag_readings[msg.I]["Z"].append(msg.MagZ)
        elif msg_type == "PARM":
            params.add(msg)

    dev_ids = [
        int(params.get_value("COMPASS_DEV_ID") or 0),
        int(params.get_value("COMPASS_DEV_ID2") or 0),
        int(params.get_value("COMPASS_DEV_ID3") or 0),
    ]

    print(file)

    for instance in mag_readings.keys():
        for dim in ["X", "Y", "Z"]:
            data = mag_readings[instance][dim]
            if not data:
                continue
            xbar = mean(data)
            min_val = min(data)
            max_val = max(data)
            dev_id = dev_ids[instance] if instance < len(dev_ids) else "unknown"
            std_str = f"{stdev(data, xbar):8.2f}" if len(data) > 1 else "    0.00"
            print(
                f"MAG[{instance}].Mag{dim} ({dev_id}): mean {xbar:8.2f}, stdev {std_str}, min {min_val:8.2f}, max {max_val:8.2f}"
            )
            if min_val < -2000 or max_val > 2000:
                print(f"MAG[{instance}].Mag{dim} ({dev_id}) OUTLIER[S], min {min_val:8.2f}, max {max_val:8.2f}")


class Mag3DReport:
    """Note transitions to/from mag 3d fusion."""

    def __init__(self, filename: str):
        self.filename = filename

    def read(self):
        mlog = mavutil.mavlink_connection(self.filename)

        prev_msg = None
        sel = prev_sel = "no info"

        try:
            while True:
                msg = mlog.recv_match(type=["XKF3"], blocking=False)
                if msg is None:
                    break

                if prev_msg is None:
                    prev_msg = msg
                    continue

                if msg.IYAW != prev_msg.IYAW:
                    sel = "fuse yaw"
                elif msg.IMX != prev_msg.IMX or msg.IMY != prev_msg.IMY or msg.IMZ != prev_msg.IMZ:
                    sel = "fuse mag"

                prev_msg = msg

                if sel != prev_sel:
                    print(f"{util.time_us_str(msg.TimeUS)}, core {msg.C}, {prev_sel} to {sel}")
                    prev_sel = sel

        except Exception as e:
            print(f'CRASH WITH ERROR "{e}", SHOWING PARTIAL RESULTS')


def analyze_gyro_bias(file: str):
    """Read dataflash logs and report on XKF1 gyro bias values."""
    mlog = mavutil.mavlink_connection(file, robust_parsing=False, dialect="ardupilotmega")

    gx, gy, gz = [], [], []
    while (msg := mlog.recv_match(blocking=False, type=["XKF1"])) is not None:
        gx.append(msg.GX)
        gy.append(msg.GY)
        gz.append(msg.GZ)

    if gx and gy and gz:
        print(
            f"{file:40} range gx ({min(gx):6.2f}, {max(gx):6.2f}), gy ({min(gy):6.2f}, {max(gy):6.2f}), gz ({min(gz):6.2f}, {max(gz):6.2f})"
        )
    else:
        print(f"{file:40} no XKF1 gyro bias records found")
