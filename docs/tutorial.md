# Find the bright spot of a scan

This runs on the made-up SPEC file from `splotter demo`, so no measurement is needed. The commands
use an isolated uv environment with the published package.

Write the file:

<!-- test console -->
```console
$ uv run -q --no-project --python 3.13 --with splotter splotter demo tutorial.spec
wrote tutorial.spec
wrote tutorial_fwhm.csv
```

It holds eight scans, which `splotter info` lists:

```
 scan  start                duration  points  command
    1  2026-01-01 09:01:00   0:07:20     441  mesh sy -1 1 20 sx -1 1 20  0.5
    2  2026-01-01 09:08:52   0:03:50     231  mesh sy -1 1 20 sx 0.8 1.8 10  0.5
    3  2026-01-01 09:13:14   0:00:20      21  ascan  sx 0.2 0.6  20 0.5
    4  2026-01-01 09:14:06   0:00:20      21  ascan  sy -0.5 -0.1  20 0.5
    5  2026-01-01 09:14:58   0:01:39     100  mesh sy 1 2 10 sx -1 1 20  0.5
    6  2026-01-01 09:17:09   0:00:40      41  ascan  th 14.5 15.5  40 0.5
    7  2026-01-01 09:18:21   0:00:40      41  ascan  th 19.5 20.5  40 0.5
    8  2026-01-01 09:19:33   0:00:40      41  ascan  th 24.5 25.5  40 0.5
```

Scan 5 was aborted after 100 of its 231 points. Ask scan 1 for its three brightest points:

<!-- test console -->
```console
$ uv run -q --no-project --python 3.13 --with splotter splotter info tutorial.spec 1 -c imtot Sample_X Sample_Y --top 3 --csv
point,imtot,Sample_X,Sample_Y
301,97699.0,0.4,-0.3
300,45909.0,0.4,-0.4
322,45702.0,0.5,-0.3
```

The generator put the spot at `Sample_X` = 0.4, `Sample_Y` = -0.3. Point 301 is that spot, counted
from 0, and everything measured there is one command away:

```
splotter info tutorial.spec 1 301
```

```
Time at point 301: 2026-01-01 09:06:01

Motors at point 301:
   Delta = 50.9             Theta = 25.45              Chi = 90                 Phi = 0
      Mu = 0                Gamma = 0             Sample_X = 0.4           Sample_Y = -0.3

Counters at point 301:
  Epoch = 363           Seconds = 0.5             imtot = 97699          imroi1 = 1957
 imroi2 = 4976           imroi3 = 90149           immax = 465
```

Finally, put the meshes and the line scans through the spot on one map. Runs given later are drawn
on top, and what was not measured is hatched gray:

```
splotter mesh tutorial.spec 1 2 5 3 4 --log
```

From here, see [looking up scans](guides/looking-up-scans.md) and [mesh maps](guides/mesh-maps.md).
