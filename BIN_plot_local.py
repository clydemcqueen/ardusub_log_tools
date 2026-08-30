#!/usr/bin/env python3

"""
Look for XKF1 and VISO messages in BIN files, plot x and y, and write PDF files.

Supports segments.
"""

import argparse

import matplotlib

import util
from geometry import Pose
from segment_reader import add_segment_args, choose_reader_list

# Set backend before importing matplotlib.pyplot
matplotlib.use("pdf")
import matplotlib.pyplot as plt

MSG_TYPES = ["XKF1", "VISO", "AHR2", "ATT"]


def plot_bin_local(reader, outfile: str, dvl: bool = False):
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
        # Create a figure and 1 subplot
        figure, (plot) = plt.subplots(1)
        plot.set_aspect(1)

        if len(xkf_xs) > 0:
            plot.plot(xkf_xs, xkf_ys, label="Local Position")

        if len(dvl_xs) > 0:
            plot.plot(dvl_xs, dvl_ys, label="DVL Position")

        plot.legend()

        # [Over]write PDF
        plt.savefig(outfile)
        dvl_msg = f" and {len(dvl_xs)} DVL points" if len(dvl_xs) > 0 else ""
        print(f"{outfile} written with {len(xkf_xs)} points{dvl_msg}")

        # Close the figure to reclaim the memory
        plt.close(figure)
    else:
        print("Nothing to plot")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser, ".BIN")
    parser.add_argument("--dvl", action="store_true", help="Plot DVL trajectory using VISO messages")
    args = parser.parse_args()

    readers = choose_reader_list(args, MSG_TYPES, ".BIN")
    for reader in readers:
        plot_bin_local(reader, util.get_outfile_name(reader.name, "", ".pdf"), args.dvl)


if __name__ == "__main__":
    main()
