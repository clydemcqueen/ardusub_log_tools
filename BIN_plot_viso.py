#!/usr/bin/env python3

"""
Read BIN files and plot VISO (Visual Odometry) data alongside EKF estimated position,
EKF innovations, and thruster outputs (RCOU).

Plots:
1. VISO Delta Position (PosDX, PosDY) and Confidence (conf)
2. EKF Estimated Position (PN, PE)
3. EKF Innovations (IPN, IPE)
4. Thruster PWMs (RCOU C1..C6)
"""

import argparse
import os

import matplotlib.pyplot as plt

import util
from segment_reader import add_segment_args, choose_reader_list
from table_types import MODE_NAMES

WANTED_TYPES = ["MODE", "VISO", "XKF3", "XKF1", "RCOU"]


def get_mode_name(mode_num: int) -> str:
    return MODE_NAMES.get(mode_num, f"Unknown({mode_num})")


def process_reader(reader, pdf_outfile: str | None = None, show_plot: bool = True):
    viso_data = {"TimeUS": [], "dX": [], "dY": [], "dZ": [], "conf": []}
    ekf_innov_data = {"TimeUS": [], "IPN": [], "IPE": [], "IVN": [], "IVE": []}
    ekf_pos_data = {"TimeUS": [], "PN": [], "PE": [], "PD": []}
    rcout_data = {"TimeUS": [], "C1": [], "C2": [], "C3": [], "C4": [], "C5": [], "C6": []}
    mode_data = {"TimeUS": [], "ModeNum": []}

    print(f"Reading {reader.name}...")

    for msg in reader:
        mtype = msg.get_type()
        d = msg.to_dict()

        if "TimeUS" not in d and not hasattr(msg, "TimeUS"):
            continue
        time_us = getattr(msg, "TimeUS", d.get("TimeUS", 0))

        if mtype == "MODE":
            mode_num = d.get("ModeNum", d.get("Mode", -1))
            mode_data["TimeUS"].append(time_us)
            mode_data["ModeNum"].append(mode_num)

        elif mtype == "VISO":
            viso_data["TimeUS"].append(time_us)
            viso_data["dX"].append(d.get("PosDX", d.get("dX", 0.0)))
            viso_data["dY"].append(d.get("PosDY", d.get("dY", 0.0)))
            viso_data["dZ"].append(d.get("PosDZ", d.get("dZ", 0.0)))
            viso_data["conf"].append(d.get("conf", 0.0))

        elif mtype == "XKF3":
            if d.get("C", d.get("Core", 0)) != 0:
                continue
            ekf_innov_data["TimeUS"].append(time_us)
            ekf_innov_data["IPN"].append(d.get("IPN", 0.0))
            ekf_innov_data["IPE"].append(d.get("IPE", 0.0))
            ekf_innov_data["IVN"].append(d.get("IVN", 0.0))
            ekf_innov_data["IVE"].append(d.get("IVE", 0.0))

        elif mtype == "XKF1":
            if d.get("C", d.get("Core", 0)) != 0:
                continue
            ekf_pos_data["TimeUS"].append(time_us)
            ekf_pos_data["PN"].append(d.get("PN", d.get("PosN", 0.0)))
            ekf_pos_data["PE"].append(d.get("PE", d.get("PosE", 0.0)))
            ekf_pos_data["PD"].append(d.get("PD", d.get("PosD", 0.0)))

        elif mtype == "RCOU":
            rcout_data["TimeUS"].append(time_us)
            rcout_data["C1"].append(d.get("C1", 0))
            rcout_data["C2"].append(d.get("C2", 0))
            rcout_data["C3"].append(d.get("C3", 0))
            rcout_data["C4"].append(d.get("C4", 0))
            rcout_data["C5"].append(d.get("C5", 0))
            rcout_data["C6"].append(d.get("C6", 0))

    if not viso_data["TimeUS"] and not ekf_pos_data["TimeUS"]:
        print(f"No VISO or EKF position data found in {reader.name}")
        return

    all_ts = (
        viso_data["TimeUS"]
        + ekf_pos_data["TimeUS"]
        + ekf_innov_data["TimeUS"]
        + rcout_data["TimeUS"]
        + mode_data["TimeUS"]
    )
    t0 = min(all_ts) if all_ts else 0

    viso_t_sec = [(t - t0) / 1e6 for t in viso_data["TimeUS"]]
    ekf_pos_t_sec = [(t - t0) / 1e6 for t in ekf_pos_data["TimeUS"]]
    ekf_innov_t_sec = [(t - t0) / 1e6 for t in ekf_innov_data["TimeUS"]]
    rcout_t_sec = [(t - t0) / 1e6 for t in rcout_data["TimeUS"]]

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)

    # Subplot 1: VISO Delta Position & Confidence
    ax_viso = axes[0]
    if viso_t_sec:
        ax_viso.plot(viso_t_sec, viso_data["dX"], label="VISO dX (Forward)", color="blue")
        ax_viso.plot(viso_t_sec, viso_data["dY"], label="VISO dY (Right)", color="cyan")
        ax_viso.set_ylabel("Delta (m)")
        ax_viso.legend(loc="upper left")

        if any(c > 0 for c in viso_data["conf"]):
            ax_conf = ax_viso.twinx()
            ax_conf.plot(viso_t_sec, viso_data["conf"], label="Confidence", color="gray", linestyle="--", alpha=0.5)
            ax_conf.set_ylabel("Conf (0-1)")
            ax_conf.set_ylim(-0.05, 1.05)
            ax_conf.legend(loc="upper right")
    ax_viso.set_title(f"VISO Delta Position (from SLAM) - {os.path.basename(reader.name)}")
    ax_viso.grid(True)

    # Subplot 2: EKF Position
    ax_pos = axes[1]
    if ekf_pos_t_sec:
        ax_pos.plot(ekf_pos_t_sec, ekf_pos_data["PN"], label="EKF PN (North)", color="green")
        ax_pos.plot(ekf_pos_t_sec, ekf_pos_data["PE"], label="EKF PE (East)", color="orange")
        ax_pos.set_ylabel("Position (m)")
        ax_pos.legend(loc="upper left")
    ax_pos.set_title("EKF Estimated Position (World Frame)")
    ax_pos.grid(True)

    # Subplot 3: EKF Innovations
    ax_innov = axes[2]
    if ekf_innov_t_sec:
        ax_innov.plot(ekf_innov_t_sec, ekf_innov_data["IPN"], label="IPN (North Innov)", color="purple")
        ax_innov.plot(ekf_innov_t_sec, ekf_innov_data["IPE"], label="IPE (East Innov)", color="magenta")
        ax_innov.set_ylabel("Innovation (m)")
        ax_innov.legend(loc="upper left")
    ax_innov.set_title("EKF Innovations (High = rejecting VISO)")
    ax_innov.grid(True)

    # Subplot 4: RCOUT (Thrusters)
    ax_rcout = axes[3]
    if rcout_t_sec:
        for ch in ["C1", "C2", "C3", "C4"]:
            if rcout_data[ch]:
                ax_rcout.plot(rcout_t_sec, rcout_data[ch], label=f"Ch{ch[1]} (Thruster)")
        ax_rcout.set_ylabel("PWM")
        ax_rcout.set_xlabel("Time (s)")
        ax_rcout.legend(loc="upper left")
    ax_rcout.set_title("RCOut (Thrusters)")
    ax_rcout.grid(True)

    # Highlight POS_HOLD mode segments if available
    if mode_data["TimeUS"]:
        current_mode = None
        mode_start_t = None
        pos_hold_labeled = False

        for i, t_us in enumerate(mode_data["TimeUS"]):
            m_num = mode_data["ModeNum"][i]
            m_name = get_mode_name(m_num)
            t_sec = (t_us - t0) / 1e6
            if m_name != current_mode:
                if current_mode == "POS_HOLD" and mode_start_t is not None:
                    lbl = "POS_HOLD" if not pos_hold_labeled else None
                    pos_hold_labeled = True
                    for ax in axes:
                        ax.axvspan(mode_start_t, t_sec, color="yellow", alpha=0.15, label=lbl)
                current_mode = m_name
                mode_start_t = t_sec

        if current_mode == "POS_HOLD" and mode_start_t is not None:
            end_t_sec = (max(all_ts) - t0) / 1e6
            lbl = "POS_HOLD" if not pos_hold_labeled else None
            for ax in axes:
                ax.axvspan(mode_start_t, end_t_sec, color="yellow", alpha=0.15, label=lbl)

    plt.tight_layout()

    if pdf_outfile:
        plt.savefig(pdf_outfile)
        print(f"Plot saved to {pdf_outfile}")

    if show_plot:
        plt.show()

    plt.close(fig)

    # Stats summary
    print(f"\n--- Stats for {reader.name} ---")
    if viso_data["dX"]:
        print(
            f"  VISO PosDX mean: {sum(viso_data['dX']) / len(viso_data['dX']):.4f}, "
            f"max: {max(viso_data['dX']):.4f}, min: {min(viso_data['dX']):.4f}"
        )
        print(
            f"  VISO PosDY mean: {sum(viso_data['dY']) / len(viso_data['dY']):.4f}, "
            f"max: {max(viso_data['dY']):.4f}, min: {min(viso_data['dY']):.4f}"
        )
        if viso_data["conf"]:
            print(f"  VISO conf mean: {sum(viso_data['conf']) / len(viso_data['conf']):.2f}")

    if ekf_innov_data["IPN"]:
        print(
            f"  EKF IPN mean: {sum(ekf_innov_data['IPN']) / len(ekf_innov_data['IPN']):.4f}, "
            f"max: {max(ekf_innov_data['IPN']):.4f}, min: {min(ekf_innov_data['IPN']):.4f}"
        )
        print(
            f"  EKF IPE mean: {sum(ekf_innov_data['IPE']) / len(ekf_innov_data['IPE']):.4f}, "
            f"max: {max(ekf_innov_data['IPE']):.4f}, min: {min(ekf_innov_data['IPE']):.4f}"
        )

    if rcout_data["C1"]:
        print(f"  RCOut Ch1 mean: {sum(rcout_data['C1']) / len(rcout_data['C1']):.1f}")
        print(f"  RCOut Ch2 mean: {sum(rcout_data['C2']) / len(rcout_data['C2']):.1f}")
        print(f"  RCOut Ch3 mean: {sum(rcout_data['C3']) / len(rcout_data['C3']):.1f}")
        print(f"  RCOut Ch4 mean: {sum(rcout_data['C4']) / len(rcout_data['C4']):.1f}")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser, ".BIN")
    parser.add_argument("--pdf", action="store_true", help="Write plot to PDF instead of showing it")
    args = parser.parse_args()

    readers = choose_reader_list(args, WANTED_TYPES, ".BIN")

    for reader in readers:
        pdf_outfile = util.get_outfile_name(reader.name, "", ".pdf") if args.pdf else None
        show_plot = not args.pdf
        process_reader(reader, pdf_outfile=pdf_outfile, show_plot=show_plot)


if __name__ == "__main__":
    main()
