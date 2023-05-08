#!/usr/bin/env python3

"""
Read csv or tlog files and build Leaflet (interactive HTML) maps from GPS coordinates.

For csv files:
    Latitude column header should be 'gps.lat' or 'lat'
    Longitude column header should be 'gps.lon' or 'lon'

For tlog files, these messages are read:
    GPS_RAW_INT -- sensor data sent from ArduSub to QGC, will appear as a blue line, should be close to the csv file
    GLOBAL_POSITION_INT -- the filtered position estimate, green line
    GPS_INPUT -- sensor data sent from ugps-extension to ArduSub, not filtered, red line

"""

import argparse
from argparse import ArgumentParser
import folium
from pymavlink import mavutil
import pandas as pd
import os
import table_types
import util

# Use MAVLink2
os.environ['MAVLINK20'] = '1'


class MapMaker:
    @staticmethod
    def build_map_from_df(df, lat_col, lon_col, outfile, verbose, center, zoom):
        mm = MapMaker(verbose, center, zoom)
        mm.add_df(df, lat_col, lon_col, 'blue')
        mm.write(outfile)

    def __init__(self, verbose, center, zoom):
        self.m = None
        self.verbose = verbose
        self.center = center
        self.zoom = zoom

    def add_df(self, df, lat_col, lon_col, color):
        if self.m is None:
            if self.center[0] is None:
                self.center[0] = df[lat_col].mean()
            if self.center[1] is None:
                self.center[1] = df[lon_col].mean()
            self.m = folium.Map(location=self.center, zoom_start=self.zoom, max_zoom=24)

        if self.verbose:
            print(df.head())
            print(len(df))
        folium.PolyLine(df[[lat_col, lon_col]].values, color=color, weight=1).add_to(self.m)

    def write(self, outfile):
        if self.m:
            print(f'Writing {outfile}')
            self.m.save(outfile)
        else:
            print(f'Nothing to write')


def build_map_from_csv(infile, outfile, verbose, center, zoom):
    # Read csv file, don't crash
    try:
        df = pd.read_csv(infile)
    except Exception as e:
        print(f'exception parsing csv file: {e}')
        return

    if 'gps.lat' in df.columns and 'gps.lat' in df.columns:
        if verbose:
            print('QGC csv file')
        df = pd.read_csv(infile, usecols=['gps.lat', 'gps.lon'])
        MapMaker.build_map_from_df(df, 'gps.lat', 'gps.lon', outfile, verbose, center, zoom)
    elif 'lat' in df.columns and 'lon' in df.columns:
        if verbose:
            print('cleaned csv file')
        df = pd.read_csv(infile, usecols=['lat', 'lon'])
        MapMaker.build_map_from_df(df, 'lat', 'lon', outfile, verbose, center, zoom)
    else:
        print('GPS information not found')


def build_map_from_tlog(infile, outfile, verbose, center, zoom):
    # Create tables
    # TODO GPS_INPUT will crash pymavlink, so ignore for now
    # msg_types = ['GLOBAL_POSITION_INT', 'GPS_INPUT', 'GPS_RAW_INT']
    msg_types = ['GLOBAL_POSITION_INT', 'GPS_RAW_INT']
    tables: dict[str, table_types.Table] = {}
    for msg_type in msg_types:
        tables[msg_type] = table_types.Table.create_table(msg_type)

    # Read tlog file, don't crash
    # TODO this loop is common w/ code in tlog_merge.py, move to table_types.py?
    mlog = mavutil.mavlink_connection(infile, robust_parsing=False, dialect='ardupilotmega')
    try:
        while True:
            msg = mlog.recv_match(blocking=False, type=msg_types)
            if msg is None:
                break

            msg_type = msg.get_type()
            raw_data = msg.to_dict()
            timestamp = getattr(msg, '_timestamp', 0.0)

            # Clean up the data: add the timestamp, remove mavpackettype, and rename the keys
            clean_data = {'timestamp': timestamp}
            for key in raw_data.keys():
                if key != 'mavpackettype':
                    clean_data[f'{msg_type}.{key}'] = raw_data[key]

            tables[msg_type].append(clean_data)

    except Exception as e:
        print(f'CRASH WITH ERROR "{e}", PARTIAL RESULTS')

    mm = MapMaker(verbose, center, zoom)

    for msg_type in msg_types:
        df = tables[msg_type].get_dataframe(False)
        if len(df) > 0:
            if msg_type == 'GPS_RAW_INT':
                mm.add_df(df, 'GPS_RAW_INT.lat_deg', 'GPS_RAW_INT.lon_deg', 'blue')
            elif msg_type == 'GLOBAL_POSITION_INT':
                mm.add_df(df, 'GLOBAL_POSITION_INT.lat_deg', 'GLOBAL_POSITION_INT.lon_deg', 'green')
            else:
                mm.add_df(df, 'GPS_INPUT.lat_deg', 'GPS_INPUT.lon_deg', 'red')
        else:
            if verbose:
                print(f'{msg_type} table is empty, ignoring')

    mm.write(outfile)


def build_map(infile, verbose, center, zoom):
    dirname, basename = os.path.split(infile)
    root, ext = os.path.splitext(basename)
    outfile = os.path.join(dirname, root + '.html')

    if ext == '.csv':
        build_map_from_csv(infile, outfile, verbose, center, zoom)
    else:
        build_map_from_tlog(infile, outfile, verbose, center, zoom)


def float_or_none(x):
    if x is None:
        return None

    try:
        return float(x)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{x} is not a floating-point literal')


# TODO reject outliers; if we do this then auto-center will work a lot better

def main():
    parser = ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true',
                        help='enter directories looking for tlog and csv files')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print a lot more information')
    parser.add_argument('--lat', default=None, type=float_or_none,
                        help='center the map at this latitude, default is mean of all points')
    parser.add_argument('--lon', default=None, type=float_or_none,
                        help='center the map at this longitude, default is mean of all points')
    parser.add_argument('--zoom', default=18, type=int,
                        help='initial zoom, default is 18')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, ['.csv', '.tlog'])
    print(f'Processing {len(files)} files')

    for file in files:
        print('-------------------')
        print(file)
        build_map(file, args.verbose, [args.lat, args.lon], args.zoom)


if __name__ == '__main__':
    main()
