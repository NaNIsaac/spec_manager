"""The SPEC parser and the scripts, on generated data (tests/synthetic_spec.py)."""

import io
import subprocess
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from synthetic_spec import (
    EXTRA_SCANS,
    MOTORS,
    POINTS,
    SDD,
    fwhm,
    header,
    line_block,
    mesh_block,
    peak,
    scan_block,
    write_scan_lists,
    write_spec,
)

from splotter.cli import main
from splotter.spec import Spec, SpecScan


def test_scan_fields(tmp_path):
    path = write_spec(tmp_path / "s.spec", [7, 12, 879])
    with Spec(path) as spec:
        assert sorted(spec.scans) == [7, 12, 879]
        assert spec.motor_names == MOTORS
        scan = spec.get_scan(12)
    assert scan.command.split()[:4] == [
        "ascan",
        "th",
        scan.command.split()[2],
        scan.command.split()[3],
    ]
    assert scan.time == datetime(2025, 6, 26, 12, 24, 30)
    assert scan.motors["Delta"] == 2.0 and scan.motors["SDD"] == SDD and len(scan.motors) == 16
    assert scan.columns == ["th", "Epoch", "Seconds", "imroi1"]
    df = scan.to_dataframe()
    assert len(df) == POINTS
    _, centre, _, _ = peak(12)
    assert df["th"].iloc[np.argmax(df["imroi1"])] == pytest.approx(centre, abs=1e-6)


def test_uxml_is_nested_and_typed(tmp_path):
    with Spec(write_spec(tmp_path / "s.spec", [1])) as spec:
        uxml = spec.get_scan(1).uxml
    assert uxml["ad_detector"]["sample_detector_distance"] == SDD
    assert uxml["ad_detector"]["model"] == "synthetic"
    rois = uxml["ad_regions_of_interest"]["roi"]
    assert [r["number"] for r in rois] == ["1", "2"]
    assert [r["min_x"] for r in rois] == [10, 20]


def test_sdd_helper_and_missing_uxml(tmp_path):
    with Spec(write_spec(tmp_path / "s.spec", [1])) as spec:
        assert spec.get_scan(1).sdd_from_uxml == SDD
    with Spec(write_spec(tmp_path / "n.spec", [1], uxml=False)) as spec:
        assert spec.get_scan(1).uxml == {}
        assert spec.get_scan(1).sdd_from_uxml is None


def test_unknown_scan_raises_key_error(tmp_path):
    with Spec(write_spec(tmp_path / "s.spec", [1])) as spec, pytest.raises(KeyError):
        spec.get_scan(2)


def test_row_that_is_not_numbers_is_skipped(tmp_path):
    with Spec(write_spec(tmp_path / "s.spec", [1], bad_row=True)) as spec:
        assert len(spec.get_scan(1).data) == POINTS


def test_a_later_scan_with_the_same_number_replaces_the_earlier(tmp_path):
    path = tmp_path / "s.spec"
    path.write_text("\n".join(scan_block(5) + scan_block(5, uxml=False)), encoding="utf-8")
    with Spec(path) as spec:
        assert len(spec.scans) == 1 and spec.get_scan(5).uxml == {}


def test_fit_gaussian_fwhm_recovers_the_generated_width():
    from splotter.fwhm_vs_q import fit_gaussian_fwhm

    for no in (3, 11, 40):
        amp, centre, sigma, bg = peak(no)
        x = np.linspace(centre - 0.4, centre + 0.4, POINTS)
        y = bg + amp * np.exp(-((x - centre) ** 2) / (2 * sigma**2))
        assert fit_gaussian_fwhm(x, y) == pytest.approx(fwhm(no), rel=1e-4)
    assert np.isnan(fit_gaussian_fwhm(np.arange(3.0), np.arange(3.0)))


