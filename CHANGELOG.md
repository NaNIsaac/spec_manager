# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `scan["th"]`: a data column as an array, or the start position (`#P`) of a motor that did not
  move, by name or by mnemonic. `scan.at(point)`, `scan.positioners_at_start`, `scan.axes` (the
  `#L` names of what the command scanned) and `scan.warnings` (a `#P` count that does not match
  the motor names).
- The `#o`, `#J` and `#j` header rows are read, so `sx` finds `Sample_X`.
- `splotter.command.ScanCommand` parses a `#S` command in the forms of the standard SPEC macros:
  `ascan`, `a2scan`, `a3scan`, `dscan`/`lup`, `d2scan`, `d3scan`, `th2th`, `mesh`, `dmesh`,
  `hscan`/`kscan`/`lscan`, `hklscan` and `hklmesh`. Other commands are kept with no axes.
- `timescan [count [sleep]]` and `loopscan points count [sleep]` are known commands too, with
  `Time` as their axis (`Space.TIME`) and the sleep time in `ScanCommand.sleep`. A timescan has no
  planned number of points. A file whose time scan has no `Time` column gives it no axes.
- `scan.column(name)` and `scan.motor(name)`: the `#L` column or `#O` motor meant by a name or a
  mnemonic.
- `splotter fwhm --scans RUN ...`: a series without a scan list, with gamma and delta from `#P`;
  `--gamma` and `--delta` name those motors in `fwhm` and `gamdel`.

### Changed

- `mesh`, `probe`, `info`, `rock`, `gamdel` and `fwhm` take motors and counters by mnemonic too
  (`--x sx`, `--counter det`, `-c tth`) where the file has `#o` and `#j` rows.
- `mesh` and `probe` read the motors and ranges from the parsed command, so `lup` maps as a line
  as `ascan` and `dscan` do, and a scan that is no map of two motors (`a2scan`, `hklmesh`,
  `timescan`) is refused by name. Without `--x` and `--y`, a mesh of motors other than `Sample_X`
  and `Sample_Y` puts its outer motor across and its inner one down.
- `rock` and `fwhm` take the axis of a curve from the command (`Time` for a time scan), not the
  first column, and stop with the columns listed when the counter is missing. The `rock` axis is
  labeled with that column instead of ω.
- `gamdel` stops with the motor named when a run lacks gamma or delta, instead of leaving it out.

- The plot windows of `mesh`, `probe`, `rock`, `gamdel` and `fwhm` open in a detached process,
  so the command returns and the terminal stays free; closing the terminal leaves the window open.
  Errors in the arguments are still reported in the terminal. `--wait` keeps the window in the
  terminal as before, and `--save` opens no window.

## [0.1.4] - 2026-11-03

### Changed

- `splotter probe` takes the arguments of `splotter mesh`: several runs, drawn on one map with the
  same axes, color scale, outlines and legend. Where scans overlap, the panel lists the later run.
  The drawing code is shared with `splotter mesh`.

## [0.1.3] - 2026-11-03

### Added

- `splotter probe FILE RUN`: the map of one scan, where hovering over a cell lists its point number,
  time, motor positions and counters in a fixed panel at the left, and clicking it prints everything
  recorded at that point.

## [0.1.2] - 2026-11-02

### Changed

- `splotter info` fits the terminal: motors and counters fill as many columns as the terminal is
  wide instead of four, a command too long for the scan list is cut short with `…`, and the counter
  summary prints compact numbers (`2103.23`, not `2103.231293`).

### Added

- `splotter info FILE -c NAME --scans RUN [RUN ...]`: motors at the start of the listed scans only,
  from a single read of the file.

## [0.1.1] - 2026-11-02

### Changed

- The `splotter mesh` window takes the shape of the map: tall for a tall map, wide for a wide one.
- The `splotter mesh` color scale ends at 10 times the mean instead of the maximum; `--vmax` sets it.
  The printed lines also give the mean of each scan.
- `splotter mesh` has minor ticks on the axes and the color bar, which keeps the height of the map.

### Added

- Documentation in `docs/`, a citation file, and a check that the README commands run.

## [0.1.0] - 2026-11-02

First release, under the new name splotter (formerly spec_manager).

### Added

- `splotter` command with `info`, `mesh`, `rock`, `gamdel`, `fwhm` and `demo`.
- `splotter demo`: writes a made-up SPEC file to try the commands on and to test them with.
- `splotter info`: scan list, point values, metadata, and values by column name (`-c`, `--top`,
  `--csv`, `--names`).
- `splotter mesh`: counter maps that combine mesh, ascan and dscan scans and mark what was not
  measured.

### Fixed

- Motor and column names with a space (`Sample Y`) no longer shift the values after them.
- A SPEC session restarted inside a file no longer changes the time of the scan before it, and its
  motor names apply from there on.
- Times of points no longer depend on the file header.
- Scans that reuse a run number are kept: `12.1` and `12.2` name them, `12` the last one.
- Macro output between the data no longer enters the data.
- Files without a header, without scans or with bytes that are not UTF-8 no longer stop the commands.

### Changed

- The code is a package: `from spec import Spec` is now `from splotter.spec import Spec`.
- `rocking_curve.py` and `main.py` are now `splotter rock` and `splotter fwhm`, and take scans and
  scan lists as arguments instead of hardcoded values.
- `splotter fwhm` requires `--energy`, and its gamma and delta offsets default to 0. The figure of
  the 2025-06-26 data used `--energy 5.55 --gamma-offset 1.4367 --delta-offset 0.0112`.
