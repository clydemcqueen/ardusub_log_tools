#!/usr/bin/env python3

"""
Read GPS_INPUT messages and look for problems.

Supports segments.
"""

from argparse import ArgumentParser

from segment_reader import add_segment_args, choose_reader_list


def check_gps_input_messages(reader):
    num_bad_fix = 0
    num_no_sat = 0
    num_bad = 0
    num_good = 0

    for msg in reader:
        good = True

        if msg.fix_type == 0:
            good = False
            num_bad_fix += 1

        if msg.satellites_visible == 0:
            good = False
            num_no_sat += 1

        if good:
            num_good += 1
        else:
            num_bad += 1

    print(f'{num_bad_fix} bad fix, {num_no_sat} no satellites, {num_bad} bad, {num_good} good')


def main():
    parser = ArgumentParser(description=__doc__)
    add_segment_args(parser)
    args = parser.parse_args()
    readers = choose_reader_list(args, ['GPS_INPUT'])
    for reader in readers:
        check_gps_input_messages(reader)


if __name__ == '__main__':
    main()
