# README media

`mesh_map.png` is drawn by `make_figure.py` from this commit's code, with no measured data:

```sh
uv run docs/media/make_figure.py
```

It writes the made-up file of `splotter demo` to a temporary folder and runs
`splotter mesh FILE 1 2 5 3 4 --log`. The file is seeded, so the same data comes out every time.
