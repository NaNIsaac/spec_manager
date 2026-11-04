"""splotter shell: the commands on the hand-written file of test_scan_api.py."""

import pytest
from test_scan_api import HEADER, RESTART, SCANS

from splotter import spec as spec_module
from splotter.shell import Shell


@pytest.fixture
def shell(tmp_path, monkeypatch):
    monkeypatch.setattr(spec_module, "CHECK_SECONDS", 0.0)
    path = tmp_path / "manual.spec"
    path.write_text(HEADER + SCANS, encoding="utf-8")
    return Shell(path)


def run(shell: Shell, capsys, line: str) -> list[str]:
    capsys.readouterr()
    shell.postcmd(shell.onecmd(line), line)
    return capsys.readouterr().out.splitlines()


def test_ls_lists_scans_by_kind_and_range(shell, capsys):
    assert len(run(shell, capsys, "ls")) == 1 + 7
    lines = run(shell, capsys, "ls mesh a2scan")
    assert [line.split()[0] for line in lines[1:]] == ["3", "4"]
    lines = run(shell, capsys, "ls 2-3 7")
    assert [line.split()[0] for line in lines[1:]] == ["2", "3", "7"]


def test_show_gives_the_summary_with_axes(shell, capsys):
    lines = run(shell, capsys, "show 3")
    assert lines[0] == "Scan 3: mesh  sy -1 1 2  sx 0 1 1  0.5"
    assert "Axes: Sample_Y, Sample_X" in lines
    assert any(line.startswith("Detector") for line in lines)


def test_wa_lists_motors_with_mnemonics(shell, capsys):
    text = "\n".join(run(shell, capsys, "wa 1"))
    assert "Two Theta (tth) = 26" in text and "Sample_Y (sy) = -0.3" in text


def test_pa_gives_a_moved_motor_per_point_and_a_still_one_once(shell, capsys):
    lines = run(shell, capsys, "pa 2 th det")
    assert lines[0].split() == ["th", "det"] and len(lines) == 2 + 3
    lines = run(shell, capsys, "pa 2 chi")
    assert lines[-1].split() == ["0", "90.0"]


def test_errors_end_the_command_not_the_shell(shell, capsys):
    assert run(shell, capsys, "show 99") == ["no scan 99; the file has scans up to 7"]
    assert run(shell, capsys, "show x") == ["'x' is not a run number"]
    assert run(shell, capsys, "pa 1 nope")[0].startswith("scan 1 has no 'nope'")
    assert run(shell, capsys, "frobnicate 1") == [
        "unknown command 'frobnicate'; help lists the commands"
    ]


def test_tail_reports_new_and_ended_scans(shell, capsys):
    assert run(shell, capsys, "tail on") == []
    with shell.path.open("a", encoding="utf-8") as out:
        out.write("#S 9 ascan  tth 1 2  1 1\n#L Two Theta  Detector\n1 5\n")
    # scan 7 ended at load, on its "Scan aborted" comment
    assert run(shell, capsys, "") == ["scan 9 started: ascan  tth 1 2  1 1"]
    with shell.path.open("a", encoding="utf-8") as out:
        out.write("2 6\n")
    assert run(shell, capsys, "") == ["scan 9 ended (complete), 2 points"]
    run(shell, capsys, "tail off")
    with shell.path.open("a", encoding="utf-8") as out:
        out.write(RESTART)
    assert run(shell, capsys, "") == []
    assert len(run(shell, capsys, "ls")) == 1 + 8


def test_plot_commands_run_the_command_line_tools(shell, capsys, tmp_path):
    out = tmp_path / "rock.png"
    run(shell, capsys, f"rock 1 2 --counter det --save {out}")
    assert out.exists()
    assert run(shell, capsys, "mesh 1 --counter nope")[-1].startswith("no counter 'nope'")


def test_quit_leaves(shell):
    assert shell.onecmd("quit") is True and shell.onecmd("EOF") is True
