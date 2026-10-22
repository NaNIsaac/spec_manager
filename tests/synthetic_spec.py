"""Write a SPEC-format file made of generated data, for the tests and for trying the scripts.

Nothing here is a measurement. The tags follow the SPEC layout that `spec.py` reads (file header
`#F #E #D #C #O`, per scan `#S #D #T #Q #P #UXML #N #L` and data rows); the numbers come from
`peak()` below, so a test knows the answer.

    python tests/synthetic_spec.py OUT [SCAN_NUMBER ...]
"""

import sys
from collections.abc import Iterable
from pathlib import Path

import numpy as np

MOTORS = ["Delta", "Theta", "Chi", "Phi", "Mu", "Gamma", "Sample_X", "Sample_Y",
          "SHOLD", "SDD", "DETY", "DETZ", "xt", "zt", "m1", "m2"]  # fmt: skip
SDD = 600.0
POINTS = 41


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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    numbers = [int(a) for a in sys.argv[2:]] or [1, 2, 3, 879, 1104]
    print(write_spec(Path(sys.argv[1]), numbers))