def test_q_geometry_against_the_textbook_value():
    from splotter.fwhm_vs_q import HC_KEV_ANGSTROM, calculate_q_geometry

    # lambda = 1 angstrom at hc; delta = 60 deg, gamma = 0 gives 2theta = 60 deg
    q = calculate_q_geometry(60.0, 0.0, energy_kev=HC_KEV_ANGSTROM)
    assert q == pytest.approx(4 * np.pi * np.sin(np.radians(30.0)), abs=1e-12)
    assert calculate_q_geometry(1.4367, 0.0112, 5.55, g_off=0.0112, d_off=1.4367) == pytest.approx(
        0.0, abs=1e-12
    )


def run_script(command, args, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["splotter"])
    main([command, *map(str, args)])


def test_rocking_curve_script_writes_the_figure(tmp_path, monkeypatch):
    spec_file = write_spec(tmp_path / "s.spec", EXTRA_SCANS)
    out = tmp_path / "rc.png"
    run_script("rock", [spec_file, *EXTRA_SCANS, "--save", out], monkeypatch)
    assert out.exists()


def test_fwhm_vs_q_script_writes_the_figure(tmp_path, monkeypatch):
    data = tmp_path / "data"
    spec_file = write_spec(tmp_path / "s.spec", write_scan_lists(data))
    out = tmp_path / "fwhm.png"
    csvs = [data / name for name in ("data1.csv", "data2.csv", "data3.csv")]
    run_script("fwhm", [spec_file, *csvs, "--energy", 5.55, "--save", out], monkeypatch)
    assert out.exists()


def test_gam_del_script_runs_on_generated_scans(tmp_path, monkeypatch):
    spec_file = write_spec(tmp_path / "s.spec", EXTRA_SCANS)
    run_script("gamdel", [spec_file, *EXTRA_SCANS], monkeypatch)


def test_gam_del_reads_gamma_and_delta_in_run_order(tmp_path):
    from splotter.gam_del import load_run_data

    with Spec(write_spec(tmp_path / "s.spec", EXTRA_SCANS)) as spec:
        df = load_run_data(spec, [1104, 879])
    assert df["run_n"].tolist() == [1104, 879]
    # the generator writes #P0 as scan_no % 10 + motor index; Delta is motor 0, Gamma motor 5
    assert df["delta"].tolist() == [4.0, 9.0] and df["gamma"].tolist() == [9.0, 14.0]


def write_mesh(path, **options):
    lines = header() + mesh_block(1, **options) + scan_block(2)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_mesh_map(tmp_path, monkeypatch, spec_file, *options):
    args = [spec_file, 1, *options, "--save", tmp_path / "map.png"]
    run_script("mesh", args, monkeypatch)


def mesh_scan(points=6):
    data = [
        [sy, sx, n + 1.0]
        for n, (sx, sy) in enumerate((sx, sy) for sx in (1, 2) for sy in (0, 0.5, 1))
    ]
    return SpecScan(
        scan_no=1,
        command="mesh sy 0 1 2 sx 1 2 1  0.5",
        motor_names=[],
        columns=["Sample_Y", "Sample_X", "imtot"],
        data=data[:points],
    )


def test_scan_map_puts_each_point_at_its_motor_positions():
    from splotter.mesh_map import scan_map

    m = scan_map(mesh_scan(), "imtot", "Sample_X", "Sample_Y")
    assert m.x_edges.tolist() == [0.5, 1.5, 2.5] and m.y_edges.tolist() == [-0.25, 0.25, 0.75, 1.25]
    assert m.values.tolist() == [[1, 4], [2, 5], [3, 6]]
    assert m.peak() == (6, 2, 1)


def test_scan_map_follows_the_axes_asked_for():
    from splotter.mesh_map import scan_map

    m = scan_map(mesh_scan(), "imtot", "Sample_Y", "Sample_X")
    assert m.x_edges.tolist() == [-0.25, 0.25, 0.75, 1.25] and m.y_edges.tolist() == [0.5, 1.5, 2.5]
    assert m.values.tolist() == [[1, 2, 3], [4, 5, 6]]


def test_scan_map_leaves_points_of_an_aborted_scan_nan():
    from splotter.mesh_map import scan_map

    m = scan_map(mesh_scan(points=4), "imtot", "Sample_X", "Sample_Y")
    assert np.array_equal(m.values, [[1, 4], [2, np.nan], [3, np.nan]], equal_nan=True)


