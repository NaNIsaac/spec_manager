import argparse
import shutil
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from splotter.spec import Spec, SpecScan, run_id, scan_or_exit

TIME = "time"  # for --columns: not a SPEC column, computed from Epoch and #D
CELL_GAP = 3


def terminal_width() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def value_grid(values: dict[str, float]) -> str:
    """name = value cells in as many columns as the terminal is wide, so that a hundred motors
    fit on one screen and a line is never wrapped."""
    shown = {name: f"{value:.8g}" for name, value in values.items()}
    name_width = max(map(len, shown), default=0)
    value_width = max(map(len, shown.values()), default=0)
    cell_width = name_width + 3 + value_width
    per_row = max(1, (terminal_width() + CELL_GAP) // (cell_width + CELL_GAP))
    cells = [f"{name:>{name_width}} = {value:<{value_width}}" for name, value in shown.items()]
    rows = [cells[i : i + per_row] for i in range(0, len(cells), per_row)]
    return "\n".join((" " * CELL_GAP).join(row).rstrip() for row in rows)


def point_values(
    motors: dict[str, float], df: pd.DataFrame, point: int
) -> tuple[dict[str, float], dict[str, float]]:
    """Motors and other columns at one point; a motor the scan moved takes its value at that point."""
    row = df.iloc[point].to_dict()
    at_point = {name: row.get(name, value) for name, value in motors.items()}
    return at_point, {name: value for name, value in row.items() if name not in motors}


def point_time(scan: SpecScan, df: pd.DataFrame, point: int) -> datetime | None:
    """Clock time of a data row, as #D of the scan plus the Epoch seconds since its first row.

    Epoch counts from the file header, which a restarted SPEC session writes anew, and some files
    have none. The first row follows #D by a second or two, which this leaves out.
    """
    if "Epoch" not in df.columns or df.empty:
        return None
    seconds = float(df["Epoch"].iloc[point] - df["Epoch"].iloc[0])
    return scan.time + timedelta(seconds=seconds)


def flatten(value: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """(dotted path, leaf) pairs of the nested dicts and lists that #UXML parses to."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from flatten(child, f"{prefix}.{key}" if prefix else key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from flatten(child, f"{prefix}[{i}]")
    else:
        yield prefix, value


def point_table(scan: SpecScan, names: list[str]) -> pd.DataFrame:
    """The named data columns and motors of a scan, one row per point; "time" is the clock time.

    Motors that stay put give one row, as their value would only repeat.
    """
    df = scan.to_dataframe()
    table = pd.DataFrame(index=df.index.rename("point"))
    only_fixed_motors = True
    for name in names:
        column, motor = scan.column(name) if not df.empty else None, scan.motor(name)
        if name == TIME and "Epoch" in df.columns:
            seconds = df["Epoch"] - df["Epoch"].iloc[0]
            table[name] = scan.time + pd.to_timedelta(seconds, unit="s")
            only_fixed_motors = False
        elif column:
            table[name] = df[column]
            only_fixed_motors = False
        elif motor:
            table[name] = scan.motors[motor]
        else:
            raise SystemExit(f"scan {scan.label} has no '{name}'; --names lists what it has")
    return table.iloc[:1] if only_fixed_motors else table


def scan_table(scans: list[SpecScan], names: list[str]) -> pd.DataFrame:
    """The named motors of scans at their start, one row per scan; "time" is the start time."""
    rows = {}
    for scan in scans:
        row = {}
        for name in names:
            motor = scan.motor(name)
            if name != TIME and not motor:
                raise SystemExit(
                    f"scan {scan.label} has no motor '{name}'; give a run for counters"
                )
            row[name] = scan.time if name == TIME else scan.motors[motor]
        rows[scan.label] = row
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("scan")


def print_table(table: pd.DataFrame, csv: bool) -> None:
    print(table.to_csv(lineterminator="\n").rstrip() if csv else table.to_string())


def print_scan_list(scans: list[SpecScan]) -> None:
    """One line per scan; a command that would wrap the line is cut short with an ellipsis."""
    labels = max((len(scan.label) for scan in scans), default=0)
    label_width = max(labels, len("scan"))
    prefix = f"{'scan':>{label_width}}  {'start':<19}  {'duration':>8}  {'points':>6}  "
    print(prefix + "command")
    room = max(terminal_width() - len(prefix) - 1, 10)
    for scan in scans:
        df = scan.to_dataframe()
        end = point_time(scan, df, -1)
        duration = str(end - scan.time) if end else "-"
        command = " ".join(scan.command.split())
        if len(command) > room:
            command = command[: room - 1] + "…"
        print(
            f"{scan.label:>{label_width}}  {scan.time:%Y-%m-%d %H:%M:%S}  {duration:>8}  "
            f"{len(df):>6}  {command}"
        )


def print_scan_header(scan: SpecScan, df: pd.DataFrame) -> None:
    print(f"Scan {scan.label}: {scan.command}")
    print(f"Started: {scan.time}")
    print(f"Last point: {point_time(scan, df, -1) or '-'}")
    print(f"Points: {len(df)}")


def print_scan_summary(scan: SpecScan, df: pd.DataFrame) -> None:
    """Motors at the start, and the range of each counter with the point of its maximum."""
    print(f"\nMotors at the start of the scan:\n{value_grid(scan.motors)}")
    if not df.empty:
        summary = df.drop(columns=[c for c in df.columns if c in scan.motors]).agg(
            ["min", "max", "mean"]
        )
        summary = summary.T.assign(max_point=df.idxmax(numeric_only=True))
        summary = summary.astype(object).map(lambda value: f"{value:.6g}")
        print(f"\nCounters over the scan:\n{summary.to_string(line_width=None)}")


def print_scan_metadata(scan: SpecScan) -> None:
    print("\nHeader lines:")
    for tag, text in scan.metadata.items():
        print(f"{tag} {text}")
    print("\nUXML:")
    for path, value in flatten(scan.uxml):
        print(f"{path} = {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="splotter info",
        description="Times, motors, counters and metadata of the scans in a SPEC file.",
    )
    parser.add_argument("spec_file", type=Path, help="the SPEC file to read")
    parser.add_argument(
        "scan",
        type=run_id,
        nargs="?",
        help="run number, 12.2 for the second scan numbered 12; default: list all scans of the file",
    )
    parser.add_argument(
        "point",
        type=int,
        nargs="?",
        help="data row of the scan, counted from 0 (default: summary of the whole scan)",
    )
    parser.add_argument(
        "--meta", action="store_true", help="metadata of the scan, or of the file without a scan"
    )
    parser.add_argument("--last", type=int, help="list only the last N scans")
    parser.add_argument(
        "--scans",
        type=run_id,
        nargs="+",
        metavar="RUN",
        help="with -c and no scan: only these scans, read in one go",
    )
    parser.add_argument(
        "-c",
        "--columns",
        nargs="+",
        metavar="NAME",
        help="print only these as a table: data columns or motors of the scan, by name or "
        "mnemonic, and 'time'; without a scan, motors at the start of each scan",
    )
    parser.add_argument(
        "--top", type=int, metavar="N", help="with -c: the N points largest in the first column"
    )
    parser.add_argument("--csv", action="store_true", help="with -c: comma-separated output")
    parser.add_argument("--names", action="store_true", help="list the names -c accepts")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.meta and args.point is not None:
        parser.error("--meta describes a scan or the file, not one point")
    if args.meta and args.columns:
        parser.error("--meta and --columns print different things")
    if (args.top or args.csv) and not args.columns:
        parser.error("--top and --csv go with --columns")
    if args.top and (args.scan is None or args.point is not None):
        parser.error("--top ranks the points of one scan")
    if args.scans and (args.scan is not None or not args.columns):
        parser.error("--scans goes with --columns and no scan")

    with Spec(args.spec_file) as spec:
        pass

    if args.scan is None:
        scans = spec.all_scans[-args.last :] if args.last else spec.all_scans
        if args.scans:
            scans = [scan_or_exit(spec, run) for run in args.scans]
        if args.names:
            print("\n".join([TIME, *spec.motor_names]))
        elif args.meta:
            for tag, text in spec.file_metadata.items():
                print(f"{tag} {text}")
        elif args.columns:
            print_table(scan_table(scans, args.columns), args.csv)
        else:
            print_scan_list(scans)
        return

    scan = scan_or_exit(spec, args.scan)
    df = scan.to_dataframe()
    if args.point is not None and not 0 <= args.point < len(df):
        raise SystemExit(f"no point {args.point}; scan {args.scan} has points 0 to {len(df) - 1}")
    if args.names:
        print("\n".join(dict.fromkeys([TIME, *df.columns, *scan.motors])))
        return
    if args.columns:
        table = point_table(scan, args.columns)
        if args.top:
            table = table.nlargest(args.top, args.columns[0])
        if args.point is not None:
            table = table.loc[[args.point]]
        print_table(table, args.csv)
        return

    print_scan_header(scan, df)
    if args.meta:
        print_scan_metadata(scan)
    elif args.point is None:
        print_scan_summary(scan, df)
    else:
        motors, counters = point_values(scan.motors, df, args.point)
        print(f"\nTime at point {args.point}: {point_time(scan, df, args.point) or '-'}")
        print(f"\nMotors at point {args.point}:\n{value_grid(motors)}")
        print(f"\nCounters at point {args.point}:\n{value_grid(counters)}")


if __name__ == "__main__":
    main()
