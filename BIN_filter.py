#!/usr/bin/env python3

"""
Read Dataflash (BIN) file(s), filter messages, and write new BIN file(s) with the kept messages.
Always preserves FMT messages to ensure the file remains valid.
"""

import argparse
import os
import sys
from pymavlink import mavutil
import util

def filter_bin(input_file, output_file, keep_types, exclude_types, start_time, stop_time, verbose):
    print(f"Reading {input_file}")
    print(f"Writing {output_file}")
    
    mlog = mavutil.mavlink_connection(input_file, robust_parsing=False, dialect='ardupilotmega')
    
    # Ensure FMT is always kept
    if keep_types is not None and 'FMT' not in keep_types:
        keep_types.append('FMT')
        
    msg_count = 0
    kept_count = 0
    
    with open(output_file, 'wb') as outfile:
        while True:
            msg = mlog.recv_match(blocking=False)
            if msg is None:
                break
                
            msg_count += 1
            msg_type = msg.get_type()
            timestamp = getattr(msg, '_timestamp', 0.0)
            
            # Always keep FMT messages
            if msg_type == 'FMT':
                outfile.write(msg.get_msgbuf())
                kept_count += 1
                continue
            
            # Filter by time
            if start_time is not None and timestamp < start_time:
                continue
            if stop_time is not None and timestamp > stop_time:
                continue
                
            # Filter by type
            if keep_types is not None and msg_type not in keep_types:
                continue
            if exclude_types is not None and msg_type in exclude_types:
                continue
                
            # Write the raw message buffer
            outfile.write(msg.get_msgbuf())
            kept_count += 1
            
            if verbose and msg_count % 20000 == 0:
                print(f"... processed {msg_count} messages, kept {kept_count}")
                
    print(f"Done. Processed {msg_count} messages, kept {kept_count}")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--types', help='Comma separated list of message types to keep')
    parser.add_argument('--exclude', help='Comma separated list of message types to exclude')
    parser.add_argument('--start', type=float, help='Start time (seconds)')
    parser.add_argument('--stop', type=float, help='Stop time (seconds)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-r', '--recurse', action='store_true', help='Recurse into directories')
    parser.add_argument('path', nargs='+', help='Input BIN file(s) or directories')
    
    args = parser.parse_args()
    
    files = util.expand_path(args.path, args.recurse, '.BIN')
    print(f"Processing {len(files)} files")
    
    keep_types = args.types.split(',') if args.types else None
    exclude_types = args.exclude.split(',') if args.exclude else None
    
    for input_file in files:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_filtered{ext}"
        filter_bin(input_file, output_file, keep_types, exclude_types, args.start, args.stop, args.verbose)

if __name__ == '__main__':
    main()
