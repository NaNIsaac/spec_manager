"""The commands take motors and counters by name or mnemonic, and read axes from the scan command.

The file is the hand-written one of test_scan_api.py, with its #o and #j rows.
"""

from contextlib import nullcontext

import pytest
from synthetic_spec import write_scan_lists, write_spec
from test_scan_api import HEADER, RESTART, SCANS
from test_spec import mesh_scan, run_script

from splotter.fwhm_vs_q import scan_series
from splotter.gam_del import detector_angles
from splotter.mesh_map import SAMPLE_AXES, default_axes, load_maps, point_map, scan_map
from splotter.probe import Probe
from splotter.scan_info import point_table, scan_table
from splotter.spec import Spec, SpecScan, curve_columns


@pytest.fixture
def path(tmp_path):
    path = tmp_path / "manual.spec"
    path.write_text(HEADER + SCANS + RESTART, encoding="utf-8")
    return path


@pytest.fixture
def spec(path):
    with Spec(path) as spec:
        return spec


def test_column_and_motor_take_names_or_mnemonics(spec):
    scan = spec.get_scan(3)
    assert scan.column("sx") == scan.column("Sample X") == "Sample_X"
    assert scan.column("det") == "Detector"
    assert scan.column("tth") is None  # a motor that stayed is no column
    assert scan.motor("tth") == "Two Theta"
    assert scan.motor("det") is None


def test_a_mesh_maps_the_same_by_mnemonic(spec):
    scan = spec.get_scan(3)
    by_name = scan_map(scan, "Detector", "Sample_X", "Sample_Y")
    by_mnemonic = scan_map(scan, "det", "sx", "sy")
    assert by_mnemonic.values.tolist() == by_name.values.tolist() == [[1, 4], [2, 90], [3, 6]]
    assert by_mnemonic.x_edges.tolist() == by_name.x_edges.tolist() == [-0.5, 0.5, 1.5]


def test_a_lup_is_a_line_at_the_start_position_of_the_other_motor(spec):
    m = scan_map(spec.get_scan(2), "det", "th", "tth")
    assert m.x_edges.tolist() == [12, 13, 14, 15] and m.y_edges.tolist() == [26.5, 27.5]
    assert m.values.tolist() == [[3, 40, 4]]


@pytest.mark.parametrize("run", [4, 6, 7])
def test_scans_that_are_no_map_of_two_motors_are_refused(spec, run):
    with pytest.raises(SystemExit, match="neither a mesh nor a line scan of one motor"):
        scan_map(spec.get_scan(run), "det", "sx", "sy")


def test_without_mnemonics_only_names_resolve():
    with pytest.raises(SystemExit, match="not sx and sy"):
        scan_map(mesh_scan(), "imtot", "sx", "sy")


def test_default_axes_keep_the_sample_motors_or_follow_the_mesh(spec):
    assert default_axes([spec.get_scan(3)]) == SAMPLE_AXES
    assert default_axes([spec.get_scan(2)]) == SAMPLE_AXES
    chi_phi = SpecScan(
        scan_no=1,
        command="mesh chi 0 1 1  phi 0 1 1  1",
        motor_names=[],
        columns=["Chi", "Phi", "Detector"],
        data=[[0, 0, 1], [1, 0, 2], [0, 1, 3], [1, 1, 4]],
    )
    # the outer motor across, the inner one down
    assert default_axes([chi_phi]) == ("Phi", "Chi")


def test_load_maps_gives_the_names_of_what_it_drew(path):
    _, maps, counter, x, y = load_maps(path, ["3"], "det")
    assert (counter, x, y) == ("Detector", "Sample_X", "Sample_Y")
    assert maps[0].values.tolist() == [[1, 4], [2, 90], [3, 6]]


def test_probe_shows_names_given_by_mnemonic(spec):
    scan = spec.get_scan(3)
    probe = Probe(
        scan,
        scan_map(scan, "det", "sx", "sy"),
        point_map(scan, "sx", "sy"),
        "sx",
        "sy",
        ["det", "tth"],
    )
    assert probe.values_at(4) == {"Sample_X": 1, "Sample_Y": 0, "Detector": 90, "Two Theta": 27}


def test_info_tables_take_mnemonics(spec):
    points = point_table(spec.get_scan(3), ["sx", "det", "tth"])
    assert points["sx"].tolist() == [0, 0, 0, 1, 1, 1] and points["tth"].tolist() == [27] * 6
    starts = scan_table([spec.get_scan(1), spec.get_scan(2)], ["tth", "sx"])
    assert starts.to_dict("list") == {"tth": [26, 27], "sx": [0.5, 0.5]}


@pytest.mark.parametrize(
    ("run", "counter", "columns"),
    [
        (1, "det", ("Two Theta", "Detector")),
        (2, "det", ("Theta", "Detector")),
        (7, "det", ("Time", "Detector")),
        # the restarted session has no #j: its counters go by name only
        (8, "Detector", ("Stage Z", "Detector")),
    ],
)
def test_a_curve_runs_along_the_axis_of_its_command(spec, run, counter, columns):
    assert curve_columns(spec.get_scan(run), counter) == columns
    with pytest.raises(SystemExit) if run == 8 else nullcontext():
        curve_columns(spec.get_scan(run), "det")


def test_a_curve_without_the_counter_names_the_columns(spec):
    with pytest.raises(SystemExit, match="no counter 'imroi1'; columns: Theta, H, K, L"):
        curve_columns(spec.get_scan(2), "imroi1")


def test_detector_angles_come_from_the_start_positions(spec):
    assert detector_angles(spec.get_scan(1), "tth", "Theta") == (26, 13)
    with pytest.raises(SystemExit, match="no motor 'Gamma'"):
        detector_angles(spec.get_scan(1), "Gamma", "Delta")


def test_fwhm_takes_scans_without_a_scan_list(tmp_path, monkeypatch):
    runs = write_scan_lists(tmp_path / "data")[:4]
    spec_file = write_spec(tmp_path / "s.spec", runs)
    with Spec(spec_file) as spec:
        series = scan_series(spec, [str(run) for run in runs], "Gamma", "Delta")
    # the generator writes #P0 as scan_no % 10 + motor index; Delta is motor 0, Gamma motor 5
    assert [(g, d) for _, g, d in series] == [(run % 10 + 5, run % 10) for run in runs]
    out = tmp_path / "fwhm.png"
    args = [spec_file, "--scans", *runs[:2], "--scans", *runs[2:], "--energy", 5.55]
    run_script("fwhm", [*args, "--save", out], monkeypatch)
    assert out.exists()
    with pytest.raises(SystemExit):
        run_script("fwhm", [spec_file, "--energy", 5.55], monkeypatch)
    with pytest.raises(SystemExit):
        run_script("fwhm", [*args, "--labels", "one"], monkeypatch)


def test_rock_plots_a_time_scan_against_time(path, tmp_path, monkeypatch):
    out = tmp_path / "rock.png"
    run_script("rock", [path, 7, "--counter", "det", "--save", out], monkeypatch)
    assert out.exists()
