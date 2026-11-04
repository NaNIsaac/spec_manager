import argparse
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from splotter.command import ScanCommand, Space
from splotter.names import Names, name_key
from splotter.names import find as find_name

__all__ = ["Spec", "SpecScan", "curve_columns", "find_name", "name_key", "run_id", "scan_or_exit"]

NAME_GAP = re.compile(r"\s{2,}|\t")


def split_names(text: str, expected: int | None = None) -> list[str]:
    """Names on an #O or #L line. Two spaces separate them; one space can be inside: "Sample X".

    A line that misses the count #N declares and fits it when split on any space is taken that way.
    """
    names = NAME_GAP.split(text.strip())
    if expected is not None and len(names) != expected and len(text.split()) == expected:
        return text.split()
    return names


def data_row(line: str, n_columns: int) -> list[float] | None:
    """The numbers of a data line, or None for what macros printed between the data.

    float() would accept the underscore of a label such as 6_1.
    """
    if not n_columns or "_" in line:
        return None
    parts = line.split()
    if len(parts) != n_columns:
        return None
    try:
        return [float(part) for part in parts]
    except ValueError:
        return None


HEADER_ROW = re.compile(r"#([OoJj])(\d+)(?:\s|$)")


def _xml_to_dict(element: ET.Element) -> Any:
    """An element as nested dicts: a leaf as int, float or text, a repeated tag as a list."""
    if len(element) == 0:
        val = element.text.strip() if element.text else ""
        if val.isdigit():
            return int(val)
        try:
            return float(val)
        except ValueError:
            return val

    result = {}
    # a parent's attributes, such as number="1", sit among its children
    if element.attrib:
        result.update(element.attrib)

    for child in element:
        child_data = _xml_to_dict(child)
        tag = child.tag

        if tag in result:
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(child_data)
        else:
            result[tag] = child_data
    return result


class ReadOnUse:
    """A field of SpecScan that the parser leaves as text until it is first asked for.

    Turning every number of a file into a float takes most of a parse, while a command mostly
    looks at a few scans. The data lines are read into arrays when the rows, the count of skipped
    lines or the frame are first wanted, and the arrays into lists only for the rows.
    """

    def __init__(self, default: Any, convert):
        self.default, self.convert = default, convert

    def __set_name__(self, owner: type, name: str) -> None:
        self.name, self.attribute = name, f"_{name}_value"

    def __get__(self, scan: "SpecScan | None", owner: type | None = None) -> Any:
        if scan is None:
            return self.default
        if scan._lines is not None:
            scan._read_lines()
        if self.name == "data" and scan._arrays is not None:
            arrays, scan._arrays = scan._arrays, None
            getattr(scan, self.attribute).extend(row for array in arrays for row in array.tolist())
            scan._rows_from_file = True
        return getattr(scan, self.attribute)

    def __set__(self, scan: "SpecScan", value: Any) -> None:
        setattr(scan, self.attribute, self.convert(value))
        if self.name == "data":
            scan._arrays, scan._rows_from_file = None, False


