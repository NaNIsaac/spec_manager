# Mesh maps

`splotter mesh` draws one counter over two motors, from one scan or several.

```
splotter mesh demo.spec 1 --counter imroi3 --log
splotter mesh demo.spec 1 2 5 3 4 --log --save map.png
```

For each scan it prints the command, the mean of the counter and where it peaks:

```
Scan 1: mesh sy -1 1 20 sx -1 1 20  0.5
  mean imtot = 2103, max imtot = 97699 at Sample_X = 0.4, Sample_Y = -0.3
```

![Three mesh scans and two line scans on one map](../media/mesh_map.png)

## Reading the map

- **Scans:** `mesh` scans, and `ascan` or `dscan` line scans of one of the two motors. A line scan
  sits at the position of the other motor, read from the `#P` lines of the scan.
- **Color:** all scans share one scale, so their colors compare. It ends at 10 times the mean of the
  scans, not at the maximum, so that a few hot points do not leave the rest in one color. Points above
  it take the brightest color, so the printed maximum or `--vmax` tells how bright they are.
- **Gray hatching:** nothing was measured there. This includes the missing points of an aborted scan.
- **Overlaps:** the run given later is drawn on top. Change the order to see the other one.
- **Outlines:** with several scans, each has its own color and line style, named in the legend.
- **Axes:** the horizontal axis is `Sample_X` and the vertical one is `Sample_Y`, with smaller numbers
  at the top. Equal lengths on both axes are the same distance.

## Options

| Option | Effect |
|---|---|
| `--counter NAME` | The counter to draw (default `imtot`) |
| `--log` | Log color scale; zero counts take its lowest color, so they do not look unmeasured |
| `--vmax VALUE` | Top of the color scale (default: 10 times the mean) |
| `--x NAME`, `--y NAME` | The motors of the axes (default `Sample_X`, `Sample_Y`) |
| `--save FILE` | Write the figure to a file instead of opening a window |

Names match without regard to case, spaces and underscores. Files before 2015 usually have no
`imtot`, so give a `--counter`; the error message lists the columns of the scan.

## Limits

- Line scans have no width of their own and are drawn with square cells. A short step can be too thin
  to read on a large map, so use the printed maximum or `splotter info` for its values.
- Cell positions start from the first measured point and use the step of the command. Motor positions
  that wander during a scan are not followed.
- Other scan types, such as `a2scan`, are refused.
