# Its presence puts this directory on sys.path, so the tests can import spec and main.
import os

os.environ.setdefault("MPLBACKEND", "Agg")