@dataclass
class SpecScan:
    scan_no: int
    command: str
    motor_names: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    columns: list[str] = field(default_factory=list)
    data: list[list[float]] = ReadOnUse(
        (), lambda rows: rows if isinstance(rows, list) else [*rows]
    )
    time: datetime = field(default_factory=datetime.now)
    # lines between the data that are not a row of the #L columns
    skipped_lines: int = ReadOnUse(0, int)
    label: str = ""  # the run number, or 12.2 for the second scan numbered 12
    motor_mnemonics: list[str] = field(default_factory=list)
    counter_names: list[str] = field(default_factory=list)
    counter_mnemonics: list[str] = field(default_factory=list)
    _raw_p_values: list[float] = field(default_factory=list, repr=False)
    _raw_uxml: list[str] = field(default_factory=list, repr=False)
    _uxml_dict: dict[str, Any] | None = field(default=None, repr=False, init=False)
    # the data lines the parser kept, each run under the #L width it follows; None once read
    _lines: list[tuple[int, list[str]]] | None = field(
        default=None, repr=False, init=False, compare=False
    )
    # the rows read from those lines, one array per run, until the rows are asked for as lists
    _arrays: list[np.ndarray] | None = field(default=None, repr=False, init=False, compare=False)
    _rows_from_file: bool = field(default=False, repr=False, init=False, compare=False)

    def __post_init__(self) -> None:
        self.label = self.label or str(self.scan_no)

    def _read_lines(self) -> None:
        lines, self._lines = self._lines, None
        arrays, skipped = [], 0
        for n_columns, run in lines:
            tokens, kept = [], 0
            for line in run:
                parts = line.split()
                # float() would accept the underscore of a label such as 6_1
                if n_columns and len(parts) == n_columns and "_" not in line:
                    tokens += parts
                    kept += 1
            try:
                array = np.array(tokens, dtype=float)
            except ValueError:
                # words as many as the columns: find them line by line
                rows = [row for line in run if (row := data_row(line, n_columns)) is not None]
                array, kept = np.array(rows, dtype=float), len(rows)
            skipped += len(run) - kept
            if kept:
                arrays.append(array.reshape(kept, n_columns))
        self.skipped_lines += skipped
        rows = self._data_value
        if rows:
            # rows already made into lists, as by a scan that grew after they were read
            rows.extend(row for array in arrays for row in array.tolist())
            self._rows_from_file = True
        else:
            self._arrays = (self._arrays or []) + arrays

    @property
    def motors(self) -> dict[str, float]:
        return dict(zip(self.motor_names, self._raw_p_values, strict=False))

    @property
    def positioners_at_start(self) -> dict[str, float]:
        """Motor positions at the start of the scan (#P), by the names of #O."""
        return self.motors

    @property
    def motor_table(self) -> Names:
        return Names(self.motor_names, self.motor_mnemonics)

    @property
    def counter_table(self) -> Names:
        return Names(self.counter_names, self.counter_mnemonics)

    @cached_property
    def scan_command(self) -> ScanCommand:
        return ScanCommand.parse(self.command)

    @property
    def warnings(self) -> list[str]:
        """What makes values of this scan doubtful; the parser reads on regardless."""
        out = []
        if self._raw_p_values and len(self._raw_p_values) != len(self.motor_names):
            out.append(
                f"#P has {len(self._raw_p_values)} values for {len(self.motor_names)} motor names; "
                "the motor values are paired in order and may be wrong"
            )
        if self.motor_mnemonics and len(self.motor_mnemonics) != len(self.motor_names):
            out.append(
                f"#o has {len(self.motor_mnemonics)} mnemonics for {len(self.motor_names)} motor "
                "names; mnemonics are not used"
            )
        return out

    @property
    def axes(self) -> tuple[str, ...]:
        """The #L names of what the command scanned, in its order; () for a command not known.

        A motor typed by a mnemonic needs #o to be found. Without it, the position of the axis in
        the command is taken as its column, as the standard macros write the scanned motors first.
        A timescan or loopscan has the Time column as its axis.
        """
        command = self.scan_command
        if not command.known:
            return ()
        # the #L labels, not the frame: a scan aborted before its first point has no rows
        columns = self.columns
        found = []
        for i, axis in enumerate(command.axes):
            if command.space in (Space.HKL, Space.TIME):
                name = find_name(axis.name, columns)
            else:
                name = self.motor_table.resolve(axis.name, columns)
                if name is None and i < len(columns):
                    name = columns[i]
            if name is None:
                return ()
            found.append(name)
        return tuple(found)

    def column(self, key: str) -> str | None:
        """The #L column meant by a name or a mnemonic (#o for motors, #j for counters)."""
        return self.motor_table.resolve(key, self.columns) or self.counter_table.resolve(
            key, self.columns
        )

    def motor(self, key: str) -> str | None:
        """The motor of #O and #P meant by a name or a mnemonic."""
        return self.motor_table.resolve(key, self.motors)

    def __getitem__(self, key: str) -> np.ndarray | float:
        """A data column as an array, else a motor's start position (#P); by name or mnemonic.

        A motor the scan moved is a column, so this gives its value at every point.
        """
        columns = list(self._frame.columns)
        column = self.motor_table.resolve(key, columns) or self.counter_table.resolve(key, columns)
        if column is not None:
            return self._frame[column].to_numpy(dtype=float)
        motors = self.motors
        motor = self.motor_table.resolve(key, motors)
        if motor is not None:
            return motors[motor]
        raise KeyError(f"scan {self.label} has no column or motor {key!r}")

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        try:
            self[key]
        except KeyError:
            return False
        return True

    def at(self, point: int) -> dict[str, float]:
        """Every motor and column at one data row; a motor the scan moved takes its value there."""
        row = self._frame.iloc[point].to_dict()
        motors = {name: row.get(name, value) for name, value in self.motors.items()}
        return motors | {name: value for name, value in row.items() if name not in motors}

    @cached_property
    def _frame(self) -> pd.DataFrame:
        return self.to_dataframe()

    @property
    def uxml(self) -> dict[str, Any]:
        if self._uxml_dict is not None:
            return self._uxml_dict
        if not self._raw_uxml:
            self._uxml_dict = {}
            return {}

        xml_string = "<root>\n" + "\n".join(self._raw_uxml) + "\n</root>"
        try:
            root = ET.fromstring(xml_string)
            self._uxml_dict = _xml_to_dict(root)
        except ET.ParseError as e:
            print(f"XML Parsing Error on scan {self.scan_no}: {e}")
            self._uxml_dict = {"raw": self._raw_uxml}

        return self._uxml_dict

    def to_dataframe(self):
        if self._lines is not None:
            self._read_lines()
        if self._arrays is not None:
            # the arrays hold the rows, so the lists need not be made
            if not self.columns or not self._arrays:
                return pd.DataFrame()
            # a second #L inside a scan changes the width; keep the rows of the last one
            arrays = [array for array in self._arrays if array.shape[1] == len(self.columns)]
            if not arrays:
                return pd.DataFrame([], columns=self.columns)
            return pd.DataFrame(np.concatenate(arrays), columns=self.columns)
        if not self.columns or not self.data:
            return pd.DataFrame()
        # a second #L inside a scan changes the width; keep the rows of the last one
        rows = [row for row in self.data if len(row) == len(self.columns)]
        if rows and self._rows_from_file:
            # every value went through float(), so one array gives the frame pandas would build
            # column by column, many times faster
            return pd.DataFrame(np.array(rows, dtype=float), columns=self.columns)
        return pd.DataFrame(rows, columns=self.columns)

    @property
    def sdd_from_uxml(self) -> float | None:
        """sample_detector_distance of the ad_detector element of #UXML, if there is one."""
        try:
            return float(self.uxml.get("ad_detector", {}).get("sample_detector_distance", None))
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True, eq=False)
class ScanStarted:
    scan: SpecScan


