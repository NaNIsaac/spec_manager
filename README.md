# splotter

[![PyPI](https://img.shields.io/pypi/v/splotter)](https://pypi.org/project/splotter/) [![Tests](https://github.com/NaNIsaac/splotter/actions/workflows/tests.yml/badge.svg)](https://github.com/NaNIsaac/splotter/actions/workflows/tests.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

splotter reads the scan files that SPEC writes at X-ray diffraction beamlines. From the command line
it lists the scans of a file, prints the motors and counters of a scan or of one point, pulls values
by column name, shows the metadata, and plots counter maps, rocking curves, detector angles and peak
widths. The same parser is a small Python library.

It works on the SPEC file alone: it does not read detector images.

The name comes from `splot`, the plotting command in SPEC. splotter is an independent project and is
not affiliated with or endorsed by [Certified Scientific Software](https://certif.com/), the makers
of SPEC.

## Install

Requires Python 3.13 or later. Install it as a command with `uv tool install splotter` or
`pip install splotter`, or create a small uv project:

<!-- test -->
```sh
uv init --no-workspace --python 3.13 splotter-demo
uv add --directory splotter-demo splotter
```

## Quick start

No measured data ships with splotter. `splotter demo` writes a made-up SPEC file, the same one every
time. Run this from the directory where you created `splotter-demo`:

<!-- test console -->
```console
$ uv run -q --directory splotter-demo splotter demo demo.spec
wrote demo.spec
wrote demo_fwhm.csv
$ uv run -q --directory splotter-demo splotter info demo.spec --last 3
scan  start                duration  points  command
   6  2026-01-01 09:17:09   0:00:40      41  ascan th 14.5 15.5 40 0.5
   7  2026-01-01 09:18:21   0:00:40      41  ascan th 19.5 20.5 40 0.5
   8  2026-01-01 09:19:33   0:00:40      41  ascan th 24.5 25.5 40 0.5
$ uv run -q --directory splotter-demo splotter info demo.spec 1 -c imtot Sample_X Sample_Y --top 1 --csv
point,imtot,Sample_X,Sample_Y
301,97699.0,0.4,-0.3
```

The first is the scan list; the second is the brightest point of the mesh in scan 1.

## Commands

Every command takes the SPEC file first, then run numbers. `splotter COMMAND --help` lists the
options.

| Command | What it does |
|---|---|
| `info` | Scan list, the summary of one scan, the values at one point, columns by name, metadata |
| `rock` | Rocking curves of several scans, each normalized to its maximum, on a log scale |
| `fwhm` | Gaussian FWHM of rocking scans against the momentum transfer Q |
| `gamdel` | Measured detector angles gamma and delta against the arc of one 2θ |
| `mesh` | Map of a counter over two motors, from one mesh or several mesh and line scans |
| `probe` | The `mesh` map in a window that lists the values of the cell under the pointer |
| `demo` | A made-up SPEC file to try the commands on |

Motors and counters are taken by name (`Sample_X`) or by the mnemonic the file records (`sx`) in
every command. A run number that was used twice in a file, as after a restart, is told apart as
`12.1` and `12.2`; `12` is the last one.

### Looking up scans

```
splotter info FILE                         # every scan: start time, duration, points, command
splotter info FILE --last 20               # the last 20 scans
splotter info FILE 6                       # one scan: times, motors at the start, counter ranges
splotter info FILE 6 20                    # every motor and counter at point 20 of scan 6
splotter info FILE 6 -c th imroi1          # columns by name, one row per point
splotter info FILE 6 -c imroi1 th --top 5  # the 5 points largest in imroi1
splotter info FILE -c Sample_X Sample_Y    # motors at the start of each scan
splotter info FILE 6 --names               # the names -c accepts in scan 6
splotter info FILE 6 --meta                # #T, #Q, #R lines and the #UXML metadata of scan 6
splotter info FILE --meta                  # the file header
```

`--csv` writes the `-c` table comma-separated, for a spreadsheet or another program.

### Plots

```
splotter rock FILE 6 7 8 --counter imroi1          # rocking curves, one per scan
splotter fwhm FILE list.csv --energy 10            # FWHM against Q for the scans of a list
splotter fwhm FILE --scans 6 7 8 --energy 10       # the same, gamma and delta read from the file
splotter gamdel FILE 6 7 8                         # detector angles of the runs, in this order
splotter mesh FILE 1 2 5 --log                     # one map of three scans
splotter probe FILE 1 2 5 --log                    # the same map, to hover over and click
```

A plot opens in a window of its own and the command returns, so the terminal stays free; `--wait`
keeps the window in the terminal instead. `mesh`, `rock` and `fwhm` take `--save FILE.png` to
write the figure without a window.

`rock` plots each counter against what the scan command moved. `fwhm` fits a Gaussian to each scan
and computes Q from the beam energy and the detector angles, which come from a headerless CSV of
`scan, gamma, delta, theta` or from the `#P` motor positions. `mesh` and `probe` take the two motors
from the scan command, put several scans on one set of axes and one color scale, and hatch the area
no scan measured:

<img src="https://raw.githubusercontent.com/NaNIsaac/splotter/main/docs/media/mesh_map.png" width="420" alt="Three mesh scans and two line scans of a made-up SPEC file on one map, with the unmeasured area hatched gray">

Three meshes and two line scans of the made-up file from `splotter demo`
([reproduce the figure](docs/media/README.md)).

### Python

```python
from splotter.spec import Spec

with Spec("demo.spec") as spec:
    scan = spec.get_scan(6)
    scan.command  # 'ascan  th 14.5 15.5  40 0.5'
    scan.axes  # ('Theta',): the columns the command scanned
    scan["imroi1"]  # a data column as a NumPy array, by name or mnemonic
    scan["chi"]  # a motor that did not move: its position at the start
    scan.at(20)  # every motor and counter at point 20
    scan.to_dataframe()  # the data as a pandas DataFrame
    scan.uxml["ad_detector"]  # the #UXML metadata as nested dicts
```

`spec.all_scans` lists every scan in file order, and `spec.scans` maps each run number to its last
scan. `scan.scan_command` parses the `#S` command of the standard SPEC scan macros (`ascan`,
`dscan`, `a2scan`, `mesh`, `hklscan`, `timescan` and others) into motors, ranges and points.

## Documentation

- [Overview](docs/index.md), [installation](docs/install.md) and [tutorial](docs/tutorial.md).
- [Looking up scans](docs/guides/looking-up-scans.md): the scan list, points, column names, metadata.
- [Mesh maps](docs/guides/mesh-maps.md): combining scans and what the hatching means.
- [Rocking curves and peak widths](docs/guides/rocking-and-widths.md).
- [SPEC files across the years](docs/guides/spec-formats.md): what the parser handles, and its limits.
- [Changelog](CHANGELOG.md) and [citation](CITATION.cff).

## Performance

Time to read a file of about 60 MB, best and median of 10 runs:

| File | Step | 0.1.4 | main (7692ca6) |
|---|---|---|---|
| generated, 60 MB, 3704 scans | read (`with Spec(file)`) | 1.28 / 1.45 s | 0.45 / 0.49 s |
| | read and build the frame of every scan | 2.14 / 2.37 s | 1.08 / 1.16 s |
| a 62 MB scan log, 3753 scans | read | 1.36 / 1.46 s | 0.45 / 0.49 s |
| | read and build the frame of every scan | 2.19 / 2.34 s | 1.14 / 1.18 s |

AMD Ryzen 5 7500F (6 cores, 12 threads), Windows 11, Python 3.13.14. The generated file has the
line mix of a measured log (30-column ascans, a few meshes and time scans, `#P` and `#UXML` lines);
[`benchmarks/parse_speed.py`](benchmarks/parse_speed.py) writes it from a fixed seed and times both
versions by turns, each in a process of its own:

```sh
uv run python benchmarks/parse_speed.py --against 0.1.4
uv run python benchmarks/parse_speed.py --against 0.1.4 --file YOUR.spec
```

## Development

```
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
```

## License

MIT, see [LICENSE](LICENSE).
