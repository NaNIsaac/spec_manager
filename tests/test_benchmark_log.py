"""The log that benchmarks/parse_speed.py times reads as what it was written to be."""

import importlib.util
from pathlib import Path

from splotter.spec import Spec

SCRIPT = Path(__file__).parents[1] / "benchmarks" / "parse_speed.py"


def load_script():
    spec = importlib.util.spec_from_file_location("parse_speed", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_generated_log_reads_without_warnings(tmp_path):
    bench = load_script()
    path = tmp_path / "generated.spec"
    scans = bench.write_log(path, megabytes=2)
    assert abs(path.stat().st_size - 2e6) < 50e3
    with Spec(path) as spec:
        assert len(spec.all_scans) == scans
        kinds = {scan.scan_command.kind for scan in spec.all_scans}
        assert kinds == {"ascan", "mesh", "timescan"}
        for scan in spec.all_scans:
            assert not scan.warnings and scan.skipped_lines == 0
            assert scan.columns[-len(bench.COUNTERS) :] == bench.COUNTERS
            assert scan.axes, scan.command
    # a fixed seed, so every run times the same file
    again = tmp_path / "again.spec"
    bench.write_log(again, megabytes=2)
    assert again.read_bytes() == path.read_bytes()
