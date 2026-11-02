"""Provenance is assigned by the trusted control plane, never parsed from model text."""
from dataclasses import dataclass, field
import ast
from pathlib import Path
import sys
from time import perf_counter

_TRUSTED_RECEIPTS = {}
EXTRA_FIXTURES = {
    "runtime_failure": "    raise ValueError('reviewed runtime failure')\n    return -bins",
    "wrong_shape": "    return np.array([1.0])",
    "nonfinite": "    return np.full_like(bins, np.nan, dtype=float)",
    "positive_infinity": "    return np.full_like(bins, np.inf, dtype=float)",
    "negative_infinity": "    return np.full_like(bins, -np.inf, dtype=float)",
    "boolean_priorities": "    return np.zeros_like(bins, dtype=bool)",
    "infinite_loop": "    while True:\n        pass\n    return -bins",
}


@dataclass(frozen=True)
class Candidate:
    text: str
    origin: str
    finish_reason: str = "stop"
    generation_seconds: float = 0.0
    usage: dict | None = None
    response_metadata: dict = field(default_factory=dict)
    fixture: str | None = None
    permit: object = field(default=None, repr=False, compare=False)


def trusted_permit(candidate):
    try:
        return (candidate.origin == "trusted_fixture" and
                _TRUSTED_RECEIPTS.get(candidate.permit) == (candidate.text, candidate.fixture))
    except TypeError:
        return False


def _mint(text, fixture, seconds=0.0):
    permit = object()
    _TRUSTED_RECEIPTS[permit] = (text, fixture)
    return Candidate(text, "trusted_fixture", generation_seconds=seconds,
                     fixture=fixture, permit=permit)


def seed_candidate():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from trusted_cases import BODIES
    return _mint("def priority(item: float, bins: np.ndarray) -> np.ndarray:\n"
                 + BODIES["reference_seed"], "reference_seed")


class TrustedSampler:
    """Deterministic fixed functions; no model or API calls."""
    def __init__(self, fixtures):
        self.fixtures = iter(fixtures)

    def draw(self, prompt, messages):
        from interface import expected_name
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from trusted_cases import BODIES
        start = perf_counter()
        fixture = next(self.fixtures)
        known = {key: BODIES[key] for key in
                 ("first_fit", "best_fit", "reference_seed", "invalid_source")}
        known.update(EXTRA_FIXTURES)
        if fixture not in known:
            raise ValueError("Unknown trusted fixture.")
        name = expected_name(prompt)
        source = f"def {name}(item: float, bins: np.ndarray) -> np.ndarray:\n" + known[fixture]
        return _mint(source, fixture, perf_counter()-start)
