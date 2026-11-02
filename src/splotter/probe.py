import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from splotter.mesh_map import (
    COLORBAR_AND_LABELS,
    MEAN_FACTOR,
    NOT_MEASURED_FILL,
    NOT_MEASURED_HATCH,
    TITLE_AND_LABELS,
    ScanMap,
    color_scale,
    figure_size,
    point_map,
    scan_map,
    shown_values,
)
from splotter.scan_info import point_time, point_values, value_grid
from splotter.spec import Spec, SpecScan, find_name, run_id, scan_or_exit

HOVER_COLOR, PIN_COLOR = "#e8e8e8", "#6fc7d6"
HINT = "hover over a cell\nfor its values,\nclick to keep it"
# inches
PANEL_WIDTH = 2.2  # left of the map
AXIS_LABEL_ROOM, TITLE_ROOM = 0.9, 0.6
COLORBAR_GAP, COLORBAR_WIDTH, COLORBAR_LABEL_ROOM = 0.15, 0.3, 1.2
NOT_SHOWN = {"Epoch"}  # the time line says it better


def cell_index(edges: np.ndarray, value: float) -> int | None:
    """Index of the cell of equally spaced edges holding value; the edges may run down."""
    n = len(edges) - 1
    t = (value - edges[0]) / (edges[-1] - edges[0]) * n
    return int(t) if 0 <= t < n else None


class Probe:
    """Finds the data row under a place on the map and describes it."""

    def __init__(self, scan: SpecScan, grid: ScanMap, rows: ScanMap, x: str, y: str, show):
        self.scan, self.grid, self.rows, self.x, self.y = scan, grid, rows, x, y
        self.df = scan.to_dataframe()
        self.show = show

    def cell_at(self, x: float, y: float) -> tuple[int, int] | None:
        """(ix, iy) of the measured cell at the motor positions x, y."""
        ix, iy = cell_index(self.grid.x_edges, x), cell_index(self.grid.y_edges, y)
        if ix is None or iy is None or np.isnan(self.rows.values[iy, ix]):
            return None
        return ix, iy

    def point_of(self, cell: tuple[int, int]) -> int:
        ix, iy = cell
        return int(self.rows.values[iy, ix])

    def bounds(self, cell: tuple[int, int]) -> tuple[float, float, float, float]:
        """left, bottom, width, height of the cell."""
        ix, iy = cell
        x0, x1 = sorted(self.grid.x_edges[ix : ix + 2])
        y0, y1 = sorted(self.grid.y_edges[iy : iy + 2])
        return x0, y0, x1 - x0, y1 - y0

    def values_at(self, point: int) -> dict[str, float]:
        """Motors and counters at the point, the two motors of the axes first."""
        motors, counters = point_values(self.scan.motors, self.df, point)
        everything = {**motors, **counters}
        asked = [*(self.show or [])]
        found = {name: find_name(name, everything) for name in [self.x, self.y, *asked]}
        missing = [name for name, key in found.items() if key is None]
        if missing:
            raise SystemExit(
                f"scan {self.scan.label} has no '{missing[0]}'; "
                "splotter info FILE RUN --names lists what it has"
            )
        names = [found[name] for name in asked]
        if not asked:
            names = [name for name in counters if name not in NOT_SHOWN]
        axes = [found[self.x], found[self.y]]
        return {name: everything[name] for name in dict.fromkeys([*axes, *names])}

    def tooltip(self, point: int) -> str:
        when = point_time(self.scan, self.df, point)
        header = f"point {point}" + (f"   {when:%H:%M:%S}" if when else "")
        values = self.values_at(point)
        width = max(map(len, values))
        return "\n".join([header, *(f"{name:<{width}} = {v:.8g}" for name, v in values.items())])

    def report(self, point: int) -> str:
        """Everything the scan recorded at the point, for the terminal."""
        motors, counters = point_values(self.scan.motors, self.df, point)
        when = point_time(self.scan, self.df, point)
        return (
            f"Scan {self.scan.label} point {point}, time {when or '-'}\n"
            f"Motors:\n{value_grid(motors)}\nCounters:\n{value_grid(counters)}"
        )


