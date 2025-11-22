#!/usr/bin/env python3

"""
Read one or more tlog files, filter messages, and write a single, combined, valid tlog file with the resulting
messages.

The default action is similar to specifying the "--all" argument, where messages from all timestamps are kept in the
output. Users can override this by specifying one or more "--keep" arguments.

Files are named using the standard segment file naming method.
"""

import os
import struct

# Bug? I'm seeing mavlink.WIRE_PROTOCOL_VERSION == "1.0" for some QGC-generated tlog files
# Force WIRE_PROTOCOL_VERSION to be 2.0
os.environ['MAVLINK20'] = '1'

import argparse

import util
from segment_reader import add_segment_args, choose_reader_list


def filter_tlog(reader, msg_types, sysid, compid, max_msgs, verbose):
    """
    Filter messages and write them to a new tlog file.
    """
    output_filename = util.get_outfile_name(reader.name, suffix='_filtered')
    output_filename = os.path.splitext(output_filename)[0] + '.tlog'
    print(f'Writing {output_filename}')

    with open(output_filename, 'wb') as outfile:
        msg_count = 0
        kept_count = 0

        for msg in reader:
            msg_count += 1

            # Stop if we've hit the message limit
            if kept_count >= max_msgs:
                print(f'Wrote {kept_count} messages, stopping')
                break

            # Filter by sysid and compid
            if sysid is not None and sysid != msg.get_srcSystem():
                continue
            if compid is not None and compid != msg.get_srcComponent():
                continue

            # Filter by message type
            if msg_types is not None and msg.get_type() not in msg_types:
                continue

            # We need to reconstruct the tlog header (8 bytes, Big Endian unsigned long long, microseconds)
            header = struct.pack('>Q', int(msg._timestamp * 1_000_000))

            # Write the header
            outfile.write(header)

            # Write the raw MAVLink packet data
            outfile.write(msg.get_msgbuf())

            kept_count += 1

            if verbose and msg_count % 20000 == 0:
                print(f'... {msg_count} messages read, {kept_count} messages kept')

        print(f'{msg_count} messages read, {kept_count} messages kept')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print a lot more information')
    parser.add_argument('--types', default=None,
                        help='comma separated list of message types, e.g., "ATTITUDE,RC_CHANNELS"')
    parser.add_argument('--sysid', type=int, default=None,
                        help='select source system id, default is all systems')
    parser.add_argument('--compid', type=int, default=None,
                        help='select source component id, default is all components')
    parser.add_argument('--max-msgs', type=int, default=500000,
                        help='stop after keeping this number of messages, default is 500K')
    args = parser.parse_args()

    # If --keep is not specified, default to --all
    if not args.keep:
        args.all = True

    msg_types = args.types.split(',') if args.types else None

    if msg_types:
        print(f'Filtering for these types: {msg_types}')

    # A SegmentReaderList iterates through one or more tlog files, and returns SegmentReaders
    # A SegmentReader iterates through messages in a single segment
    # Each SegmentReader also has a name, used for the output file
    readers = choose_reader_list(args, msg_types)
    for reader in readers:
        filter_tlog(reader, msg_types, args.sysid, args.compid, args.max_msgs, args.verbose)


if __name__ == '__main__':
    main()
