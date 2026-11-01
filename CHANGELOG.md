# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - unreleased

First release, under the new name splotter (formerly spec_manager).

### Added

- `splotter` command with `info`, `mesh`, `rock`, `gamdel`, `fwhm` and `demo`.
- `splotter demo`: writes a made-up SPEC file to try the commands on and to test them with.
- `splotter info`: scan list, point values, metadata, and values by column name (`-c`, `--top`,
  `--csv`, `--names`).
- `splotter mesh`: counter maps that combine mesh, ascan and dscan scans and mark what was not
  measured.

### Changed

- The code is a package: `from spec import Spec` is now `from splotter.spec import Spec`.
- `rocking_curve.py` and `main.py` are now `splotter rock` and `splotter fwhm`, and take scans and
  scan lists as arguments instead of hardcoded values.
- `splotter fwhm` requires `--energy`, and its gamma and delta offsets default to 0. The figure of
  the 2025-06-26 data used `--energy 5.55 --gamma-offset 1.4367 --delta-offset 0.0112`.
