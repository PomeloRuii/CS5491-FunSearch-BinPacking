"""Reuse the existing audited core and hardened worker controller."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
PHASE1B = PROJECT / "phase1b"
for path in (PHASE1B/"phase1d", PHASE1B, PHASE1B/"phase1c", PHASE1B/"reference"):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))
import bootstrap
