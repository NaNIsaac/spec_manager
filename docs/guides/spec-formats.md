# SPEC files across the years

SPEC files change with the instrument. The parser was run on 3,618 measured files from 2005 to 2026,
about 640,000 scans of one beamline. None of them ship with splotter. The tests write the same
situations by hand in `tests/test_old_formats.py`.

## What changed over time

| Years | What the files look like |
|---|---|
| 2005-2013 | Counters such as `Detector` and `Monitor`, without `imtot`; 55 to about 95 motors |
| 2014 | `#o`, `#J` and `#j` lines with short names |
| 2015 on | `imtot`, `imroi1` to `imroi4` and `#UXML` metadata, in part of the files |
| 2019-2020 | Motor names change from `Sample X` to `Sample_X` |
| 2022 on | Stable, with 168 to 178 motors |

Other beamlines and setups may differ, in particular in motor and counter names.

## What the parser does

- **Names with a space.** Two spaces or a tab separate names, as `Sample Y` holds one space. A `#L`
  line that only fits the count in `#N` when split on single spaces is split that way.
- **Restarts.** A SPEC session restarted inside a file writes a new header. From there on, scans use
  its motor names. `spec.file_metadata` keeps the first header.
- **Reused run numbers.** A restart can start the numbers again. Every scan is kept: the plain number
  means the last one, and `12.1`, `12.2` name each. `splotter info FILE` lists them that way.
- **Times.** `Epoch` counts from the header of the session, and some files have no header. Times of
  points are therefore computed from the `#D` line of the scan.
- **Text between the data.** Macros print into the file. A line counts as data only if it holds as
  many numbers as `#L` has names; `scan.skipped_lines` counts the rest.
- **Odd files.** A file without a header, without scans or with bytes that are not UTF-8 is still read.

## Known limits

Found by that survey and not solved:

- In 5,028 scans (0.8%), the number of `#P` values does not match the number of motor names, so their
  motor values cannot be trusted. Nearly all are from 2016 or earlier, and none from 2023 on. The
  parser pairs names and values in order without warning.
- In 6 scans the `#L` names do not match the `#N` count in either way of splitting.
- A data line cut short, by an aborted scan for instance, is dropped.
- A motor that the file calls differently is not recognized as the same motor: `sx` is not `Sample_X`.

The survey used this release of the parser. A file that reads wrongly is worth
[an issue](https://github.com/NaNIsaac/splotter/issues), with a few lines of its header and of the scan
but no data you cannot share.
