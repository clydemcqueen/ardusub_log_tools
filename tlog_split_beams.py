#!/usr/bin/env python3

"""
Read DISTANCE_SENSOR messages from a tlog file and write one csv file per (src, comp, orientation) tuple.
"""

import os
from typing import Dict, Tuple, List, Any

import pandas as pd
from pymavlink import mavutil

import util


class BeamSplitter:
    def __init__(self, tlog_path: str) -> None:
        self.path: str = tlog_path
        self.sensor_data: Dict[Tuple[int, int, int], Dict[str, List[Any]]] = {}

    def process_messages(self):
        mlog = mavutil.mavlink_connection(self.path)
        while True:
            msg = mlog.recv_match(type='DISTANCE_SENSOR')
            if msg is None:
                break

            key = (msg.get_srcSystem(), msg.get_srcComponent(), msg.orientation)
            if key not in self.sensor_data:
                self.sensor_data[key] = {
                    'timestamp': [],
                    'min_distance': [],
                    'max_distance': [],
                    'current_distance': [],
                    'type': [],
                    'id': [],
                    'covariance': []
                }

            data = self.sensor_data[key]
            data['timestamp'].append(getattr(msg, '_timestamp', 0.0))
            data['min_distance'].append(msg.min_distance)
            data['max_distance'].append(msg.max_distance)
            data['current_distance'].append(msg.current_distance)
            data['type'].append(msg.type)
            data['id'].append(msg.id)
            data['covariance'].append(msg.covariance)

    def write_csv_files(self):
        base_name = os.path.splitext(self.path)[0]
        for (sys_id, comp_id, orientation), data in self.sensor_data.items():
            df = pd.DataFrame(data)
            output_file = f"{base_name}_sys{sys_id}_comp{comp_id}_orient{orientation}.csv"
            df.to_csv(output_file, index=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true', help='enter directories looking for tlog files')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    paths = util.expand_path(args.path, args.recurse, ['.tlog'])
    print(f'Processing {len(paths)} tlog files')

    for path in paths:
        print('-------------------')
        print(f'Reading {path}')
        splitter = BeamSplitter(path)
        splitter.process_messages()
        splitter.write_csv_files()