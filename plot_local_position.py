#!/usr/bin/env python3

"""
Look for LOCATION_POSITION_NED messages in tlog files, plot x and y, and write PDF files.
"""

import argparse
import os

import matplotlib
from pymavlink import mavutil

import util

# Set backend before importing matplotlib.pyplot
matplotlib.use('pdf')
import matplotlib.pyplot as plt


def plot_local_position(infile: str, outfile: str):
    # Read tlog file, get x and y values
    xs = []
    ys = []
    mlog = mavutil.mavlink_connection(infile, robust_parsing=False, dialect='ardupilotmega')
    try:
        while True:
            msg = mlog.recv_match(blocking=False, type=['LOCAL_POSITION_NED'])
            if msg is None:
                break

            xs.append(msg.x)
            ys.append(msg.y)

    except Exception as e:
        print(f'CRASH WITH ERROR "{e}", PARTIAL RESULTS')

    if len(xs) > 0:
        # Create a figure and 1 subplot
        figure, (plot) = plt.subplots(1)

        # Plot
        plot.plot(xs, ys)

        # [Over]write PDF
        plt.savefig(outfile)
        print(f'{outfile} written with {len(xs)} points')

        # Close the figure to reclaim the memory
        plt.close(figure)
    else:
        print('No LOCAL_POSITION_NED messages found')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true',
                        help='enter directories looking for tlog files')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.tlog')
    print(f'Processing {len(files)} files')

    for infile in files:
        print('-------------------')
        print(infile)
        dirname, basename = os.path.split(infile)
        root, ext = os.path.splitext(basename)
        outfile = os.path.join(dirname, root + '.pdf')
        plot_local_position(infile, outfile)


if __name__ == '__main__':
    main()
