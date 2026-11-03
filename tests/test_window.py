"""Plot windows in a detached process; no window is opened here."""

import os
import subprocess
import sys

import matplotlib.pyplot as plt
import pytest

from splotter import window
from splotter.cli import main
from splotter.demo import write_demo


class FakeChild:
    def __init__(self, code):
        self.code = code

    def wait(self, timeout):
        if self.code is None:
            raise subprocess.TimeoutExpired("splotter", timeout)
        return self.code


@pytest.fixture
def demo(tmp_path):
    spec_file, _ = write_demo(tmp_path / "demo.spec")
    return spec_file


@pytest.fixture
def spawned(monkeypatch):
    """Popen calls, with a child that keeps running unless a test sets ``code``."""
    calls = []
    state = {"code": None}

    def popen(command, **options):
        calls.append((command, options))
        return FakeChild(state["code"])

    monkeypatch.setattr(window.subprocess, "Popen", popen)
    monkeypatch.setattr(window, "interactive_backend", lambda: True)
    shown = []
    monkeypatch.setattr(window.plt, "show", lambda: shown.append(True))
    return calls, state, shown


def test_a_plot_command_starts_itself_again_with_wait_and_returns(monkeypatch, demo, spawned):
    calls, _, shown = spawned
    monkeypatch.setattr(sys, "argv", ["splotter"])
    main(["mesh", str(demo), "1", "--log"])
    [(command, options)] = calls
    assert command == [
        window.interpreter(),
        "-m",
        "splotter.mesh_map",
        str(demo),
        "1",
        "--log",
        "--wait",
    ]
    assert options["stdin"] is subprocess.DEVNULL
    assert shown == []
    assert plt.get_fignums() == []


def test_wait_shows_the_window_here(monkeypatch, demo, spawned):
    calls, _, shown = spawned
    monkeypatch.setattr(sys, "argv", ["splotter"])
    main(["rock", str(demo), "4", "--wait"])
    assert calls == []
    assert shown == [True]


def test_save_opens_no_window_and_no_process(monkeypatch, demo, spawned, tmp_path):
    calls, _, shown = spawned
    monkeypatch.setattr(sys, "argv", ["splotter"])
    main(["mesh", str(demo), "1", "--save", str(tmp_path / "map.png")])
    assert (calls, shown) == ([], [])
    assert (tmp_path / "map.png").exists()


def test_a_file_backend_never_starts_a_process(monkeypatch, spawned):
    calls, _, shown = spawned
    monkeypatch.setattr(window, "interactive_backend", lambda: False)
    window.show(window.argparse.Namespace(wait=False), "splotter.mesh_map")
    assert (calls, shown) == ([], [True])


def test_a_child_that_fails_at_once_is_reported_with_its_log(monkeypatch, spawned):
    _, state, _ = spawned
    state["code"] = 1
    monkeypatch.setattr(sys, "argv", ["splotter mesh", "demo.spec", "1"])
    with pytest.raises(SystemExit, match=r"did not open \(exit status 1\); log: .*splotter-"):
        window.show(window.argparse.Namespace(wait=False), "splotter.mesh_map")


def test_on_posix_the_child_gets_a_session_of_its_own(monkeypatch):
    monkeypatch.setattr(window.sys, "platform", "linux")
    assert window.detach_options() == {"start_new_session": True}
    assert window.detach_options(prints=True) == {"start_new_session": True}


def test_probe_keeps_the_terminal_output_for_what_a_click_prints(monkeypatch, demo, spawned):
    calls, _, _ = spawned
    monkeypatch.setattr(sys, "argv", ["splotter"])
    main(["probe", str(demo), "1"])
    [(command, options)] = calls
    assert command[:3] == [window.interpreter(prints=True), "-m", "splotter.probe"]
    assert "stdout" not in options
    assert options.pop("env")[window.QUIET_UNTIL_SHOWN] == "1"
    assert options == {"stdin": subprocess.DEVNULL, **window.detach_options(prints=True)}


def test_the_probe_child_prints_only_once_its_window_is_open(demo):
    env = os.environ | {"MPLBACKEND": "Agg", window.QUIET_UNTIL_SHOWN: "1"}
    command = [sys.executable, "-m", "splotter.probe", str(demo), "1", "--wait"]
    result = subprocess.run(
        command, check=False, env=env, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert "Scan 1" not in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Windows creation flags")
def test_on_windows_the_child_has_no_console_and_its_own_process_group():
    flags = window.detach_options()["creationflags"]
    assert flags & subprocess.DETACHED_PROCESS
    assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
    assert window.interpreter().lower().endswith(("pythonw.exe", "python.exe"))
    printing = window.detach_options(prints=True)["creationflags"]
    assert printing == subprocess.CREATE_NEW_PROCESS_GROUP
    assert window.interpreter(prints=True) == sys.executable


def test_the_child_command_runs(demo):
    """What the detached child runs, here in the foreground and without a display."""
    env = os.environ | {"MPLBACKEND": "Agg"}
    command = [sys.executable, "-m", "splotter.mesh_map", str(demo), "1", "--log", "--wait"]
    result = subprocess.run(
        command, check=False, env=env, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr


def test_logs_older_than_a_week_are_removed_when_a_window_opens(monkeypatch, spawned, tmp_path):
    monkeypatch.setattr(window.tempfile, "gettempdir", lambda: str(tmp_path))
    old, recent = tmp_path / "splotter-1-1.log", tmp_path / "splotter-2-2.log"
    other = tmp_path / "other.log"
    for path in (old, recent, other):
        path.write_text("x")
    week_ago = window.time.time() - window.KEEP_LOGS_SECONDS - 60
    os.utime(old, (week_ago, week_ago))
    os.utime(other, (week_ago, week_ago))
    monkeypatch.setattr(sys, "argv", ["splotter mesh", "demo.spec", "1"])
    window.show(window.argparse.Namespace(wait=False), "splotter.mesh_map")
    assert not old.exists()
    assert recent.exists() and other.exists()
    assert len(list(tmp_path.glob("splotter-*.log"))) == 2
