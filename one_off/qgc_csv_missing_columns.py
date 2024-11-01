#!/usr/bin/env python3

"""
Read a QGC-generated csv file and look for missing columns

Usage:
missing_columns.py -r ~/dive_logs
"""

import argparse
import csv
import os

import util


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true', help='enter directories looking for files')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    paths = util.expand_path(args.path, args.recurse, '.csv')

    count_ok = 0
    count_err = 0

    for path in paths:
        if not path.endswith('vehicle1.csv'):
            continue

        has_err = False

        with open(path, newline='') as csvfile:
            filename = os.path.basename(path)
            reader = csv.reader(csvfile, delimiter=',', quotechar='|')
            num_cols = None

            for ir, row in enumerate(reader):
                if num_cols is None:
                    num_cols = len(row)
                elif len(row) != num_cols:
                    print(f'{filename}: ERROR! change from {num_cols} columns to {len(row)} columns at row index {ir}')
                    num_cols = len(row)
                    has_err = True

            if has_err:
                count_err += 1
            else:
                count_ok += 1

    total = count_ok + count_err
    print(f'Scanned {total} QGC-generated csv files, {count_err / total:.0%} had errors')


if __name__ == '__main__':
    main()
