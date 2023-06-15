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


def get_position_acoustic_reading(base_url: str, raw: bool) -> dict:
    position_acoustic = dict(get_position_acoustic_raw(base_url) if raw else get_position_acoustic_filtered(base_url))

    # Flatten lists
    flatten_list_value(position_acoustic, 'receiver_distance', 'distance_r{i}')
    flatten_list_value(position_acoustic, 'receiver_nsd', 'nsd_r{i}')
    flatten_list_value(position_acoustic, 'receiver_rssi', 'rssi_r{i}')
    flatten_list_value(position_acoustic, 'receiver_valid', 'valid_r{i}')

    # Add a timestamp
    position_acoustic['timestamp'] = time.time()

    return position_acoustic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', type=str, default='https://demo.waterlinked.com',
                        help='URL of UGPS topside unit')
    parser.add_argument('--raw', action='store_true',
                        help='get raw acoustic position (default is filtered)')
    parser.add_argument('--hz', type=float, default=2.0,
                        help='polling rate')
    parser.add_argument('--output', type=str, default=None,
                        help='output file')
    args = parser.parse_args()

    period = 1.0 / args.hz

    output = args.output

    if output is None:
        # Use the '.ugps' extension to avoid conflict w/ other tools
        output = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output += '_raw.ugps' if args.raw else '_filtered.ugps'

    print(f'Polling {args.url}/position/acoustic/{"raw" if args.raw else "filtered"} at {args.hz} Hz')
    print(f'Writing to {output}')
    print('Press Ctrl-C to stop')

    csv_file = open(output, 'w', newline='')
    csv_writer = None


    try:
        while True:
            row = get_position_acoustic_reading(args.url, args.raw)

            if csv_writer is None:
                csv_writer = csv.DictWriter(csv_file, fieldnames=row.keys())
                csv_writer.writeheader()

            csv_writer.writerow(row)

            # Robust against crashes
            csv_file.flush()

            time.sleep(period)

    except KeyboardInterrupt:
        print('Ctrl-C detected, stopping')

    csv_file.close()


if __name__ == '__main__':
    main()
