import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm, Normalize
from matplotlib.patches import Patch, Rectangle
from matplotlib.patheffects import Normal, Stroke
from matplotlib.ticker import AutoMinorLocator
from mpl_toolkits.axes_grid1 import make_axes_locatable

from splotter import window
from splotter.command import Axis, Space
from splotter.spec import Spec, SpecScan, name_key, run_id, scan_or_exit

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
MEAN_FACTOR = 10  # the color scale ends at this many times the mean
SAMPLE_AXES = ("Sample_X", "Sample_Y")
LEGEND_STYLE = {
    "facecolor": LEGEND_FILL,
    "edgecolor": LEGEND_FILL,
    "framealpha": 1,
    "labelcolor": "white",
}
BORDER_WIDTH = 2.0
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


def centres(axis: Axis, intervals: int, first: float) -> tuple[np.ndarray, float]:
    """Cell centres of a scan axis, from its first measured position, and the step.

    The command gives only the step: dscan and dmesh ranges are relative to the start position.
    """
    step = (axis.stop - axis.start) / intervals
    return first + step * np.arange(intervals + 1), step


def edges(centre: np.ndarray, step: float) -> np.ndarray:
    return np.append(centre, centre[-1] + step) - step / 2


def scan_map(scan: SpecScan, counter: str, x: str, y: str) -> ScanMap:
    """A mesh of motors x and y, or an ascan/dscan of one of them at the #P position of the other."""
    df = scan.to_dataframe()
    if df.empty:
        raise SystemExit(f"scan {scan.label} has no data")
    column = scan.column(counter)
    if not column:
        raise SystemExit(f"no counter '{counter}'; columns: {', '.join(df.columns)}")
    return place_values(scan, df, df[column].to_numpy(dtype=float), x, y)


def point_map(scan: SpecScan, x: str, y: str) -> ScanMap:
    """The same cells as scan_map, holding the number of the data row measured there."""
    df = scan.to_dataframe()
    if df.empty:
        raise SystemExit(f"scan {scan.label} has no data")
    return place_values(scan, df, np.arange(len(df), dtype=float), x, y)


def place_values(scan: SpecScan, df, measured: np.ndarray, x: str, y: str) -> ScanMap:
    """Put one value per data row of the scan on the cell where the row was measured.

    x and y are motor names or mnemonics; the scanned ones are found among the axes of the command.
    """
    command, axes = scan.scan_command, scan.axes
    if command.space is not Space.MOTOR or not (command.is_mesh or len(axes) == 1):
        raise SystemExit(
            f"scan {scan.label} is neither a mesh nor a line scan of one motor: '{scan.command}'"
        )
    x_axis, y_axis = scan.motor_table.resolve(x, axes), scan.motor_table.resolve(y, axes)
    if command.is_mesh:
        # the first motor of "mesh sy -2.5 -1.5 25 sx -6.7 -5.7 25 0.5" runs at each point of sx
        fast, slow = axes
        if {x_axis, y_axis} != {fast, slow}:
            raise SystemExit(f"scan {scan.label} moves {fast} and {slow}, not {x} and {y}")
        fast_pos, fast_step = centres(command.axes[0], command.intervals[0], df[fast].iloc[0])
        slow_pos, slow_step = centres(command.axes[1], command.intervals[1], df[slow].iloc[0])
        grid = np.full(fast_pos.size * slow_pos.size, np.nan)
        grid[: measured.size] = measured
        grid = grid.reshape(slow_pos.size, fast_pos.size)
        x_edges, y_edges = edges(slow_pos, slow_step), edges(fast_pos, fast_step)
        if fast == x_axis:
            return ScanMap(scan.label, edges(fast_pos, fast_step), edges(slow_pos, slow_step), grid)
        return ScanMap(scan.label, x_edges, y_edges, grid.T)

    (moved,) = axes
    if moved not in (x_axis, y_axis):
        raise SystemExit(f"scan {scan.label} moves {moved}, not {x} or {y}")
    along_x = moved == x_axis
    fixed = scan.motor(y if along_x else x)
    if not fixed:
        raise SystemExit(f"scan {scan.label} records no position of {y if along_x else x}")

    along, step = centres(command.axes[0], command.intervals[0], df[moved].iloc[0])
    values = np.full(along.size, np.nan)
    values[: measured.size] = measured
    # a line has no width of its own: draw square cells
    across = edges(np.array([scan.motors[fixed]]), abs(step))
    if along_x:
        return ScanMap(scan.label, edges(along, step), across, values[np.newaxis, :])
    return ScanMap(scan.label, across, edges(along, step), values[:, np.newaxis])


def color_scale(maps: list[ScanMap], log: bool, vmax: float | None = None) -> Normalize:
    """One scale for all scans, so that colors compare between them.

    It ends at MEAN_FACTOR times the mean, not at the maximum: a few hot points would otherwise leave
    the rest of the map in one color. Points above it take the brightest color.
    """
    values = np.concatenate([m.values.ravel() for m in maps])
    top = vmax if vmax is not None else min(MEAN_FACTOR * np.nanmean(values), np.nanmax(values))
    if not log:
        return Normalize(vmin=np.nanmin(values), vmax=top)
    positive = values[values > 0]
    if positive.size == 0:
        raise SystemExit("--log needs at least one count above zero")
    return LogNorm(vmin=positive.min(), vmax=top if top > positive.min() else positive.max())


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


def default_axes(scans: list[SpecScan]) -> tuple[str, str]:
    """--x and --y when not given: Sample_X across and Sample_Y down if the scans move either;
    otherwise the outer motor of the first mesh across and its inner motor down."""
    scanned = {name_key(axis) for scan in scans for axis in scan.axes}
    meshes = [
        scan.axes
        for scan in scans
        if scan.scan_command.is_mesh and scan.scan_command.space is Space.MOTOR and scan.axes
    ]
    if not meshes or scanned & {name_key(axis) for axis in SAMPLE_AXES}:
        return SAMPLE_AXES
    inner, outer = meshes[0]
    return outer, inner


