"""Plot windows that leave the terminal free.

A command first does all its work in the terminal, so that a wrong scan number or counter is
reported there. Then, instead of blocking in ``plt.show()``, it starts itself again with
``--wait`` in a detached process, which opens the window, and returns. ``&`` cannot do this in
PowerShell, where it starts a job that cannot open a window.

A window that prints to the terminal, as ``splotter probe`` does on a click, keeps the
terminal's output instead of a log, and so closes with the terminal on Windows.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends import BackendFilter, backend_registry

# Long enough to catch a child that cannot start (no display, a broken install), short enough
# not to be noticed; a later failure is in the log.
EARLY_EXIT_SECONDS = 0.5
# A child holds its log open while the window is up, so logs are pruned by age, not at exit.
KEEP_LOGS_SECONDS = 7 * 24 * 3600
# Set for the child of a window that prints: the terminal already has its start-up lines.
QUIET_UNTIL_SHOWN = "SPLOTTER_QUIET_UNTIL_SHOWN"
_terminal = None


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """``--wait``. Called before the command reads anything, so that the child of a printing
    window does not print the lines its parent printed a moment ago."""
    global _terminal
    if os.environ.pop(QUIET_UNTIL_SHOWN, None) and _terminal is None:
        _terminal, sys.stdout = sys.stdout, open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    parser.add_argument(
        "--wait",
        action="store_true",
        help="keep the window in this terminal until it is closed (default: return at once)",
    )


def interactive_backend() -> bool:
    """False for Agg and the other file backends, where show() opens nothing (MPLBACKEND=Agg)."""
    interactive = backend_registry.list_builtin(BackendFilter.INTERACTIVE)
    return matplotlib.get_backend().lower() in {name.lower() for name in interactive}


def interpreter(prints: bool = False) -> str:
    """pythonw on Windows, so the child has no console window of its own; python when it prints."""
    if sys.platform == "win32" and not prints:
        windowed = Path(sys.executable).with_name("pythonw.exe")
        if windowed.exists():
            return str(windowed)
    return sys.executable


def detach_options(prints: bool = False) -> dict:
    """The child outlives the terminal: no console and no Ctrl+C from it on Windows, its own
    session on POSIX, so closing the terminal does not close the window. A child that prints
    keeps the console on Windows, still out of reach of Ctrl+C."""
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP
        if not prints:
            flags |= subprocess.DETACHED_PROCESS
        return {"creationflags": flags}
    return {"start_new_session": True}


def prune_logs(folder: Path, now: float) -> None:
    """Remove the logs of windows started more than a week ago; one still open stays."""
    for log in folder.glob("splotter-*.log"):
        try:
            if now - log.stat().st_mtime > KEEP_LOGS_SECONDS:
                log.unlink()
        except OSError:
            continue


def show(args: argparse.Namespace, module: str, *, prints: bool = False) -> None:
    """Show the figures of ``module``'s command, in a detached process unless ``--wait``.

    ``prints``: the window writes to the terminal, so the child keeps its output."""
    global _terminal
    if args.wait or not interactive_backend():
        if _terminal is not None:
            sys.stdout.close()
            sys.stdout, _terminal = _terminal, None
        plt.show()
        return
    plt.close("all")
    command = [interpreter(prints), "-m", module, *sys.argv[1:], "--wait"]
    options = detach_options(prints)
    log = None
    if prints:
        env = os.environ | {QUIET_UNTIL_SHOWN: "1"}
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, env=env, **options)
    else:
        folder = Path(tempfile.gettempdir())
        prune_logs(folder, time.time())
        log = folder / f"splotter-{os.getpid()}-{time.time_ns()}.log"
        with log.open("wb") as out:
            child = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, **options
            )
    try:
        code = child.wait(EARLY_EXIT_SECONDS)
    except subprocess.TimeoutExpired:
        return
    if code != 0:
        where = "" if log is None else f"; log: {log}"
        raise SystemExit(
            f"the plot window did not open (exit status {code}){where}\n"
            "run again with --wait to open it in this terminal"
        )
