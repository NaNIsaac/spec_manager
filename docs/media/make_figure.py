"""Draw docs/media/mesh_map.png from the made-up file of `splotter demo`; nothing is measured.

uv run docs/media/make_figure.py
"""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from splotter.cli import main
from splotter.demo import write_demo

OUT = Path(__file__).resolve().with_name("mesh_map.png")

with tempfile.TemporaryDirectory() as folder:
    spec_file, _ = write_demo(Path(folder) / "demo.spec")
    main(["mesh", str(spec_file), "1", "2", "5", "3", "4", "--log", "--save", str(OUT)])
