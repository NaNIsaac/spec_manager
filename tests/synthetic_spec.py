"""Write a SPEC-format file made of generated data, for the tests and for trying the scripts.

Nothing here is a measurement. The tags follow the SPEC layout that `spec.py` reads (file header
`#F #E #D #C #O`, per scan `#S #D #T #Q #P #UXML #N #L` and data rows); the numbers come from
`peak()` below, so a test knows the answer.

    python tests/synthetic_spec.py OUT_SPEC [DATA_DIR]    # DATA_DIR defaults to data/

It also writes the scan lists `main.py` reads (`data1.csv`, `data2.csv`, `data3.csv`: no header,
columns `scan, gamma, delta, theta`) and puts every scan they name, plus scans 879 and 1104 for
`rocking_curve.py`, into the SPEC file.
"""

import sys
from collections.abc import Iterable
from pathlib import Path

import numpy as np

MOTORS = ["Delta", "Theta", "Chi", "Phi", "Mu", "Gamma", "Sample_X", "Sample_Y",
          "SHOLD", "SDD", "DETY", "DETZ", "xt", "zt", "m1", "m2"]  # fmt: skip
SDD = 600.0
POINTS = 41
EXTRA_SCANS = [879, 1104]  # the scans rocking_curve.py reads
# (first scan number, gamma [deg], delta values [deg]) for each scan list
SCAN_LISTS = {
    "data1.csv": (101, 8.0, np.arange(20.0, 71.0, 5.0)),
    "data2.csv": (201, 12.0, np.arange(25.0, 66.0, 5.0)),
    "data3.csv": (301, 4.0, np.arange(30.0, 51.0, 5.0)),
}


def peak(scan_no: int) -> tuple[float, float, float, float]:
    """Gaussian parameters (amplitude, centre, sigma, background) for a scan number."""
    return (
        900.0 + 10 * (scan_no % 9),
        34.0 + 0.05 * (scan_no % 7),
        0.05 + 0.005 * (scan_no % 5),
        3.0,
    )


def fwhm(scan_no: int) -> float:
    return 2 * np.sqrt(2 * np.log(2)) * peak(scan_no)[2]


def header() -> list[str]:
    lines = ["#F synthetic.spec", "#E 1750000000", "#D Thu Jun 26 12:00:00 2025",
             "#C generated test data, not a measurement"]  # fmt: skip
    for i in range(0, len(MOTORS), 8):
        lines.append(f"#O{i // 8} " + "  ".join(MOTORS[i : i + 8]))
    return lines


def scan_block(scan_no: int, *, uxml: bool = True, bad_row: bool = False) -> list[str]:
    amp, centre, sigma, background = peak(scan_no)
    theta = np.linspace(centre - 0.4, centre + 0.4, POINTS)
    counts = background + amp * np.exp(-((theta - centre) ** 2) / (2 * sigma**2))
    lines = [
        f"#S {scan_no}  ascan  th {theta[0]:.4f} {theta[-1]:.4f}  {POINTS - 1} 1",
        "#D Thu Jun 26 12:24:30 2025",
        "#T 1  (Seconds)",
        "#Q 0 0 0",
        "#P0 " + " ".join(str(float(scan_no % 10 + i)) for i in range(8)),
        "#P1 " + " ".join([str(SDD)] * 8),
    ]
    if uxml:
        lines += [
            '#UXML <ad_detector prefix="SYN:CAM1:">',
            f'#UXML   <sample_detector_distance type="float">{SDD}</sample_detector_distance>',
            '#UXML   <model type="str">synthetic</model>',
            "#UXML </ad_detector>",
            '#UXML <ad_regions_of_interest prefix="SYN:CAM1:">',
            '#UXML   <roi number="1">',
            '#UXML     <min_x type="int">10</min_x>',
            "#UXML   </roi>",
            '#UXML   <roi number="2">',
            '#UXML     <min_x type="int">20</min_x>',
            "#UXML   </roi>",
            "#UXML </ad_regions_of_interest>",
        ]
    lines += ["#N 4", "#L th  Epoch  Seconds  imroi1"]
    for i, (t, c) in enumerate(zip(theta, counts, strict=True)):
        lines.append(f"{t:.6f} {i} 1 {c:.6f}")
        if bad_row and i == 3:
            lines.append("not a number row")
    lines.append("")
    return lines


def write_spec(path: Path, scan_numbers: Iterable[int], **scan_options) -> Path:
    lines = header() + [""]
    for no in scan_numbers:
        lines += scan_block(no, **scan_options)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_scan_lists(directory: Path) -> list[int]:
    """Write data1-3.csv (theta is half of 2theta, cos 2theta = cos delta cos gamma); return the scan numbers."""
    directory.mkdir(parents=True, exist_ok=True)
    numbers = []
    for name, (first, gamma, delta) in SCAN_LISTS.items():
        two_theta = np.degrees(np.arccos(np.cos(np.radians(delta)) * np.cos(np.radians(gamma))))
        rows = [
            f"{first + i},{gamma:.4f},{d:.4f},{t / 2:.4f}\n"
            for i, (d, t) in enumerate(zip(delta, two_theta, strict=True))
        ]
        (directory / name).write_text("".join(rows), encoding="utf-8")
        numbers += [first + i for i in range(len(rows))]
    return numbers


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 3:
        sys.exit(__doc__)
    numbers = write_scan_lists(Path(sys.argv[2]) if len(sys.argv) == 3 else Path("data"))
    print(write_spec(Path(sys.argv[1]), numbers + EXTRA_SCANS))
