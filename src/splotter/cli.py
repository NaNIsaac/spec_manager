"""The splotter command: each subcommand runs the main() of one module."""

import argparse
import importlib
import sys
from importlib.metadata import version

COMMANDS = {
    "info": ("splotter.scan_info", "scan list, point values, metadata, values by column name"),
    "mesh": ("splotter.mesh_map", "map of a counter over two motors, from one or several scans"),
    "probe": ("splotter.probe", "mesh map of one scan to hover or click for the values of a cell"),
    "rock": ("splotter.rocking_curve", "normalized rocking curves on a log scale"),
    "gamdel": ("splotter.gam_del", "measured gamma/delta against the arc of one 2theta"),
    "fwhm": ("splotter.fwhm_vs_q", "Gaussian FWHM of rocking scans against Q"),
    "demo": ("splotter.demo", "write a made-up SPEC file to try the commands on"),
}


def parsers() -> dict[str, argparse.ArgumentParser]:
    """The parser of each command, as docs/reference/cli.md is written from."""
    return {
        name: importlib.import_module(module).build_parser()
        for name, (module, _) in COMMANDS.items()
    }


def usage() -> str:
    lines = ["usage: splotter COMMAND SPEC_FILE ...", "", "commands:"]
    lines += [f"  {name:<7} {summary}" for name, (_, summary) in COMMANDS.items()]
    lines += ["", "splotter COMMAND --help lists the options of a command."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    command, *args = (sys.argv[1:] if argv is None else argv) or ["--help"]
    if command in ("-h", "--help"):
        print(usage())
    elif command == "--version":
        print(version("splotter"))
    elif command in COMMANDS:
        module, _ = COMMANDS[command]
        sys.argv = [f"splotter {command}", *args]
        try:
            importlib.import_module(module).main()
        except FileNotFoundError as error:
            raise SystemExit(
                f"no such file: '{error.filename}'\nusage: splotter {command} SPEC_FILE ..."
            ) from None
    else:
        raise SystemExit(f"unknown command '{command}'\n\n{usage()}")