@dataclass(frozen=True, eq=False)
class PointsAdded:
    scan: SpecScan
    lines: int  # data lines, before they are checked against the #L columns


@dataclass(frozen=True, eq=False)
class ScanEnded:
    """reason: "next scan", "aborted" (a #C comment), "complete" (the planned points), or
    "new session" (a header written by a restarted SPEC)."""

    scan: SpecScan
    reason: str


@dataclass(frozen=True, eq=False)
class FileReread:
    """The file was replaced or cut short, so it was read again from the start: every scan is new."""


Event = ScanStarted | PointsAdded | ScanEnded | FileReread

# a stat that shows no change is trusted this long; a network share may report a stale size
CHECK_SECONDS = 10.0
# bytes compared at the start of the file and before the read offset, to notice a replaced file
WINDOW = 4096


class Spec:
    """A SPEC file, read once by `with Spec(path) as spec`, and then by refresh() as it grows.

    The file is opened for each read and closed again, so that the program writing it, or a copy
    job, can rename or replace it in the meantime.
    """

    def __init__(self, file: str | Path):
        self.filepath = Path(file)
        self._reset()
        self._seen: tuple[int, int] | None = None  # size and mtime of the last stat
        self._checked = 0.0

    def _reset(self) -> None:
        self.file_metadata: dict[str, Any] = {}
        self.motor_names: list[str] = []
        self.scans: dict[int, SpecScan] = {}  # the last scan of each number
        self.all_scans: list[SpecScan] = []  # every scan, in file order
        # motor names, motor mnemonics, counter names, counter mnemonics of the current session
        self._rows: dict[str, list[str]] = {"O": self.motor_names, "o": [], "J": [], "j": []}
        self._scan: SpecScan | None = None  # the scan the next lines belong to
        self._ended = False  # whether ScanEnded was given for it
        self._data_lines: list[str] = []
        self._width = 0  # the #L width the data lines of the open scan fall under
        self._offset = 0  # bytes read, up to the end of the last complete line
        self._head = self._tail = b""
        # a last line without its newline, which `with Spec` reads as a line
        self._fed_partial = b""

    def __enter__(self):
        self._read(final=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def refresh(self) -> list[Event]:
        """What the file gained since the last read, as events. Only complete lines are read; a
        line SPEC is still writing waits for its newline."""
        try:
            stat = os.stat(self.filepath)
            unchanged = (stat.st_size, stat.st_mtime_ns) == self._seen
            if unchanged and time.monotonic() - self._checked < CHECK_SECONDS:
                return []
            return self._read(final=False)
        except FileNotFoundError:
            return []  # being replaced; the next refresh reads the new file

    def _read(self, final: bool) -> list[Event]:
        events: list[Event] = []
        stat = os.stat(self.filepath)
        with open(self.filepath, "rb") as file:
            # the size through the open file, not the stat a share may have cached
            size = file.seek(0, os.SEEK_END)
            if self._offset and not self._same_file(file, size):
                self._reset()
                events.append(FileReread())
            self._seen, self._checked = (stat.st_size, stat.st_mtime_ns), time.monotonic()
            if self._fed_partial:
                return events
            file.seek(self._offset)
            new = file.read()
        end = new.rfind(b"\n") + 1
        complete, partial = new[:end], new[end:] if final else b""
        if not complete and not partial:
            return events
        if len(self._head) < WINDOW:
            self._head = (self._head + complete)[:WINDOW]
        self._tail = (self._tail + complete[-WINDOW:])[-WINDOW:]
        self._offset += len(complete)
        self._fed_partial = partial
        text = (complete + partial).decode("utf-8", errors="replace")
        if "\r" in text:
            # as a file opened in text mode reads it
            text = text.replace("\r\n", "\n").replace("\r", "\n")
        events += self._feed(text)
        return events

    def _same_file(self, file, size: int) -> bool:
        """Whether the file still begins and continues as it did; a last line read without its
        newline must not have changed either, as it was taken as a whole line."""
        if size < self._offset + len(self._fed_partial):
            return False
        file.seek(0)
        if file.read(len(self._head)) != self._head:
            return False
        file.seek(self._offset - len(self._tail))
        if file.read(len(self._tail)) != self._tail:
            return False
        if self._fed_partial:
            return size == self._offset + len(self._fed_partial) and (
                file.read(len(self._fed_partial)) == self._fed_partial
            )
        return True

    def _feed(self, text: str) -> list[Event]:
        events: list[Event] = []
        rows = self._rows
        current_scan, ended, width = self._scan, self._ended, self._width
        data_lines, added = self._data_lines, 0
        if current_scan is not None:
            # the open scan grows: what was read from it before is read again
            current_scan.__dict__.pop("_frame", None)
            current_scan._uxml_dict = None
            if current_scan._lines is None:
                data_lines = []
                current_scan._lines = [(width, data_lines)]

        def close(reason: str | None) -> None:
            nonlocal added, ended
            if added:
                events.append(PointsAdded(current_scan, added))
                added = 0
            if reason and not ended:
                events.append(ScanEnded(current_scan, reason))
                ended = True

        # The lines of a scan, most of them data and #UXML, take the first branches: a file holds
        # close to a million lines, and each test on every line costs a share of the parse time.
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line[0] != "#":
                if current_scan is not None:
                    data_lines.append(line)
                    added += 1
                elif not self.all_scans:
                    tag = line.split(" ", 1)[0]
                    self.file_metadata[tag] = line[len(tag) :].strip()
                continue
            second = line[1:2]
            # no #F, #E or header row, so the line stays in the scan
            if current_scan is not None and second and second not in "FEOoJjS":
                if second == "U" and line.startswith("#UXML"):
                    if xml_content := line[5:].lstrip():
                        current_scan._raw_uxml.append(xml_content)
                elif second == "D" and line.startswith("#D "):
                    current_scan.time = datetime.strptime(line[3:], "%a %b %d %H:%M:%S %Y")
                elif second == "L" and line.startswith("#L "):
                    declared = current_scan.metadata.get("#N", "")
                    current_scan.columns = split_names(
                        line[3:], int(declared) if declared.isdigit() else None
                    )
                    width, data_lines = len(current_scan.columns), []
                    current_scan._lines.append((width, data_lines))
                elif second == "P" and line[2:3].isdigit():
                    current_scan._raw_p_values.extend(
                        [float(x) for x in line[line.find(" ") + 1 :].split()]
                    )
                else:
                    tag = line.split(" ", 1)[0]
                    value = line[len(tag) :].strip()
                    current_scan.metadata[tag] = value
                    if tag == "#C" and "Scan aborted" in value:
                        close("aborted")
                continue
            if line.startswith("#S "):
                parts = line.split(maxsplit=2)
                scan_no = int(parts[1])
                command = parts[2] if len(parts) > 2 else ""
                if current_scan is not None:
                    close("next scan")

                current_scan = SpecScan(
                    scan_no=scan_no,
                    command=command,
                    motor_names=rows["O"],
                    motor_mnemonics=rows["o"],
                    counter_names=rows["J"],
                    counter_mnemonics=rows["j"],
                )
                self.scans[scan_no] = current_scan
                self.all_scans.append(current_scan)
                width, data_lines, ended = 0, [], False
                current_scan._lines = [(0, data_lines)]
                events.append(ScanStarted(current_scan))
                continue

            # a restarted SPEC session writes a new file header between two scans
            header_row = HEADER_ROW.match(line)
            if line.startswith(("#F ", "#E ")) or header_row:
                if current_scan is not None:
                    close("new session")
                current_scan = None
            if line.startswith(("#F ", "#E ")):
                # a new session may lack a row the old one had; it must not inherit that row
                for kind, names in rows.items():
                    if names:
                        rows[kind] = []

            if current_scan is None:
                if header_row:
                    kind, number = header_row.groups()
                    if number == "0" and rows[kind]:
                        rows[kind] = []
                    value = line[header_row.end() :]
                    # names may hold one space (Sample X); mnemonics never do
                    rows[kind].extend(split_names(value) if kind in "OJ" else value.split())
                    if kind != "O" and not self.all_scans:
                        tag = line.split(" ", 1)[0]
                        self.file_metadata[tag] = value.strip()
                elif not self.all_scans:
                    tag = line.split(" ", 1)[0]
                    self.file_metadata[tag] = line[len(tag) :].strip()
            else:
                # what is left in a scan: a tag such as "#S" without a run, or a bare "#"
                tag = line.split(" ", 1)[0]
                current_scan.metadata[tag] = line[len(tag) :].strip()

        if current_scan is not None:
            planned = current_scan.scan_command.points
            close("complete" if planned and len(current_scan.data) >= planned else None)
        self._scan, self._ended, self._width = current_scan, ended, width
        self._data_lines = data_lines
        if any(isinstance(event, ScanStarted) for event in events):
            self._label_scans()
        return events

    def _label_scans(self) -> None:
        numbers = Counter(scan.scan_no for scan in self.all_scans)
        seen: Counter[int] = Counter()
        for scan in self.all_scans:
            seen[scan.scan_no] += 1
            repeated = numbers[scan.scan_no] > 1
            scan.label = f"{scan.scan_no}.{seen[scan.scan_no]}" if repeated else str(scan.scan_no)

    def get_scan(self, run: int | str) -> SpecScan:
        """The scan of a run number, the last one if a restart reused it; "12.1" is the first 12."""
        number, _, occurrence = str(run).partition(".")
        if not occurrence:
            return self.scans[int(number)]
        matches = [scan for scan in self.all_scans if scan.scan_no == int(number)]
        if not 1 <= int(occurrence) <= len(matches):
            raise KeyError(run)
        return matches[int(occurrence) - 1]


def run_id(text: str) -> str:
    """Argument type of a run number: 12, or 12.2 for the second scan numbered 12."""
    if not re.fullmatch(r"\d+(\.\d+)?", text):
        raise argparse.ArgumentTypeError(f"'{text}' is not a run number")
    return text


def curve_columns(scan: SpecScan, counter: str) -> tuple[str, str]:
    """The #L columns of a curve: what the command scanned first, and the counter.

    A command that is not known is taken to scan its first column, as the standard macros write it.
    """
    if not scan.data:
        raise SystemExit(f"scan {scan.label} has no data")
    column = scan.column(counter)
    if column is None:
        raise SystemExit(
            f"scan {scan.label} has no counter '{counter}'; columns: {', '.join(scan.columns)}"
        )
    return (scan.axes[0] if scan.axes else scan.columns[0]), column


def scan_or_exit(spec: Spec, run: int | str) -> SpecScan:
    try:
        return spec.get_scan(run)
    except KeyError:
        if not spec.scans:
            raise SystemExit(f"'{spec.filepath}' has no scans") from None
        raise SystemExit(f"no scan {run}; the file has scans up to {max(spec.scans)}") from None
