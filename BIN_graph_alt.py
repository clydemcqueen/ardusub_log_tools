#!/usr/bin/env python3

"""
Read an ArduSub BIN file and produce a graph of altitude readings.
Shows AHR2.Alt, -XKF1.PD, BARO[1].Alt, POS.Alt, and POS.RelHomeAlt.
Saves the graph as a PDF with a title and path that matches the BIN file.
"""

import argparse
import os

import matplotlib.pyplot as plt

import file_reader


def process_reader(reader):
    ahr2_t = []
    ahr2_alt = []

    xkf1_t = []
    xkf1_pd = []

    baro1_t = []
    baro1_alt = []

    orgn0_t = []
    orgn0_alt = []

    orgn1_t = []
    orgn1_alt = []

    pos_t = []
    pos_alt = []
    pos_relhomealt = []

    for msg in reader:
        msg_type = msg.get_type()
        data = msg.to_dict()

        if "TimeUS" not in data:
            continue

        t = data["TimeUS"] / 1e6

        if msg_type == "AHR2":
            ahr2_t.append(t)
            ahr2_alt.append(data["Alt"])
        elif msg_type == "XKF1":
            xkf1_t.append(t)
            xkf1_pd.append(-data["PD"])
        elif msg_type == "BARO":
            if data.get("I", 0) == 1:
                baro1_t.append(t)
                baro1_alt.append(data["Alt"])
        elif msg_type == "ORGN":
            orgn_type = data.get("Type", 0)
            if orgn_type == 0:
                orgn0_t.append(t)
                orgn0_alt.append(data["Alt"])
            elif orgn_type == 1:
                orgn1_t.append(t)
                orgn1_alt.append(data["Alt"])
        elif msg_type == "POS":
            pos_t.append(t)
            pos_alt.append(data["Alt"])
            pos_relhomealt.append(data["RelHomeAlt"])

    if not ahr2_t and not xkf1_t and not baro1_t and not orgn0_t and not orgn1_t and not pos_t:
        print(f"No altitude data found in {reader.name}")
        return

    # Plot
    plt.figure(figsize=(10, 6))
    if ahr2_t:
        plt.plot(ahr2_t, ahr2_alt, label="AHR2.Alt (AHRS2.altitude)")
    if xkf1_t:
        plt.plot(xkf1_t, xkf1_pd, label="-XKF1.PD")
    if baro1_t:
        plt.plot(baro1_t, baro1_alt, label="BARO[1].Alt")
    if orgn0_t:
        plt.plot(orgn0_t, orgn0_alt, "o", label="ORGN[ekf_origin].Alt")
    if orgn1_t:
        plt.plot(orgn1_t, orgn1_alt, "o", label="ORGN[ahrs_home].Alt")
    if pos_t:
        plt.plot(pos_t, pos_alt, label="POS.Alt (GPI.alt, VFR_HUD.alt)")
        plt.plot(pos_t, pos_relhomealt, label="POS.RelHomeAlt (GPI.relative_alt)")

    plt.xlabel("Time (s)")
    plt.ylabel("Altitude (m)")
    plt.title(f"Altitude for {os.path.relpath(reader.name)}")
    plt.legend()
    plt.grid(True)

    # Save to PDF
    pdf_path = os.path.splitext(reader.name)[0] + ".pdf"
    plt.savefig(pdf_path)
    plt.close()

    print(f"Saved graph to {pdf_path}")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    file_reader.add_file_args(parser, ext=".BIN")
    args = parser.parse_args()

    readers = file_reader.FileReaderList(args, ["AHR2", "XKF1", "BARO", "ORGN", "POS"], ext=".BIN")

    for reader in readers:
        print(f"Processing {reader.name}...")
        process_reader(reader)


if __name__ == "__main__":
    main()
