# Rocking curves and peak widths

## Rocking curves

`splotter rock` overlays scans against their first column, each normalized to its maximum, on a log
scale.

```
splotter rock demo.spec 6 7 8 --counter imroi3
```

| Option | Effect |
|---|---|
| `--counter NAME` | The counter to draw (default `imroi1`) |
| `--labels TEXT ...` | One legend label per scan (default: the run numbers) |
| `--save FILE` | Write the figure to a file instead of opening a window |
| `--wait` | Keep the window in this terminal until it is closed |

## Peak width against Q

`splotter fwhm` fits a Gaussian to each scan of a list and plots its full width at half maximum
against |Q|.

```
splotter fwhm demo.spec demo_fwhm.csv --energy 8 --counter imroi3
```

A scan list is a CSV file without a header, with the columns `scan, gamma, delta, theta`. Each list
is one series in the plot. `splotter demo` writes `demo_fwhm.csv` next to `demo.spec`.

|Q| comes from the detector angles of the list: cos 2θ = cos γ · cos δ and |Q| = 4π sin θ / λ.

| Option | Effect |
|---|---|
| `--energy KEV` | Photon energy; required |
| `--gamma-offset DEG`, `--delta-offset DEG` | Subtracted from the angles of the list (default 0) |
| `--counter NAME` | The counter to fit (default `imroi1`) |
| `--labels TEXT ...` | One legend label per list (default: the file names) |
| `--save FILE` | Write the figure to a file instead of opening a window |
| `--wait` | Keep the window in this terminal until it is closed |

The width is the fit of the data as recorded. It is not corrected for the resolution of the
instrument.

## Gamma and delta

`splotter gamdel` plots the detector angles of a list of runs and opens a window with a slider for
2θ, to compare them with the arc of one 2θ. It needs a screen.

```
splotter gamdel demo.spec 6 7 8
```
