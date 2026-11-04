"""Time the SPEC parser on a generated file the size of a long beamtime log.

    uv run python benchmarks/parse_speed.py                    # this checkout
    uv run python benchmarks/parse_speed.py --against 0.1.4    # and a release from PyPI, by turns

The file is made from a fixed seed, about 60 MB: mostly 41-point ascans with 30 columns, a few
meshes and stopped timescans, and the #P, #G, #R and #UXML lines of each scan, in about the
proportions of a measured log. Each round times `with Spec(file)` alone and with the frame of every
scan, `--repeats` times each, in a process of its own; the table gives best and median.
"""

import argparse
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SEED = 20250626
MOTORS_PER_LINE = 8
MOTOR_LINES = 23
COUNTERS = ["H", "K", "L", "Epoch", "Seconds", "Monitor", "imtot"] + [
    f"imroi{i}" for i in range(1, 23)
]
UXML_LINES = 142


def motor_names() -> list[str]:
    return [f"motor{i:03d}" for i in range(MOTORS_PER_LINE * MOTOR_LINES)]


def header() -> list[str]:
    names = motor_names()
    lines = [
        "#F generated.spec",
        "#E 1750000000",
        "#D Thu Jun 26 12:00:00 2025",
        "#C generated for benchmarks/parse_speed.py, not a measurement",
    ]
    for i in range(MOTOR_LINES):
        part = names[i * MOTORS_PER_LINE : (i + 1) * MOTORS_PER_LINE]
        lines.append(f"#O{i} " + "  ".join(part))
        lines.append(f"#o{i} " + " ".join(name.replace("motor", "m") for name in part))
    lines.append("#J0 " + "  ".join(COUNTERS[4:]))
    lines.append("#j0 " + " ".join(f"c{i}" for i in range(len(COUNTERS) - 4)))
    return lines


def uxml(scan_no: int, rng: random.Random) -> list[str]:
    lines = []
    while len(lines) < UXML_LINES:
        n = len(lines) // 6
        lines += [
            f'#UXML <ad_roi number="{n}">',
            f'#UXML   <min_x type="int">{rng.randrange(2048)}</min_x>',
            f'#UXML   <size_x type="int">{rng.randrange(1, 64)}</size_x>',
            f'#UXML   <file_number type="int">{scan_no}</file_number>',
            f'#UXML   <exposure type="float">{rng.uniform(0.1, 2):.4f}</exposure>',
            "#UXML </ad_roi>",
        ]
    return lines[:UXML_LINES]


def row(rng: random.Random, positions: tuple[float, ...], i: int) -> str:
    hkl = [f"{rng.uniform(-1, 3):.5f}" for _ in range(3)]
    counts = [str(rng.randrange(0, 200000)) for _ in range(len(COUNTERS) - 7)]
    return " ".join(
        [
            *(f"{x:.4f}" for x in positions),
            *hkl,
            f"{1000 + 3.1 * i:.3f}",
            "1",
            str(rng.randrange(90000, 110000)),
            str(rng.randrange(10**5, 10**7)),
            *counts,
        ]
    )


def scan_block(scan_no: int, rng: random.Random) -> list[str]:
    # one mesh and one stopped timescan in every 150 scans, as in the measured log
    if scan_no % 150 == 40:
        steps = 10
        command = f"mesh m006 -1 1 {steps} m007 -1 1 {steps}  1"
        names = ["motor006", "motor007"]
        grid = [-1 + 0.2 * i for i in range(steps + 1)]
        points = [(x, y) for y in grid for x in grid]
        tail = []
    elif scan_no % 150 == 110:
        count = rng.randrange(5, 200)
        command = "timescan 1 0"
        names = ["Time"]
        points = [(float(i),) for i in range(count)]
        tail = [f"#C Thu Jun 26 13:00:00 2025.  Scan aborted after {count} points."]
    else:
        start = rng.uniform(4, 30)
        command = f"ascan  m001 {start:.4f} {start + 0.4:.4f}  40 1"
        names = ["motor001"]
        points = [(start + 0.01 * i,) for i in range(41)]
        tail = []
    lines = [
        f"#S {scan_no}  {command}",
        "#D Thu Jun 26 12:24:30 2025",
        "#T 1  (Seconds)",
    ]
    lines += [
        f"#G{i} " + " ".join(f"{rng.uniform(-9, 9):.6g}" for _ in range(14)) for i in range(4)
    ]
    lines.append("#Q " + " ".join(f"{rng.uniform(-1, 3):.6f}" for _ in range(3)))
    for i in range(MOTOR_LINES):
        values = (f"{rng.uniform(-90, 90):.4f}" for _ in range(MOTORS_PER_LINE))
        lines.append(f"#P{i} " + " ".join(values))
    lines += uxml(scan_no, rng)
    columns = names + COUNTERS
    lines += [f"#N {len(columns)}", "#L " + "  ".join(columns)]
    lines += [row(rng, positions, i) for i, positions in enumerate(points)]
    lines += tail
    lines.append(
        f"#R N= {scan_no}, MAX= {rng.uniform(1e4, 1e6):.6g}, CEN= {rng.uniform(4, 30):.6g}, "
        f"FWHM= {rng.uniform(0.01, 0.2):.6g}, COM= {rng.uniform(4, 30):.6g}, "
        f"SUM= {rng.uniform(1e5, 1e7):.6g}, Filter = 0 0 0 0, E= 5.3032"
    )
    lines.append("")
    return lines


