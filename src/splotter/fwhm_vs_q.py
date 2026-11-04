import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from splotter import window
from splotter.gam_del import add_angle_arguments, detector_angles
from splotter.spec import Spec, SpecScan, curve_columns, run_id, scan_or_exit

HC_KEV_ANGSTROM = 12.398419843320026  # CODATA 2018 hc [keV·Å]


def calculate_q_geometry(delta, gamma, energy_kev, g_off=0.0, d_off=0.0):
    """|Q| [1/Å] from detector gamma/delta [deg] minus their offsets; cos 2θ = cos γ · cos δ."""
    wavelength = HC_KEV_ANGSTROM / energy_kev
    gam_corr = np.radians(gamma - g_off)
    del_corr = np.radians(delta - d_off)
    two_theta = np.arccos(np.clip(np.cos(gam_corr) * np.cos(del_corr), -1.0, 1.0))
    return (4.0 * np.pi / wavelength) * np.sin(two_theta / 2.0)


def gaussian(x, a, xc, sigma, y0):
    return y0 + a * np.exp(-((x - xc) ** 2) / (2 * sigma**2))


def fit_gaussian_fwhm(x, y):
    """Fits data to Gaussian and returns FWHM."""
    if len(y) < 4:
        return np.nan

    p0 = [np.max(y) - np.min(y), x[np.argmax(y)], (np.max(x) - np.min(x)) / 10.0, np.min(y)]

    popt, _ = curve_fit(gaussian, x, y, p0=p0, maxfev=2000)
    return 2.3548 * abs(popt[2])


def csv_series(spec: Spec, csv_path: Path) -> list[tuple[SpecScan, float, float]]:
    """The scans of a scan list with the gamma and delta it gives them."""
    csv_df = pd.read_csv(csv_path, header=None, names=["scan", "gamma", "delta", "theta"])
    return [
        (scan_or_exit(spec, int(row.scan)), row.gamma, row.delta) for row in csv_df.itertuples()
    ]


def scan_series(
    spec: Spec, runs: list[str], gamma: str, delta: str
) -> list[tuple[SpecScan, float, float]]:
    """The scans of the runs with their gamma and delta at the start (#P)."""
    scans = [scan_or_exit(spec, run) for run in runs]
    return [(scan, *detector_angles(scan, gamma, delta)) for scan in scans]


def main():
    parser = argparse.ArgumentParser(
        description="Gaussian FWHM of rocking scans vs Q: one series per scan-list CSV and one per "
        "--scans, whose gamma and delta are read from the file."
    )
    parser.add_argument("spec_file", type=Path)
    parser.add_argument(
        "csv_files", type=Path, nargs="*", help="headerless CSV: scan, gamma, delta, theta"
    )
    parser.add_argument(
        "--scans",
        type=run_id,
        nargs="+",
        action="append",
        default=[],
        metavar="RUN",
        help="one series of runs, with gamma and delta from #P; give it again for another",
    )
    parser.add_argument(
        "--labels",
        nargs="+",
        help="one legend label per series, CSVs first (default: file stem, or the runs)",
    )
    parser.add_argument("--energy", type=float, required=True, help="keV")
    parser.add_argument("--gamma-offset", type=float, default=0.0, help="deg")
    parser.add_argument("--delta-offset", type=float, default=0.0, help="deg")
    parser.add_argument("--counter", default="imroi1", help="name or mnemonic")
    add_angle_arguments(parser)
    parser.add_argument("--save", type=Path, help="write the figure here instead of showing it")
    window.add_arguments(parser)
    args = parser.parse_args()
    if not args.csv_files and not args.scans:
        parser.error("give a scan-list CSV or --scans")
    labels = args.labels or [
        *(f.stem for f in args.csv_files),
        *(
            f"runs {runs[0]}-{runs[-1]}" if len(runs) > 1 else f"run {runs[0]}"
            for runs in args.scans
        ),
    ]
    if len(labels) != len(args.csv_files) + len(args.scans):
        parser.error("--labels needs one label per series")

    plt.figure(figsize=(10, 7))

    with Spec(args.spec_file) as spec:
        series = [csv_series(spec, path) for path in args.csv_files]
        series += [scan_series(spec, runs, args.gamma, args.delta) for runs in args.scans]
        for points, label in zip(series, labels, strict=True):
            group_results = []

            for scan, gamma, delta in points:
                if not scan.data:
                    continue

                q_val = calculate_q_geometry(
                    delta, gamma, args.energy, g_off=args.gamma_offset, d_off=args.delta_offset
                )
                axis, counter = curve_columns(scan, args.counter)
                y_data = scan[counter]
                fwhm = fit_gaussian_fwhm(scan[axis], y_data)

                if not np.isnan(fwhm):
                    group_results.append({"q": q_val, "fwhm": fwhm, "intensity": sum(y_data)})

            if group_results:
                res_df = pd.DataFrame(group_results).sort_values("q")
                plt.scatter(res_df["q"], res_df["fwhm"], label=label, s=50, edgecolors="k")

    plt.xlabel(r"$Q$ ($\AA^{-1}$)", fontsize=13)
    plt.ylabel(r"fwhm ($^\circ$)", fontsize=13)
    plt.title(
        rf"Broadening (Offsets: $\gamma={args.gamma_offset}^\circ, \delta={args.delta_offset}^\circ$)",
        fontsize=13,
    )
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend()
    plt.tight_layout()
    if args.save:
        plt.savefig(args.save, dpi=300, bbox_inches="tight")
    else:
        window.show(args, __spec__.name)


if __name__ == "__main__":
    main()
