"""One bounded source body per fresh container. No network/model access.

Only the host's reviewed-fixture path may currently send a request. A successful
run does not confer permission on any other candidate.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import sys
from time import perf_counter

VALIDITY_POLICY = "obp-validity-v1"


def validate_priority_scores(scores, bins):
    """Common acceptance rule, separate from unchanged packing/fitness semantics."""
    import numpy as np
    scores = np.asarray(scores)
    if scores.shape != bins.shape:
        raise ValueError("priority must return one score for each feasible bin.")
    if scores.dtype.kind not in "iuf" or not np.isfinite(scores).all():
        raise ValueError("Priority scores must be finite real numbers under " + VALIDITY_POLICY)
    return scores


def execute_request(payload):
    body = payload["body"]
    if not isinstance(body, str) or len(body) > 32768:
        raise ValueError("Invalid candidate body size.")
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    if body_hash != payload["body_sha256"]:
        raise ValueError("Candidate body checksum mismatch.")
    fragment = ast.parse("def priority(item, bins):\n" + body)
    if len(fragment.body) != 1 or not isinstance(fragment.body[0], ast.FunctionDef):
        raise ValueError("Body escaped the function boundary.")
    if len(list(ast.walk(fragment))) > 3000:
        raise ValueError("Candidate AST exceeds the size limit.")
    tree = ast.parse(Path("/app/specification.txt").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
            if node.name == "priority":
                node.body = fragment.body[0].body
    ast.fix_missing_locations(tree)
    namespace = {}
    setup = perf_counter()
    exec(compile(tree, "<isolated-candidate>", "exec"), namespace)
    import numpy as np
    raw_priority = namespace["priority"]
    priority_calls = 0

    def checked_priority(item, bins):
        nonlocal priority_calls
        scores = validate_priority_scores(raw_priority(item, bins), bins)
        priority_calls += 1
        return scores

    namespace["priority"] = checked_priority
    instances = json.loads(Path("/app/or3.json").read_text(encoding="utf-8"))
    setup_seconds = perf_counter() - setup
    start = perf_counter()
    score = float(namespace["evaluate"](instances))
    pure = perf_counter() - start
    if not math.isfinite(score):
        raise ValueError("Non-finite aggregate score.")
    expected_calls = sum(len(instance["items"]) for instance in instances.values())
    if priority_calls != expected_calls:
        raise ValueError("Partial item evaluation is not valid experimental data.")
    return {"job_id": payload["job_id"], "body_sha256": body_hash, "score": score,
            "pure_evaluate_seconds": pure, "setup_seconds": setup_seconds,
            "validity_policy": VALIDITY_POLICY, "instances_completed": len(instances),
            "priority_calls": priority_calls}


def main():
    try:
        if sys.platform != "linux" or not Path("/.dockerenv").is_file():
            raise PermissionError("Candidate worker requires the isolated Linux container.")
        sys.path.insert(0, "/app")
        from worker import context
        print(json.dumps({"kind": "context", "context": context()}), file=sys.stderr, flush=True)
        line = sys.stdin.buffer.readline(65537)
        if len(line) > 65536 or not line.endswith(b"\n"):
            raise ValueError("Oversized or incomplete request.")
        payload = json.loads(line)
        result = execute_request(payload)
        print(json.dumps({"kind": "result", "result": result}, allow_nan=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"kind": "error",
                          "error": {"type": type(exc).__name__, "message": str(exc)}}),
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
