#!/usr/bin/env python3

"""
Look for LOCATION_POSITION_NED messages in tlog files, plot x and y, and write PDF files.
"""

import argparse

import matplotlib

import util
from segment_reader import add_segment_args, choose_reader_list

# Set backend before importing matplotlib.pyplot
matplotlib.use('pdf')
import matplotlib.pyplot as plt

MSG_TYPES = ['LOCAL_POSITION_NED']


def plot_local_position(reader, outfile: str):
    """
    Read tlog file, get x and y values.
    """
    xs = []
    ys = []
    try:
        for msg in reader:
            xs.append(msg.y)
            ys.append(msg.x)

    except Exception as e:
        print(f'CRASH WITH ERROR "{e}", PARTIAL RESULTS')

    if len(xs) > 0:
        # Create a figure and 1 subplot
        figure, (plot) = plt.subplots(1)

        # Plot
        plot.set_aspect(1)
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
    add_segment_args(parser)
    args = parser.parse_args()

    readers = choose_reader_list(args, MSG_TYPES)
    for reader in readers:
        plot_local_position(reader, util.get_outfile_name(reader.name, '', '.pdf'))


if __name__ == '__main__':
    main()
