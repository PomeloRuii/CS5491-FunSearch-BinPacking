"""Reviewed, fixed fixtures only. This module never loads model responses."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "reference"))

from implementation import code_manipulation as cm
from development_data_v1 import load_development, CONTRACT as HOST_DATA_CONTRACT

SPECIFICATION = (ROOT / "reference/specification.txt").read_text(encoding="utf-8")
_template = cm.text_to_program(SPECIFICATION)
BODIES = {
    "reference_seed": _template.get_function("priority").body,
    "first_fit": "    return -np.arange(len(bins), dtype=float)",
    "best_fit": "    return -bins",
    "invalid_source": "    return (",
    "runtime_error": "    raise RuntimeError('fixed trusted failure fixture')",
    "timeout": "    import time\n    time.sleep(5)\n    return -bins",
}
TOY = {"toy": {"capacity": 10, "num_items": 4, "items": [6, 7, 3, 4]}}
# Prospective host-development-only-v1. Historical whole-OR3 fixtures/results
# remain historical; their old execution grants must not validate this helper.


def __getattr__(name):
    if name != "GROUPS":
        raise AttributeError(name)
    # The public export omits instance values. Importing specifications and
    # reviewed bodies needs only code; requesting GROUPS still checks the data.
    groups = {"toy": TOY, "OR3": load_development()["OR3"]}
    globals()["GROUPS"] = groups
    return groups


def content_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def trusted_program(case):
    if case not in BODIES or case == "invalid_source":
        raise ValueError("Not an executable trusted fixture.")
    program = cm.text_to_program(SPECIFICATION)
    program.get_function("priority").body = BODIES[case]
    return str(program)


def case_for_program(program):
    for case in BODIES:
        if case != "invalid_source" and program == trusted_program(case):
            return case
    raise PermissionError("Program is outside the fixed trusted fixture allowlist.")
