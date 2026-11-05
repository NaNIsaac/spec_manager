import argparse
import logging
from pathlib import Path

import matplotlib.pyplot as plt

from splotter import window
from splotter.spec import Spec, curve_columns, run_id, scan_or_exit

plt.rcParams["font.weight"] = "bold"
plt.rcParams["axes.labelweight"] = "bold"
# matplotlib 3.11 reports every math font without a bold face; the figures are not affected
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="splotter rock",
        description="Normalized rocking curves of SPEC scans, log scale: the counter against what "
        "the command scanned, or against the first column for a command not known.",
    )
    parser.add_argument("spec_file", type=Path, help="the SPEC file to read")
    parser.add_argument("scans", type=run_id, nargs="+")
    parser.add_argument(
        "--labels", nargs="+", help="one legend label per scan (default: scan number)"
    )
    parser.add_argument("--counter", default="imroi1", help="name or mnemonic")
    parser.add_argument("--save", type=Path, help="write the figure here instead of showing it")
    window.add_arguments(parser)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    labels = args.labels or [str(n) for n in args.scans]

    print(f"Load spec file: '{args.spec_file}'")
    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    axes = []
    with Spec(args.spec_file) as spec:
        for scan_n, label in zip(args.scans, labels, strict=True):
            scan = scan_or_exit(spec, scan_n)
            print(f"Command: {scan.command}")
            axis, counter = curve_columns(scan, args.counter)
            axes.append(axis)
            intensity = scan[counter]
            ax.plot(scan[axis], intensity / intensity.max(), label=label)

    border_width = 2.0
    for side in ["top", "bottom", "left", "right"]:
        ax.spines[side].set_linewidth(border_width)

    ax.set_xlabel(", ".join(dict.fromkeys(axes)), fontsize=14, fontweight="bold")
    ax.set_ylabel("Intensity [A.U]", fontsize=14, fontweight="bold")
    ax.set_yscale("log")
    ax.tick_params(direction="in", length=6, width=border_width, labelsize=12, top=True, right=True)
    ax.legend(frameon=True, fontsize=12)

    if args.save:
        fig.savefig(args.save, dpi=300, bbox_inches="tight")
    else:
        window.show(args, __spec__.name)


if __name__ == "__main__":
    main()
