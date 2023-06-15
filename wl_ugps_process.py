#!/usr/bin/env python3

"""
Generate a folium map from the log generated by wl_ugps_logger.py.
"""

import argparse
import math
import os
from argparse import ArgumentParser
from typing import NamedTuple

import pandas as pd

import util
from map_maker import MapMaker

# WL UGPS reference frames: https://waterlinked.github.io/underwater-gps/reference-frames/

# Default antenna location is just off the Seattle Aquarium diver ramp, with "Forward" pointing west
DEFAULT_ANTENNA_LATITUDE = 47.6075779801547
DEFAULT_ANTENNA_LONGITUDE = -122.34390446166833
DEFAULT_ANTENNA_HEADING = -90

# Fields we use
# x == Forward
# y == Right
REQUIRED_FIELDS = ['position_valid', 'x', 'y']

# Radius of the Earth
EARTH_RADIUS_M = 6378000


def lat_plus_dist(lat, d):
    return lat + (d / EARTH_RADIUS_M) * (180.0 / math.pi)


def lon_plus_dist(lat, lon, d):
    return lon + (d / EARTH_RADIUS_M) * (180 / math.pi) / math.cos(lat * math.pi / 180.0)


def rotate_x(x, y, a):
    return math.cos(a) * x - math.sin(a) * y


def rotate_y(x, y, a):
    return math.sin(a) * x + math.cos(a) * y


class Antenna(NamedTuple):
    lat: float
    lon: float
    heading_rad: float


def process_wl_log(infile: str, antenna: Antenna, zoom: int):
    # Read csv file, don't crash
    try:
        df = pd.read_csv(infile)
    except Exception as e:
        print(f'Exception parsing csv file: {e}')
        return

    for field in REQUIRED_FIELDS:
        if field not in df.columns:
            print(f'Required field [{field}] missing, skipping')
            return

    print(f'{len(df)} rows')

    # Filter out rows where 'position_valid' is False
    df = df[df['position_valid'] == True]
    print(f'{len(df)} valid rows')

    # Rotate
    df['rot_x'] = df.apply(lambda row: rotate_x(row.x, row.y, antenna.heading_rad), axis=1)
    df['rot_y'] = df.apply(lambda row: rotate_y(row.x, row.y, antenna.heading_rad), axis=1)

    # Translate (global antenna position + relative ROV position)
    df['lat'] = df.apply(lambda row: lat_plus_dist(antenna.lat, row.rot_x), axis=1)
    df['lon'] = df.apply(lambda row: lon_plus_dist(antenna.lat, antenna.lon, row.rot_y), axis=1)

    # Temp: save csv
    outfile = util.get_outfile_name(infile, suffix='_position_valid', ext='.csv')
    print(f'Writing {outfile}')
    df.to_csv(outfile)

    # Filter out rows where only 3 transducers have a valid signal
    df_4_good = df[df['valid_r0'] == 1]
    df_4_good = df_4_good[df_4_good['valid_r1'] == 1]
    df_4_good = df_4_good[df_4_good['valid_r2'] == 1]
    df_4_good = df_4_good[df_4_good['valid_r3'] == 1]

    # Temp: save csv
    outfile = util.get_outfile_name(infile, suffix='_all_4_valid', ext='.csv')
    print(f'Writing {outfile}')
    df_4_good.to_csv(outfile)

    # Generate map
    mm = MapMaker(False, [df['lat'].mean(), df['lon'].mean()], zoom)
    mm.add_df(df, 'lat', 'lon', 'blue')
    mm.add_df(df_4_good, 'lat', 'lon', 'green')
    mm.write(util.get_outfile_name(infile, ext='.html'))


def main():
    parser = ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true',
                        help='enter directories looking for csv files')
    parser.add_argument('--lat', default=DEFAULT_ANTENNA_LATITUDE, type=float,
                        help='WL UGPS antenna latitude')
    parser.add_argument('--lon', default=DEFAULT_ANTENNA_LONGITUDE, type=float,
                        help='WL UGPS antenna longitude')
    parser.add_argument('--heading', default=DEFAULT_ANTENNA_HEADING, type=float,
                        help='WL UGPS antenna heading')
    parser.add_argument('--zoom', default=18, type=int,
                        help='initial zoom, default is 18')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.ugps')
    print(f'Processing {len(files)} files')

    for infile in files:
        print('-------------------')
        print(infile)
        process_wl_log(infile, Antenna(args.lat, args.lon, math.radians(args.heading)), args.zoom)


if __name__ == '__main__':
    main()
