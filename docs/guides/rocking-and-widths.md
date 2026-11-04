# Rocking curves and peak widths

## Rocking curves

`splotter rock` overlays scans against the motor their command scanned, each normalized to its
maximum, on a log scale. A `timescan` or `loopscan` runs against `Time`, and a command splotter does
not know against the first column. The horizontal axis is labeled with that column.

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

Without a list, `--scans` names the runs of one series and takes gamma and delta from the start
positions (`#P`) of each scan; give it again for another series:

```
splotter fwhm demo.spec --scans 6 7 8 --energy 8 --counter imroi3
```

|Q| comes from the detector angles: cos 2θ = cos γ · cos δ and |Q| = 4π sin θ / λ.

| Option | Effect |
|---|---|
| `--energy KEV` | Photon energy; required |
| `--scans RUN ...` | One series of runs, with gamma and delta from `#P` |
| `--gamma NAME`, `--delta NAME` | The detector motors `--scans` reads (default `Gamma`, `Delta`) |
| `--gamma-offset DEG`, `--delta-offset DEG` | Subtracted from the angles (default 0) |
| `--counter NAME` | The counter to fit (default `imroi1`) |
| `--labels TEXT ...` | One legend label per series, lists first (default: the file names, or the runs) |
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

| Option | Effect |
|---|---|
| `--gamma NAME`, `--delta NAME` | The detector motors, by name or mnemonic (default `Gamma`, `Delta`) |
| `--wait` | Keep the window in this terminal until it is closed |

A run without one of the two motors stops the command with its name.
