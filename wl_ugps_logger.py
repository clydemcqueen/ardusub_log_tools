#!/usr/bin/env python3

"""
Get acoustic position data from the Water Linked UGPS API and write it to a csv file.
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


def get_position_acoustic_raw(base_url):
    return get_data("{}/api/v1/position/acoustic/raw".format(base_url))


def get_position_acoustic_filtered(base_url):
    return get_data("{}/api/v1/position/acoustic/filtered".format(base_url))


def get_position_global(base_url):
    return get_data("{}/api/v1/position/global".format(base_url))


def get_position_master(base_url):
    return get_data("{}/api/v1/position/master".format(base_url))


def flatten_list_value(d: dict, old_key: str, new_key_format: str):
    # Add new items, one for each value in the list
    # The new key names are generated from new_key_format
    list_value = d[old_key]
    for i in range(len(list_value)):
        d[new_key_format.format(i=i)] = list_value[i]

    # Delete the list
    del d[old_key]


def get_position_acoustic_reading(endpoint) -> dict:
    position_acoustic = dict(get_data(endpoint))

    # Flatten lists
    flatten_list_value(position_acoustic, 'receiver_distance', 'distance_r{i}')
    flatten_list_value(position_acoustic, 'receiver_nsd', 'nsd_r{i}')
    flatten_list_value(position_acoustic, 'receiver_rssi', 'rssi_r{i}')
    flatten_list_value(position_acoustic, 'receiver_valid', 'valid_r{i}')

    # Add a timestamp
    position_acoustic['timestamp'] = time.time()

    return position_acoustic


class Logger:
    def __init__(self, endpoint: str, filename: str):
        print(f'Polling {endpoint}, writing to {filename}')
        self.endpoint = endpoint
        self.csv_file = open(filename, 'w', newline='')
        self.csv_writer = None

    def poll_and_log(self):
        row = get_position_acoustic_reading(self.endpoint)

        if self.csv_writer is None:
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=row.keys())
            self.csv_writer.writeheader()

        self.csv_writer.writerow(row)

        # Robust against crashes
        self.csv_file.flush()

    def close(self):
        self.csv_file.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', type=str, default='https://demo.waterlinked.com',
                        help='URL of UGPS topside unit')
    parser.add_argument('--filtered', action='store_true',
                        help='log position/acoustic/filtered')
    parser.add_argument('--raw', action='store_true',
                        help='log position/acoustic/raw')
    parser.add_argument('--all', action='store_true',
                        help='log everything')
    parser.add_argument('--rate', type=float, default=2.0,
                        help='polling rate')
    args = parser.parse_args()

    prefix = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    loggers = []

    if args.raw or args.all:
        loggers.append(Logger(args.url + '/api/v1/position/acoustic/raw', prefix + '_raw.csv'))

    if args.filtered or args.all:
        loggers.append(Logger(args.url + '/api/v1/position/acoustic/filtered', prefix + '_filtered.csv'))

    if len(loggers) == 0:
        print('Nothing to log (did you mean to log something?)')
        return

    print('Press Ctrl-C to stop')

    period = 1.0 / args.rate

    try:
        while True:
            for logger in loggers:
                logger.poll_and_log()

            time.sleep(period)

    except KeyboardInterrupt:
        print('Ctrl-C detected, stopping')

    for logger in loggers:
        logger.close()


if __name__ == '__main__':
    main()
