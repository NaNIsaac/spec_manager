from pathlib import Path
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from io import TextIOWrapper
from typing import Any
import re

import pandas as pd


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

    _raw_p_values: list[float] = field(default_factory=list, repr=False)
    _raw_uxml: list[str] = field(default_factory=list, repr=False)
    _uxml_dict: dict[str, Any] | None = field(default=None, repr=False, init=False)

    @property
    def motors(self) -> dict[str, float]:
        return dict(zip(self.motor_names, self._raw_p_values))
    
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
        return pd.DataFrame(self.data, columns=self.columns)


class Spec:
    def __init__(self, file: str | Path):
        self.file_metadata: dict[str, Any] = {}
        self.motor_names: list[str] = []
        self.scans: dict[int, SpecScan] = {}
        self._file: TextIOWrapper | None = None
        self.filepath = Path(file)

    def __enter__(self):
        self._file = open(self.filepath, 'r', encoding='utf-8')
        self._parse(self._file)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

    def _parse(self, file: TextIOWrapper):
        current_scan = None
        
        for line in file:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#S '):
                parts = line.split(maxsplit=2)
                scan_no = int(parts[1])
                command = parts[2] if len(parts) > 2 else ""

                current_scan = SpecScan(scan_no=scan_no, command=command, motor_names=self.motor_names)
                self.scans[scan_no] = current_scan
                continue
    
            if current_scan is None:
                if line.startswith('#O') and line[2:3].isdigit():
                    self.motor_names.extend(line[line.find(' ')+1:].split())
                else:
                    tag = line.split(' ', 1)[0]
                    self.file_metadata[tag] = line[len(tag):].strip()
            else:
                if line.startswith('#L '):
                    current_scan.columns = line[3:].split()
                elif line.startswith('#P') and line[2:3].isdigit():
                    current_scan._raw_p_values.extend([float(x) for x in line[line.find(' ')+1:].split()])
                elif line.startswith('#UXML'):
                    xml_content = re.sub(r'^#UXML\s*', '', line)
                    if xml_content:
                        current_scan._raw_uxml.append(xml_content)
                elif line.startswith('#'):
                    tag = line.split(' ', 1)[0]
                    current_scan.metadata[tag] = line[len(tag):].strip()
                else:
                    try:
                        current_scan.data.append([float(x) for x in line.split()])
                    except ValueError:
                        pass
    
    def _parse_file_header(self, line: str):
        tag = line.split(' ', 1)[0]
        val = line[len(tag):].strip()
        
        if tag.startswith('#O') and tag[2:].isdigit():
            self.motor_names.extend(val.split())
        self.file_metadata[tag] = val

    def _parse_scan_header(self, scan: SpecScan, line: str):
        tag = line.split(' ', 1)[0]
        val = line[len(tag):].strip()

        if tag == '#L':
            scan.columns = val.split()
        elif tag.startswith('#P') and tag[2:].isdigit():
            scan._raw_p_values.extend(float(x) for x in val.split())
        else:
            scan.metadata[tag] = val

    def _parse_data_row(self, scan: SpecScan, line: str):
        try:
            scan.data.append([float(x) for x in line.split()])
        except ValueError:
            pass
    
    def get_scan(self, scan_no: int) -> SpecScan:
        return self.scans[scan_no]



if __name__ == '__main__':

    file = 'data/250626'
    with Spec(file) as spec:
        scan1 = spec.get_scan(1)

        if scan1 and scan1.uxml:
            center_x = scan1.uxml['ad_center']['beam_center_x']
            center_y = scan1.uxml['ad_center']['beam_center_y']
            print(f"Beam Center: ({center_x}, {center_y})")

            df_rois = pd.DataFrame(scan1.uxml['ad_regions_of_interest']['roi'])
            print("\n[ ROI DataFrame ]")
            print(df_rois[['number', 'array_port', 'min_x', 'size_x', 'min_y', 'size_y']])

            df_counters = pd.DataFrame(scan1.uxml['ad_counters']['counter'])
            print("\n[ Counters DataFrame ]")
            print(df_counters[['number', 'name', 'value_description']])