#!/usr/bin/env python3

"""Read a CSV file, look at the timestamp field, and report on time going backwards."""

from argparse import ArgumentParser

import pandas as pd


def check_csv(csv_path: str, timestamp_col: str = "timestamp") -> None:
    df = pd.read_csv(csv_path)

    col = timestamp_col
    if col not in df.columns:
        # Check for case-insensitive match
        matches = [c for c in df.columns if c.lower() == col.lower()]
        if matches:
            col = matches[0]
        else:
            print(f"{csv_path}: Column '{col}' not found. Available columns: {list(df.columns)}")
            return

    diffs = df[col].diff()
    bad_mask = diffs < 0

    if not bad_mask.any():
        print(f"{csv_path}: No backwards timestamps found ({len(df)} rows).")
        return

    bad_locs = [i for i, is_bad in enumerate(bad_mask) if is_bad]
    print(f"{csv_path}: Found {len(bad_locs)} instance(s) of time going backwards:")
    for loc in bad_locs:
        prev_time = df[col].iloc[loc - 1]
        curr_time = df[col].iloc[loc]
        delta = curr_time - prev_time
        row_id = df.index[loc]
        print(f"  Row {row_id}: time went backwards from {prev_time} to {curr_time} (delta: {delta})")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="+", help="path to CSV file(s)")
    parser.add_argument("--column", default="timestamp", help="name of timestamp column (default: %(default)s)")
    args = parser.parse_args()

    for p in args.path:
        check_csv(p, timestamp_col=args.column)


if __name__ == "__main__":
    main()
