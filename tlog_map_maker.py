#!/usr/bin/env python3

"""
Read tlog files and build Leaflet (interactive HTML) maps from GPS coordinates.

By default, read these messages:
    GPS_RAW_INT -- sensor data sent from ArduSub to QGC, will appear as a blue line, should be close to the csv file
    GLOBAL_POSITION_INT -- the filtered position estimate, green line
    GPS_INPUT -- sensor data sent from ugps-extension to ArduSub, not filtered, red line

Supports segments.
"""

import argparse

import table_types
import util
from map_maker import MapMaker, add_map_maker_args
from segment_reader import add_segment_args, choose_reader_list


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
            tables[msg_type] = table_types.Table.create_table(msg_type, verbose=verbose, hdop_max=hdop_max)

        tables[msg_type].append(clean_data)

    mm = MapMaker(verbose, center, zoom)

    # Build the map in a specific order
    if 'GPS_RAW_INT' in tables and len(tables['GPS_RAW_INT']):
        mm.add_table(tables['GPS_RAW_INT'], 'GPS_RAW_INT.lat_deg', 'GPS_RAW_INT.lon_deg', 'blue')
    if 'GLOBAL_POSITION_INT' in tables and len(tables['GLOBAL_POSITION_INT']):
        mm.add_table(tables['GLOBAL_POSITION_INT'], 'GLOBAL_POSITION_INT.lat_deg', 'GLOBAL_POSITION_INT.lon_deg', 'green')
    if 'GPS_INPUT' in tables and len(tables['GPS_INPUT']):
        mm.add_table(tables['GPS_INPUT'], 'GPS_INPUT.lat_deg', 'GPS_INPUT.lon_deg', 'red')

    mm.write(outfile)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    add_map_maker_args(parser)
    parser.add_argument('--types', default=None, help='comma separated list of message types')
    args = parser.parse_args()

    if args.types is None:
        # GPS_INPUT may result in a pymavlink crash, see https://github.com/ArduPilot/pymavlink/issues/807
        # Workaround: `export MAV_IGNORE_CRC=1`
        msg_types = ['GLOBAL_POSITION_INT', 'GPS_RAW_INT', 'GPS_INPUT']
    else:
        msg_types = args.types.split(',')

    readers = choose_reader_list(args, msg_types)

    for reader in readers:
        outfile = util.get_outfile_name(reader.name, '', '.html')
        build_map_from_tlog(reader, outfile, args.verbose, [args.lat, args.lon], args.zoom, args.hdop_max)


if __name__ == '__main__':
    main()
