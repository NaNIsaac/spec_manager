import argparse

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from splotter.mesh_map import (
    COLORBAR_AND_LABELS,
    LEGEND_STYLE,
    TITLE_AND_LABELS,
    ScanMap,
    add_map_arguments,
    color_scale,
    draw_maps,
    figure_size,
    load_maps,
    map_spans,
    point_map,
    style_axes,
    style_colorbar,
)
from splotter.scan_info import point_time, point_values, value_grid
from splotter.spec import SpecScan, find_name

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


class Probes:
    """The Probe of each scan; a cell is (scan index, ix, iy). Scans drawn later lie on top."""

    def __init__(self, probes: list[Probe]):
        self.probes = probes

    def cell_at(self, x: float, y: float) -> tuple[int, int, int] | None:
        for i in reversed(range(len(self.probes))):
            cell = self.probes[i].cell_at(x, y)
            if cell is not None:
                return i, *cell
        return None

    def bounds(self, cell: tuple[int, int, int]) -> tuple[float, float, float, float]:
        return self.probes[cell[0]].bounds(cell[1:])

    def tooltip(self, cell: tuple[int, int, int]) -> str:
        probe = self.probes[cell[0]]
        return f"scan {probe.scan.label}\n" + probe.tooltip(probe.point_of(cell[1:]))

    def report(self, cell: tuple[int, int, int]) -> str:
        probe = self.probes[cell[0]]
        return probe.report(probe.point_of(cell[1:]))


class InfoPanel:
    """Marks the cells of a Probe on a map and lists their values in a fixed panel beside it.

    The panel does not move or resize with the mouse, so the window keeps its shape.
    """

    def __init__(self, fig, ax, probe: Probes):
        self.fig, self.ax, self.probe = fig, ax, probe
        self.hovered: tuple[int, int, int] | None = None
        self.pinned: tuple[int, int, int] | None = None
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

    def place(self, rectangle: Rectangle, cell: tuple[int, int, int] | None) -> None:
        rectangle.set_visible(cell is not None)
        if cell is not None:
            left, bottom, width, height = self.probe.bounds(cell)
            rectangle.set_bounds(left, bottom, width, height)

    def refresh(self) -> None:
        """The hovered cell is listed; with none, the clicked one; with none, the hint."""
        cell = self.hovered or self.pinned
        self.text.set_text(HINT if cell is None else self.probe.tooltip(cell))
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
        print(f"\n{self.probe.report(cell)}")
        self.refresh()

    def on_leave(self, _event) -> None:
        if self.hovered is not None:
            self.hovered = None
            self.hover_mark.set_visible(False)
            self.refresh()


def draw(scans: list[SpecScan], maps: list[ScanMap], args) -> tuple:
    """Figure of the maps with an InfoPanel on it; the panel must stay referenced."""
    probes = [
        Probe(scan, grid, point_map(scan, args.x, args.y), args.x, args.y, args.show)
        for scan, grid in zip(scans, maps, strict=True)
    ]
    if args.show:
        probes[0].values_at(0)  # an unknown name stops here, not on the first hover
    norm = color_scale(maps, args.log, args.vmax)
    # every part has a place of its own in inches, so that nothing the mouse does can move the map
    map_width, map_height = figure_size(*map_spans(maps))
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
    mesh, legend_handles = draw_maps(ax, maps, norm)
    style_axes(ax, maps, args.counter, args.x, args.y)
    style_colorbar(fig.colorbar(mesh, cax=colorbar_axes, label=f"{args.counter} [counts]"))
    if legend_handles:
        # under the panel text, in the corner of the window
        fig.legend(
            handles=legend_handles, loc="lower left", bbox_to_anchor=(0.005, 0.01), **LEGEND_STYLE
        )
    return fig, InfoPanel(fig, ax, Probes(probes))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="The map of splotter mesh, to point at: hover over a cell and the panel at its "
        "left lists the scan, point number, motor positions and counters; click to mark the cell "
        "and print everything recorded there. Where scans overlap, the later run is the one listed."
    )
    add_map_arguments(parser)
    parser.add_argument(
        "--show",
        nargs="+",
        metavar="NAME",
        help="counters and motors in the panel (default: every counter)",
    )
    args = parser.parse_args()

    scans, maps = load_maps(args.spec_file, args.scans, args.counter, args.x, args.y)
    _fig, _panel = draw(scans, maps, args)
    plt.show()


if __name__ == "__main__":
    main()
