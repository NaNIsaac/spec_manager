# The shell and a growing file

`splotter shell FILE` reads a SPEC file once and then answers at a `splotter>` prompt, so a long
file is not read again for every question. With `tail on` it also follows the file while SPEC is
still writing it. The examples use the file from `splotter demo demo.spec`.

```
$ splotter shell demo.spec
demo.spec: 8 scans. help lists the commands, quit leaves.
splotter>
```

## Commands

```
ls                     # every scan: start time, duration, points, command
ls ascan 6-8           # scans of a kind, in a range of run numbers; ls 2 5-7 mesh mixes them
show 6                 # command, times, axes, motors at the start, range of each counter
wa 6                   # every motor at the start of scan 6, with its mnemonic
pa 6 th imroi1         # columns or motors by name or mnemonic, one row per point
tail on                # follow the file as it grows; tail off stops
quit                   # or exit, or Ctrl-D (Ctrl-Z and Enter on Windows)
```

`wa` lists names with their mnemonics:

```
splotter> wa 6
  Delta (del) = 30        Theta (th) = 14.5       Chi (chi) = 90
    Phi (phi) = 0            Mu (mu) = 0        Gamma (gam) = 0
Sample_X (sx) = 0      Sample_Y (sy) = 0
```

`pa` gives a motor the scan moved at every point, and one that did not move once, at its start
position. A wrong run number or name prints what went wrong and keeps the shell open.

The plot commands of the command line work at the prompt with the same options, on this file:
`rock 6 7 8 --counter imroi1`, `mesh 1 2 5 --log`, `probe 1 2 5`, `gamdel 6 7 8` and
`fwhm --scans 6 7 8 --energy 10`. Their windows open as from the command line, in a process of
their own that reads the file again, so the prompt stays free. `help` lists every command and
`help pa` explains one.

## Following a file

With `tail on`, each command and each empty line (Enter) first reads what the file gained, and
lists scans that started and ended:

```
splotter> tail on
splotter>
scan 9 started: ascan  th 29.5 30.5  40 0.5
splotter>
scan 9 ended (complete), 41 points
```

A scan ends for one of four reasons:

- `next scan`: the next `#S` line was written.
- `aborted`: a `#C` comment says "Scan aborted", as SPEC writes after Ctrl-C.
- `complete`: the scan has the number of points its command plans, such as 41 for
  `ascan th 29.5 30.5 40 0.5`. A `timescan` plans none, so it ends only in the other ways.
- `new session`: SPEC was restarted and wrote a new file header.

Only complete lines are read: a line SPEC is still writing waits for its newline. If the file is
replaced or cut shorter, it is read again from the start and the shell says so.

### Files on a network share

Each refresh asks for the size and modification time of the file, which costs microseconds. A
network share can report an old size for a while, so when nothing seems to change for 10 seconds,
the next refresh opens the file anyway and checks its size and the 4 KB at its start and before the
last line read. The whole file is read again only when those disagree.

## From Python

`Spec.refresh()` is what the shell uses. It returns what happened since the last read as a list of
events:

```python
from splotter.spec import FileReread, PointsAdded, ScanEnded, ScanStarted, Spec

with Spec("demo.spec") as spec:
    pass  # the whole file as it is now

for event in spec.refresh():
    match event:
        case ScanStarted(scan=scan):
            print("started", scan.label, scan.command)
        case PointsAdded(scan=scan, lines=lines):
            print(scan.label, "has", len(scan.data), "points")
        case ScanEnded(scan=scan, reason=reason):
            print("ended", scan.label, reason)
        case FileReread():
            print("read again:", len(spec.all_scans), "scans")
```

Call it as often as you like: on a file that did not change it returns `[]` after one `stat`. A
scan's rows, columns and frame include the new points the next time they are asked for.
