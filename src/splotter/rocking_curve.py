import argparse
import logging
from pathlib import Path

import matplotlib.pyplot as plt

from splotter.spec import Spec, run_id, scan_or_exit

plt.rcParams["font.weight"] = "bold"
plt.rcParams["axes.labelweight"] = "bold"
# matplotlib 3.11 reports every math font without a bold face; the figures are not affected
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalized rocking curves (counter vs first column) of SPEC scans, log scale."
    )
    parser.add_argument("spec_file", type=Path)
    parser.add_argument("scans", type=run_id, nargs="+")
    parser.add_argument(
        "--labels", nargs="+", help="one legend label per scan (default: scan number)"
    )
    parser.add_argument("--counter", default="imroi1")
    parser.add_argument("--save", type=Path, help="write the figure here instead of showing it")
    args = parser.parse_args()
    labels = args.labels or [str(n) for n in args.scans]

    print(f"Load spec file: '{args.spec_file}'")
    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    with Spec(args.spec_file) as spec:
        for scan_n, label in zip(args.scans, labels, strict=True):
            scan = scan_or_exit(spec, scan_n)
            print(f"Command: {scan.command}")
            df = scan.to_dataframe()
            theta = df.iloc[:, 0].to_numpy()
            intensity = df[args.counter].to_numpy()
            ax.plot(theta, intensity / intensity.max(), label=label)

    border_width = 2.0
    for side in ["top", "bottom", "left", "right"]:
        ax.spines[side].set_linewidth(border_width)

    ax.set_xlabel("$\\omega [\\circ]$", fontsize=14, fontweight="bold")
    ax.set_ylabel("Intensity [A.U]", fontsize=14, fontweight="bold")
    ax.set_yscale("log")
    ax.tick_params(direction="in", length=6, width=border_width, labelsize=12, top=True, right=True)
    ax.legend(frameon=True, fontsize=12)

    if args.save:
        fig.savefig(args.save, dpi=300, bbox_inches="tight")
    else:
        plt.show()


if __name__ == "__main__":
    main()
