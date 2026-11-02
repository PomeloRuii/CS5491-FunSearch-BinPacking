from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PHASE1B = ROOT.parent
PHASE1C = PHASE1B / "phase1c"
for path in (PHASE1B, PHASE1C, PHASE1B / "reference"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
