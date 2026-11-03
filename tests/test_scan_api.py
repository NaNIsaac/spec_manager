"""Scan commands, names and mnemonics, and scan[name], on a file written by hand.

The command forms follow the standard SPEC scan macros (SPEC manual, release 6: "Motor Scans",
"Basic Reciprocal Space Scans" and "Standard Data-File Format"). The numbers are made up.
"""

import numpy as np
import pytest

from splotter.command import ScanCommand, Space
from splotter.names import Names
from splotter.spec import Spec

HEADER = """\
#F manual.spec
#E 1000000000
#D Wed Feb 17 19:22:16 1994
#C hand-written, not a measurement
#O0 Two Theta  Theta  Chi  Phi
#O1 Sample_X  Sample_Y
#o0 tth th chi phi
#o1 sx sy
#J0 Seconds  Monitor  Detector
#j0 sec mon det
"""

SCANS = """
#S 1 ascan  tth 26 28  2 60
#D Wed Feb 17 19:25:55 1994
#T 60  (Seconds)
#P0 26 13 90 0
#P1 0.5 -0.3
#N 7
#L Two Theta  H  K  L  Epoch  Monitor  Detector
26 0 0 1 10 1000 5
27 0 0 1 70 1001 50
28 0 0 1 130 999 6

#S 2 lup  th -1 1  2 -1000
#D Wed Feb 17 19:30:00 1994
#M 1000  (Monitor)
#P0 27 13.5 90 0
#P1 0.5 -0.3
#N 7
#L Theta  H  K  L  Epoch  Seconds  Detector
12.5 0 0 1 200 1.1 3
13.5 0 0 1 202 1.0 40
14.5 0 0 1 204 1.2 4

#S 3 mesh  sy -1 1 2  sx 0 1 1  0.5
#D Wed Feb 17 19:40:00 1994
#P0 27 13.5 90 0
#P1 0 -1
#N 4
#L Sample_Y  Sample_X  Epoch  Detector
-1 0 300 1
0 0 301 2
1 0 302 3
-1 1 303 4
0 1 304 90
1 1 305 6

#S 4 a2scan  sx 0 1  sy 0 2  2 1
#D Wed Feb 17 19:50:00 1994
#P0 27 13.5 90 0
#P1 0 0
#N 4
#L Sample_X  Sample_Y  Epoch  Detector
0 0 400 1
0.5 1 401 2
1 2 402 3

#S 5 th2th 1 2 1 1
#D Wed Feb 17 20:00:00 1994
#P0 27 13.5 90 0
#P1 0 0
#N 4
#L Two Theta  Theta  Epoch  Detector
28 14 500 1
29 14.5 501 2

#S 6 hklmesh  H 0.9 1.1 1  K 0 0.2 1  1
#D Wed Feb 17 20:10:00 1994
#P0 27 13.5 90 0
#P1 0 0
#N 4
#L H  K  L  Detector
0.9 0 0 1
1.1 0 0 2
0.9 0.2 0 3
1.1 0.2 0 4

#S 7 timescan 1 10
#D Wed Feb 17 20:20:00 1994
#P0 27 13.5 90 0
#P1 0 0
#N 2
#L Epoch  Detector
600 1
601 2
"""

RESTART = """
#F manual.spec
#E 1000003600
#D Wed Feb 17 20:22:16 1994
#O0 Stage X  Stage Z
#o0 x z

#S 8 dscan  z -0.5 0.5  1 1
#D Wed Feb 17 20:30:00 1994
#P0 3 4
#N 3
#L Stage Z  Epoch  Detector
3.5 10 1
4.5 11 2
"""


@pytest.fixture
def spec(tmp_path):
    path = tmp_path / "manual.spec"
    path.write_text(HEADER + SCANS + RESTART, encoding="utf-8")
    with Spec(path) as spec:
        return spec


