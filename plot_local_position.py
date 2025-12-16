#!/usr/bin/env python3

"""
Look for LOCATION_POSITION_NED and VISION_POSITION_DELTA messages in tlog files, plot x and y, and write PDF files.

Supports segments.
"""

import argparse

import matplotlib

import util
from geometry import Pose
from segment_reader import add_segment_args, choose_reader_list

# Set backend before importing matplotlib.pyplot
matplotlib.use('pdf')
import matplotlib.pyplot as plt

MSG_TYPES = ['LOCAL_POSITION_NED', 'VISION_POSITION_DELTA', 'GLOBAL_POSITION_INT']


def plot_local_position(reader, outfile: str, dvl: bool = False):
    """
    Read tlog file, get x and y values.
    """
    lpn_xs = []
    lpn_ys = []

    dvl_xs = []
    dvl_ys = []

    pose = None
    last_global_msg = None

    try:
        for msg in reader:
            if msg.get_type() == 'LOCAL_POSITION_NED':
                lpn_xs.append(msg.y)
                lpn_ys.append(msg.x)
            elif dvl and msg.get_type() == 'GLOBAL_POSITION_INT':
                last_global_msg = msg
            elif dvl and msg.get_type() == 'VISION_POSITION_DELTA':
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
        # Create a figure and 1 subplot
        figure, (plot) = plt.subplots(1)
        plot.set_aspect(1)

        if len(lpn_xs) > 0:
            plot.plot(lpn_xs, lpn_ys, label='Local Position')

        if len(dvl_xs) > 0:
            plot.plot(dvl_xs, dvl_ys, label='DVL Position')

        plot.legend()

        # [Over]write PDF
        plt.savefig(outfile)
        dvl_msg = f' and {len(dvl_xs)} DVL points' if len(dvl_xs) > 0 else ''
        print(f'{outfile} written with {len(lpn_xs)} points{dvl_msg}')

        # Close the figure to reclaim the memory
        plt.close(figure)
    else:
        print('Nothing to plot')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    parser.add_argument('--dvl', action='store_true', help='Plot DVL trajectory using VISION_POSITION_DELTA messages')
    args = parser.parse_args()

    readers = choose_reader_list(args, MSG_TYPES)
    for reader in readers:
        plot_local_position(reader, util.get_outfile_name(reader.name, '', '.pdf'), args.dvl)


if __name__ == '__main__':
    main()
