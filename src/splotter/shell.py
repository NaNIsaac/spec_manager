"""splotter shell FILE: one read of the file, then queries and plots at a prompt.

The text commands work on the scans read when the shell started, and on what `tail on` reads as
the file grows. The plot commands are those of the command line and open their windows the same
way, in a process of their own that reads the file again.
"""

import argparse
import cmd
import os
import shlex
import sys
from pathlib import Path

import matplotlib.pyplot as plt

from splotter import cli
from splotter.scan_info import (
    point_table,
    print_scan_header,
    print_scan_list,
    print_scan_summary,
    print_table,
    value_grid,
)
from splotter.spec import FileReread, ScanEnded, ScanStarted, Spec, SpecScan, run_id, scan_or_exit

PLOT_COMMANDS = ("mesh", "probe", "rock", "gamdel", "fwhm")


def split_words(line: str) -> list[str]:
    """Words as a shell gives them; on Windows the backslashes of a path stay."""
    if os.name != "nt":
        return shlex.split(line)
    words = shlex.split(line, posix=False)
    return [w[1:-1] if len(w) > 1 and w[0] == w[-1] and w[0] in "\"'" else w for w in words]


class Shell(cmd.Cmd):
    prompt = "splotter> "

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        with Spec(path) as spec:
            self.spec = spec
        self.following = False
        self.intro = f"{path}: {len(spec.all_scans)} scans. help lists the commands, quit leaves."

    def onecmd(self, line: str) -> bool:
        # a wrong run or name ends the command, not the shell
        try:
            return super().onecmd(line)
        except SystemExit as error:
            if error.code not in (None, 0, 2):
                print(error.code)
            return False

    def postcmd(self, stop: bool, line: str) -> bool:
        if self.following and not stop:
            self.report(self.spec.refresh())
        return stop

    def emptyline(self) -> bool:
        """An empty line reads what the file gained, with tail on; it does not repeat a command."""
        return False

    def default(self, line: str) -> None:
        print(f"unknown command '{line.split()[0]}'; help lists the commands")

    def scan(self, text: str) -> SpecScan:
        try:
            return scan_or_exit(self.spec, run_id(text))
        except argparse.ArgumentTypeError as error:
            raise SystemExit(str(error)) from None

    def do_ls(self, arg: str) -> None:
        """ls [KIND ...] [RUN | FIRST-LAST ...]: the scans, or those of a kind (mesh, ascan) or in
        a range of run numbers."""
        kinds, ranges = set(), []
        for word in arg.split():
            first, dash, last = word.partition("-")
            if first.isdigit() and (not dash or last.isdigit()):
                ranges.append((int(first), int(last or first)))
            else:
                kinds.add(word)
        scans = [
            scan
            for scan in self.spec.all_scans
            if (not kinds or scan.scan_command.kind in kinds)
            and (not ranges or any(lo <= scan.scan_no <= hi for lo, hi in ranges))
        ]
        print_scan_list(scans)

    def do_show(self, arg: str) -> None:
        """show RUN: command, times, points, motors at the start, and the range of each counter."""
        scan = self.scan(arg.strip())
        df = scan.to_dataframe()
        print_scan_header(scan, df)
        if scan.axes:
            print(f"Axes: {', '.join(scan.axes)}")
        for warning in scan.warnings:
            print(f"Warning: {warning}")
        print_scan_summary(scan, df)

    def do_wa(self, arg: str) -> None:
        """wa RUN: where all, every motor at the start of the scan, with its mnemonic."""
        scan = self.scan(arg.strip())
        table = scan.motor_table
        named = {}
        for name, value in scan.motors.items():
            mnemonic = table.mnemonic(name)
            named[f"{name} ({mnemonic})" if mnemonic else name] = value
        print(value_grid(named))

    def do_pa(self, arg: str) -> None:
        """pa RUN NAME ...: a motor or column by name or mnemonic, at each point if it moved,
        else its start position."""
        run, *names = arg.split()
        if not names:
            raise SystemExit("pa RUN NAME ...")
        print_table(point_table(self.scan(run), names), csv=False)

    def do_tail(self, arg: str) -> None:
        """tail on | off: with on, each command and each empty line first read what the file
        gained, and new and ended scans are listed."""
        if arg.strip() not in ("on", "off"):
            print(f"tail is {'on' if self.following else 'off'}; tail on | off")
            return
        self.following = arg.strip() == "on"

    def report(self, events: list) -> None:
        for event in events:
            if isinstance(event, FileReread):
                print(f"{self.path} was replaced; read again: {len(self.spec.all_scans)} scans")
            elif isinstance(event, ScanStarted):
                print(f"scan {event.scan.label} started: {event.scan.command}")
            elif isinstance(event, ScanEnded):
                points = len(event.scan.data)
                print(f"scan {event.scan.label} ended ({event.reason}), {points} points")

    def plot(self, command: str, arg: str) -> None:
        argv = sys.argv
        try:
            cli.main([command, str(self.path), *split_words(arg)])
        finally:
            sys.argv = argv
            plt.close("all")

    def do_quit(self, arg: str) -> bool:
        """quit: leave the shell."""
        return True

    do_exit = do_quit

    def do_EOF(self, arg: str) -> bool:
        """EOF: Ctrl-D, or Ctrl-Z and Enter on Windows, leaves the shell too."""
        print()
        return True


def plot_command(name: str):
    def run(self: Shell, arg: str) -> None:
        self.plot(name, arg)

    run.__doc__ = f"{name} ARGS: splotter {name} on this file, e.g. {name} --help"
    return run


for _name in PLOT_COMMANDS:
    setattr(Shell, f"do_{_name}", plot_command(_name))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read a SPEC file once and query it at a prompt: ls, show, wa, pa, the plot "
        "commands, and tail to follow the file as it grows."
    )
    parser.add_argument("spec_file", type=Path)
    args = parser.parse_args()
    Shell(args.spec_file).cmdloop()


if __name__ == "__main__":
    main()
