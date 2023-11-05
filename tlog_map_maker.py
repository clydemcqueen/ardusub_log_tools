#!/usr/bin/env python3

"""
Read tlog files and build Leaflet (interactive HTML) maps from GPS coordinates.

By default, read these messages and draw them bottom-to-top:
    GPS_INPUT -- sensor data sent from ugps-extension to ArduSub, light grey line
    GPS_RAW_INT -- sensor data sent from ArduSub to QGC, slightly darker grey line
    GLOBAL_POSITION_INT -- the filtered position estimate, blue line

Supports segments.
"""

import argparse

import table_types
import util
from map_maker import MapMaker, add_map_maker_args
from segment_reader import add_segment_args, choose_reader_list

# The list order is also the z-order in the map
GPS_MSG_TYPES = ['GPS_INPUT', 'GPS_RAW_INT', 'GLOBAL_POSITION_INT']
GPS_MSG_COLORS = ['#999999', '#777777', '#0000AA']


def build_map_from_tlog(reader, outfile, verbose, center, zoom, hdop_max):
    tables: dict[str, table_types.Table] = {}

    for msg in reader:
        msg_type = msg.get_type()
        raw_data = msg.to_dict()
        timestamp = getattr(msg, '_timestamp', 0.0)

        # Clean up the data: add the timestamp, remove mavpackettype, and rename the keys
        clean_data = {'timestamp': timestamp}
        for key in raw_data.keys():
            if key != 'mavpackettype':
                clean_data[f'{msg_type}.{key}'] = raw_data[key]

        if msg_type not in tables:
            tables[msg_type] = table_types.Table.create_table(msg_type, verbose=verbose, hdop_max=hdop_max, filter=True)

        tables[msg_type].append(clean_data)

    mm = MapMaker(verbose, center, zoom)

    for msg_type, msg_color in zip(GPS_MSG_TYPES, GPS_MSG_COLORS):
        if msg_type in tables and len(tables[msg_type]):
            mm.add_table(tables[msg_type], f'{msg_type}.lat_deg', f'{msg_type}.lon_deg', msg_color)

    mm.write(outfile)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    add_map_maker_args(parser)
    parser.add_argument('--types', default=None,
                        help='comma separated list of message types')
    parser.add_argument('--hdop-max', default=100.0, type=float,
                        help='reject GPS_INPUT messages where hdop exceeds this limit, default 100.0 (no limit)')
    args = parser.parse_args()

    if args.types is None:
        # GPS_INPUT may result in a pymavlink crash, see https://github.com/ArduPilot/pymavlink/issues/807
        # Workaround: `export MAV_IGNORE_CRC=1`
        msg_types = GPS_MSG_TYPES
    else:
        msg_types = args.types.split(',')

    readers = choose_reader_list(args, msg_types)

    for reader in readers:
        outfile = util.get_outfile_name(reader.name, '', '.html')
        build_map_from_tlog(reader, outfile, args.verbose, [args.lat, args.lon], args.zoom, args.hdop_max)


if __name__ == '__main__':
    main()
