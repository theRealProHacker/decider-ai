import sys
from pathlib import Path

# bench/ is a scripts directory, not a package; make its modules importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench"))
