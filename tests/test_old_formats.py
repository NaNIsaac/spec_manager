"""What SPEC files of other years do, written out by hand; no file here comes from a measurement."""

import sys

import pytest

from splotter.cli import main
from splotter.mesh_map import scan_map
from splotter.spec import Spec, find_name, split_names

HEADER = """#F old
#E 1000000000
#D Sun Sep 09 10:00:00 2001
#C sixc  User = old
#O0 Delta  HXP Theta  Sample X
#O1 Sample Y  SDD
"""
SCAN = """
#S 1  ascan  sx 0 1  1 1
#D Sun Sep 09 10:01:00 2001
#T 1  (Seconds)
#P0 1 2 3
#P1 4 5
#N 3
#L Sample X  Epoch  Counter 5
0 60 10
1 62 20
"""
RESTART = """
#F old
#E 1000090000
#D Mon Sep 10 11:00:00 2001
#O0 Theta  Sample_X
#O1 Sample_Y

#S 1  ascan  sx 0 1  1 1
#D Mon Sep 10 11:01:00 2001
#P0 7 8
#P1 9
#N 3
#L Sample_X  Epoch  imtot
0 60 30
1 65 40
"""


def write(tmp_path, text):
    path = tmp_path / "old.spec"
    path.write_text(text, encoding="utf-8")
    return path


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["splotter"])
    main([*map(str, args)])


def test_names_may_hold_one_space(tmp_path):
    with Spec(write(tmp_path, HEADER + SCAN)) as spec:
        scan = spec.get_scan(1)
    assert scan.motors == {"Delta": 1, "HXP Theta": 2, "Sample X": 3, "Sample Y": 4, "SDD": 5}
    assert scan.columns == ["Sample X", "Epoch", "Counter 5"]
    assert scan.to_dataframe()["Counter 5"].tolist() == [10, 20]


def test_a_line_with_single_spaces_fits_the_declared_count():
    assert split_names("Theta H K", 3) == ["Theta", "H", "K"]
    assert split_names("Two Theta  H", 2) == ["Two Theta", "H"]


def test_a_restart_keeps_the_time_of_the_scan_before_it_and_brings_its_motors(tmp_path):
    with Spec(write(tmp_path, HEADER + SCAN + RESTART)) as spec:
        first, second = spec.get_scan("1.1"), spec.get_scan("1.2")
        assert spec.get_scan(1) is second
        assert spec.file_metadata["#E"] == "1000000000"
        assert spec.motor_names[0] == "Delta"
    assert (first.label, second.label) == ("1.1", "1.2")
    assert first.time.hour == 10 and second.time.hour == 11
    assert first.motors["SDD"] == 5
    assert second.motors == {"Theta": 7, "Sample_X": 8, "Sample_Y": 9}


def test_macro_output_stays_out_of_the_data(tmp_path):
    noise = "1\t0.000\t-0.500\t6_1\n1\t2\n1 2 x\nloopindex th del\n1_0 2 3\n"
    with Spec(write(tmp_path, HEADER + SCAN + noise + "2 64 30\n")) as spec:
        scan = spec.get_scan(1)
    assert scan.to_dataframe()["Counter 5"].tolist() == [10, 20, 30]
    assert scan.skipped_lines == 5


def test_a_second_column_line_in_a_scan_keeps_the_rows_that_fit(tmp_path):
    text = HEADER + SCAN + "#L a  b\n1 2\n"
    with Spec(write(tmp_path, text)) as spec:
        assert spec.get_scan(1).to_dataframe().to_dict("list") == {"a": [1], "b": [2]}


def test_times_of_points_follow_the_scan_not_the_file_header(tmp_path, monkeypatch, capsys):
    path = write(tmp_path, HEADER + SCAN + RESTART)
    run(monkeypatch, "info", path, "1.2", 1)
    assert "Time at point 1: 2001-09-10 11:01:05" in capsys.readouterr().out


def test_info_lists_both_scans_of_a_reused_number(tmp_path, monkeypatch, capsys):
    run(monkeypatch, "info", write(tmp_path, HEADER + SCAN + RESTART))
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines[1:]] == ["1.1", "1.2"]


def test_a_file_without_a_header_works(tmp_path, monkeypatch, capsys):
    path = write(tmp_path, SCAN)
    run(monkeypatch, "info", path, 1, 1)
    assert "Time at point 1: 2001-09-09 10:01:02" in capsys.readouterr().out


def test_a_file_without_scans_says_so(tmp_path, monkeypatch, capsys):
    path = write(tmp_path, HEADER)
    run(monkeypatch, "info", path)
    assert len(capsys.readouterr().out.splitlines()) == 1
    with pytest.raises(SystemExit, match="has no scans"):
        run(monkeypatch, "info", path, 1)


def test_bytes_that_are_not_utf8_do_not_stop_the_parser(tmp_path):
    path = tmp_path / "old.spec"
    path.write_bytes((HEADER + SCAN).encode() + b"1 66 \xff\xff\n2 68 40\n")
    with Spec(path) as spec:
        assert spec.get_scan(1).to_dataframe()["Counter 5"].tolist() == [10, 20, 40]


def test_a_missing_file_names_the_usage(monkeypatch):
    with pytest.raises(SystemExit, match="no such file: '2032'"):
        run(monkeypatch, "info", 2032)


def test_names_match_across_spaces_underscores_and_case():
    assert find_name("Sample_X", ["Sample X", "Sample_X"]) == "Sample_X"
    assert find_name("sample_x", ["Sample X"]) == "Sample X"
    assert find_name("nope", ["Sample X"]) is None


def test_mesh_map_finds_the_motors_of_an_old_file(tmp_path):
    with Spec(write(tmp_path, HEADER + SCAN)) as spec:
        m = scan_map(spec.get_scan(1), "counter_5", "Sample_X", "Sample_Y")
    assert m.values.tolist() == [[10, 20]]
    assert m.y_edges.tolist() == [3.5, 4.5]


def test_run_numbers_are_checked(tmp_path, monkeypatch):
    path = write(tmp_path, HEADER + SCAN + RESTART)
    with pytest.raises(SystemExit, match="no scan 1.3"):
        run(monkeypatch, "info", path, "1.3")
    with pytest.raises(SystemExit):
        run(monkeypatch, "info", path, "abc")
