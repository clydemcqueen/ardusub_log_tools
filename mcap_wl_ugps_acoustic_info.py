#!/usr/bin/env python3

"""
Read Water Linked UGPS extension logs from an MCAP file and print a summary of acoustic tracking performance.
"""

import argparse

import mcap_explode_extension_logs
import util

TRANSDUCER_DESCRIPTIONS = [
    "Transducer 0 (R1, -x, aft)",
    "Transducer 1 (R2, +y, starboard)",
    "Transducer 2 (R3, +x, forward)",
    "Transducer 3 (R4, +z, down)",
]


class AcousticLogInfo:
    def __init__(self, mcap_file: str):
        self.mcap_file = mcap_file
        self.passes = []

    def read(self):
        self.passes = mcap_explode_extension_logs.parse_waterlinked_ugps(self.mcap_file)

    def report(self):
        print(f"Reading {self.mcap_file}")
        if not self.passes:
            print("  No waterlinked.ugps extension logs found.")
            return

        total_readings = len(self.passes)
        first_time = self.passes[0].get("timestamp")
        last_time = self.passes[-1].get("timestamp")

        if first_time is not None and last_time is not None:
            duration = last_time - first_time
            print(f"  Log span: {util.time_str(first_time)} to {util.time_str(last_time)} ({duration:.1f} s)")

        print(f"  Total readings: {total_readings}")

        # 1. Acoustic Fixes
        valid_fixes = [p for p in self.passes if p.get("acoustic_valid") is True]
        pct_fixes = (100.0 * len(valid_fixes) / total_readings) if total_readings > 0 else 0.0
        print("\n  Acoustic fixes:")
        print(f"    Valid acoustic fixes: {len(valid_fixes)} / {total_readings} ({pct_fixes:.2f}%)")

        if valid_fixes:
            first_fix_ts = valid_fixes[0].get("timestamp")
            print(
                f"    Time of first valid acoustic fix: {util.time_str(first_fix_ts)} (timestamp: {first_fix_ts:.3f})"
            )
        else:
            print("    Time of first valid acoustic fix: None")

        # 2. Transducer Readings
        print("\n  Transducer valid readings:")
        for idx in range(4):
            valid_count = sum(
                1 for p in self.passes if p.get(f"receiver_valid_{idx}") == 1 or p.get(f"receiver_valid_{idx}") is True
            )
            pct = (100.0 * valid_count / total_readings) if total_readings > 0 else 0.0
            print(f"    {TRANSDUCER_DESCRIPTIONS[idx]:35s}: {valid_count:5d} / {total_readings} ({pct:6.2f}%)")

        # 3. Simultaneous valid transducer count distribution
        simultaneous_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        for p in self.passes:
            count = sum(
                1 for idx in range(4) if p.get(f"receiver_valid_{idx}") == 1 or p.get(f"receiver_valid_{idx}") is True
            )
            simultaneous_counts[count] += 1

        print("\n  Simultaneous valid transducers distribution:")
        print(
            f"    4 valid (full 3D solution)   : {simultaneous_counts[4]:5d} / {total_readings} ({100.0 * simultaneous_counts[4] / total_readings:6.2f}%)"
        )
        print(
            f"    3 valid (minimum 3D solution): {simultaneous_counts[3]:5d} / {total_readings} ({100.0 * simultaneous_counts[3] / total_readings:6.2f}%)"
        )
        print(
            f"    2 valid (no 3D solution)     : {simultaneous_counts[2]:5d} / {total_readings} ({100.0 * simultaneous_counts[2] / total_readings:6.2f}%)"
        )
        print(
            f"    1 valid (no 3D solution)     : {simultaneous_counts[1]:5d} / {total_readings} ({100.0 * simultaneous_counts[1] / total_readings:6.2f}%)"
        )
        print(
            f"    0 valid (no signal)          : {simultaneous_counts[0]:5d} / {total_readings} ({100.0 * simultaneous_counts[0] / total_readings:6.2f}%)"
        )

        # 4. Transducer Signal Levels (mean RSSI and NSD)
        rssi_avgs = []
        nsd_avgs = []
        for idx in range(4):
            rssi_vals = [p[f"receiver_rssi_{idx}"] for p in self.passes if p.get(f"receiver_rssi_{idx}") is not None]
            nsd_vals = [p[f"receiver_nsd_{idx}"] for p in self.passes if p.get(f"receiver_nsd_{idx}") is not None]
            rssi_avg = sum(rssi_vals) / len(rssi_vals) if rssi_vals else None
            nsd_avg = sum(nsd_vals) / len(nsd_vals) if nsd_vals else None
            rssi_avgs.append(rssi_avg)
            nsd_avgs.append(nsd_avg)

        if any(r is not None for r in rssi_avgs) or any(n is not None for n in nsd_avgs):
            print("\n  Average transducer signal levels:")
            for idx in range(4):
                rssi_str = f"{rssi_avgs[idx]:6.1f} dBm" if rssi_avgs[idx] is not None else "   N/A    "
                nsd_str = f"{nsd_avgs[idx]:6.1f} dB" if nsd_avgs[idx] is not None else "   N/A  "
                print(f"    {TRANSDUCER_DESCRIPTIONS[idx]:35s}: mean RSSI = {rssi_str}, mean NSD = {nsd_str}")

    def read_and_report(self):
        self.read()
        self.report()


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories")
    parser.add_argument("-r", "--recurse", action="store_true", help="enter directories looking for MCAP files")
    args = parser.parse_args()

    files = util.expand_path(args.paths, args.recurse, ".mcap")
    print(f"Processing {len(files)} files")

    for file in files:
        print("-------------------")
        info = AcousticLogInfo(file)
        info.read_and_report()


if __name__ == "__main__":
    main()
