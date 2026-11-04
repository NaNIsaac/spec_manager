import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.widgets import Slider, TextBox

from splotter import window
from splotter.spec import Spec, SpecScan, run_id, scan_or_exit


def calculate_theory_delta(gamma_array, tth):
    gam_rad = np.radians(gamma_array)
    tth_rad = np.radians(tth)
    cos_val = np.cos(tth_rad) / np.cos(gam_rad)
    cos_val = np.clip(cos_val, -1.0, 1.0)
    return np.degrees(np.arccos(cos_val))


def detector_angles(scan: SpecScan, gamma: str, delta: str) -> tuple[float, float]:
    """Gamma and delta at the start of the scan (#P), from motors named or given by mnemonic."""
    found = {name: scan.motor(name) for name in (gamma, delta)}
    missing = [name for name, motor in found.items() if motor is None]
    if missing:
        raise SystemExit(
            f"scan {scan.label} has no motor '{missing[0]}'; "
            "splotter info FILE RUN --names lists what it has"
        )
    return scan.motors[found[gamma]], scan.motors[found[delta]]


def load_run_data(
    sp: Spec, run_ns: list[str], gamma: str = "Gamma", delta: str = "Delta"
) -> pd.DataFrame:
    """Gamma and delta of the given runs as a DataFrame, in the order of run_ns."""
    data = []
    for run_n in run_ns:
        g, d = detector_angles(scan_or_exit(sp, run_n), gamma, delta)
        data.append({"run_n": run_n, "gamma": g, "delta": d})
    return pd.DataFrame(data)


def add_angle_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--gamma", default="Gamma", help="detector motor of gamma, name or mnemonic"
    )
    parser.add_argument(
        "--delta", default="Delta", help="detector motor of delta, name or mnemonic"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Measured gamma/delta of runs against the theoretical arc of one 2theta."
    )
    parser.add_argument("spec_file", type=Path)
    parser.add_argument(
        "runs", type=run_id, nargs="+", help="run numbers, plotted in the given order"
    )
    add_angle_arguments(parser)
    window.add_arguments(parser)
    args = parser.parse_args()
    spec_file, run_ns = args.spec_file, args.runs

    with Spec(spec_file) as sp:
        df = load_run_data(sp, run_ns, args.gamma, args.delta)
    gamma_data = df["gamma"].values
    delta_data = df["delta"].values

    fig, ax = plt.subplots(figsize=(11, 8))
    plt.subplots_adjust(bottom=0.25)

    # no sorting: the line joins the points in run_ns order
    ax.plot(
        gamma_data,
        delta_data,
        color="black",
        lw=2.0,
        marker="o",
        markersize=6,
        alpha=0.8,
        label="Measured Run Data",
    )

    (theory_line,) = ax.plot(
        [], [], color="crimson", lw=2.5, linestyle="--", label="Theoretical Casing Arc"
    )

    ax.set_title(
        r"Diffractometer Space Check: Spec Data vs Pure Theoretical Curve",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_xlabel(r"Gamma ($\gamma$) [deg]", fontsize=11)
    ax.set_ylabel(r"Delta ($\delta$) [deg]", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.6)

    border_width = 1.5
    for side in ["top", "bottom", "left", "right"]:
        ax.spines[side].set_linewidth(border_width)
    ax.tick_params(direction="in", length=5, width=border_width, labelsize=10, top=True, right=True)

    ax_tth = plt.axes([0.15, 0.11, 0.45, 0.03])
    ax_txt = plt.axes([0.72, 0.11, 0.15, 0.03])

    init_tth = 70.0
    STEP_SIZE = 0.001

    s_tth = Slider(
        ax_tth,
        r"True $2\theta$ (°)",
        30.0,
        120.0,
        valinit=init_tth,
        valstep=STEP_SIZE,
        valfmt="%.3f",
        color="teal",
    )
    t_tth = TextBox(ax_txt, r"Direct $2\theta$ ", initial=str(init_tth))

    # the theory curve spans the gamma range of the data, sampled finely to look smooth
    g_range = np.linspace(gamma_data.min() - 4, gamma_data.max() + 4, 500)

    def update(val=None):
        current_tth = s_tth.val
        y_theory = calculate_theory_delta(g_range, current_tth)
        theory_line.set_data(g_range, y_theory)
        fig.suptitle(
            f"True $2\\theta$ (Adjusted): {current_tth:.3f}°\n(Use Mouse or Left/Right Arrow Keys)",
            fontsize=12,
            fontweight="bold",
            color="darkblue",
        )
        fig.canvas.draw_idle()

    def submit(text):
        try:
            val = float(text)
            s_tth.set_val(val)
        except ValueError:
            pass

    def on_key_press(event):
        if event.key == "right":
            new_val = min(s_tth.valmax, s_tth.val + STEP_SIZE)
            s_tth.set_val(new_val)
        elif event.key == "left":
            new_val = max(s_tth.valmin, s_tth.val - STEP_SIZE)
            s_tth.set_val(new_val)

    s_tth.on_changed(update)
    t_tth.on_submit(submit)
    fig.canvas.mpl_connect("key_press_event", on_key_press)

    ax.set_xlim(gamma_data.min() - 2, gamma_data.max() + 2)
    ax.set_ylim(delta_data.min() - 1, delta_data.max() + 1)
    ax.legend(loc="upper right", frameon=True)

    update()
    window.show(args, __spec__.name)


if __name__ == "__main__":
    main()
