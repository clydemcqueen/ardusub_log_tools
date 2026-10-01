#!/usr/bin/env python3

"""
Look for local position and DVL messages across tlog, BIN, and MCAP files, plot x and y, and write PDF files.
"""

import matplotlib

from ardusub_log_tools.core import util
from ardusub_log_tools.core.geometry import Pose

# Set backend before importing matplotlib.pyplot
matplotlib.use("pdf")
import matplotlib.pyplot as plt

TLOG_MSG_TYPES = ["LOCAL_POSITION_NED", "VISION_POSITION_DELTA", "GLOBAL_POSITION_INT"]
BIN_MSG_TYPES = ["XKF1", "VISO", "AHR2", "ATT"]
MCAP_MSG_TYPES = ["LOCAL_POSITION_NED", "VISION_POSITION_DELTA", "GLOBAL_POSITION_INT"]


def plot_local_position(reader, outfile: str | None = None, dvl: bool = False, show: bool = False):
    """
    Read tlog file, get x and y values from LOCAL_POSITION_NED and optionally VISION_POSITION_DELTA.
    """
    lpn_xs = []
    lpn_ys = []

    dvl_xs = []
    dvl_ys = []

    pose = None
    last_global_msg = None

    try:
        for msg in reader:
            if msg.get_type() == "LOCAL_POSITION_NED":
                lpn_xs.append(msg.y)
                lpn_ys.append(msg.x)
            elif dvl and msg.get_type() == "GLOBAL_POSITION_INT":
                last_global_msg = msg
            elif dvl and msg.get_type() == "VISION_POSITION_DELTA":
                if pose is None and last_global_msg is not None:
                    pose = Pose((0, 0, last_global_msg.hdg / 100.0), (0, 0, -last_global_msg.relative_alt / 1000.0))

                if pose is not None:
                    pose.add_angle_delta(msg.angle_delta)
                    pose.add_position_delta(msg.position_delta)
                    dvl_xs.append(pose.position[1])
                    dvl_ys.append(pose.position[0])

    except Exception as e:
        print(f'CRASH WITH ERROR "{e}", PARTIAL RESULTS')

    if len(lpn_xs) > 0 or len(dvl_xs) > 0:
        figure, (plot) = plt.subplots(1)
        plot.set_aspect(1)

        if len(lpn_xs) > 0:
            plot.plot(lpn_xs, lpn_ys, label="Local Position")

        if len(dvl_xs) > 0:
            plot.plot(dvl_xs, dvl_ys, label="DVL Position")

        plot.legend()

        if show:
            plt.show()
        if outfile:
            plt.savefig(outfile)
            dvl_msg = f" and {len(dvl_xs)} DVL points" if len(dvl_xs) > 0 else ""
            print(f"{outfile} written with {len(lpn_xs)} points{dvl_msg}")

        plt.close(figure)
    else:
        print("Nothing to plot")


