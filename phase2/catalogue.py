"""Fixed manually reviewed heuristics. Never load a model-generated body here."""
from dataclasses import dataclass
import hashlib

import phase2_bootstrap
from candidates import Candidate
from trusted_cases import BODIES as PREVIOUS_BODIES

BODIES = {
    "seed": PREVIOUS_BODIES["reference_seed"],
    "worst_fit": "    return bins",
    "first_fit": "    return -np.arange(len(bins), dtype=float)",
    "best_fit": "    return -bins",
    "best_fit_shift": "    residual = bins - item\n    return -residual",
    "best_fit_scale": "    return -2.0 * bins",
    "first_fit_scale": "    return -2.0 * np.arange(len(bins), dtype=float)",
    "worst_fit_scale": "    return 2.0 * bins + item",
    "best_fit_rare_37": "    if item == 37:\n        return -np.arange(len(bins), dtype=float)\n    return -bins",
    "best_fit_rare_21": "    if item == 21:\n        return -np.arange(len(bins), dtype=float)\n    return -bins",
    "best_fit_rare_99": "    if item == 99:\n        return -np.arange(len(bins), dtype=float)\n    return -bins",
    "best_fit_square": "    return -(bins - item) ** 2",
    "last_fit": "    return np.arange(len(bins), dtype=float)",
    "tight_or_first": "    residual = bins - item\n    return np.where(residual < 10, 1000.0 - residual, -np.arange(len(bins), dtype=float))",
    "invalid_syntax": "    return (",
    "invalid_scalar": "    return 0",
    "invalid_shape": "    return np.array([1.0])",
    "invalid_nan": "    return np.full_like(bins, np.nan, dtype=float)",
    "runtime_error": "    raise ValueError('reviewed replay failure')\n    return -bins",
    "validation_dtype": "    if bins.dtype != np.dtype('int64') or not isinstance(item, int):\n        return np.full_like(bins, np.nan, dtype=float)\n    return -bins",
}

STREAM = ["worst_fit","first_fit","best_fit","first_fit","best_fit_shift",
          "best_fit_scale","first_fit_scale","worst_fit_scale","best_fit_rare_37",
          "best_fit_rare_21","best_fit_rare_99","worst_fit","best_fit",
          "best_fit_square","last_fit","tight_or_first","invalid_syntax",
          "invalid_scalar","invalid_shape","invalid_nan","runtime_error"]
_PERMITS = {}


def reviewed_candidate(fixture, name):
    if fixture not in BODIES:
        raise PermissionError("Only fixed reviewed Phase 2 fixtures are authorized.")
    text=f"def {name}(item: float, bins: np.ndarray) -> np.ndarray:\n"+BODIES[fixture]
    permit=object(); _PERMITS[permit]=(text,fixture)
    return Candidate(text,"phase2_reviewed_fixture",fixture=fixture,permit=permit)


def require_reviewed(candidate):
    if (candidate.origin != "phase2_reviewed_fixture" or candidate.finish_reason != "stop"
            or _PERMITS.get(candidate.permit) != (candidate.text,candidate.fixture)):
        raise PermissionError("Generated-code execution remains locked; no Phase 2 approval is implied.")


def stream_manifest():
    return [{"candidate_id":i,"fixture":f,"body":BODIES[f],
             "body_sha256":hashlib.sha256(BODIES[f].encode()).hexdigest()}
            for i,f in enumerate(STREAM,1)]
