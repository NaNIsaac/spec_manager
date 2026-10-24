"""The SPEC parser and the two scripts, on generated data (tests/synthetic_spec.py)."""

import runpy
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from synthetic_spec import (
    EXTRA_SCANS,
    MOTORS,
    POINTS,
    SDD,
    fwhm,
    peak,
    scan_block,
    write_scan_lists,
    write_spec,
)

from spec import Spec

ROOT = Path(__file__).resolve().parent.parent


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
    from main import fit_gaussian_fwhm

    for no in (3, 11, 40):
        amp, centre, sigma, bg = peak(no)
        x = np.linspace(centre - 0.4, centre + 0.4, POINTS)
        y = bg + amp * np.exp(-((x - centre) ** 2) / (2 * sigma**2))
        assert fit_gaussian_fwhm(x, y) == pytest.approx(fwhm(no), rel=1e-4)
    assert np.isnan(fit_gaussian_fwhm(np.arange(3.0), np.arange(3.0)))


def test_q_geometry_against_the_textbook_value():
    from main import calculate_q_geometry

    # lambda = 1 angstrom at 12398.41 eV; delta = 60 deg, gamma = 0 gives 2theta = 60 deg
    q = calculate_q_geometry(60.0, 0.0, energy=12398.41, g_off=0.0, d_off=0.0)
    assert q == pytest.approx(4 * np.pi * np.sin(np.radians(30.0)), abs=1e-12)
    assert calculate_q_geometry(1.4367, 0.0112, g_off=0.0112, d_off=1.4367) == pytest.approx(
        0.0, abs=1e-12
    )


def run_script(name, spec_file, cwd, monkeypatch):
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(sys, "argv", [name, str(spec_file)])
    monkeypatch.syspath_prepend(str(ROOT))
    runpy.run_path(str(ROOT / name), run_name="__main__")


def test_rocking_curve_script_runs_on_generated_scans(tmp_path, monkeypatch):
    spec_file = write_spec(tmp_path / "s.spec", EXTRA_SCANS)
    run_script("rocking_curve.py", spec_file, tmp_path, monkeypatch)


def test_fwhm_vs_q_script_runs_on_generated_scans(tmp_path, monkeypatch):
    numbers = write_scan_lists(tmp_path / "data")
    spec_file = write_spec(tmp_path / "s.spec", numbers)
    run_script("main.py", spec_file, tmp_path, monkeypatch)


def test_scan_lists_name_scans_that_the_generated_spec_holds(tmp_path):
    numbers = write_scan_lists(tmp_path / "data")
    assert len(numbers) == len(set(numbers)) == 25
    with Spec(write_spec(tmp_path / "s.spec", numbers)) as spec:
        assert set(numbers) <= set(spec.scans)
