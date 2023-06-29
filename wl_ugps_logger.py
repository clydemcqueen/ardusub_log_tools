#!/usr/bin/env python3

"""
Get position data from the Water Linked UGPS API and write it to one or more csv files.
"""

import argparse
import csv
import datetime
import time

import requests


def get_data(url) -> dict | None:
    try:
        r = requests.get(url)
    except requests.exceptions.RequestException as e:
        print(f'Exception occurred {e}')
        return None

    if r.status_code != requests.codes.ok:
        print(f'Got error {r.status_code}: {r.text}')
        return None

    return r.json()


def flatten_list_value(d: dict, old_key: str, new_key_format: str):
    # Add new items, one for each value in the list
    # The new key names are generated from new_key_format
    list_value = d[old_key]
    for i in range(len(list_value)):
        d[new_key_format.format(i=i)] = list_value[i]

    # Delete the list
    del d[old_key]


class Logger:
    def __init__(self, endpoint: str, filename: str):
        print(f'Polling {endpoint}, writing to {filename}')
        self.endpoint = endpoint
        self.csv_file = open(filename, 'w', newline='')
        self.csv_writer = None

    def poll(self) -> dict | None:
        data = get_data(self.endpoint)
        if data is None:
            return None
        else:
            return dict(data)

    def log(self):
        row = self.poll()

        if row is None:
            return

        if self.csv_writer is None:
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=row.keys())
            self.csv_writer.writeheader()

        self.csv_writer.writerow(row)

        # Robust against crashes
        self.csv_file.flush()

    def close(self):
        self.csv_file.close()


class AcousticLogger(Logger):
    def poll(self) -> dict | None:
        row = super().poll()

        if row is None:
            return None

        # Flatten lists
        flatten_list_value(row, 'receiver_distance', 'distance_r{i}')
        flatten_list_value(row, 'receiver_nsd', 'nsd_r{i}')
        flatten_list_value(row, 'receiver_rssi', 'rssi_r{i}')
        flatten_list_value(row, 'receiver_valid', 'valid_r{i}')

        # Add a timestamp
        row['timestamp'] = time.time()

        return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', type=str, default='https://demo.waterlinked.com',
                        help='URL of UGPS topside unit')
    parser.add_argument('--filtered', action='store_true',
                        help='log position/acoustic/filtered')
    parser.add_argument('--raw', action='store_true',
                        help='log position/acoustic/raw')
    parser.add_argument('--locator', action='store_true',
                        help='log position/global (locator)')
    parser.add_argument('--g2', action='store_true',
                        help='log position/master (G2 box)')
    parser.add_argument('--all', action='store_true',
                        help='log everything')
    parser.add_argument('--rate', type=float, default=2.0,
                        help='polling rate')
    args = parser.parse_args()

    loggers = []
    base = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    if args.raw or args.all:
        loggers.append(AcousticLogger(args.url + '/api/v1/position/acoustic/raw', base + '_acoustic_raw.csv'))

    if args.filtered or args.all:
        loggers.append(AcousticLogger(args.url + '/api/v1/position/acoustic/filtered', base + '_acoustic_filtered.csv'))

    if args.locator or args.all:
        loggers.append(Logger(args.url + '/api/v1/position/global', base + '_locator.csv'))

    if args.g2 or args.all:
        loggers.append(Logger(args.url + '/api/v1/position/master', base + '_g2.csv'))

    if len(loggers) == 0:
        print('Nothing to log (did you mean to log something?)')
        return

    print('Press Ctrl-C to stop')

    period = 1.0 / args.rate

    try:
        while True:
            for logger in loggers:
                logger.log()

            time.sleep(period)

    except KeyboardInterrupt:
        print('Ctrl-C detected, stopping')

    finally:
        print('Cleaning up')
        for logger in loggers:
            logger.close()


if __name__ == '__main__':
    main()
