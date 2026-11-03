# splotter

[![PyPI](https://img.shields.io/pypi/v/splotter)](https://pypi.org/project/splotter/) [![Tests](https://github.com/NaNIsaac/splotter/actions/workflows/tests.yml/badge.svg)](https://github.com/NaNIsaac/splotter/actions/workflows/tests.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Read SPEC scan files from the command line: list scans, pull values by column name, look up metadata
and draw mesh maps that combine several scans.

<img src="https://raw.githubusercontent.com/NaNIsaac/splotter/main/docs/media/mesh_map.png" width="520" alt="Three mesh scans and two line scans of a made-up SPEC file on one map, with the unmeasured area hatched gray">

Three meshes and two line scans of the made-up file from `splotter demo`, on one map ([reproduce the figure](docs/media/README.md)).

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
$ uv run -q --directory splotter-demo splotter info demo.spec 1 -c imtot Sample_X Sample_Y --top 1 --csv
point,imtot,Sample_X,Sample_Y
301,97699.0,0.4,-0.3
```

That is the brightest point of the mesh in scan 1. Every command takes the SPEC file first:

```
splotter info FILE --last 20                 # scan list: start time, duration, points, command
splotter info FILE 2032 669                  # time, motors and counters of one point
splotter info FILE 2032 -c imtot Sample_X    # values by column name
splotter info FILE 2032 --meta               # #T, #Q, #R lines and #UXML metadata
splotter mesh FILE 2032 2036 --log           # map of several scans
splotter probe FILE 2614 2616 --log          # the same map: hover a cell for its values, click to print them
splotter rock FILE 2033 --counter imroi1     # rocking curve
```

A plot opens in a window of its own and the command returns at once, so the terminal stays free.
`--wait` keeps the window in the terminal until it is closed; `--save FILE` writes the figure and
opens no window.

## Documentation

- [Overview](docs/index.md), [installation](docs/install.md) and [tutorial](docs/tutorial.md).
- [Looking up scans](docs/guides/looking-up-scans.md): the scan list, points, column names, metadata.
- [Mesh maps](docs/guides/mesh-maps.md): combining scans and what the hatching means.
- [Rocking curves and peak widths](docs/guides/rocking-and-widths.md).
- [SPEC files across the years](docs/guides/spec-formats.md): what the parser handles, and its limits.
- [Changelog](CHANGELOG.md) and [citation](CITATION.cff).

## Development

```
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
```

## License

MIT, see [LICENSE](LICENSE).