@pytest.mark.parametrize(
    ("text", "kind", "axes", "intervals", "points", "relative", "space"),
    [
        ("ascan  tth 26 28  20 60", "ascan", ["tth"], (20,), 21, False, Space.MOTOR),
        ("a2scan sx 0 1 sy 0 2 4 1", "a2scan", ["sx", "sy"], (4,), 5, False, Space.MOTOR),
        ("a3scan a 0 1 b 0 2 c 1 3 4 1", "a3scan", ["a", "b", "c"], (4,), 5, False, Space.MOTOR),
        ("mesh sy -1 1 20 sx 0 1 10 0.5", "mesh", ["sy", "sx"], (20, 10), 231, False, Space.MOTOR),
        ("dmesh sy -1 1 2 sx 0 1 1 0.5", "dmesh", ["sy", "sx"], (2, 1), 6, True, Space.MOTOR),
        ("lup th -1 1 10 1", "lup", ["th"], (10,), 11, True, Space.MOTOR),
        ("dscan th -1 1 10 1", "dscan", ["th"], (10,), 11, True, Space.MOTOR),
        ("d2scan tth -1 1 th -0.5 0.5 10 1", "d2scan", ["tth", "th"], (10,), 11, True, Space.MOTOR),
        ("th2th 1 2 10 1", "th2th", ["tth", "th"], (10,), 11, True, Space.MOTOR),
        ("hscan 0.9 1.1 10 1", "hscan", ["H"], (10,), 11, False, Space.HKL),
        ("hklscan 0.9 1.1 0 0 2 2 10 1", "hklscan", ["H", "K", "L"], (10,), 11, False, Space.HKL),
        ("hklmesh H 0.9 1.1 2 K 0 0.2 2 1", "hklmesh", ["H", "K"], (2, 2), 9, False, Space.HKL),
    ],
)
def test_manual_scan_forms(text, kind, axes, intervals, points, relative, space):
    command = ScanCommand.parse(text)
    assert command.known
    assert command.kind == kind
    assert [a.name for a in command.axes] == axes
    assert (command.intervals, command.points, command.relative, command.space) == (
        intervals,
        points,
        relative,
        space,
    )
    assert command.is_mesh == (len(intervals) == 2)


def test_th2th_moves_theta_half_the_range():
    tth, th = ScanCommand.parse("th2th -2 4 10 1").axes
    assert (tth.start, tth.stop, th.start, th.stop) == (-2, 4, -1, 2)


def test_negative_time_counts_to_monitor():
    assert ScanCommand.parse("ascan th 0 1 10 -1000").counts_to_monitor
    assert not ScanCommand.parse("ascan th 0 1 10 1").counts_to_monitor


@pytest.mark.parametrize(
    "text",
    [
        "timescan 1 10",
        "ascan th 0 1 10",
        "mesh sx 0 1 x sy 0 1 2 1",
        "hklmesh H 0 1 2 H 0 1 2 1",
        "",
    ],
)
def test_unknown_or_malformed_commands_have_no_axes(text):
    command = ScanCommand.parse(text)
    assert (command.known, command.axes, command.points) == (False, (), None)


def test_names_resolve_mnemonics_only_when_rows_pair_up():
    names = Names(["Two Theta", "Sample_X"], ["tth", "sx"])
    assert names.resolve("tth") == "Two Theta"
    assert names.resolve("sample x") == "Sample_X"
    assert names.mnemonic("Sample X") == "sx"
    assert names.resolve("sx", among=["Two Theta"]) is None
    unpaired = Names(["Two Theta", "Sample_X"], ["tth"])
    assert unpaired.resolve("tth") is None
    assert unpaired.resolve("Two Theta") == "Two Theta"


def test_a_moved_motor_is_its_column_by_name_or_mnemonic(spec):
    scan = spec.get_scan(1)
    np.testing.assert_array_equal(scan["tth"], [26, 27, 28])
    np.testing.assert_array_equal(scan["Two Theta"], scan["tth"])
    np.testing.assert_array_equal(scan["det"], [5, 50, 6])


def test_a_motor_that_stayed_is_its_start_position(spec):
    scan = spec.get_scan(1)
    assert scan["sx"] == 0.5
    assert scan["Sample_Y"] == -0.3
    assert scan.positioners_at_start["Chi"] == 90
    assert "chi" in scan and "nothing" not in scan
    with pytest.raises(KeyError, match="scan 1 has no column or motor 'nothing'"):
        scan["nothing"]


