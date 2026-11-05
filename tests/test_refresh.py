"""Spec.refresh: a file read as it grows reads to what one read of the whole file gives."""

import os
import random
from types import SimpleNamespace

import pytest
from synthetic_spec import header, line_block, mesh_block, scan_block
from test_read_on_use import TEXT as LAZY_TEXT
from test_scan_api import HEADER, RESTART, SCANS

from splotter import spec as spec_module
from splotter.spec import FileReread, PointsAdded, ScanEnded, ScanStarted, Spec

SYNTHETIC = "\n".join(
    header() + scan_block(7, bad_row=True) + mesh_block(8, points=4) + line_block(9)
)
FILES = {
    "manual": HEADER + SCANS + RESTART,
    "lazy": LAZY_TEXT,
    "synthetic": SYNTHETIC + "\n",
    "crlf": (HEADER + SCANS).replace("\n", "\r\n"),
}


def fields(spec: Spec) -> list:
    """Everything a read gives, frames included."""
    out = [spec.file_metadata, spec.motor_names, sorted(spec.scans)]
    for scan in spec.all_scans:
        df = scan.to_dataframe()
        out.append(
            (
                scan.label,
                scan.command,
                scan.motor_names,
                scan.motor_mnemonics,
                scan.counter_names,
                scan.counter_mnemonics,
                scan.metadata,
                scan.columns,
                scan.data,
                scan.time,
                scan.skipped_lines,
                scan.motors,
                scan._raw_uxml,
                list(df.columns),
                df.to_numpy().tolist(),
            )
        )
    return out


def read_whole(path) -> list:
    with Spec(path) as spec:
        return fields(spec)


def grow(path, data: bytes, cuts: list[int], read_between=False) -> tuple[Spec, list]:
    """Write data in pieces ending at cuts, refreshing after each; returns the spec and events."""
    path.write_bytes(b"")
    spec, events, written = Spec(path), [], 0
    for cut in [*cuts, len(data)]:
        with path.open("ab") as out:
            out.write(data[written:cut])
        written = cut
        events += spec.refresh()
        if read_between:
            # rows and frames read before the next piece must not stop it from coming in
            fields(spec)
    return spec, events


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("seed", range(6))
def test_any_pieces_read_to_the_whole_file(tmp_path, monkeypatch, name, seed):
    monkeypatch.setattr(spec_module, "CHECK_SECONDS", 0.0)
    data = FILES[name].encode("utf-8")
    whole = tmp_path / "whole.spec"
    whole.write_bytes(data)
    rng = random.Random(seed)
    cuts = sorted(rng.sample(range(1, len(data)), k=min(len(data) - 1, 3 + seed * 7)))
    spec, _ = grow(tmp_path / "grown.spec", data, cuts, read_between=seed % 2 == 1)
    assert fields(spec) == read_whole(whole)


def test_a_line_waits_for_its_newline(tmp_path, monkeypatch):
    monkeypatch.setattr(spec_module, "CHECK_SECONDS", 0.0)
    path = tmp_path / "s.spec"
    path.write_text(HEADER + "#S 1 ascan tth 26 28 2 60\n#L Two Theta  Detector\n1 2", "utf-8")
    spec = Spec(path)
    spec.refresh()
    assert spec.get_scan(1).data == []
    with path.open("a", encoding="utf-8") as out:
        out.write("0\n")
    spec.refresh()
    assert spec.get_scan(1).data == [[1, 20]]


def test_with_spec_reads_a_last_line_without_newline_and_rereads_once_it_grows(tmp_path):
    path = tmp_path / "s.spec"
    path.write_text(HEADER + "#S 1 ascan tth 26 28 2 60\n#L Two Theta  Detector\n1 2", "utf-8")
    with Spec(path) as spec:
        assert spec.get_scan(1).data == [[1, 2]]
    with path.open("a", encoding="utf-8") as out:
        out.write("0\n3 4\n")
    events = spec.refresh()
    assert isinstance(events[0], FileReread)
    assert spec.get_scan(1).data == [[1, 20], [3, 4]]


def kinds(events) -> list:
    out = []
    for event in events:
        match event:
            case ScanStarted(scan=scan):
                out.append(("started", scan.label))
            case PointsAdded(scan=scan, lines=n):
                out.append(("points", scan.label, n))
            case ScanEnded(scan=scan, reason=reason):
                out.append(("ended", scan.label, reason))
            case FileReread():
                out.append(("reread",))
    return out


