"""splotter probe: which data row lies under a place on the map, and what the tooltip says."""

import argparse

import pytest
from matplotlib.backend_bases import MouseEvent
from synthetic_spec import header, mesh_block, scan_block
from test_spec import mesh_scan

from splotter.mesh_map import point_map, scan_map
from splotter.probe import Probe, cell_index, draw
from splotter.spec import Spec


def probe_of(points=6, show=None):
    scan = mesh_scan(points)
    args = ("Sample_X", "Sample_Y")
    return Probe(scan, scan_map(scan, "imtot", *args), point_map(scan, *args), *args, show)


def options(**changed):
    values = {"counter": "imtot", "x": "Sample_X", "y": "Sample_Y"}
    values |= {"show": None, "log": False, "vmax": None}
    return argparse.Namespace(**{**values, **changed})


def fire(fig, name, x, y, **kwargs):
    fig.canvas.callbacks.process(name, MouseEvent(name, fig.canvas, x, y, **kwargs))


def test_cell_index_follows_edges_in_either_direction():
    assert [cell_index([0.0, 1.0, 2.0, 3.0], v) for v in (-0.1, 0.0, 1.5, 2.99, 3.0)] == [
        None,
        0,
        1,
        2,
        None,
    ]
    assert [cell_index([3.0, 2.0, 1.0, 0.0], v) for v in (3.0, 1.5, 0.0)] == [0, 1, None]


def test_the_row_map_numbers_the_points_in_the_order_they_were_measured():
    assert point_map(mesh_scan(), "Sample_X", "Sample_Y").values.tolist() == [
        [0, 3],
        [1, 4],
        [2, 5],
    ]


def test_a_place_on_the_map_gives_the_point_measured_there():
    probe = probe_of()
    assert probe.point_of(probe.cell_at(2.0, 1.0)) == 5
    assert probe.point_of(probe.cell_at(1.2, -0.2)) == 0
    assert probe.cell_at(3.0, 0.0) is None and probe.cell_at(2.0, 2.0) is None


def test_a_place_not_measured_gives_nothing():
    assert probe_of(points=4).cell_at(2.0, 0.5) is None


def test_the_tooltip_names_the_point_the_motors_and_the_counters():
    probe = probe_of()
    text = probe.tooltip(probe.point_of(probe.cell_at(2.0, 1.0)))
    assert text.splitlines() == [
        "point 5",
        "Sample_X = 2",
        "Sample_Y = 1",
        "imtot    = 6",
    ]


def test_show_limits_the_tooltip_to_the_names_asked_for():
    probe = probe_of(show=["sample y"])
    assert probe.tooltip(5).splitlines() == ["point 5", "Sample_X = 2", "Sample_Y = 1"]


def test_an_unknown_name_to_show_is_refused():
    with pytest.raises(SystemExit, match="has no 'nope'"):
        probe_of(show=["nope"]).values_at(0)


def write_mesh_file(tmp_path):
    path = tmp_path / "s.spec"
    path.write_text("\n".join(header() + mesh_block(1) + scan_block(2)), encoding="utf-8")
    with Spec(path) as spec:
        return spec.get_scan(1)


def test_hover_lists_the_point_in_the_panel_and_click_prints_it(tmp_path, capsys):
    fig, panel = draw(write_mesh_file(tmp_path), options())
    fig.canvas.draw()
    size = tuple(fig.get_size_inches())
    x, y = panel.ax.transData.transform((2.0, 0.5))
    assert "hover" in panel.text.get_text()

    fire(fig, "motion_notify_event", x, y)
    assert panel.hover_mark.get_visible()
    assert "Sample_X = 2" in panel.text.get_text() and "imtot" in panel.text.get_text()

    fire(fig, "button_press_event", x, y, button=1)
    printed = capsys.readouterr().out
    assert "Scan 1 point" in printed and "Counters:" in printed and panel.pin_mark.get_visible()

    fire(fig, "axes_leave_event", x, y)
    assert not panel.hover_mark.get_visible()
    assert "Sample_X = 2" in panel.text.get_text()  # the clicked cell stays listed
    assert tuple(fig.get_size_inches()) == size
