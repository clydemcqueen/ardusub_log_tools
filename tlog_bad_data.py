#!/usr/bin/env python3

"""
Read MAVLink messages from a tlog file (telemetry log) and report on BAD_DATA messages.
"""

from argparse import ArgumentParser

from pymavlink import mavutil

import util


class BadDataInfo:
    """
    Gather data about a BAD_DATA message.

    MAVLink 1 header:
    uint8_t magic;              ///< protocol magic marker == 0xFE
    uint8_t len;                ///< Length of payload
    uint8_t seq;                ///< Sequence of packet
    uint8_t sysid;              ///< ID of message sender system/aircraft
    uint8_t compid;             ///< ID of the message sender component
    uint8_t msgid;              ///< ID of the message

    MAVLink 2 header:
    uint8_t magic;              ///< protocol magic marker == 0xFD
    uint8_t len;                ///< Length of payload
    uint8_t incompat_flags;     ///< flags that must be understood
    uint8_t compat_flags;       ///< flags that can be ignored if not understood
    uint8_t seq;                ///< Sequence of packet
    uint8_t sysid;              ///< ID of message sender system/aircraft
    uint8_t compid;             ///< ID of the message sender component
    uint8_t msgid 0:7;          ///< first 8 bits of the ID of the message
    uint8_t msgid 8:15;         ///< middle 8 bits of the ID of the message
    uint8_t msgid 16:23;        ///< last 8 bits of the ID of the message

    Reference: https://mavlink.io/en/guide/serialization.html#packet_format
    """

    def __init__(self, msg):
        # String w/ error message
        self.reason = msg.reason

        # Is this a CRC error?
        self.crc_error = True if msg.reason.find('invalid MAVLink CRC') >= 0 else False

        # Parse the MAVLink header
        b = bytes(msg.data)
        self.mavlink2 = True if b[0] == 0xFD else False

        if self.mavlink2:
            self.sysid = int(b[5])
            self.compid = int(b[6])
            self.msg_id = (b[9] << 16) + (b[8] << 8) + b[7]
        else:
            self.sysid = int(b[3])
            self.compid = int(b[4])
            self.msg_id = int(b[5])

    def __str__(self):
        return f'BadDataMsg mavlink2={self.mavlink2} sysid={self.sysid} compid={self.compid} msg_id={self.msg_id} reason: {self.reason}'


class BadDataFinder:
    def __init__(self, infile: str, verbose: bool):
        self.infile = infile
        self.verbose = verbose

    def read(self):
        print(f'Results for {self.infile}')

        mlog = mavutil.mavlink_connection(self.infile, dialect='ardupilotmega')

        total_count = 0
        crc_errors = 0
        counts = {}
        while True:
            try:
                # It appears that I can't filter for BAD_DATA messages, so get them all
                msg = mlog.recv_match(blocking=False)
            except Exception as e:
                print(f'CRASH WITH ERROR "{e}" READING {self.infile}')
                return

            if msg is None:
                break

            if msg.get_type() == 'BAD_DATA':
                msg_info = BadDataInfo(msg)
                # Count number of bad messages
                total_count += 1

                # Count number of bad messages due to CRC errors
                crc_errors = crc_errors + (1 if msg_info.crc_error else 0)

                # Count by underlying message type
                if msg_info.msg_id not in counts:
                    counts[msg_info.msg_id] = 0

                counts[msg_info.msg_id] += 1

                # Verbose!
                if self.verbose:
                    print(BadDataInfo(msg))

        for msg_id_item in sorted(counts.items()):
            print(f'msg_id {msg_id_item[0]} count {msg_id_item[1]}')

        print(f'{total_count} BAD_DATA messages, {crc_errors} of them were CRC errors')


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true', help='enter directories looking for tlog files')
    parser.add_argument('-v', '--verbose', action='store_true', help='print a lot more information')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.tlog')
    print(f'Processing {len(files)} files')

    for file in files:
        print('-------------------')
        scanner = BadDataFinder(file, args.verbose)
        scanner.read()


if __name__ == '__main__':
    main()
