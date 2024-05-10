#!/usr/bin/env python3

"""
Read PARM messages from a dataflash file and write them to a params file.
"""

from argparse import ArgumentParser
from operator import attrgetter

from pymavlink import mavutil

from tlog_param import EK3_SRCn_POSXY, EK3_SRCn_VELXY, EK3_SRCn_POSZ, EK3_SRCn_VELZ, EK3_SRCn_YAW
import util


class DataflashParam:
    def __init__(self, msg):
        self.time_us = msg.TimeUS
        self.id = msg.Name
        self.value = msg.Value

    def comment(self) -> str | None:
        if self.id.startswith('EK3_SRC'):
            if self.id.endswith('POSXY'):
                return EK3_SRCn_POSXY[int(self.value)]
            elif self.id.endswith('VELXY'):
                return EK3_SRCn_VELXY[int(self.value)]
            elif self.id.endswith('POSZ'):
                return EK3_SRCn_POSZ[int(self.value)]
            elif self.id.endswith('VELZ'):
                return EK3_SRCn_VELZ[int(self.value)]
            elif self.id.endswith('YAW'):
                return EK3_SRCn_YAW[int(self.value)]
            elif self.id == 'EK3_SRC_OPTIONS':
                return 'FuseAllVelocities' if int(self.value) == 1 else 'None'
        return None


class DataFlashParams:
    """
    Use a list and keep all copies of the same parameter.
    This will show parameter changes.
    """

    def __init__(self, interesting: list[str] = None):
        self.interesting = interesting
        self.params: list[DataflashParam] = []

    def add(self, msg):
        if self.interesting is None or msg.Name in self.interesting:
            self.params.append(DataflashParam(msg))

    def write_params_file(self, outfile: str):
        if not len(self.params):
            print('Nothing to write')
            return

        print(f'Writing {outfile}')
        f = open(outfile, 'w')

        previous_id = None
        for param in sorted(self.params, key=attrgetter('id', 'time_us')):  # Sort by id, then by time
            s = f'{param.id :20s}{param.time_us :12}'
            s = s + (f' >>>' if param.id == previous_id else '    ')
            s = s + f'{param.value :30}'
            comment = param.comment()
            if comment is not None:
                s = s + f'  # {comment}'

            f.write(s + '\n')
            previous_id = param.id

        f.close()


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', help='enter directories looking for BIN files', action='store_true')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.BIN')
    print(f'Processing {len(files)} files')

    for file in files:
        mlog = mavutil.mavlink_connection(file, robust_parsing=False, dialect='ardupilotmega')

        params = DataFlashParams()

        print(f'Reading {file}')
        while (msg := mlog.recv_match(blocking=False, type=['PARM'])) is not None:
            params.add(msg)

        params.write_params_file(util.get_outfile_name(file, ext='.params'))


if __name__ == '__main__':
    main()