def test_at_gives_every_motor_and_column_of_one_point(spec):
    values = spec.get_scan(1).at(1)
    assert values["Two Theta"] == 27
    assert values["Chi"] == 90
    assert values["Detector"] == 50


@pytest.mark.parametrize(
    ("run", "axes"),
    [
        (1, ("Two Theta",)),
        (2, ("Theta",)),
        (3, ("Sample_Y", "Sample_X")),
        (4, ("Sample_X", "Sample_Y")),
        (5, ("Two Theta", "Theta")),
        (6, ("H", "K")),
        (7, ()),
        (8, ("Stage Z",)),
    ],
)
def test_axes_come_from_the_command_and_the_header(spec, run, axes):
    assert spec.get_scan(run).axes == axes


def test_lup_counting_to_monitor(spec):
    scan = spec.get_scan(2)
    assert scan.scan_command.counts_to_monitor
    assert scan.scan_command.relative


def test_a_restart_brings_its_own_mnemonics(spec):
    scan = spec.get_scan(8)
    assert scan.motor_table.resolve("z") == "Stage Z"
    assert scan.motor_table.resolve("sx") is None
    assert spec.get_scan(1).motor_table.resolve("z") is None


def test_header_rows_stay_in_the_file_metadata(spec):
    assert spec.file_metadata["#o0"] == "tth th chi phi"
    assert spec.file_metadata["#j0"] == "sec mon det"
    assert spec.motor_names == ["Two Theta", "Theta", "Chi", "Phi", "Sample_X", "Sample_Y"]


def test_without_mnemonics_the_axes_are_the_first_columns(tmp_path):
    text = HEADER.replace("#o0 tth th chi phi\n#o1 sx sy\n", "") + SCANS
    path = tmp_path / "old.spec"
    path.write_text(text, encoding="utf-8")
    with Spec(path) as spec:
        scan = spec.get_scan(3)
    assert scan.axes == ("Sample_Y", "Sample_X")
    assert "sx" not in scan
    np.testing.assert_array_equal(scan["Sample_X"], [0, 0, 0, 1, 1, 1])


def test_a_short_p_line_is_reported(tmp_path):
    text = HEADER + SCANS.replace("#P1 0.5 -0.3\n#N 7\n#L Two Theta", "#N 7\n#L Two Theta", 1)
    path = tmp_path / "short.spec"
    path.write_text(text, encoding="utf-8")
    with Spec(path) as spec:
        warnings = spec.get_scan(1).warnings
    assert warnings == [
        "#P has 4 values for 6 motor names; the motor values are paired in order and may be wrong"
    ]
    assert spec.get_scan(3).warnings == []


def test_a_restart_without_mnemonics_does_not_inherit_the_old_ones(tmp_path):
    # the new session has as many motors as the old one, so stale #o rows would pair up silently
    restart = """
#F manual.spec
#E 1000007200
#D Wed Feb 17 21:22:16 1994
#O0 M1  M2  M3  M4
#O1 M5  M6

#S 9 ascan  M5 0 1  1 1
#D Wed Feb 17 21:30:00 1994
#P0 1 2 3 4
#P1 5 6
#N 2
#L M5  Detector
0 1
1 2
"""
    path = tmp_path / "mixed.spec"
    path.write_text(HEADER + SCANS + restart, encoding="utf-8")
    with Spec(path) as spec:
        old, new = spec.get_scan(1), spec.get_scan(9)
    assert old.motor_table.resolve("sx") == "Sample_X"
    assert (new.motor_mnemonics, new.counter_names, new.counter_mnemonics) == ([], [], [])
    assert not new.motor_table.paired
    assert "sx" not in new and new["M6"] == 6
    assert new.axes == ("M5",)


def test_hklmesh_takes_lower_case_coordinates():
    command = ScanCommand.parse("hklmesh h 0.9 1.1 2 l 0 0.2 2 1")
    assert command.known and [a.name for a in command.axes] == ["H", "L"]
