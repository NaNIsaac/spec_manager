# Looking up scans

`splotter info` reads one SPEC file. What it prints depends on what you ask for. The examples use the
file from `splotter demo demo.spec`.

## The scan list

```
splotter info demo.spec              # all scans
splotter info demo.spec --last 3     # the last three
```

Each line has the run number, the start time, the time to the last point, the number of points and
the command. To search the list, filter it with your shell, for example
`splotter info demo.spec | Select-String mesh` in PowerShell or `| grep mesh` elsewhere.

## One scan

`splotter info demo.spec 1` prints the command, the times, the motors at the start of the scan and
the range of each counter, with the point where it peaks:

```
Scan 1: mesh sy -1 1 20 sx -1 1 20  0.5
Started: 2026-01-01 09:01:00
Last point: 2026-01-01 09:08:20
Points: 441

Motors at the start of the scan:
   Delta = 50.9             Theta = 25.45              Chi = 90                 Phi = 0
      Mu = 0                Gamma = 0             Sample_X = -1            Sample_Y = -1

Counters over the scan:
            min      max         mean  max_point
Epoch      62.0    502.0   282.000000        440
Seconds     0.5      0.5     0.500000          0
imtot    1104.0  97699.0  2103.231293        301
imroi1      0.0   1957.0    18.716553        301
imroi2      0.0   4976.0    50.623583        301
imroi3    525.0  90149.0  1434.022676        301
immax     118.0    465.0   157.142857        301
```

## One point

`splotter info demo.spec 1 301` prints the time, motors and counters of point 301. Points count from
0, in the order they were measured. A motor the scan moved shows its value at that point.

## Values by name

`-c` prints only what you name, as a table with one row per point:

```
splotter info demo.spec 1 -c time Sample_X imtot
```

```
                     time  Sample_X    imtot
point
0     2026-01-01 09:01:00      -1.0   1222.0
1     2026-01-01 09:01:01      -1.0   1197.0
```

| Option | Effect |
|---|---|
| `-c NAME ...` | Data columns and motors of the scan, and `time` |
| `--top N` | The N points largest in the first named column |
| `--csv` | Comma-separated output, for saving: `... --csv > scan1.csv` |
| `--names` | The names `-c` accepts for this scan |

Names match without regard to case, spaces and underscores, so `sample_x` finds `Sample_X` and the
`Sample X` of older files.

A motor that stays put gives one row, as its value would only repeat:

```
splotter info demo.spec 1 -c Delta Chi
```

```
       Delta   Chi
point
0       50.9  90.0
```

Add a point number to get that one row of a moved motor: `splotter info demo.spec 1 0 -c Sample_X`
is where the scan began.

Without a run number, `-c` reads the motors at the start of each scan. Counters need a run number.

```
splotter info demo.spec -c time Delta Gamma --last 3
```

```
                    time  Delta  Gamma
scan
6    2026-01-01 09:17:09   30.0    0.0
7    2026-01-01 09:18:21   40.0    0.0
8    2026-01-01 09:19:33   50.0    0.0
```

`--scans` picks the scans by number, in the order given, and reads the file once. This is much faster
than one `splotter info` call per scan:

```
splotter info demo.spec -c Gamma --scans 2 5 7
```

## Metadata

```
splotter info demo.spec 1 --meta     # #T, #Q, #G, #R lines and the #UXML metadata
splotter info demo.spec --meta       # the file header
```

`#UXML` prints as dotted paths such as `ad_detector.sample_detector_distance`, which you can filter
with your shell.

## Times

The start of a scan is its `#D` line. The time of a point is that plus the `Epoch` seconds since the
first point, so the first point shows the `#D` time although it was measured a second or two later.

## From Python

```python
from splotter.spec import Spec

with Spec("demo.spec") as spec:
    scan = spec.get_scan(1)
    scan.command, scan.time, scan.motors["Delta"]
    df = scan.to_dataframe()  # columns named as in #L
    scan.uxml  # #UXML as a dict
```

The file is read when the `with` block starts. `spec.all_scans` has every scan in file order.
