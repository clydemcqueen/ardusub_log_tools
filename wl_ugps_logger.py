#!/usr/bin/env python3

"""
Get data from the Water Linked UGPS API and write it to a csv file.
"""

import time
import argparse
import requests
import pandas as pd


def get_data(url):
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


class Row:
    def __init__(self, url: str):
        self.timestamp = time.time()
        self.position_acoustic_raw = get_position_acoustic_raw(url)


class WaterLinkedLogWriter:
    def __init__(self):
        self.rows = []

    def record_data(self, url: str, hz: float, send_mavlink: bool):
        period = 1.0 / hz
        while True:
            position_acoustic_raw = get_position_acoustic_raw(url)

            row = {**position_acoustic_raw, 'timestamp': time.time()}

            self.rows.append(row)

            # TODO send mavlink

            time.sleep(period)

    def write_csv(self, outfile: str):
        if len(self.rows):
            dataframe = pd.DataFrame(self.rows)
            print(dataframe.head())

            print(f'Writing {len(dataframe)} rows')
            dataframe.to_csv(outfile)
        else:
            print('Nothing to write')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-u', '--url', type=str, default='https://demo.waterlinked.com',
                        help='URL of UGPS topside unit')
    parser.add_argument('-o', '--output', type=str, default='ugps.csv',
                        help='output file')
    parser.add_argument('--hz', type=float, default=2.0,
                        help='polling rate')
    parser.add_argument('--mavlink', action='store_true',
                        help='write MAVLink messages')
    args = parser.parse_args()

    logger = WaterLinkedLogWriter()

    try:
        print(f'Logging data from {args.url}, press Ctrl-C to stop')
        logger.record_data(args.url, args.hz, args.mavlink)
    except KeyboardInterrupt:
        pass

    logger.write_csv(args.output)


if __name__ == '__main__':
    main()