def load_maps(
    spec_file: Path, runs: list[str], counter: str, x: str | None = None, y: str | None = None
):
    """The scans of the runs, their maps and the names of counter, x and y; prints each command,
    mean and peak.

    The names may be given as mnemonics; x and y default to default_axes.
    """
    print(f"Load spec file: '{spec_file}'")
    with Spec(spec_file) as spec:
        scans = [scan_or_exit(spec, run) for run in runs]
    default_x, default_y = default_axes(scans)
    x, y = x or default_x, y or default_y
    first = scans[0]
    x, y, counter = first.motor(x) or x, first.motor(y) or y, first.column(counter) or counter
    maps = []
    for run, scan in zip(runs, scans, strict=True):
        print(f"Scan {run}: {scan.command}")
        maps.append(scan_map(scan, counter, x, y))
        value, peak_x, peak_y = maps[-1].peak()
        mean = np.nanmean(maps[-1].values)
        print(
            f"  mean {counter} = {mean:.4g}, "
            f"max {counter} = {value:g} at {x} = {peak_x:g}, {y} = {peak_y:g}"
        )
    return scans, maps, counter, x, y


def map_spans(maps: list[ScanMap]) -> tuple[float, float]:
    x_span = max(m.x_edges.max() for m in maps) - min(m.x_edges.min() for m in maps)
    y_span = max(m.y_edges.max() for m in maps) - min(m.y_edges.min() for m in maps)
    return x_span, y_span


def draw_maps(ax, maps: list[ScanMap], norm: Normalize):
    """The maps on the axes, later ones on top; returns the last mesh and the legend entries."""
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
    if several or any(np.isnan(m.values).any() for m in maps):
        legend_handles.append(
            Patch(
                facecolor=NOT_MEASURED_FILL,
                edgecolor=NOT_MEASURED_HATCH,
                hatch="///",
                label="not measured",
            )
        )
    return mesh, legend_handles


def style_axes(ax, maps: list[ScanMap], counter: str, x: str, y: str) -> None:
    for side in ["top", "bottom", "left", "right"]:
        ax.spines[side].set_linewidth(BORDER_WIDTH)
    runs = ", ".join(str(m.run) for m in maps)
    title = f"Scan{'s' if len(maps) > 1 else ''} {runs}: {counter}"
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel(x, fontsize=14)
    ax.set_ylabel(y, fontsize=14)
    # outward: ticks inside would vanish on the dark cells
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.tick_params(which="major", direction="out", length=7, width=BORDER_WIDTH, labelsize=12)
    ax.tick_params(which="minor", direction="out", length=4, width=BORDER_WIDTH / 2)


def style_colorbar(colorbar) -> None:
    colorbar.outline.set_linewidth(BORDER_WIDTH)
    colorbar.ax.minorticks_on()
    colorbar.ax.tick_params(which="major", direction="out", length=6, width=BORDER_WIDTH / 1.3)
    colorbar.ax.tick_params(which="minor", direction="out", length=3.5, width=BORDER_WIDTH / 2)


def add_map_arguments(parser: argparse.ArgumentParser) -> None:
    """The arguments of splotter mesh, which splotter probe takes as well."""
    parser.add_argument("spec_file", type=Path)
    parser.add_argument("scans", type=run_id, nargs="+", help="mesh, ascan or dscan run numbers")
    parser.add_argument(
        "--counter", default="imtot", help="name or mnemonic, e.g. imtot, imroi1, imroi2, immax"
    )
    parser.add_argument(
        "--x",
        help="motor of the horizontal axis, name or mnemonic (default: Sample_X if the scans move "
        "Sample_X or Sample_Y, else the outer motor of the first mesh)",
    )
    parser.add_argument(
        "--y",
        help="motor of the vertical axis (default: Sample_Y, or the inner motor of the first mesh)",
    )
    parser.add_argument(
        "--log", action="store_true", help="log color scale; zero counts take its lowest color"
    )
    parser.add_argument(
        "--vmax",
        type=float,
        help=f"top of the color scale (default: {MEAN_FACTOR} times the mean of the scans)",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Map of one counter over the motor positions of SPEC mesh and line scans. "
        "Several scans share the axes and the color scale; later runs draw over earlier ones."
    )
    add_map_arguments(parser)
    parser.add_argument("--save", type=Path, help="write the figure here instead of showing it")
    window.add_arguments(parser)
    args = parser.parse_args()

    _, maps, counter, x, y = load_maps(args.spec_file, args.scans, args.counter, args.x, args.y)
    norm = color_scale(maps, args.log, args.vmax)
    fig, ax = plt.subplots(1, 1, figsize=figure_size(*map_spans(maps)), layout="constrained")
    mesh, legend_handles = draw_maps(ax, maps, norm)
    style_axes(ax, maps, counter, x, y)
    # beside the axes, so that it keeps their height when equal units shorten them
    colorbar_axes = make_axes_locatable(ax).append_axes("right", size=0.3, pad=0.15)
    colorbar = fig.colorbar(mesh, cax=colorbar_axes, label=f"{counter} [counts]")
    style_colorbar(colorbar)
    if legend_handles:
        fig.legend(
            handles=legend_handles,
            loc="outside lower center",
            ncols=min(len(legend_handles), 3),
            **LEGEND_STYLE,
        )

    if args.save:
        fig.savefig(args.save, dpi=300, bbox_inches="tight")
    else:
        window.show(args, __spec__.name)


if __name__ == "__main__":
    main()
