from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from spec import Spec

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

    # scan_nums: list[int] = load_scan_nums()
    scan_nums: list[int] = [1340, 1104, 1586, 876, 1962]
    print(f"Scan numbers: {scan_nums}")
    scan_data: dict[int, dict] = {}
    with Spec(file) as spec:
        for scan_n in scan_nums:
            scan = spec.get_scan(scan_n)
            command = scan.command
            print(f"Command: {command}")
            df = scan.to_dataframe()
            scan_data[scan_n] = {}
            scan_data[scan_n]["theta"] = df.iloc[:, 0].to_numpy()
            scan_data[scan_n]["intensity"] = df["imroi1"].to_numpy()


    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    for scan_n, data in scan_data.items():
        intensity = data['intensity']
        argmax = np.argmax(intensity)
        centered_theta = data['theta'] - data['theta'][argmax]
        intensites_norm = intensity / intensity.max()

        ax.plot(centered_theta, intensites_norm, label=f'# {scan_n}')
    ax.set_title("Rocking Curve: $\\omega$ - Intensity (imroi1 normalized log scale)")
    ax.set_xlabel("$\\omega [^\\circ]$")
    ax.set_ylabel("Intensity [A.U]")
    ax.set_yscale('log')
    plt.legend()
    plt.show()

if __name__ == '__main__':
    main()