#!/usr/bin/env python3

"""
Read BIN files and plot VISO latency and the effect on Position Control (lurching).

Plots:
1. VISO Message Interval (Lag) vs Time.
2. Position Controller Acceleration (PSCN.AN / PSCE.AE) vs Time.
"""

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import util
from segment_reader import add_segment_args, choose_reader_list
from table_types import MODE_NAMES

MODE_COLORS = {
    "SURFTRAK": "green",
    "GUIDED": "cyan",
    "POS_HOLD": "orange",
    "ALT_HOLD": "blue",
    "STABILIZE": "magenta",
    "MANUAL": "gray",
    "SURFACE": "purple",
}


def get_mode_name(mode_num):
    return MODE_NAMES.get(mode_num, f"Unknown({mode_num})")


def load_data(reader):
    data = {
        "MODE": [],
        "VISO": [],
        "PSCN": [],
        "PSCE": [],
    }

    wanted_types = set(data.keys())

    for msg in reader:
        mtype = msg.get_type()
        if mtype in wanted_types:
            data[mtype].append(msg.to_dict())

    dfs = {}
    for k, v in data.items():
        if v:
            dfs[k] = pd.DataFrame(v)
        else:
            dfs[k] = pd.DataFrame()

    return dfs


def plot_viso(dfs, pdf_outfile, csv_outfile, show_plot):
    if dfs["VISO"].empty:
        print("No VISO data found. Cannot plot.")
        return

    # Base time on VISO
    viso_df = dfs["VISO"][["TimeUS", "dt"]].copy()
    viso_df.sort_values("TimeUS", inplace=True)

    # Calculate interval between received messages
    viso_df["VISO_Interval"] = viso_df["TimeUS"].diff() / 1e6

    t0 = viso_df["TimeUS"].iloc[0]
    viso_df["TimeS"] = (viso_df["TimeUS"] - t0) / 1e6

    if not dfs["MODE"].empty:
        mode_df = dfs["MODE"][["TimeUS", "ModeNum"]].copy()
        mode_df.sort_values("TimeUS", inplace=True)
    else:
        mode_df = pd.DataFrame([{"TimeUS": t0, "ModeNum": -1}])

    # Process PSCN and PSCE
    if not dfs["PSCN"].empty:
        pscn_df = dfs["PSCN"].copy()
        pscn_df.sort_values("TimeUS", inplace=True)
        pscn_df["TimeS"] = (pscn_df["TimeUS"] - t0) / 1e6
        if "AN" in pscn_df.columns:
            pscn_df["AccelN"] = pscn_df["AN"]
        elif "Acc" in pscn_df.columns:
            pscn_df["AccelN"] = pscn_df["Acc"]
        else:
            pscn_df["AccelN"] = np.nan
    else:
        pscn_df = pd.DataFrame({"TimeUS": [], "TimeS": [], "AccelN": []})

    if not dfs["PSCE"].empty:
        psce_df = dfs["PSCE"].copy()
        psce_df.sort_values("TimeUS", inplace=True)
        psce_df["TimeS"] = (psce_df["TimeUS"] - t0) / 1e6
        if "AE" in psce_df.columns:
            psce_df["AccelE"] = psce_df["AE"]
        elif "Acc" in psce_df.columns:
            psce_df["AccelE"] = psce_df["Acc"]
        else:
            psce_df["AccelE"] = np.nan
    else:
        psce_df = pd.DataFrame({"TimeUS": [], "TimeS": [], "AccelE": []})

    # Merge MODE onto VISO to color the lines
    merged_viso = pd.merge_asof(viso_df, mode_df, on="TimeUS", direction="backward")
    merged_viso["ModeNum"] = merged_viso["ModeNum"].ffill().bfill()
    merged_viso["ModeName"] = merged_viso["ModeNum"].map(get_mode_name)

    if csv_outfile:
        merged_viso.to_csv(csv_outfile, index=False)
        print(f"CSV saved to {csv_outfile}")

    if not (pdf_outfile or show_plot):
        return

    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(12, 12), sharex=True)

    # --- PLOT 1: VISO Interval ---
    ax_viso = axes[0]
    ax_viso.set_title("VISO Message Interval (Lag)")
    ax_viso.set_ylabel("Interval (s)")
    ax_viso.grid(True)
    ax_viso.set_ylim(0, 2.5)
    ax_viso.axhline(0.4, color="r", linestyle="--", label="400ms")

    # Color segments by mode
    merged_viso["ModeChange"] = merged_viso["ModeNum"].diff().ne(0).cumsum()

    for _, group in merged_viso.groupby("ModeChange"):
        mode_num = group["ModeNum"].iloc[0]
        mode_name = get_mode_name(mode_num)
        color = MODE_COLORS.get(mode_name, "gray")

        label = mode_name if mode_name not in [line.get_label() for line in ax_viso.get_lines()] else None
        ax_viso.plot(group["TimeS"], group["VISO_Interval"], color=color, label=label, marker=".", markersize=2)

    ax_viso.legend(loc="upper right", fontsize="small")

    # --- PLOT 2: PSCN / PSCE acceleration ---
    ax_accel = axes[1]
    ax_accel.set_title("Position Controller Acceleration (Lurching)")
    ax_accel.set_xlabel("Time (s)")
    ax_accel.set_ylabel("Acceleration (m/s/s)")
    ax_accel.grid(True)

    # Plot north acceleration
    if not pscn_df.empty:
        ax_accel.plot(pscn_df["TimeS"], pscn_df["AccelN"], color="blue", label="North accel", alpha=0.7)

    # Plot east acceleration
    if not psce_df.empty:
        ax_accel.plot(psce_df["TimeS"], psce_df["AccelE"], color="orange", label="East accel", alpha=0.7)

    # Shrink legend for accel plot to avoid covering data
    ax_accel.legend(loc="upper right", fontsize="small", ncol=2)

    plt.tight_layout()
    if pdf_outfile:
        plt.savefig(pdf_outfile)
        print(f"Plot saved to {pdf_outfile}")

    if show_plot:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_segment_args(parser, ".BIN")
    parser.add_argument("--pdf", action="store_true", help="Write plot to PDF instead of showing it")
    parser.add_argument("--csv", action="store_true", help="Write results to CSV")

    args = parser.parse_args()
    readers = choose_reader_list(args, None, ".BIN")

    for reader in readers:
        print(f"Processing {reader.name}...")
        dfs = load_data(reader)

        pdf_outfile = None
        if args.pdf:
            pdf_outfile = util.get_outfile_name(reader.name, "", ".pdf")

        csv_outfile = None
        if args.csv:
            csv_outfile = util.get_outfile_name(reader.name, "", ".csv")

        show_plot = not (args.pdf or args.csv)
        plot_viso(dfs, pdf_outfile, csv_outfile, show_plot)


if __name__ == "__main__":
    main()
