"""Write a Markdown reference of an argparse command line, from the parsers themselves.

    python tools/argparse_markdown.py splotter.cli:parsers docs/reference/cli.md
    python tools/argparse_markdown.py splotter.cli:parsers docs/reference/cli.md --check

MODULE:FUNC names a function that returns an ArgumentParser, or a mapping of command names to
parsers. Subcommands made with add_subparsers get sections of their own. Each section has the
description, the usage, a table of the arguments and the epilog of its parser, laid out at a fixed
width so the page does not depend on the terminal. --check writes nothing and exits 1 when OUT
differs from what it would write.
"""

import argparse
import importlib
import re
import sys
from collections.abc import Mapping
from pathlib import Path

WIDTH = 100


def slug(heading: str) -> str:
    """The anchor GitHub gives a heading."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def first_sentence(text: str | None) -> str:
    text = " ".join((text or "").split())
    match = re.match(r"(.+?\.)(\s|$)", text)
    return match.group(1) if match else text


def cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def formatter(parser: argparse.ArgumentParser) -> argparse.HelpFormatter:
    # the formatter argparse itself uses for --help, at a fixed width and without color
    out = parser.formatter_class(prog=parser.prog, width=WIDTH)
    if hasattr(out, "_set_color"):
        out._set_color(False)
    return out


def usage(parser: argparse.ArgumentParser) -> str:
    out = formatter(parser)
    out.add_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups)
    return out.format_help().strip()


def subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    found = {}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            seen = set()
            for name, sub in action.choices.items():
                if id(sub) not in seen:  # an alias names the same parser again
                    seen.add(id(sub))
                    found[name] = sub
    return found


def section(parser: argparse.ArgumentParser, level: int) -> list[str]:
    out = formatter(parser)
    lines = [f"{'#' * level} {parser.prog}", ""]
    if parser.description:
        lines += [" ".join(parser.description.split()), ""]
    lines += ["```", usage(parser), "```", ""]
    for group in parser._action_groups:
        actions = [
            action
            for action in group._group_actions
            if action.help != argparse.SUPPRESS
            and not isinstance(action, argparse._HelpAction | argparse._SubParsersAction)
        ]
        if not actions:
            continue
        title = (group.title or "arguments").capitalize()
        lines += [f"{'#' * (level + 1)} {title}", ""]
        if group.description:
            lines += [" ".join(group.description.split()), ""]
        lines += ["| Argument | Description |", "|---|---|"]
        for action in actions:
            text = out._expand_help(action) if action.help else ""
            if action.required and action.option_strings:
                text = f"{text} (required)" if text else "required"
            lines.append(f"| `{cell(out._format_action_invocation(action))}` | {cell(text)} |")
        lines.append("")
    if parser.epilog:
        lines += [" ".join(parser.epilog.split()), ""]
    for sub in subcommands(parser).values():
        lines += section(sub, level + 1)
    return lines


def render(
    parsers: argparse.ArgumentParser | Mapping[str, argparse.ArgumentParser],
    title: str,
    source: str,
) -> str:
    if isinstance(parsers, argparse.ArgumentParser):
        parsers = {parsers.prog: parsers}
    lines = [
        f"# {title}",
        "",
        f"<!-- written by tools/argparse_markdown.py from {source}; edit the parsers -->",
        "",
    ]
    if len(parsers) > 1:
        lines += ["| Command | What it does |", "|---|---|"]
        for parser in parsers.values():
            lines.append(
                f"| [`{parser.prog}`](#{slug(parser.prog)}) | "
                f"{cell(first_sentence(parser.description))} |"
            )
        lines.append("")
    for parser in parsers.values():
        lines += section(parser, 2)
    return "\n".join(lines).rstrip() + "\n"


def load(source: str):
    module, _, name = source.partition(":")
    return getattr(importlib.import_module(module), name)()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", help="MODULE:FUNC returning a parser or a mapping of parsers")
    parser.add_argument("out", type=Path)
    parser.add_argument("--title", default="Command-line reference")
    parser.add_argument("--check", action="store_true", help="exit 1 if OUT is not up to date")
    args = parser.parse_args()
    text = render(load(args.source), args.title, args.source)
    if args.check:
        current = args.out.read_text("utf-8").replace("\r\n", "\n") if args.out.exists() else ""
        if current != text:
            sys.exit(f"{args.out} is out of date; run: python {' '.join(sys.argv[:3])}")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(text.encode("utf-8"))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