class InfoPanel:
    """Marks the cells of a Probe on a map and lists their values in a fixed panel beside it.

    The panel does not move or resize with the mouse, so the window keeps its shape.
    """

    def __init__(self, fig, ax, probe: Probe):
        self.fig, self.ax, self.probe = fig, ax, probe
        self.hovered: tuple[int, int] | None = None
        self.pinned: tuple[int, int] | None = None
        self.hover_mark = self.mark(HOVER_COLOR, linewidth=1.5, zorder=4)
        self.pin_mark = self.mark(PIN_COLOR, linewidth=2.5, zorder=5)
        self.text = fig.text(
            0.01,
            0.98,
            HINT,
            va="top",
            ha="left",
            fontsize=9,
            family="monospace",
            fontweight="normal",
        )
        fig.canvas.mpl_connect("motion_notify_event", self.on_move)
        fig.canvas.mpl_connect("button_press_event", self.on_click)
        fig.canvas.mpl_connect("axes_leave_event", self.on_leave)

    def mark(self, color: str, linewidth: float, zorder: int) -> Rectangle:
        rectangle = Rectangle(
            (0, 0), 1, 1, fill=False, edgecolor=color, linewidth=linewidth, zorder=zorder
        )
        rectangle.set_visible(False)
        self.ax.add_patch(rectangle)
        return rectangle

    def place(self, rectangle: Rectangle, cell: tuple[int, int] | None) -> None:
        rectangle.set_visible(cell is not None)
        if cell is not None:
            left, bottom, width, height = self.probe.bounds(cell)
            rectangle.set_bounds(left, bottom, width, height)

    def refresh(self) -> None:
        """The hovered cell is listed; with none, the clicked one; with none, the hint."""
        cell = self.hovered or self.pinned
        self.text.set_text(HINT if cell is None else self.probe.tooltip(self.probe.point_of(cell)))
        self.fig.canvas.draw_idle()

    def on_move(self, event) -> None:
        if event.inaxes is not self.ax:
            return
        cell = self.probe.cell_at(event.xdata, event.ydata)
        if cell != self.hovered:
            self.hovered = cell
            self.place(self.hover_mark, cell)
            self.refresh()

    def on_click(self, event) -> None:
        if event.inaxes is not self.ax or event.button != 1:
            return
        cell = self.probe.cell_at(event.xdata, event.ydata)
        if cell is None:
            return
        self.pinned = cell
        self.place(self.pin_mark, cell)
        print(f"\n{self.probe.report(self.probe.point_of(cell))}")
        self.refresh()

    def on_leave(self, _event) -> None:
        if self.hovered is not None:
            self.hovered = None
            self.hover_mark.set_visible(False)
            self.refresh()


def draw(scan: SpecScan, args) -> tuple:
    """Figure of the scan's map with an InfoPanel on it; the panel must stay referenced."""
    grid = scan_map(scan, args.counter, args.x, args.y)
    probe = Probe(scan, grid, point_map(scan, args.x, args.y), args.x, args.y, args.show)
    if args.show:
        probe.values_at(0)  # an unknown name stops here, not on the first hover
    norm = color_scale([grid], args.log, args.vmax)
    x_span = grid.x_edges.max() - grid.x_edges.min()
    y_span = grid.y_edges.max() - grid.y_edges.min()
    # every part has a place of its own in inches, so that nothing the mouse does can move the map
    map_width, map_height = figure_size(x_span, y_span)
    map_width, map_height = map_width - COLORBAR_AND_LABELS, map_height - TITLE_AND_LABELS
    left = PANEL_WIDTH + AXIS_LABEL_ROOM
    total_width = left + map_width + COLORBAR_GAP + COLORBAR_WIDTH + COLORBAR_LABEL_ROOM
    total_height = AXIS_LABEL_ROOM + map_height + TITLE_ROOM
    fig = plt.figure(figsize=(total_width, total_height))

    def inches(x: float, y: float, width: float, height: float) -> list[float]:
        return [x / total_width, y / total_height, width / total_width, height / total_height]

    ax = fig.add_axes(inches(left, AXIS_LABEL_ROOM, map_width, map_height))
    colorbar_axes = fig.add_axes(
        inches(left + map_width + COLORBAR_GAP, AXIS_LABEL_ROOM, COLORBAR_WIDTH, map_height)
    )
    ax.patch.set(facecolor=NOT_MEASURED_FILL, edgecolor=NOT_MEASURED_HATCH, hatch="///")
    mesh = ax.pcolormesh(
        grid.x_edges, grid.y_edges, shown_values(grid.values, norm), cmap="magma", norm=norm
    )
    ax.set_xlim(grid.x_edges.min(), grid.x_edges.max())
    # the vertical axis runs downward, as on the mesh map
    ax.set_ylim(grid.y_edges.max(), grid.y_edges.min())
    ax.set_aspect("equal")
    ax.set_title(f"Scan {scan.label}: {args.counter}", fontsize=14, fontweight="bold")
    ax.set_xlabel(args.x, fontsize=14)
    ax.set_ylabel(args.y, fontsize=14)
    fig.colorbar(mesh, cax=colorbar_axes, label=f"{args.counter} [counts]")
    return fig, InfoPanel(fig, ax, probe)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mesh or line scan map to point at: hover over a cell and the panel at its left "
        "lists the point number, motor positions and counters; click to mark the cell and print "
        "everything recorded there."
    )
    parser.add_argument("spec_file", type=Path)
    parser.add_argument("scan", type=run_id, help="mesh, ascan or dscan run number")
    parser.add_argument("--counter", default="imtot", help="counter that gives the colors")
    parser.add_argument("--x", default="Sample_X", help="motor of the horizontal axis")
    parser.add_argument("--y", default="Sample_Y", help="motor of the vertical axis")
    parser.add_argument(
        "--show",
        nargs="+",
        metavar="NAME",
        help="counters and motors in the panel (default: every counter)",
    )
    parser.add_argument("--log", action="store_true", help="log color scale")
    parser.add_argument(
        "--vmax",
        type=float,
        help=f"top of the color scale (default: {MEAN_FACTOR} times the mean of the scan)",
    )
    args = parser.parse_args()

    with Spec(args.spec_file) as spec:
        scan = scan_or_exit(spec, args.scan)
    print(f"Scan {scan.label}: {scan.command}")
    _fig, _panel = draw(scan, args)
    plt.show()


if __name__ == "__main__":
    main()
