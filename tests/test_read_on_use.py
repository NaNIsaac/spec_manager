"""The parser keeps the data lines as text; rows, skipped lines and frames read them on first use."""

import pandas as pd
import pytest

from splotter.spec import Spec, SpecScan

TEXT = """\
#F lazy.spec
#E 1000000000
#O0 Theta  Sample_X

#S 1 ascan th 0 2 2 1
#D Wed Feb 17 19:25:55 1994
#P0 0 5
before the column names
#N 3
#L Theta  Epoch  Detector
0 10 1
1 11 not
a b c
1_0 12 3
2 12 50
#L Theta  Detector
3 4
5 6 7
"""


@pytest.fixture
def path(tmp_path):
    path = tmp_path / "lazy.spec"
    path.write_text(TEXT, encoding="utf-8")
    return path


def scan_of(path) -> SpecScan:
    with Spec(path) as spec:
        return spec.get_scan(1)


def test_rows_and_skipped_lines_are_those_of_the_file(path):
    scan = scan_of(path)
    assert scan.data == [[0, 10, 1], [2, 12, 50], [3, 4]]
    # before #L, a word in a row, words alone, an underscore, and a row of the old width
    assert scan.skipped_lines == 5
    assert scan.columns == ["Theta", "Detector"]
    assert scan.to_dataframe().to_dict("list") == {"Theta": [3.0], "Detector": [4.0]}


def test_the_frame_is_the_same_whichever_is_read_first(path):
    rows_first = scan_of(path)
    assert len(rows_first.data) == 3
    frame_first = scan_of(path)
    frame = frame_first.to_dataframe()
    pd.testing.assert_frame_equal(frame, rows_first.to_dataframe())
    assert frame_first.data == rows_first.data
    assert frame_first.skipped_lines == rows_first.skipped_lines
    assert frame_first == rows_first


def test_rows_added_after_reading_reach_the_frame(path):
    scan = scan_of(path)
    scan.data.append([7.0, 8.0])
    assert scan.to_dataframe()["Detector"].tolist() == [4.0, 8.0]


def test_a_scan_made_by_hand_keeps_its_rows_and_their_types():
    rows = [[1, 0.5], [2, 1.5]]
    scan = SpecScan(scan_no=1, command="", motor_names=[], columns=["n", "x"], data=rows)
    assert scan.data is rows and scan.skipped_lines == 0
    assert [str(t) for t in scan.to_dataframe().dtypes] == ["int64", "float64"]
    scan.data = [[3, 2.5]]
    assert scan.to_dataframe()["n"].tolist() == [3]