def test_events_say_how_each_scan_ended(tmp_path, monkeypatch):
    monkeypatch.setattr(spec_module, "CHECK_SECONDS", 0.0)
    path = tmp_path / "s.spec"
    path.write_text(HEADER, "utf-8")
    spec = Spec(path)
    assert spec.refresh() == []

    def append(text: str) -> list:
        with path.open("a", encoding="utf-8") as out:
            out.write(text)
        return kinds(spec.refresh())

    assert append("#S 1 ascan tth 26 28 4 1\n#L Two Theta  Detector\n26 1\n26.5 2\n") == [
        ("started", "1"),
        ("points", "1", 2),
    ]
    assert append("27 3\n#C Wed Feb 17 19:26:00 1994.  Scan aborted after 3 points.\n") == [
        ("points", "1", 1),
        ("ended", "1", "aborted"),
    ]
    # the planned 3 points of an ascan of 2 intervals; the next #S does not end it again
    assert append("#S 2 ascan tth 26 28 2 1\n#L Two Theta  Detector\n26 1\n27 2\n28 3\n") == [
        ("started", "2"),
        ("points", "2", 3),
        ("ended", "2", "complete"),
    ]
    assert append("#S 3 timescan 1 0\n#L Time  Detector\n0 1\n") == [
        ("started", "3"),
        ("points", "3", 1),
    ]
    assert append("#S 4 timescan 1 0\n") == [("ended", "3", "next scan"), ("started", "4")]
    assert append("#F s.spec\n#E 2\n") == [("ended", "4", "new session")]
    assert append("") == []


def test_a_replaced_or_shorter_file_is_read_again(tmp_path, monkeypatch):
    monkeypatch.setattr(spec_module, "CHECK_SECONDS", 0.0)
    path = tmp_path / "s.spec"
    path.write_text(HEADER + SCANS, "utf-8")
    with Spec(path) as spec:
        pass
    path.write_text(HEADER + SCANS.split("#S 3")[0], "utf-8")
    assert kinds(spec.refresh())[0] == ("reread",)
    assert [scan.label for scan in spec.all_scans] == ["1", "2"]
    # the same size, another first line: a new file under the same name
    text = path.read_text("utf-8").replace("#F manual.spec", "#F manuel.spec")
    path.write_text(text, "utf-8")
    assert kinds(spec.refresh())[0] == ("reread",)
    assert spec.file_metadata["#F"] == "manuel.spec"


def test_a_stale_stat_is_trusted_only_for_a_while(tmp_path, monkeypatch):
    path = tmp_path / "s.spec"
    path.write_text(HEADER + "#S 1 ascan tth 26 28 2 60\n#L Two Theta  Detector\n", "utf-8")
    clock = [1000.0]
    monkeypatch.setattr(spec_module.time, "monotonic", lambda: clock[0])
    spec = Spec(path)
    spec.refresh()
    old = os.stat(path)
    with path.open("a", encoding="utf-8") as out:
        out.write("26 1\n")
    # a share that still reports the old size and time
    stale_os = SimpleNamespace(stat=lambda _path: old, SEEK_END=os.SEEK_END)
    monkeypatch.setattr(spec_module, "os", stale_os)
    assert spec.refresh() == []
    clock[0] += spec_module.CHECK_SECONDS + 1
    assert kinds(spec.refresh()) == [("points", "1", 1)]


def test_rows_read_before_the_scan_grew_take_the_new_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(spec_module, "CHECK_SECONDS", 0.0)
    path = tmp_path / "s.spec"
    path.write_text(HEADER + "#S 1 ascan tth 26 28 4 1\n#L Two Theta  Detector\n26 1\n", "utf-8")
    spec = Spec(path)
    spec.refresh()
    scan = spec.get_scan(1)
    assert scan.data == [[26, 1]] and scan["Detector"].tolist() == [1]
    with path.open("a", encoding="utf-8") as out:
        out.write("26.5 2\nnot a row\n")
    spec.refresh()
    assert scan.data == [[26, 1], [26.5, 2]] and scan.skipped_lines == 1
    assert scan["Detector"].tolist() == [1, 2]


def test_a_file_gone_between_stat_and_open_gives_no_events(tmp_path, monkeypatch):
    path = tmp_path / "s.spec"
    path.write_text(HEADER, "utf-8")
    spec = Spec(path)
    spec.refresh()
    grown = SimpleNamespace(st_size=10**6, st_mtime_ns=1)
    monkeypatch.setattr(spec_module, "os", SimpleNamespace(stat=lambda _path: grown, SEEK_END=2))
    path.unlink()
    assert spec.refresh() == []
