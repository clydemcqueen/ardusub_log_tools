#!/usr/bin/env python3

"""
Look for LOCAL_POSITION_NED and VISION_POSITION_DELTA messages in mcap files, plot x and y, and write PDF files.
"""

import argparse
import json

import matplotlib

import util
from geometry import Pose

# Set backend before importing matplotlib.pyplot
matplotlib.use("pdf")
import matplotlib.pyplot as plt
from mcap.reader import make_reader

MSG_TYPES = ["LOCAL_POSITION_NED", "VISION_POSITION_DELTA", "GLOBAL_POSITION_INT"]


def plot_mcap_local(mcap_file: str, outfile: str, dvl: bool = False):
    """
    Read MCAP file, extract x and y values, and generate a 2D PDF plot.
    """
    lpn_xs = []
    lpn_ys = []

    dvl_xs = []
    dvl_ys = []

    pose = None
    last_global_msg = None

    try:
        with open(mcap_file, "rb") as f:
            reader = make_reader(f)
            for schema, channel, message in reader.iter_messages(topics=["mavlink/out"]):
                data = json.loads(message.data)
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
        # Create a figure and 1 subplot
        figure, (plot) = plt.subplots(1)
        plot.set_aspect(1)

        if len(lpn_xs) > 0:
            plot.plot(lpn_xs, lpn_ys, label="Local Position")

        if len(dvl_xs) > 0:
            plot.plot(dvl_xs, dvl_ys, label="DVL Position")

        plot.legend()

        # [Over]write PDF
        plt.savefig(outfile)
        dvl_msg = f" and {len(dvl_xs)} DVL points" if len(dvl_xs) > 0 else ""
        print(f"{outfile} written with {len(lpn_xs)} points{dvl_msg}")

        # Close the figure to reclaim the memory
        plt.close(figure)
    else:
        print("Nothing to plot")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for mcap files")
    parser.add_argument("--dvl", action="store_true", help="Plot DVL trajectory using VISION_POSITION_DELTA messages")
    args = parser.parse_args()

    files = util.expand_path(args.paths, args.recurse, ".mcap")
    for file in files:
        outfile = util.get_outfile_name(file, "", ".pdf")
        plot_mcap_local(file, outfile, args.dvl)


if __name__ == "__main__":
    main()
