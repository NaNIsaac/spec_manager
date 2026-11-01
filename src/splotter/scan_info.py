import argparse
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from splotter.spec import Spec, SpecScan

CELLS_PER_ROW = 4
TIME = "time"  # for --columns: not a SPEC column, computed from Epoch or #D


def value_grid(values: dict[str, float]) -> str:
    """name = value cells in rows, so that a hundred motors fit on one screen."""
    width = max(map(len, values), default=0)
    cells = [f"{name:>{width}} = {value:<12g}" for name, value in values.items()]
    rows = [cells[i : i + CELLS_PER_ROW] for i in range(0, len(cells), CELLS_PER_ROW)]
    return "\n".join("  ".join(row).rstrip() for row in rows)


def point_values(
    motors: dict[str, float], df: pd.DataFrame, point: int
) -> tuple[dict[str, float], dict[str, float]]:
    """Motors and other columns at one point; a motor the scan moved takes its value at that point."""
    row = df.iloc[point].to_dict()
    at_point = {name: row.get(name, value) for name, value in motors.items()}
    return at_point, {name: value for name, value in row.items() if name not in motors}


def point_time(file_start: datetime, df: pd.DataFrame, point: int) -> datetime | None:
    """Clock time of a data row: Epoch counts seconds from the #D line of the file header."""
    if "Epoch" not in df.columns or df.empty:
        return None
    return file_start + timedelta(seconds=float(df["Epoch"].iloc[point]))


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


def point_table(scan: SpecScan, file_start: datetime, names: list[str]) -> pd.DataFrame:
    """The named data columns and motors of a scan, one row per point; "time" is the clock time."""
    df = scan.to_dataframe()
    table = pd.DataFrame(index=df.index.rename("point"))
    for name in names:
        if name == TIME and "Epoch" in df.columns:
            table[name] = file_start + pd.to_timedelta(df["Epoch"], unit="s")
        elif name in df.columns:
            table[name] = df[name]
        elif name in scan.motors:
            table[name] = scan.motors[name]
        else:
            raise SystemExit(f"scan {scan.scan_no} has no '{name}'; --names lists what it has")
    return table


def scan_table(scans: list[SpecScan], names: list[str]) -> pd.DataFrame:
    """The named motors of scans at their start, one row per scan; "time" is the start time."""
    rows = {}
    for scan in scans:
        row = {}
        for name in names:
            if name != TIME and name not in scan.motors:
                raise SystemExit(f"no motor '{name}'; give a scan number to read counters")
            row[name] = scan.time if name == TIME else scan.motors[name]
        rows[scan.scan_no] = row
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("scan")


def print_table(table: pd.DataFrame, csv: bool) -> None:
    print(table.to_csv(lineterminator="\n").rstrip() if csv else table.to_string())


def print_scan_list(scans: list[SpecScan], file_start: datetime) -> None:
    print(f"{'scan':>5}  {'start':<19}  {'duration':>8}  {'points':>6}  command")
    for scan in scans:
        df = scan.to_dataframe()
        end = point_time(file_start, df, -1)
        duration = str(end - scan.time) if end else "-"
        print(
            f"{scan.scan_no:>5}  {scan.time:%Y-%m-%d %H:%M:%S}  {duration:>8}  {len(df):>6}  {scan.command}"
        )


def print_scan_metadata(scan: SpecScan) -> None:
    print("\nHeader lines:")
    for tag, text in scan.metadata.items():
        print(f"{tag} {text}")
    print("\nUXML:")
    for path, value in flatten(scan.uxml):
        print(f"{path} = {value}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Times, motors, counters and metadata of the scans in a SPEC file."
    )
    parser.add_argument("spec_file", type=Path)
    parser.add_argument("scan", type=int, nargs="?", help="default: list all scans of the file")
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
        "-c",
        "--columns",
        nargs="+",
        metavar="NAME",
        help="print only these as a table: data columns or motors of the scan, and 'time'; "
        "without a scan, motors at the start of each scan",
    )
    parser.add_argument(
        "--top", type=int, metavar="N", help="with -c: the N points largest in the first column"
    )
    parser.add_argument("--csv", action="store_true", help="with -c: comma-separated output")
    parser.add_argument("--names", action="store_true", help="list the names -c accepts")
    args = parser.parse_args()
    if args.meta and args.point is not None:
        parser.error("--meta describes a scan or the file, not one point")
    if args.meta and args.columns:
        parser.error("--meta and --columns print different things")
    if (args.top or args.csv) and not args.columns:
        parser.error("--top and --csv go with --columns")
    if args.top and (args.scan is None or args.point is not None):
        parser.error("--top ranks the points of one scan")

    with Spec(args.spec_file) as spec:
        if args.scan is not None and args.scan not in spec.scans:
            raise SystemExit(f"no scan {args.scan}; the file has scans up to {max(spec.scans)}")
        file_start = datetime.strptime(spec.file_metadata["#D"], "%a %b %d %H:%M:%S %Y")

    if args.scan is None:
        scans = list(spec.scans.values())
        scans = scans[-args.last :] if args.last else scans
        if args.names:
            print("\n".join([TIME, *spec.motor_names]))
        elif args.meta:
            for tag, text in spec.file_metadata.items():
                print(f"{tag} {text}")
        elif args.columns:
            print_table(scan_table(scans, args.columns), args.csv)
        else:
            print_scan_list(scans, file_start)
        return

    scan = spec.get_scan(args.scan)
    df = scan.to_dataframe()
    if args.point is not None and not 0 <= args.point < len(df):
        raise SystemExit(f"no point {args.point}; scan {args.scan} has points 0 to {len(df) - 1}")
    if args.names:
        print("\n".join(dict.fromkeys([TIME, *df.columns, *scan.motors])))
        return
    if args.columns:
        table = point_table(scan, file_start, args.columns)
        if args.top:
            table = table.nlargest(args.top, args.columns[0])
        if args.point is not None:
            table = table.loc[[args.point]]
        print_table(table, args.csv)
        return

    print(f"Scan {scan.scan_no}: {scan.command}")
    print(f"Started: {scan.time}")
    print(f"Last point: {point_time(file_start, df, -1) or '-'}")
    print(f"Points: {len(df)}")

    if args.meta:
        print_scan_metadata(scan)
    elif args.point is None:
        print(f"\nMotors at the start of the scan:\n{value_grid(scan.motors)}")
        if not df.empty:
            summary = df.drop(columns=[c for c in df.columns if c in scan.motors]).agg(
                ["min", "max", "mean"]
            )
            summary = summary.T.assign(max_point=df.idxmax(numeric_only=True))
            print(f"\nCounters over the scan:\n{summary.to_string()}")
    else:
        motors, counters = point_values(scan.motors, df, args.point)
        print(f"\nTime at point {args.point}: {point_time(file_start, df, args.point) or '-'}")
        print(f"\nMotors at point {args.point}:\n{value_grid(motors)}")
        print(f"\nCounters at point {args.point}:\n{value_grid(counters)}")


if __name__ == "__main__":
    main()