def test_scan_map_of_a_relative_scan_starts_from_the_measured_position():
    from splotter.mesh_map import scan_map

    scan = mesh_scan()
    scan.command = "dmesh sy -0.5 0.5 2 sx -0.5 0.5 1  0.5"
    m = scan_map(scan, "imtot", "Sample_X", "Sample_Y")
    assert m.x_edges.tolist() == [0.5, 1.5, 2.5] and m.y_edges.tolist() == [-0.25, 0.25, 0.75, 1.25]


def test_scan_map_puts_a_line_scan_at_the_position_of_the_other_motor(tmp_path):
    from splotter.mesh_map import scan_map

    path = tmp_path / "s.spec"
    path.write_text("\n".join(header() + line_block(3)), encoding="utf-8")
    with Spec(path) as spec:
        scan = spec.get_scan(3)
    m = scan_map(scan, "imtot", "Sample_X", "Sample_Y")
    assert m.x_edges.tolist() == [0.75, 1.25, 1.75, 2.25] and m.y_edges.tolist() == [2.75, 3.25]
    assert m.values.tolist() == [[5, 50, 0]]
    assert m.peak() == (50, 1.5, 3)
    m = scan_map(scan, "imtot", "Sample_Y", "Sample_X")
    assert m.values.tolist() == [[5], [50], [0]]


def test_a_log_scale_shows_zero_counts_but_keeps_unmeasured_points_empty():
    from splotter.mesh_map import ScanMap, color_scale, shown_values

    values = np.array([[0.0, 10.0], [100.0, np.nan]])
    m = ScanMap(1, np.arange(3.0), np.arange(3.0), values)
    norm = color_scale([m], log=True)
    assert (norm.vmin, norm.vmax) == (10, 100)
    assert np.array_equal(shown_values(values, norm), [[10, 10], [100, np.nan]], equal_nan=True)
    with pytest.raises(SystemExit, match="above zero"):
        color_scale([ScanMap(1, np.arange(2.0), np.arange(2.0), np.zeros((1, 1)))], log=True)


def test_the_figure_takes_the_shape_of_the_map():
    from splotter.mesh_map import figure_size

    wide, tall, square = figure_size(4, 1), figure_size(1, 4), figure_size(1, 1)
    assert wide[0] > wide[1] and tall[1] > tall[0]
    assert wide[0] == tall[1] - 1.6 + 2.2 == square[0]
    assert figure_size(100, 1)[1] == figure_size(4, 1)[1]


def test_outline_style_tells_scans_apart():
    from splotter.mesh_map import OUTLINE_COLORS, OUTLINE_STYLES, outline_style

    n_colors, n_styles = len(OUTLINE_COLORS), len(OUTLINE_STYLES)
    styles = [outline_style(i) for i in range(n_colors * n_styles)]
    assert len(set(styles)) == len(styles)
    assert len({color for color, _ in styles[:n_colors]}) == n_colors
    assert len({style for _, style in styles[:n_colors]}) == n_styles


@pytest.mark.parametrize("options", [[], ["--log"]])
def test_mesh_map_script_reports_the_generated_maximum(tmp_path, monkeypatch, capsys, options):
    run_mesh_map(tmp_path, monkeypatch, write_mesh(tmp_path / "s.spec"), *options)
    assert "max imtot = 100 at Sample_X = 2, Sample_Y = 0.5" in capsys.readouterr().out
    assert (tmp_path / "map.png").exists()


def test_mesh_map_script_draws_an_aborted_scan(tmp_path, monkeypatch, capsys):
    run_mesh_map(tmp_path, monkeypatch, write_mesh(tmp_path / "s.spec", points=5))
    assert "max imtot = 100 at Sample_X = 2, Sample_Y = 0.5" in capsys.readouterr().out


