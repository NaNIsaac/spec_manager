"""docs/reference/cli.md is what tools/argparse_markdown.py writes from the parsers of today."""

import argparse
import importlib.util
from pathlib import Path

from splotter import cli

ROOT = Path(__file__).parents[1]
REFERENCE = ROOT / "docs" / "reference" / "cli.md"


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "argparse_markdown", ROOT / "tools" / "argparse_markdown.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_reference_is_up_to_date():
    tool = load_tool()
    text = tool.render(cli.parsers(), "Command-line reference", "splotter.cli:parsers")
    committed = REFERENCE.read_text("utf-8").replace("\r\n", "\n")
    assert committed == text, (
        "docs/reference/cli.md is out of date; run: "
        "uv run python tools/argparse_markdown.py splotter.cli:parsers docs/reference/cli.md"
    )


def test_every_command_and_option_is_in_the_reference():
    text = REFERENCE.read_text("utf-8")
    for name, parser in cli.parsers().items():
        assert f"## splotter {name}\n" in text
        for action in parser._actions:
            for option in action.option_strings:
                if option not in ("-h", "--help"):
                    assert f"`{option}" in text or f", {option}" in text, (name, option)


def test_any_parser_renders_with_its_subcommands():
    tool = load_tool()
    parser = argparse.ArgumentParser(prog="tool", description="Does things. More words here.")
    parser.add_argument("--mode", choices=["a", "b"], default="a", help="pick | one (%(default)s)")
    parser.add_argument("--secret", help=argparse.SUPPRESS)
    quiet = parser.add_mutually_exclusive_group()
    quiet.add_argument("-q", action="store_true", help="less")
    quiet.add_argument("-v", action="store_true", help="more")
    sub = parser.add_subparsers(title="commands")
    run = sub.add_parser("run", aliases=["r"], prog="tool run", description="Run it.")
    run.add_argument("target", help="what to run")
    run.add_argument("--times", type=int, required=True, metavar="N")
    text = tool.render(parser, "Reference", "example:parser")
    assert text.startswith("# Reference\n")
    assert "## tool\n" in text and "### tool run\n" in text
    assert text.count("### tool run") == 1  # the alias is not a second section
    assert "| `--mode {a,b}` | pick \\| one (a) |" in text
    assert "--secret" not in text
    assert "[-q | -v]" in text
    assert "| `--times N` | required |" in text
    assert "| `target` | what to run |" in text
    many = tool.render({"one": parser, "two": run}, "Reference", "example:parsers")
    assert "| [`tool`](#tool) | Does things. |" in many
    assert "| [`tool run`](#tool-run) | Run it. |" in many
