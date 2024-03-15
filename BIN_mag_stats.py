#!/usr/bin/env python3

"""
Read dataflash logs and report on some MAG stats.
"""

from argparse import ArgumentParser
from statistics import mean, stdev

from pymavlink import mavutil

import util


class DataflashParam:
    def __init__(self, msg):
        self.time_us = msg.TimeUS
        self.id = msg.Name
        self.value = msg.Value
        self.default = msg.Default


class DataFlashParams:
    def __init__(self, interesting: list[str]):
        self.interesting = interesting
        self.params: dict[str, DataflashParam] = {}

    def add(self, msg):
        if msg.Name in self.interesting:
            self.params[msg.Name] = (DataflashParam(msg))

    def get_value(self, name):
        assert name in self.interesting
        if name in self.params.keys():
            return self.params[name].value
        else:
            return None


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', help='enter directories looking for BIN files', action='store_true')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.BIN')
    print(f'Processing {len(files)} files')

    mag_param_names = [
        'COMPASS_DEV_ID',
        'COMPASS_DEV_ID2',
        'COMPASS_DEV_ID3',
    ]

    for file in files:
        mlog = mavutil.mavlink_connection(file, robust_parsing=False, dialect='ardupilotmega')

        params = DataFlashParams(mag_param_names)
        mag_readings = {}

        while (msg := mlog.recv_match(blocking=False, type=['MAG', 'PARM'])) is not None:
            msg_type = msg.get_type()
            if msg_type == 'MAG':
                if msg.I not in mag_readings:
                    mag_readings[msg.I] = {'X': [], 'Y': [], 'Z': []}
                mag_readings[msg.I]['X'].append(msg.MagX)
                mag_readings[msg.I]['Y'].append(msg.MagY)
                mag_readings[msg.I]['Z'].append(msg.MagZ)
            elif msg_type == 'PARM':
                params.add(msg)

        # TODO get the human readable name from decode_devid.py -- how can I import ArduPilot code?
        dev_ids = [
            int(params.get_value('COMPASS_DEV_ID')),
            int(params.get_value('COMPASS_DEV_ID2')),
            int(params.get_value('COMPASS_DEV_ID3'))
        ]

        print(file)

        for instance in mag_readings.keys():
            for dim in ['X', 'Y', 'Z']:
                data = mag_readings[instance][dim]
                xbar = mean(data)
                min_val = min(data)
                max_val = max(data)
                print(f'MAG[{instance}].Mag{dim} ({dev_ids[instance]}): mean {xbar :8.2f}, stdev {stdev(data, xbar) :8.2f}, min {min_val :8.2f}, max {max_val :8.2f}')
                if min_val < -2000 or max_val > 2000:
                    print(f'MAG[{instance}].Mag{dim} ({dev_ids[instance]}) OUTLIER[S], min {min_val :8.2f}, max {max_val :8.2f}')


if __name__ == '__main__':
    main()
