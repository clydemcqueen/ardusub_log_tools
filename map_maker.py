#!/usr/bin/env python3

"""
Read csv or tlog files and build Leaflet (interactive HTML) maps from GPS coordinates.
"""

from argparse import ArgumentParser
import folium
import pandas as pd
import os
import util


def build_map_from_dataframe(df, lat_col, lon_col, outfile):
    print(df.head())
    print(len(df))
    center = [df[lat_col].mean(), df[lon_col].mean()]

    m = folium.Map(location=center, zoom_start=18, max_zoom=24)
    folium.PolyLine(df[[lat_col, lon_col]].values).add_to(m)
    m.save(outfile)


def build_map_from_csv(infile, outfile):
    df = pd.read_csv(infile)
    if 'gps.lat' in df.columns and 'gps.lat' in df.columns:
        print('QGC csv file')
        build_map_from_dataframe(pd.read_csv(infile, usecols=['gps.lat', 'gps.lon']), 'gps.lat', 'gps.lon', outfile)
    else:
        # TODO read cleaned csv
        print('csv variant not implemented yet')


def build_map(infile):
    dirname, basename = os.path.split(infile)
    root, ext = os.path.splitext(basename)
    outfile = os.path.join(dirname, root + '.html')

    if ext == '.csv':
        build_map_from_csv(infile, outfile)
    else:
        # TODO
        print('extension not implemented yet')


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', help='enter directories looking for tlog and csv files', action='store_true')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, ['.csv', '.tlog'])
    print(f'Processing {len(files)} files')

    for file in files:
        print('-------------------')
        print(file)
        build_map(file)


if __name__ == '__main__':
    main()