def test_mesh_map_script_combines_a_mesh_and_a_line_scan(tmp_path, monkeypatch, capsys):
    path = tmp_path / "s.spec"
    path.write_text("\n".join(header() + mesh_block(1) + line_block(3)), encoding="utf-8")
    out = tmp_path / "map.png"
    run_script("mesh", [path, 1, 3, "--log", "--save", out], monkeypatch)
    printed = capsys.readouterr().out
    assert "max imtot = 100 at Sample_X = 2, Sample_Y = 0.5" in printed
    assert "max imtot = 50 at Sample_X = 1.5, Sample_Y = 3" in printed
    assert out.exists()


@pytest.mark.parametrize(
    ("scan", "options", "message"),
    [
        ("2", ["--counter", "imroi1"], "scan 2 moves th, not Sample_X or Sample_Y"),
        ("1", ["--counter", "nope"], "no counter 'nope'"),
        ("1", ["--x", "Delta"], "scan 1 moves Sample_Y and Sample_X, not Delta and Sample_Y"),
        ("9", [], "no scan 9"),
    ],
)
def test_mesh_map_script_refuses_wrong_input(tmp_path, monkeypatch, scan, options, message):
    spec_file = write_mesh(tmp_path / "s.spec")
    with pytest.raises(SystemExit, match=message):
        run_script("mesh", [spec_file, scan, *options], monkeypatch)


def test_scan_info_point_shows_the_scanned_motor_at_that_point():
    from splotter.scan_info import point_values

    df = pd.DataFrame({"Sample_X": [1.0, 2.0], "imtot": [10.0, 20.0]})
    motors, counters = point_values({"Sample_X": 0.5, "Delta": 3.0}, df, 1)
    assert motors == {"Sample_X": 2.0, "Delta": 3.0}
    assert counters == {"imtot": 20.0}


def test_scan_info_script_prints_one_point(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [12])
    run_script("info", [spec_file, 12, 3], monkeypatch)
    out = capsys.readouterr().out
    assert "Motors at point 3:" in out and "Delta = 2" in out
    assert "imroi1 = " in out and "Seconds = 1" in out


def test_scan_info_script_prints_the_clock_time_of_a_point(tmp_path, monkeypatch, capsys):
    # scan 12 starts at 12:24:30 and Epoch is the row number
    spec_file = write_spec(tmp_path / "s.spec", [12])
    run_script("info", [spec_file, 12, 3], monkeypatch)
    assert "Time at point 3: 2025-06-26 12:24:33" in capsys.readouterr().out


def test_scan_info_script_lists_the_scans_of_the_file(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [7, 12])
    run_script("info", [spec_file], monkeypatch)
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3 and lines[1].split()[:3] == ["7", "2025-06-26", "12:24:30"]
    assert "ascan" in lines[2]

    run_script("info", [spec_file, "--last", 1], monkeypatch)
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2 and lines[1].split()[0] == "12"


def test_scan_info_script_prints_scan_and_file_metadata(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [12])
    run_script("info", [spec_file, 12, "--meta"], monkeypatch)
    out = capsys.readouterr().out
    assert "#T 1  (Seconds)" in out
    assert f"ad_detector.sample_detector_distance = {SDD}" in out
    assert "ad_regions_of_interest.roi[1].min_x = 20" in out

    run_script("info", [spec_file, "--meta"], monkeypatch)
    assert "#F synthetic.spec" in capsys.readouterr().out


def scan_info_table(spec_file, args, monkeypatch, capsys):
    run_script("info", [spec_file, *args, "--csv"], monkeypatch)
    return pd.read_csv(io.StringIO(capsys.readouterr().out))


def test_scan_info_columns_gives_one_row_per_point(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [12])
    table = scan_info_table(spec_file, [12, "-c", "time", "imroi1", "Delta"], monkeypatch, capsys)
    assert table.columns.tolist() == ["point", "time", "imroi1", "Delta"]
    assert len(table) == POINTS and table["Delta"].eq(2.0).all()
    assert table["time"].iloc[3] == "2025-06-26 12:24:33"