def plot_bin_local(reader, outfile: str | None = None, dvl: bool = False, show: bool = False):
    """
    Read BIN file, get x and y values from XKF1 and optionally VISO.
    """
    xkf_xs = []
    xkf_ys = []

    dvl_xs = []
    dvl_ys = []

    pose = None
    last_yaw = None
    last_roll = 0.0
    last_pitch = 0.0

    try:
        for msg in reader:
            mtype = msg.get_type()

            if mtype == "XKF1":
                if getattr(msg, "C", getattr(msg, "Core", 0)) == 0:
                    pn = getattr(msg, "PN", getattr(msg, "PosN", 0.0))
                    pe = getattr(msg, "PE", getattr(msg, "PosE", 0.0))
                    xkf_xs.append(pe)
                    xkf_ys.append(pn)
                    last_yaw = getattr(msg, "Yaw", last_yaw)
                    last_roll = getattr(msg, "Roll", last_roll)
                    last_pitch = getattr(msg, "Pitch", last_pitch)

            elif mtype in ("AHR2", "ATT"):
                last_yaw = getattr(msg, "Yaw", last_yaw)
                last_roll = getattr(msg, "Roll", last_roll)
                last_pitch = getattr(msg, "Pitch", last_pitch)

            elif dvl and mtype == "VISO":
                if pose is None:
                    init_yaw = last_yaw if last_yaw is not None else 0.0
                    pose = Pose((last_roll, last_pitch, init_yaw), (0.0, 0.0, 0.0))

                ang_dx = getattr(msg, "AngDX", getattr(msg, "dX", 0.0))
                ang_dy = getattr(msg, "AngDY", getattr(msg, "dY", 0.0))
                ang_dz = getattr(msg, "AngDZ", getattr(msg, "dZ", 0.0))
                pos_dx = getattr(msg, "PosDX", 0.0)
                pos_dy = getattr(msg, "PosDY", 0.0)
                pos_dz = getattr(msg, "PosDZ", 0.0)

                pose.add_angle_delta((ang_dx, ang_dy, ang_dz))
                pose.add_position_delta((pos_dx, pos_dy, pos_dz))
                dvl_xs.append(pose.position[1])
                dvl_ys.append(pose.position[0])

    except Exception as e:
        print(f'CRASH WITH ERROR "{e}", PARTIAL RESULTS')

    if len(xkf_xs) > 0 or len(dvl_xs) > 0:
        figure, (plot) = plt.subplots(1)
        plot.set_aspect(1)

        if len(xkf_xs) > 0:
            plot.plot(xkf_xs, xkf_ys, label="Local Position")

        if len(dvl_xs) > 0:
            plot.plot(dvl_xs, dvl_ys, label="DVL Position")

        plot.legend()

        if show:
            plt.show()
        if outfile:
            plt.savefig(outfile)
            dvl_msg = f" and {len(dvl_xs)} DVL points" if len(dvl_xs) > 0 else ""
            print(f"{outfile} written with {len(xkf_xs)} points{dvl_msg}")

        plt.close(figure)
    else:
        print("Nothing to plot")


def plot_mcap_local(mcap_file: str, outfile: str | None = None, dvl: bool = False, show: bool = False):
    """
    Read MCAP file, extract x and y values, and generate a 2D PDF plot.
    """
    lpn_xs = []
    lpn_ys = []

    dvl_xs = []
    dvl_ys = []

    pose = None
    last_global_msg = None

    target_types = ["LOCAL_POSITION_NED"]
    if dvl:
        target_types.extend(["GLOBAL_POSITION_INT", "VISION_POSITION_DELTA"])

    try:
        for schema, channel, message in util.iter_mcap_messages(
            mcap_file, message_types=target_types, sys_id=None, comp_id=None
        ):
            data = message.json
            msg_data = data.get("message", {})
            msg_type = msg_data.get("type")

            if msg_type == "LOCAL_POSITION_NED":
                lpn_xs.append(msg_data["y"])
                lpn_ys.append(msg_data["x"])
            elif dvl and msg_type == "GLOBAL_POSITION_INT":
                last_global_msg = msg_data
            elif dvl and msg_type == "VISION_POSITION_DELTA":
                if pose is None and last_global_msg is not None:
                    pose = Pose(
                        (0, 0, last_global_msg.get("hdg", 0) / 100.0),
                        (0, 0, -last_global_msg.get("relative_alt", 0) / 1000.0),
                    )
                elif pose is None:
                    pose = Pose((0, 0, 0), (0, 0, 0))

                if pose is not None:
                    pose.add_angle_delta(msg_data.get("angle_delta", [0.0, 0.0, 0.0]))
                    pose.add_position_delta(msg_data.get("position_delta", [0.0, 0.0, 0.0]))
                    dvl_xs.append(pose.position[1])
                    dvl_ys.append(pose.position[0])

    except Exception as e:
        print(f'CRASH WITH ERROR "{e}", PARTIAL RESULTS')

    if len(lpn_xs) > 0 or len(dvl_xs) > 0:
        figure, (plot) = plt.subplots(1)
        plot.set_aspect(1)

        if len(lpn_xs) > 0:
            plot.plot(lpn_xs, lpn_ys, label="Local Position")

        if len(dvl_xs) > 0:
            plot.plot(dvl_xs, dvl_ys, label="DVL Position")

        plot.legend()

        if show:
            plt.show()
        if outfile:
            plt.savefig(outfile)
            dvl_msg = f" and {len(dvl_xs)} DVL points" if len(dvl_xs) > 0 else ""
            print(f"{outfile} written with {len(lpn_xs)} points{dvl_msg}")

        plt.close(figure)
    else:
        print("Nothing to plot")
