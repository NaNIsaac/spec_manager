# Installation

splotter is available from [PyPI](https://pypi.org/project/splotter/). It requires Python 3.13 or
later and installs Matplotlib, NumPy, pandas and SciPy.

To have the `splotter` command everywhere:

```sh
uv tool install splotter
```

or `pip install splotter` in an environment of your choice. To run it once without installing:

```sh
uvx splotter --version
```

The version on the `main` branch installs the same way from the repository:

```sh
uv tool install git+https://github.com/NaNIsaac/splotter
```

For development, clone the repository and run `uv sync`, then `uv run pytest`. Inside a clone, put
`uv run` in front of the commands: `uv run splotter info FILE`.