def test_scan_info_columns_of_one_point(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [12])
    table = scan_info_table(spec_file, [12, 3, "-c", "Epoch"], monkeypatch, capsys)
    assert table.to_dict("records") == [{"point": 3, "Epoch": 3}]


def test_scan_info_columns_of_fixed_motors_gives_one_row(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [12])
    table = scan_info_table(spec_file, [12, "-c", "delta", "Chi"], monkeypatch, capsys)
    assert table.to_dict("records") == [{"point": 0, "delta": 2.0, "Chi": 4.0}]


def test_scan_info_top_ranks_points_by_the_first_column(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [12])
    table = scan_info_table(spec_file, [12, "-c", "imroi1", "th", "--top", 2], monkeypatch, capsys)
    _, centre, _, _ = peak(12)
    assert len(table) == 2 and table["th"].iloc[0] == pytest.approx(centre, abs=1e-6)
    assert table["imroi1"].is_monotonic_decreasing


def test_scan_info_columns_without_a_scan_reads_motors_of_each_scan(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [7, 12])
    table = scan_info_table(spec_file, ["-c", "Delta", "--last", 1], monkeypatch, capsys)
    assert table.to_dict("records") == [{"scan": 12, "Delta": 2.0}]
    with pytest.raises(SystemExit, match="give a run for counters"):
        run_script("info", [spec_file, "-c", "imroi1"], monkeypatch)


def test_scan_info_names_lists_what_columns_accepts(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [12])
    run_script("info", [spec_file, 12, "--names"], monkeypatch)
    names = capsys.readouterr().out.split()
    assert {"time", "imroi1", "th", "Delta"} <= set(names)
    with pytest.raises(SystemExit, match="has no 'nope'"):
        run_script("info", [spec_file, 12, "-c", "nope"], monkeypatch)


def test_scan_info_script_summarizes_the_scan(tmp_path, monkeypatch, capsys):
    spec_file = write_spec(tmp_path / "s.spec", [12])
    run_script("info", [spec_file, 12], monkeypatch)
    out = capsys.readouterr().out
    assert f"Points: {POINTS}" in out and "max_point" in out and "imroi1" in out


@pytest.mark.parametrize(
    ("scan", "point", "message"), [(13, 0, "no scan 13"), (12, POINTS, f"no point {POINTS}")]
)
def test_scan_info_script_refuses_what_the_file_does_not_hold(
    tmp_path, monkeypatch, scan, point, message
):
    spec_file = write_spec(tmp_path / "s.spec", [12])
    with pytest.raises(SystemExit, match=message):
        run_script("info", [spec_file, scan, point], monkeypatch)


def test_scan_lists_name_scans_that_the_generated_spec_holds(tmp_path):
    numbers = write_scan_lists(tmp_path / "data")
    assert len(numbers) == len(set(numbers)) == 25
    with Spec(write_spec(tmp_path / "s.spec", numbers)) as spec:
        assert set(numbers) <= set(spec.scans)


@pytest.mark.parametrize("command", ["mesh", "rock"])
def test_log_axes_print_no_font_warnings(tmp_path, command):
    # in a new process: matplotlib warns about a font once per process
    spec_file = write_spec(tmp_path / "s.spec", [12]) if command == "rock" else None
    spec_file = spec_file or write_mesh(tmp_path / "s.spec")
    run = "12" if command == "rock" else "1"
    options = ["--counter", "imroi1"] if command == "rock" else ["--log"]
    argv = [command, str(spec_file), run, *options, "--save", str(tmp_path / "out.png")]
    done = subprocess.run(
        [sys.executable, "-m", "splotter", *argv], capture_output=True, text=True, check=True
    )
    assert "findfont" not in done.stderr


def test_the_command_lists_its_subcommands(capsys):
    main([])
    usage = capsys.readouterr().out
    assert all(name in usage for name in ("info", "mesh", "rock", "gamdel", "fwhm"))
    with pytest.raises(SystemExit, match="unknown command 'nope'"):
        main(["nope"])


def test_the_command_reports_its_version(capsys):
    main(["--version"])
    assert capsys.readouterr().out.strip() == "0.1.0"
