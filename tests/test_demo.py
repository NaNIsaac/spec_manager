"""The made-up SPEC file of `splotter demo`, read back through the commands."""

import sys

import numpy as np
import pytest

from splotter.cli import main
from splotter.demo import ROCKING_SCANS, SPOT_X, SPOT_Y, write_demo
from splotter.fwhm_vs_q import fit_gaussian_fwhm
from splotter.mesh_map import scan_map
from splotter.spec import Spec


@pytest.fixture
def demo(tmp_path):
    spec_file, _ = write_demo(tmp_path / "demo.spec")
    return spec_file


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["splotter"])
    main([*map(str, args)])


def test_the_same_file_comes_out_every_time(tmp_path, demo):
    other, _ = write_demo(tmp_path / "other.spec")
    assert other.read_text(encoding="utf-8") == demo.read_text(encoding="utf-8")


def test_the_file_says_it_is_not_a_measurement(demo):
    with Spec(demo) as spec:
        assert "not a measurement" in spec.file_metadata["#C"]


def test_the_parser_reads_every_scan(demo):
    with Spec(demo) as spec:
        assert sorted(spec.scans) == list(range(1, 9))
        scan = spec.get_scan(1)
    assert scan.motors["Delta"] == 50.9 and scan.motors["Sample_X"] == -1
    assert scan.uxml["ad_detector"]["sample_detector_distance"] == 600
    assert [roi["min_x"] for roi in scan.uxml["ad_regions_of_interest"]["roi"]] == [250, 200]
    assert len(scan.to_dataframe()) == 21 * 21


def test_the_bright_spot_is_where_the_generator_put_it(demo):
    with Spec(demo) as spec:
        maps = [scan_map(spec.get_scan(n), "imtot", "Sample_X", "Sample_Y") for n in (1, 3, 4)]
    for m in maps:
        _, x, y = m.peak()
        assert x == pytest.approx(SPOT_X, abs=0.02) and y == pytest.approx(SPOT_Y, abs=0.02)


def test_the_aborted_mesh_has_unmeasured_points(demo):
    with Spec(demo) as spec:
        m = scan_map(spec.get_scan(5), "imtot", "Sample_X", "Sample_Y")
    assert m.values.size == 231 and np.isnan(m.values).sum() == 131


def test_rocking_scans_have_the_generated_widths(demo):
    with Spec(demo) as spec:
        for number, sigma, _ in ROCKING_SCANS:
            df = spec.get_scan(number).to_dataframe()
            width = fit_gaussian_fwhm(df["Theta"].to_numpy(), df["imroi3"].to_numpy())
            assert width == pytest.approx(2.3548 * sigma, rel=0.05)


def test_every_command_runs_on_it(tmp_path, demo, monkeypatch, capsys):
    run(monkeypatch, "info", demo)
    assert len(capsys.readouterr().out.splitlines()) == 1 + 8
    run(monkeypatch, "info", demo, 1, "-c", "Sample_X", "Sample_Y", "--top", 1)
    run(monkeypatch, "info", demo, 1, "--meta")
    run(monkeypatch, "mesh", demo, 1, 2, 5, 3, 4, "--log", "--save", tmp_path / "mesh.png")
    run(monkeypatch, "rock", demo, 6, 7, 8, "--counter", "imroi3", "--save", tmp_path / "rock.png")
    run(monkeypatch, "gamdel", demo, 6, 7, 8)
    scan_list = tmp_path / "demo_fwhm.csv"
    out = tmp_path / "fwhm.png"
    run(monkeypatch, "fwhm", demo, scan_list, "--energy", 8, "--counter", "imroi3", "--save", out)
    assert all((tmp_path / name).exists() for name in ("mesh.png", "rock.png", "fwhm.png"))


def test_the_command_keeps_existing_files(tmp_path, monkeypatch, capsys):
    out = tmp_path / "demo.spec"
    run(monkeypatch, "demo", out)
    assert f"wrote {out}" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="--force overwrites"):
        run(monkeypatch, "demo", out)
    run(monkeypatch, "demo", out, "--force")
