# Command-line reference

<!-- written by tools/argparse_markdown.py from splotter.cli:parsers; edit the parsers -->

| Command | What it does |
|---|---|
| [`splotter info`](#splotter-info) | Times, motors, counters and metadata of the scans in a SPEC file. |
| [`splotter mesh`](#splotter-mesh) | Map of one counter over the motor positions of SPEC mesh and line scans. |
| [`splotter probe`](#splotter-probe) | The map of splotter mesh, to point at: hover over a cell and the panel at its left lists the scan, point number, motor positions and counters; click to mark the cell and print everything recorded there. |
| [`splotter rock`](#splotter-rock) | Normalized rocking curves of SPEC scans, log scale: the counter against what the command scanned, or against the first column for a command not known. |
| [`splotter gamdel`](#splotter-gamdel) | Measured gamma/delta of runs against the theoretical arc of one 2theta. |
| [`splotter fwhm`](#splotter-fwhm) | Gaussian FWHM of rocking scans vs Q: one series per scan-list CSV and one per --scans, whose gamma and delta are read from the file. |
| [`splotter shell`](#splotter-shell) | Read a SPEC file once and query it at a prompt: ls, show, wa, pa, the plot commands, and tail to follow the file as it grows. |
| [`splotter demo`](#splotter-demo) | Write a made-up SPEC file to try the commands on; nothing in it is measured. |

## splotter info

Times, motors, counters and metadata of the scans in a SPEC file.

```
usage: splotter info [-h] [--meta] [--last LAST] [--scans RUN [RUN ...]] [-c NAME [NAME ...]]
                     [--top N] [--csv] [--names]
                     spec_file [scan] [point]
```

### Positional arguments

| Argument | Description |
|---|---|
| `spec_file` | the SPEC file to read |
| `scan` | run number, 12.2 for the second scan numbered 12; default: list all scans of the file |
| `point` | data row of the scan, counted from 0 (default: summary of the whole scan) |

### Options

| Argument | Description |
|---|---|
| `--meta` | metadata of the scan, or of the file without a scan |
| `--last LAST` | list only the last N scans |
| `--scans RUN [RUN ...]` | with -c and no scan: only these scans, read in one go |
| `-c, --columns NAME [NAME ...]` | print only these as a table: data columns or motors of the scan, by name or mnemonic, and 'time'; without a scan, motors at the start of each scan |
| `--top N` | with -c: the N points largest in the first column |
| `--csv` | with -c: comma-separated output |
| `--names` | list the names -c accepts |

## splotter mesh

Map of one counter over the motor positions of SPEC mesh and line scans. Several scans share the axes and the color scale; later runs draw over earlier ones.

```
usage: splotter mesh [-h] [--counter COUNTER] [--x X] [--y Y] [--log] [--vmax VMAX] [--save SAVE]
                     [--wait]
                     spec_file scans [scans ...]
```

### Positional arguments

| Argument | Description |
|---|---|
| `spec_file` | the SPEC file to read |
| `scans` | mesh, ascan or dscan run numbers |

### Options

| Argument | Description |
|---|---|
| `--counter COUNTER` | name or mnemonic, e.g. imtot, imroi1, imroi2, immax |
| `--x X` | motor of the horizontal axis, name or mnemonic (default: Sample_X if the scans move Sample_X or Sample_Y, else the outer motor of the first mesh) |
| `--y Y` | motor of the vertical axis (default: Sample_Y, or the inner motor of the first mesh) |
| `--log` | log color scale; zero counts take its lowest color |
| `--vmax VMAX` | top of the color scale (default: 10 times the mean of the scans) |
| `--save SAVE` | write the figure here instead of showing it |
| `--wait` | keep the window in this terminal until it is closed (default: return at once) |

## splotter probe

The map of splotter mesh, to point at: hover over a cell and the panel at its left lists the scan, point number, motor positions and counters; click to mark the cell and print everything recorded there. Where scans overlap, the later run is the one listed.

```
usage: splotter probe [-h] [--counter COUNTER] [--x X] [--y Y] [--log] [--vmax VMAX]
                      [--show NAME [NAME ...]] [--wait]
                      spec_file scans [scans ...]
```

### Positional arguments

| Argument | Description |
|---|---|
| `spec_file` | the SPEC file to read |
| `scans` | mesh, ascan or dscan run numbers |

### Options

| Argument | Description |
|---|---|
| `--counter COUNTER` | name or mnemonic, e.g. imtot, imroi1, imroi2, immax |
| `--x X` | motor of the horizontal axis, name or mnemonic (default: Sample_X if the scans move Sample_X or Sample_Y, else the outer motor of the first mesh) |
| `--y Y` | motor of the vertical axis (default: Sample_Y, or the inner motor of the first mesh) |
| `--log` | log color scale; zero counts take its lowest color |
| `--vmax VMAX` | top of the color scale (default: 10 times the mean of the scans) |
| `--show NAME [NAME ...]` | counters and motors in the panel, names or mnemonics (default: every counter) |
| `--wait` | keep the window in this terminal until it is closed (default: return at once) |

## splotter rock

Normalized rocking curves of SPEC scans, log scale: the counter against what the command scanned, or against the first column for a command not known.

```
usage: splotter rock [-h] [--labels LABELS [LABELS ...]] [--counter COUNTER] [--save SAVE] [--wait]
                     spec_file scans [scans ...]
```

### Positional arguments

| Argument | Description |
|---|---|
| `spec_file` | the SPEC file to read |
| `scans` |  |

### Options

| Argument | Description |
|---|---|
| `--labels LABELS [LABELS ...]` | one legend label per scan (default: scan number) |
| `--counter COUNTER` | name or mnemonic |
| `--save SAVE` | write the figure here instead of showing it |
| `--wait` | keep the window in this terminal until it is closed (default: return at once) |

## splotter gamdel

Measured gamma/delta of runs against the theoretical arc of one 2theta.

```
usage: splotter gamdel [-h] [--gamma GAMMA] [--delta DELTA] [--wait] spec_file runs [runs ...]
```

### Positional arguments

| Argument | Description |
|---|---|
| `spec_file` | the SPEC file to read |
| `runs` | run numbers, plotted in the given order |

### Options

| Argument | Description |
|---|---|
| `--gamma GAMMA` | detector motor of gamma, name or mnemonic |
| `--delta DELTA` | detector motor of delta, name or mnemonic |
| `--wait` | keep the window in this terminal until it is closed (default: return at once) |

## splotter fwhm

Gaussian FWHM of rocking scans vs Q: one series per scan-list CSV and one per --scans, whose gamma and delta are read from the file.

```
usage: splotter fwhm [-h] [--scans RUN [RUN ...]] [--labels LABELS [LABELS ...]] --energy ENERGY
                     [--gamma-offset GAMMA_OFFSET] [--delta-offset DELTA_OFFSET] [--counter COUNTER]
                     [--gamma GAMMA] [--delta DELTA] [--save SAVE] [--wait]
                     spec_file [csv_files ...]
```

### Positional arguments

| Argument | Description |
|---|---|
| `spec_file` | the SPEC file to read |
| `csv_files` | headerless CSV: scan, gamma, delta, theta |

### Options

| Argument | Description |
|---|---|
| `--scans RUN [RUN ...]` | one series of runs, with gamma and delta from #P; give it again for another |
| `--labels LABELS [LABELS ...]` | one legend label per series, CSVs first (default: file stem, or the runs) |
| `--energy ENERGY` | keV (required) |
| `--gamma-offset GAMMA_OFFSET` | deg |
| `--delta-offset DELTA_OFFSET` | deg |
| `--counter COUNTER` | name or mnemonic |
| `--gamma GAMMA` | detector motor of gamma, name or mnemonic |
| `--delta DELTA` | detector motor of delta, name or mnemonic |
| `--save SAVE` | write the figure here instead of showing it |
| `--wait` | keep the window in this terminal until it is closed (default: return at once) |

## splotter shell

Read a SPEC file once and query it at a prompt: ls, show, wa, pa, the plot commands, and tail to follow the file as it grows.

```
usage: splotter shell [-h] spec_file
```

### Positional arguments

| Argument | Description |
|---|---|
| `spec_file` | the SPEC file to read |

## splotter demo

Write a made-up SPEC file to try the commands on; nothing in it is measured.

```
usage: splotter demo [-h] [--force] out
```

### Positional arguments

| Argument | Description |
|---|---|
| `out` | SPEC file to write, e.g. demo.spec |

### Options

| Argument | Description |
|---|---|
| `--force` | overwrite existing files |
