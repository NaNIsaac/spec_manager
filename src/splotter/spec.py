import argparse
import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path
from typing import Any

import pandas as pd

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


def name_key(name: str) -> str:
    return re.sub(r"[\s_]", "", name).lower()


def find_name(name: str, names: Iterable[str]) -> str | None:
    """The entry of names meant by name; older files write Sample X where newer ones say Sample_X."""
    names = list(names)
    if name in names:
        return name
    return next((candidate for candidate in names if name_key(candidate) == name_key(name)), None)


def _xml_to_dict(element: ET.Element) -> Any:
    # 1. Handle Leaf Nodes (No children)
    if len(element) == 0:
        val = element.text.strip() if element.text else ""
        # Auto-casting logic
        if val.isdigit():
            return int(val)
        try:
            return float(val)
        except ValueError:
            return val

    # 2. Handle Nested Nodes
    result = {}
    # Capture attributes only for parent nodes if necessary,
    # but for your SPEC file, usually 'number' is the only useful one.
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


@dataclass
class SpecScan:
    scan_no: int
    command: str
    motor_names: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    columns: list[str] = field(default_factory=list)
    data: list[list[float]] = field(default_factory=list)
    time: datetime = field(default_factory=datetime.now)
    skipped_lines: int = 0  # lines between the data that are not a row of the #L columns
    label: str = ""  # the run number, or 12.2 for the second scan numbered 12
    _raw_p_values: list[float] = field(default_factory=list, repr=False)
    _raw_uxml: list[str] = field(default_factory=list, repr=False)
    _uxml_dict: dict[str, Any] | None = field(default=None, repr=False, init=False)

    def __post_init__(self) -> None:
        self.label = self.label or str(self.scan_no)

    @property
    def motors(self) -> dict[str, float]:
        return dict(zip(self.motor_names, self._raw_p_values, strict=False))

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
        if not self.columns or not self.data:
            return pd.DataFrame()
        # a second #L inside a scan changes the width; keep the rows of the last one
        rows = [row for row in self.data if len(row) == len(self.columns)]
        return pd.DataFrame(rows, columns=self.columns)

    @property
    def sdd_from_uxml(self) -> float | None:
        """UXML에서 sample_detector_distance를 직접 추출하는 헬퍼"""
        try:
            # ad_detector -> sample_detector_distance 경로 탐색
            return float(self.uxml.get("ad_detector", {}).get("sample_detector_distance", None))
        except (TypeError, ValueError):
            return None


class Spec:
    def __init__(self, file: str | Path):
        self.file_metadata: dict[str, Any] = {}
        self.motor_names: list[str] = []
        self.scans: dict[int, SpecScan] = {}  # the last scan of each number
        self.all_scans: list[SpecScan] = []  # every scan, in file order
        self._file: TextIOWrapper | None = None
        self.filepath = Path(file)

    def __enter__(self):
        self._file = open(self.filepath, encoding="utf-8", errors="replace")
        self._parse(self._file)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

    def _parse(self, file: TextIOWrapper):
        current_scan = None
        motors = self.motor_names

        for line in file:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#S "):
                parts = line.split(maxsplit=2)
                scan_no = int(parts[1])
                command = parts[2] if len(parts) > 2 else ""

                current_scan = SpecScan(scan_no=scan_no, command=command, motor_names=motors)
                self.scans[scan_no] = current_scan
                self.all_scans.append(current_scan)
                continue

            # a restarted SPEC session writes a new file header between two scans
            is_motor_line = line.startswith("#O") and line[2:3].isdigit()
            if line.startswith(("#F ", "#E ")) or is_motor_line:
                current_scan = None

            if current_scan is None:
                if is_motor_line:
                    if line.startswith("#O0") and motors:
                        motors = []
                    motors.extend(split_names(line[line.find(" ") + 1 :]))
                elif not self.all_scans:
                    tag = line.split(" ", 1)[0]
                    self.file_metadata[tag] = line[len(tag) :].strip()
            else:
                if line.startswith("#D "):
                    # line[3:]을 통해 '#D '를 제거하고 파싱
                    current_scan.time = datetime.strptime(line[3:], "%a %b %d %H:%M:%S %Y")
                elif line.startswith("#L "):
                    declared = current_scan.metadata.get("#N", "")
                    current_scan.columns = split_names(
                        line[3:], int(declared) if declared.isdigit() else None
                    )
                elif line.startswith("#P") and line[2:3].isdigit():
                    current_scan._raw_p_values.extend(
                        [float(x) for x in line[line.find(" ") + 1 :].split()]
                    )
                elif line.startswith("#UXML"):
                    xml_content = re.sub(r"^#UXML\s*", "", line)
                    if xml_content:
                        current_scan._raw_uxml.append(xml_content)
                elif line.startswith("#"):
                    tag = line.split(" ", 1)[0]
                    current_scan.metadata[tag] = line[len(tag) :].strip()
                else:
                    row = data_row(line, len(current_scan.columns))
                    if row is None:
                        current_scan.skipped_lines += 1
                    else:
                        current_scan.data.append(row)

        numbers = Counter(scan.scan_no for scan in self.all_scans)
        seen: Counter[int] = Counter()
        for scan in self.all_scans:
            seen[scan.scan_no] += 1
            if numbers[scan.scan_no] > 1:
                scan.label = f"{scan.scan_no}.{seen[scan.scan_no]}"

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


def scan_or_exit(spec: Spec, run: int | str) -> SpecScan:
    try:
        return spec.get_scan(run)
    except KeyError:
        if not spec.scans:
            raise SystemExit(f"'{spec.filepath}' has no scans") from None
        raise SystemExit(f"no scan {run}; the file has scans up to {max(spec.scans)}") from None
