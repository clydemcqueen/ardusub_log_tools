#!/usr/bin/env python3

"""
Read csv, tlog or txt files and build Leaflet (interactive HTML) maps from GPS coordinates.

For csv files:
    Latitude column header should be 'gps.lat' or 'lat'
    Longitude column header should be 'gps.lon' or 'lon'

For tlog files, these messages are read:
    GPS_RAW_INT -- sensor data sent from ArduSub to QGC, will appear as a blue line, should be close to the csv file
    GLOBAL_POSITION_INT -- the filtered position estimate, green line
    GPS_INPUT -- sensor data sent from ugps-extension to ArduSub, not filtered, red line

For txt files, look for NMEA 0183 GGA messages of the form r'\$[A-Z]+', e.g., $GPGGA.
"""

import argparse
import os
import re
from argparse import ArgumentParser
from datetime import datetime
from statistics import fmean

import folium
import pandas as pd
import pynmea2
from pymavlink import mavutil

import table_types
import util


class MapMaker:
    @staticmethod
    def build_map_from_df(df, lat_col, lon_col, outfile, verbose, center, zoom):
        mm = MapMaker(verbose, center, zoom)
        mm.add_df(df, lat_col, lon_col, 'blue')
        mm.write(outfile)

    @staticmethod
    def build_map_from_txt(locations, outfile, verbose, center, zoom):
        mm = MapMaker(verbose, center, zoom)
        mm.add_locations(locations, 'blue')
        mm.write(outfile)

    def __init__(self, verbose, center, zoom):
        self.m = None
        self.verbose = verbose
        self.center = center
        self.zoom = zoom

    def _build_empty_map(self):
        self.m = folium.Map(location=self.center, zoom_start=self.zoom, max_zoom=24)

    def add_df(self, df, lat_col, lon_col, color, marker_function=None):
        if self.m is None:
            if self.center[0] is None:
                self.center[0] = df[lat_col].mean()
            if self.center[1] is None:
                self.center[1] = df[lon_col].mean()
            self._build_empty_map()

        if self.verbose:
            print(df.head())
            print(len(df))

        # smooth_factor=1 (default) seems to mean "do not remove points", which is what we want
        folium.PolyLine(df[[lat_col, lon_col]].values, color=color, weight=1).add_to(self.m)

        if marker_function is not None:
            for index, row in df.iterrows():
                marker = marker_function(row)
                if marker is not None:
                    marker.add_to(self.m)

    def add_table(self, table, lat_col, lon_col, color):
        self.add_df(table.get_dataframe(self.verbose), lat_col, lon_col, color)

    def add_locations(self, locations: list[tuple[float, float]], color):
        if self.m is None:
            lats, lons = zip(*locations)
            if self.center[0] is None:
                self.center[0] = fmean(lats)
            if self.center[1] is None:
                self.center[1] = fmean(lons)
            self._build_empty_map()

        # smooth_factor=1 (default) seems to mean "do not remove points", which is what we want
        folium.PolyLine(locations, color=color, weight=1).add_to(self.m)

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


def build_map_from_tlog(infile, outfile, verbose, center, zoom, msg_types, hdop_max):
    # Create tables
    tables: dict[str, table_types.Table] = {}
    for msg_type in msg_types:
        tables[msg_type] = table_types.Table.create_table(msg_type, verbose=verbose, hdop_max=hdop_max)

    # Read tlog file, don't crash
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

    # Build the map in a specific order
    if 'GPS_RAW_INT' in msg_types and len(tables['GPS_RAW_INT']):
        mm.add_table(tables['GPS_RAW_INT'], 'GPS_RAW_INT.lat_deg', 'GPS_RAW_INT.lon_deg', 'blue')
    if 'GLOBAL_POSITION_INT' in msg_types and len(tables['GLOBAL_POSITION_INT']):
        mm.add_table(tables['GLOBAL_POSITION_INT'], 'GLOBAL_POSITION_INT.lat_deg', 'GLOBAL_POSITION_INT.lon_deg', 'green')
    if 'GPS_INPUT' in msg_types and len(tables['GPS_INPUT']):
        mm.add_table(tables['GPS_INPUT'], 'GPS_INPUT.lat_deg', 'GPS_INPUT.lon_deg', 'red')

    mm.write(outfile)


def get_timestamp(line: str):
    match = re.search(r'^[^|]+', line)
    return datetime.strptime(match[0], '%Y-%m-%d %H:%M:%S.%f ')


def build_map_from_txt(infile, outfile, verbose, center, zoom):
    file = open(infile, 'r')
    line = file.readline()

    if line == '':
        print('Empty file')
        return

    # Count messages
    total_nmea = 0

    locations = []

    # Get the first and last timestamp to compute duration and message rates
    start = get_timestamp(line)
    prev_line = line

    # group(0) is everything from $<sentence_type> to end of line
    # group(1) is $<sentence_type>
    pattern = re.compile(r'(\$[A-Z]+),.*$')

    while line := file.readline():
        m = re.search(pattern, line)
        if m is not None:
            total_nmea += 1
            if m.group(1).endswith('GGA'):
                sentence = pynmea2.parse(m.group(0))
                locations.append((sentence.latitude, sentence.longitude))
        prev_line = line

    duration = get_timestamp(prev_line) - start
    print(f'{total_nmea} sentences received in {duration.seconds} seconds, {len(locations)} were GGA')

    if len(locations) > 0:
        MapMaker.build_map_from_txt(locations, outfile, verbose, center, zoom)
    else:
        print("No GGA messages found")


def float_or_none(x):
    if x is None:
        return None

    try:
        return float(x)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{x} is not a floating-point literal')


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
    parser.add_argument('--types', default=None,
                        help='comma separated list of message types, the default is GPS_RAW_INT and GPS_GLOBAL_INT')
    parser.add_argument('--hdop-max', default=100.0, type=float,
                        help='reject GPS_INPUT messages where hdop exceeds this limit, default 100.0 (no limit)')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, ['.csv', '.tlog', '.txt'])
    print(f'Processing {len(files)} files')

    if args.types:
        msg_types = args.types.split(',')
    else:
        # The default doesn't include GPS_INPUT because of this bug: https://github.com/ArduPilot/pymavlink/issues/807
        msg_types = ['GLOBAL_POSITION_INT', 'GPS_RAW_INT']

    for infile in files:
        print('-------------------')
        print(infile)
        dirname, basename = os.path.split(infile)
        root, ext = os.path.splitext(basename)
        outfile = os.path.join(dirname, root + '.html')

        if ext == '.csv':
            build_map_from_csv(infile, outfile, args.verbose, [args.lat, args.lon], args.zoom)
        elif ext == '.tlog':
            build_map_from_tlog(infile, outfile, args.verbose, [args.lat, args.lon], args.zoom, msg_types, args.hdop_max)
        else:
            build_map_from_txt(infile, outfile, args.verbose, [args.lat, args.lon], args.zoom)


if __name__ == '__main__':
    main()
