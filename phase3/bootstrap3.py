"""Phase 3 extensions over the existing audited project; no host candidate exec."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
PHASE2 = PROJECT / 'phase2'
sys.path.insert(0, str(PHASE2))
import phase2_bootstrap