def write_log(path: Path, megabytes: float) -> int:
    """Write the generated log; returns its number of scans."""
    rng = random.Random(SEED)
    target, size, scan_no = megabytes * 1e6, 0, 0
    with path.open("w", encoding="utf-8", newline="\n") as out:
        text = "\n".join(header()) + "\n\n"
        out.write(text)
        size += len(text)
        while size < target:
            scan_no += 1
            text = "\n".join(scan_block(scan_no, rng)) + "\n"
            out.write(text)
            size += len(text)
    return scan_no


def time_parse(path: Path, repeats: int) -> dict:
    """Times of this interpreter's splotter on the file, in seconds."""
    from importlib.metadata import version

    from splotter.spec import Spec

    def parse():
        with Spec(path) as spec:
            return spec

    def parse_and_frames():
        return sum(len(scan.to_dataframe()) for scan in parse().all_scans)

    out = {"version": version("splotter"), "python": platform.python_version()}
    for name, fn in (("parse", parse), ("parse+frames", parse_and_frames)):
        times = []
        for _ in range(repeats):
            start = time.perf_counter()
            fn()
            times.append(time.perf_counter() - start)
        out[name] = times
    out["scans"] = len(parse().all_scans)
    return out


def cpu_name() -> str:
    if sys.platform == "win32":
        import winreg

        key = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
            return winreg.QueryValueEx(handle, "ProcessorNameString")[0].strip()
    if sys.platform == "darwin":
        command = ["sysctl", "-n", "machdep.cpu.brand_string"]
        return subprocess.run(command, check=False, capture_output=True, text=True).stdout.strip()
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()


def child(command: list[str], path: Path, repeats: int) -> dict:
    command = [*command, "-I", __file__, "--time", str(path), "--repeats", str(repeats)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def fmt(times: list[float]) -> str:
    return f"{min(times):.2f} / {statistics.median(times):.2f} s"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", type=Path, help="time this file instead of a generated one")
    parser.add_argument("--megabytes", type=float, default=60)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--against", metavar="VERSION", help="a splotter release to time as well")
    parser.add_argument("--write", type=Path, help="only write the generated file here")
    parser.add_argument("--time", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.time:
        print(json.dumps(time_parse(args.time, args.repeats)))
        return
    if args.write:
        scans = write_log(args.write, args.megabytes)
        print(f"wrote {args.write}: {args.write.stat().st_size} bytes, {scans} scans")
        return

    with tempfile.TemporaryDirectory() as folder:
        path = args.file
        if path is None:
            path = Path(folder) / "generated.spec"
            write_log(path, args.megabytes)
        sides = {"this checkout": [sys.executable]}
        if args.against:
            # without --isolated, the .venv of this checkout would still supply its splotter
            sides = {
                args.against: [
                    "uv",
                    "run",
                    "--isolated",
                    "--no-project",
                    "--python",
                    platform.python_version(),
                    "--with",
                    f"splotter=={args.against}",
                    "python",
                ],
                **sides,
            }
        results = {name: {"parse": [], "parse+frames": []} for name in sides}
        for _ in range(args.rounds):
            for name, command in sides.items():
                out = child(command, path, args.repeats)
                for key in ("parse", "parse+frames"):
                    results[name][key] += out[key]
                results[name]["scans"] = out["scans"]
        size = path.stat().st_size

    names = list(sides)
    print(f"{size / 1e6:.0f} MB, {results[names[-1]]['scans']} scans")
    print(f"{cpu_name()}, {os.cpu_count()} threads; {platform.platform()}")
    print(f"Python {platform.python_version()}; best / median of {args.rounds * args.repeats}\n")
    ratio = len(names) == 2
    print("| | " + " | ".join(names) + (" | median ratio |" if ratio else " |"))
    print("|---" * (len(names) + 1 + ratio) + "|")
    for key in ("parse", "parse+frames"):
        cells = [fmt(results[n][key]) for n in names]
        if ratio:
            old, new = (statistics.median(results[n][key]) for n in names)
            cells.append(f"{old / new:.1f}x")
        print(f"| {key} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
