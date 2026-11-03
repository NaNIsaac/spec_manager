"""The command of a `#S` line: which scan it was, what it moved, over what range, for how long.

The argument forms are those of the standard SPEC scan macros (SPEC manual, release 6, Standard
Macro Guide, "Motor Scans" and "Basic Reciprocal Space Scans"). A motor appears as typed, usually
its mnemonic; `splotter.names` turns it into the name the `#L` line uses.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Self


class Space(StrEnum):
    MOTOR = "motor"
    HKL = "hkl"


@dataclass(frozen=True)
class Axis:
    """One scanned quantity: a motor (as typed on the command line) or H, K or L."""

    name: str
    start: float
    stop: float


@dataclass(frozen=True)
class ScanCommand:
    """A parsed `#S` command; `known` is False for a macro outside the table, whose axes are empty."""

    text: str
    kind: str
    axes: tuple[Axis, ...] = ()
    intervals: tuple[int, ...] = ()
    count: float | None = None
    relative: bool = False
    space: Space = Space.MOTOR
    known: bool = False

    @property
    def is_mesh(self) -> bool:
        """A nested scan: the first axis runs through its range at each point of the second."""
        return len(self.intervals) == 2

    @property
    def points(self) -> int | None:
        """Planned number of points: one more than the intervals, per nested axis."""
        return math.prod(n + 1 for n in self.intervals) if self.intervals else None

    @property
    def counts_to_monitor(self) -> bool:
        """A negative count time means counting to monitor counts."""
        return self.count is not None and self.count < 0

    @classmethod
    def parse(cls, text: str) -> Self:
        tokens = text.split()
        if not tokens:
            return cls(text, "")
        kind, args = tokens[0], tokens[1:]
        try:
            return _parse(text, kind, args)
        except (ValueError, IndexError):
            return cls(text, kind)


# macro: (motors, relative)
LINE_SCANS = {
    "ascan": (1, False),
    "a2scan": (2, False),
    "a3scan": (3, False),
    "dscan": (1, True),
    "lup": (1, True),
    "d2scan": (2, True),
    "d3scan": (3, True),
}
# dmesh is not in the manual's table but is the common relative form of mesh, with its arguments.
MESHES = {"mesh": False, "dmesh": True}
HKL_LINES = {"hscan": "H", "kscan": "K", "lscan": "L"}


def _parse(text: str, kind: str, args: list[str]) -> ScanCommand:
    if kind in LINE_SCANS:
        motors, relative = LINE_SCANS[kind]
        _expect(args, 3 * motors + 2)
        axes = tuple(_axis(args[3 * i : 3 * i + 3]) for i in range(motors))
        return ScanCommand(
            text, kind, axes, (int(args[-2]),), float(args[-1]), relative, known=True
        )
    if kind in MESHES:
        _expect(args, 9)
        axes = (_axis(args[0:3]), _axis(args[4:7]))
        intervals = (int(args[3]), int(args[7]))
        return ScanCommand(text, kind, axes, intervals, float(args[8]), MESHES[kind], known=True)
    if kind == "th2th":
        # a d2scan of tth with th moving half the range
        _expect(args, 4)
        start, stop = float(args[0]), float(args[1])
        axes = (Axis("tth", start, stop), Axis("th", start / 2, stop / 2))
        return ScanCommand(text, kind, axes, (int(args[2]),), float(args[3]), True, known=True)
    if kind in HKL_LINES:
        _expect(args, 4)
        axes = (Axis(HKL_LINES[kind], float(args[0]), float(args[1])),)
        return ScanCommand(
            text, kind, axes, (int(args[2]),), float(args[3]), space=Space.HKL, known=True
        )
    if kind == "hklscan":
        _expect(args, 8)
        axes = tuple(
            Axis(q, float(args[2 * i]), float(args[2 * i + 1])) for i, q in enumerate("HKL")
        )
        return ScanCommand(
            text, kind, axes, (int(args[6]),), float(args[7]), space=Space.HKL, known=True
        )
    if kind == "hklmesh":
        _expect(args, 9)
        axes = (_axis(args[0:3]), _axis(args[4:7]))
        if {axes[0].name, axes[1].name} - set("HKL") or axes[0].name == axes[1].name:
            raise ValueError("hklmesh scans two different ones of H, K and L")
        intervals = (int(args[3]), int(args[7]))
        return ScanCommand(text, kind, axes, intervals, float(args[8]), space=Space.HKL, known=True)
    return ScanCommand(text, kind)


def _expect(args: list[str], n: int) -> None:
    if len(args) != n:
        raise ValueError(f"{n} arguments expected, {len(args)} given")


def _axis(args: list[str]) -> Axis:
    name, start, stop = args
    return Axis(name, float(start), float(stop))
