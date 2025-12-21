#!/usr/bin/env python3

"""
Read BIN files and build Leaflet (interactive HTML) maps from GPS coordinates.

By default, read these messages and draw them bottom-to-top:
    GPS -- sensor data received by ArduSub, light grey line
    POS -- the filtered position estimate, blue line

Supports segments.

See dataflash/GPS.md and dataflash/POS.md for message details.
"""

import argparse
import pandas as pd

import util
from map_maker import MapMaker, add_map_maker_args
from segment_reader import add_segment_args, choose_reader_list

# The list order is also the z-order in the map
GPS_MSG_TYPES = ['GPS', 'POS']
GPS_MSG_COLORS = ['#999999', '#0000AA']


def build_map_from_BIN(reader, outfile, verbose, center, zoom, hdop_max):
    tables: dict[str, list[dict]] = {}

    for msg in reader:
        msg_type = msg.get_type()
        data = msg.to_dict()

        if msg_type == 'GPS':
            if data['HDop'] > hdop_max:
                continue
            if data['Lat'] == 0 or data['Lng'] == 0:
                continue
        elif msg_type == 'POS':
            if data['Lat'] == 0 or data['Lng'] == 0:
                continue
        else:
            continue

        if msg_type not in tables:
            tables[msg_type] = []

        tables[msg_type].append(data)

    mm = MapMaker(verbose, center, zoom)

    for msg_type, msg_color in zip(GPS_MSG_TYPES, GPS_MSG_COLORS):
        if msg_type in tables and len(tables[msg_type]):
            # Build a dataframe with just the Lat and Lng columns
            df = pd.DataFrame(tables[msg_type])
            df = df[['Lat', 'Lng']]
            mm.add_df(df, 'Lat', 'Lng', msg_color)

    mm.write(outfile)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    add_map_maker_args(parser)
    parser.add_argument('--types', default=None,
                        help='comma separated list of message types')
    parser.add_argument('--hdop-max', default=100.0, type=float,
                        help='reject GPS messages where hdop exceeds this limit, default 100.0 (no limit)')
    args = parser.parse_args()

    if args.types is None:
        msg_types = GPS_MSG_TYPES
    else:
        msg_types = args.types.split(',')

    readers = choose_reader_list(args, msg_types, '.BIN')

    for reader in readers:
        outfile = util.get_outfile_name(reader.name, '', '.html')
        build_map_from_BIN(reader, outfile, args.verbose, [args.lat, args.lon], args.zoom, args.hdop_max)


if __name__ == '__main__':
    main()
