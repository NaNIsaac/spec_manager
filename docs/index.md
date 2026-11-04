# Overview

splotter reads the scan files that [SPEC](https://certif.com/) writes at X-ray diffraction
beamlines. It lists the scans of a file, prints the motors and counters of a scan or of one measured
point, shows the metadata, and draws counter maps, rocking curves and peak widths. It also gives
Python a small parser for the same files.

It works on a SPEC file alone. It does not read detector frames, and it does not map data to
reciprocal space: that analysis is in [CXD](https://github.com/NaNIsaac/CXD), with the geometry in
[QoraGeom](https://github.com/NaNIsaac/QoraGeom).

splotter is an independent project, not affiliated with or endorsed by Certified Scientific Software.

Start with [installation](install.md) and the [tutorial](tutorial.md). Then:

- [Looking up scans](guides/looking-up-scans.md)
- [The shell and a growing file](guides/shell.md)
- [Mesh maps](guides/mesh-maps.md)
- [Rocking curves and peak widths](guides/rocking-and-widths.md)
- [SPEC files across the years](guides/spec-formats.md)

See the [changelog](https://github.com/NaNIsaac/splotter/blob/main/CHANGELOG.md),
[citation](https://github.com/NaNIsaac/splotter/blob/main/CITATION.cff) and
[figure reproduction](media/README.md).
