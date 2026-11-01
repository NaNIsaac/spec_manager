import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm, Normalize
from matplotlib.patches import Patch, Rectangle
from matplotlib.patheffects import Normal, Stroke

from splotter.spec import Spec, SpecScan, find_name, name_key, run_id, scan_or_exit

plt.rcParams["font.weight"] = "bold"
plt.rcParams["axes.labelweight"] = "bold"
# matplotlib 3.11 reports every math font without a bold face; the figures are not affected
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

NOT_MEASURED_FILL = "#d9d9d9"
NOT_MEASURED_HATCH = "#8c8c8c"
LEGEND_FILL = "#0d0a23"  # the dark end of the map, where the outlines mostly sit
OUTLINE_COLORS = ["#6fc7d6", "#9ccc65", "#e8e8e8", "#b9a3e3"]
OUTLINE_STYLES = ["solid", "dashed", "dashdot", "dotted"]
# a thin dark edge keeps them on the gray fill
OUTLINE_HALO = [Stroke(linewidth=1.8, foreground="black", alpha=0.5), Normal()]
# inches
MAX_MAP_SIDE, MIN_MAP_SIDE = 6.0, 2.5
COLORBAR_AND_LABELS, TITLE_AND_LABELS = 2.2, 1.6


def outline_style(index: int) -> tuple[str, str]:
    """Color and line style of the index-th scan; a fifth scan reuses a color with another style."""
    n = len(OUTLINE_COLORS)
    return OUTLINE_COLORS[index % n], OUTLINE_STYLES[(index + index // n) % n]


@dataclass
class ScanMap:
    """One scan on the motor plane: values[iy, ix] fills the cell between the edges; NaN = not measured."""

    run: str
    x_edges: np.ndarray
    y_edges: np.ndarray
    values: np.ndarray

    def peak(self) -> tuple[float, float, float]:
        """Largest value and the x, y of the centre of its cell."""
        iy, ix = np.unravel_index(np.nanargmax(self.values), self.values.shape)
        x = (self.x_edges[ix] + self.x_edges[ix + 1]) / 2
        y = (self.y_edges[iy] + self.y_edges[iy + 1]) / 2
        return self.values[iy, ix], x, y


def centres(start: str, stop: str, intervals: str, first: float) -> tuple[np.ndarray, float]:
    """Cell centres of a scan axis, from its first measured position, and the step.

    The command gives only the step: dscan and dmesh ranges are relative to the start position.
    """
    step = (float(stop) - float(start)) / int(intervals)
    return first + step * np.arange(int(intervals) + 1), step


def edges(centre: np.ndarray, step: float) -> np.ndarray:
    return np.append(centre, centre[-1] + step) - step / 2


def scan_map(scan: SpecScan, counter: str, x: str, y: str) -> ScanMap:
    """A mesh of motors x and y, or an ascan/dscan of one of them at the #P position of the other."""
    df = scan.to_dataframe()
    if df.empty:
        raise SystemExit(f"scan {scan.label} has no data")
    column = find_name(counter, df.columns)
    if not column:
        raise SystemExit(f"no counter '{counter}'; columns: {', '.join(df.columns)}")

    measured = df[column].to_numpy(dtype=float)
    x_key, y_key = name_key(x), name_key(y)
    tokens = scan.command.split()
    if "mesh" in tokens[0]:
        # e.g. "mesh sy -2.5 -1.5 25 sx -6.7 -5.7 25 0.5"; 25 is the number of intervals
        fast, slow = df.columns[:2]
        if {name_key(fast), name_key(slow)} != {x_key, y_key}:
            raise SystemExit(f"scan {scan.label} moves {fast} and {slow}, not {x} and {y}")
        fast_pos, fast_step = centres(*tokens[2:5], df[fast].iloc[0])
        slow_pos, slow_step = centres(*tokens[6:9], df[slow].iloc[0])
        grid = np.full(fast_pos.size * slow_pos.size, np.nan)
        grid[: measured.size] = measured
        grid = grid.reshape(slow_pos.size, fast_pos.size)
        x_edges, y_edges = edges(slow_pos, slow_step), edges(fast_pos, fast_step)
        if name_key(fast) == x_key:
            return ScanMap(scan.label, edges(fast_pos, fast_step), edges(slow_pos, slow_step), grid)
        return ScanMap(scan.label, x_edges, y_edges, grid.T)

    if tokens[0] not in ("ascan", "dscan"):
        raise SystemExit(f"scan {scan.label} is neither a mesh nor an ascan: '{scan.command}'")
    moved = df.columns[0]
    if name_key(moved) not in (x_key, y_key):
        raise SystemExit(f"scan {scan.label} moves {moved}, not {x} or {y}")
    along_x = name_key(moved) == x_key
    fixed = find_name(y if along_x else x, scan.motors)
    if not fixed:
        raise SystemExit(f"scan {scan.label} records no position of {y if along_x else x}")

    along, step = centres(*tokens[2:5], df[moved].iloc[0])
    values = np.full(along.size, np.nan)
    values[: measured.size] = measured
    # a line has no width of its own: draw square cells
    across = edges(np.array([scan.motors[fixed]]), abs(step))
    if along_x:
        return ScanMap(scan.label, edges(along, step), across, values[np.newaxis, :])
    return ScanMap(scan.label, across, edges(along, step), values[:, np.newaxis])


def color_scale(maps: list[ScanMap], log: bool) -> Normalize:
    """One scale for all scans, so that colors compare between them."""
    values = np.concatenate([m.values.ravel() for m in maps])
    if not log:
        return Normalize(vmin=np.nanmin(values), vmax=np.nanmax(values))
    positive = values[values > 0]
    if positive.size == 0:
        raise SystemExit("--log needs at least one count above zero")
    return LogNorm(vmin=positive.min(), vmax=positive.max())


def shown_values(values: np.ndarray, norm: Normalize) -> np.ndarray:
    """A log scale would blank zero counts; show them at its lowest color, as they were measured."""
    if isinstance(norm, LogNorm):
        return np.where(values <= 0, norm.vmin, values)
    return values


def figure_size(x_span: float, y_span: float) -> tuple[float, float]:
    """Width and height in inches: the axes keep equal units, so the window takes the shape of the map.

    The long side of the map stays the same; the short side stops shrinking at MIN_MAP_SIDE, so that
    a very narrow map still has room for its labels.
    """
    aspect = x_span / y_span
    width = max(MAX_MAP_SIDE * min(aspect, 1), MIN_MAP_SIDE)
    height = max(MAX_MAP_SIDE * min(1 / aspect, 1), MIN_MAP_SIDE)
    return width + COLORBAR_AND_LABELS, height + TITLE_AND_LABELS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Map of one counter over the motor positions of SPEC mesh and line scans. "
        "Several scans share the axes and the color scale; later runs draw over earlier ones."
    )
    parser.add_argument("spec_file", type=Path)
    parser.add_argument("scans", type=run_id, nargs="+", help="mesh, ascan or dscan run numbers")
    parser.add_argument("--counter", default="imtot", help="e.g. imtot, imroi1, imroi2, immax")
    parser.add_argument("--x", default="Sample_X", help="motor of the horizontal axis")
    parser.add_argument("--y", default="Sample_Y", help="motor of the vertical axis")
    parser.add_argument(
        "--log", action="store_true", help="log color scale; zero counts take its lowest color"
    )
    parser.add_argument("--save", type=Path, help="write the figure here instead of showing it")
    args = parser.parse_args()

    print(f"Load spec file: '{args.spec_file}'")
    maps = []
    with Spec(args.spec_file) as spec:
        for run in args.scans:
            scan = scan_or_exit(spec, run)
            print(f"Scan {run}: {scan.command}")
            maps.append(scan_map(scan, args.counter, args.x, args.y))
            value, x, y = maps[-1].peak()
            print(f"  max {args.counter} = {value:g} at {args.x} = {x:g}, {args.y} = {y:g}")

    norm = color_scale(maps, args.log)
    x_span = max(m.x_edges.max() for m in maps) - min(m.x_edges.min() for m in maps)
    y_span = max(m.y_edges.max() for m in maps) - min(m.y_edges.min() for m in maps)
    fig, ax = plt.subplots(1, 1, figsize=figure_size(x_span, y_span), layout="constrained")
    ax.patch.set(facecolor=NOT_MEASURED_FILL, edgecolor=NOT_MEASURED_HATCH, hatch="///")
    several = len(maps) > 1
    legend_handles = []
    for i, m in enumerate(maps):
        mesh = ax.pcolormesh(
            m.x_edges, m.y_edges, shown_values(m.values, norm), cmap="magma", norm=norm
        )
        if several:
            color, style = outline_style(i)
            left, right = sorted(m.x_edges[[0, -1]])
            bottom, top = sorted(m.y_edges[[0, -1]])
            # above every map, so that the edge of a scan stays visible where another covers it
            ax.add_patch(
                Rectangle(
                    (left, bottom),
                    right - left,
                    top - bottom,
                    fill=False,
                    edgecolor=color,
                    linestyle=style,
                    linewidth=1.0,
                    path_effects=OUTLINE_HALO,
                    zorder=3,
                )
            )
            legend_handles.append(
                Patch(fill=False, edgecolor=color, linestyle=style, linewidth=1.5, label=str(m.run))
            )

    ax.set_xlim(min(m.x_edges.min() for m in maps), max(m.x_edges.max() for m in maps))
    # the vertical axis runs downward: smaller numbers at the top
    ax.set_ylim(max(m.y_edges.max() for m in maps), min(m.y_edges.min() for m in maps))
    ax.set_aspect("equal")

    border_width = 2.0
    for side in ["top", "bottom", "left", "right"]:
        ax.spines[side].set_linewidth(border_width)

    runs = ", ".join(str(m.run) for m in maps)
    title = f"Scan{'s' if several else ''} {runs}: {args.counter}"
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel(args.x, fontsize=14)
    ax.set_ylabel(args.y, fontsize=14)
    ax.tick_params(direction="out", length=6, width=border_width, labelsize=12)
    fig.colorbar(mesh, ax=ax, label=f"{args.counter} [counts]")
    if several or any(np.isnan(m.values).any() for m in maps):
        legend_handles.append(
            Patch(
                facecolor=NOT_MEASURED_FILL,
                edgecolor=NOT_MEASURED_HATCH,
                hatch="///",
                label="not measured",
            )
        )
        fig.legend(
            handles=legend_handles,
            loc="outside lower center",
            ncols=min(len(legend_handles), 3),
            facecolor=LEGEND_FILL,
            edgecolor=LEGEND_FILL,
            framealpha=1,
            labelcolor="white",
        )

    if args.save:
        fig.savefig(args.save, dpi=300, bbox_inches="tight")
    else:
        plt.show()


if __name__ == "__main__":
    main()
