from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from spec import Spec

plt.rcParams["font.weight"] = "bold"
plt.rcParams["axes.labelweight"] = "bold"


def load_scan_nums():
    files: list[str] = ['data/data1.csv', 'data/data2.csv', 'data/data3.csv']
    scan_nums: list[int] = []
    for file in files:
        df = pd.read_csv(file, header=None)
        scan_nums.extend(df.iloc[:, 0].to_list())
    return scan_nums

def main() -> None:
    file: Path = Path('data/250626')
    print(f"Load spec file: '{file}'")

    plot_config = {
        "scans": [1104, 879],
        "labels": [
            "$SrTiO_2$ annealed at 500$^\\circ$C on $Ti$ layer / $SiO_2$ substrate",
            "$SrTiO_2$ annealed at 500$^\\circ$C on $SiO_2$ substrate",
        ],
        "colors": ["black", "blue"],
        "legend_order": [1, 0]
    }
 
    print(f"Scan numbers: {plot_config['scans']}")
    scan_data: dict[int, dict] = {}
 
    with Spec(file) as spec:
        for i, scan_n in enumerate(plot_config["scans"]):
            scan = spec.get_scan(scan_n)
            command = scan.command
            print(f"Command: {command}")
            df = scan.to_dataframe()
 
            scan_data[scan_n] = {}
            scan_data[scan_n]["theta"] = df.iloc[:, 0].to_numpy()
            scan_data[scan_n]["intensity"] = df["imroi1"].to_numpy()
            scan_data[scan_n]["label"] = plot_config["labels"][i]
            scan_data[scan_n]["color"] = plot_config["colors"][i]


    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    for scan_n, data in scan_data.items():
        intensity = data['intensity']
        argmax = np.argmax(intensity)
        centered_theta = data['theta'] # - data['theta'][argmax]
        intensites_norm = intensity / intensity.max()

        ax.plot(centered_theta, intensites_norm, label=data["label"], color=data["color"])
 
    border_width = 2.0
    for side in ['top', 'bottom', 'left', 'right']:
        ax.spines[side].set_linewidth(border_width)

    ax.set_xlabel("$\\omega [\\circ]$", fontsize=14, fontweight='bold')
    ax.set_ylabel("Intensity [A.U]", fontsize=14, fontweight='bold')
    ax.set_yscale('log')
    ax.tick_params(
        direction='in',
        length=6,
        width=border_width,
        labelsize=12,
        top=True,
        right=True
    )

    handles, labels = ax.get_legend_handles_labels()
    order = plot_config["legend_order"]

    ax.legend(
        [handles[idx] for idx in order], 
        [labels[idx] for idx in order],
        frameon=True,
        fontsize=12
    )
 
    plt.show()


if __name__ == '__main__':
    main()
