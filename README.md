# splotter

Read SPEC scan files from the command line: list the scans, pull values by column name, look up
metadata, and draw mesh maps that combine several scans.

The name comes from `splot`, the plotting command in SPEC. splotter is an independent project and
is not affiliated with or endorsed by [Certified Scientific Software](https://certif.com/), the
makers of SPEC.

## Install

Requires Python 3.13 or newer.

```
pip install splotter
```

## Try it

No measured data ships with splotter. `splotter demo` writes a made-up SPEC file, the same one every
time, and the examples below run on it:

```
splotter demo demo.spec
```

| Scan | What it is |
|---|---|
| 1 | Mesh of `sx` and `sy`, with a bright spot at `sx` = 0.4, `sy` = -0.3 |
| 2 | Mesh next to scan 1, overlapping it |
| 3, 4 | `ascan` of `sx` and of `sy` through the bright spot |
| 5 | Mesh aborted after 100 of its 231 points |
| 6-8 | Rocking scans of `th`, named by the scan list `demo_fwhm.csv` |

## Commands

Every command takes the path of the SPEC file first. `splotter COMMAND --help` lists the options.

| Command | What it does |
|---|---|
| `splotter info` | Scan list, scan summary, values of one point, metadata, values by column name |
| `splotter mesh` | Map of a counter over two motors, from one or several scans |
| `splotter rock` | Normalized rocking curves on a log scale |
| `splotter gamdel` | Measured gamma/delta against the arc of one 2theta (interactive) |
| `splotter fwhm` | Gaussian FWHM of rocking scans against Q |
| `splotter demo` | Write the made-up SPEC file |

### Look at scans

```
splotter info demo.spec --last 3      # scan number, start time, duration, points, command
splotter info demo.spec 1             # times, motors at the start, range of each counter
splotter info demo.spec 1 301         # time, motors and counters of point 301 (counted from 0)
splotter info demo.spec 1 --meta      # #T, #Q lines and the #UXML metadata
splotter info demo.spec --meta        # file header
```

### Pull values by name

`-c` prints only the named data columns and motors, as a table. `time` gives the clock time of each
point, computed from the `Epoch` column and the `#D` line of the file header.

```
splotter info demo.spec 1 -c time Sample_X Sample_Y imtot
splotter info demo.spec 1 -c imtot Sample_X Sample_Y --top 5    # the 5 points largest in imtot
splotter info demo.spec 1 -c Sample_X imtot --csv > scan1.csv
splotter info demo.spec -c time Delta Gamma --last 3            # motors at the start of each scan
splotter info demo.spec 1 --names                               # the names -c accepts
```

### Draw mesh maps

```
splotter mesh demo.spec 1 --counter imroi3 --log
splotter mesh demo.spec 1 2 5 3 4 --log --save map.png
```

Scans share one set of axes and one color scale, and can be `mesh`, `ascan` or `dscan` scans.

- Places that were not measured, including the missing points of an aborted scan, are hatched gray.
- Where scans overlap, the run given later is drawn on top.
- Each scan gets its own outline, named in the legend.
- With `--log`, zero counts take the lowest color, so they do not look unmeasured.
- The axes are `Sample_X` and `Sample_Y` unless `--x` and `--y` name other motors.

### Rocking curves and peak widths

```
splotter rock demo.spec 6 7 8 --counter imroi3
splotter gamdel demo.spec 6 7 8
splotter fwhm demo.spec demo_fwhm.csv --energy 8 --counter imroi3
```

The scan lists for `fwhm` are CSV files without a header, with the columns
`scan, gamma, delta, theta`.

## Python

```python
from splotter.spec import Spec

with Spec("demo.spec") as spec:
    scan = spec.get_scan(1)
    scan.command, scan.time, scan.motors["Delta"]
    df = scan.to_dataframe()  # columns named as in #L
    scan.uxml  # #UXML as a dict
```

## Status

Alpha. The tests run on generated data (`splotter demo` and `tests/synthetic_spec.py`). The commands
were also run on one measured file from one beamline, so other SPEC setups may differ, in particular
in motor names.

[QoraGeom](https://github.com/NaNIsaac/QoraGeom) has its own, extended copy of this parser as
`qorageom.spec`.

## Development

```
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
```

## License

MIT, see [LICENSE](LICENSE).
