"""Phase 1C reviewed-probe validation only. Generated execution stays disabled."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import uuid

from container_runner import ROOT, POLICY, PROBES, ContainerRunner, discover


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                    + "\n", encoding="utf-8")


def require_validation_receipt(previous, old_manifest, image, sources):
    """A baseline-only PASS is not a security-suite validation receipt."""
    statuses = {t["test"]: t["status"] for t in previous.get("runtime_tests", [])}
    if (previous.get("decision") != "PASS"
            or previous.get("minimal_trusted_evaluation_only")
            or previous.get("isolated_baselines") != "PASS"
            or statuses != {name: "PASS" for name in PROBES}
            or old_manifest.get("image") != image
            or old_manifest.get("source_sha256") != sources):
        raise PermissionError("Complete matching security-suite validation is required.")


def expected_outcome(result):
    """Return independently checked verdict using host state and structured channels."""
    if not result.get("cleanup_verified"):
        return False
    messages = result.get("worker_messages", [])
    if not any(m.get("kind") == "context" for m in messages):
        return False
    name = result["probe"]
    state = result.get("container_state", {})
    if name in ("infinite_loop", "process_tree"):
        return (result["status"] == "timeout" or state.get("ExitCode") in (137, 152)) \
            and not state.get("Running", True) and not state.get("OOMKilled")
    if name == "memory":
        return result["status"] == "oom_killed" and state.get("OOMKilled") is True
    if name == "output_limit":
        return result["status"] == "output_limit" \
            and result.get("output_bytes_seen", 0) > POLICY["combined_output_limit_bytes"]
    if name == "exception":
        return result["status"] == "completed" and state.get("ExitCode") == 1 and any(
            m.get("kind") == "error" and m.get("error", {}).get("type") == "ValueError"
            for m in messages)
    payload = result.get("worker_result") or {}
    if result["status"] != "completed" or state.get("ExitCode") != 0 \
            or payload.get("kind") != "result" or payload.get("probe") != name:
        return False
    data = payload.get("result") or {}
    if name.startswith("baseline_"):
        expected = {"baseline_first_fit": -212.75, "baseline_best_fit": -212.0,
                    "baseline_seed": -500.0}
        return data.get("score") == expected[name]
    if name == "normal":
        return data.get("answer") == 42
    if name == "network":
        return data.get("outbound_denied") is True
    if name == "filesystem":
        return len(data.get("write_denied", [])) == 2 and len(data.get("host_paths_absent", [])) == 4
    if name == "pids":
        return data.get("fork_denied") is True and 0 < data.get("children_created", 100) < 64
    if name in ("fresh_write", "fresh_clean"):
        return data.get("fresh_tmp") is True
    return False


def evaluate_trusted(runner, fixture):
    """A minimal existing Evaluator -> container -> database path; fixed bodies only."""
    sys.path.insert(0, str(ROOT.parent))
    from trusted_cases import BODIES, GROUPS, SPECIFICATION, case_for_program, content_hash
    from implementation import code_manipulation as cm, config, evaluator
    from implementation.programs_database import ProgramsDatabase

    class ReviewedContainerSandbox(evaluator.Sandbox):
        def run(self, program, run, evolve, inputs, key, timeout_seconds, **kwargs):
            case = case_for_program(program)
            if case not in ("first_fit", "best_fit", "reference_seed") \
                    or run != "evaluate" or evolve != "priority" or key != "OR3" \
                    or content_hash(inputs[key]) != content_hash(GROUPS["OR3"]):
                raise PermissionError("Only unchanged reviewed OR3 baselines are accepted.")
            probe = {"first_fit": "baseline_first_fit", "best_fit": "baseline_best_fit",
                     "reference_seed": "baseline_seed"}[case]
            record = runner.run_probe(probe, timeout_seconds)
            self.last_result = record
            if not expected_outcome(record):
                return None, False
            return record["worker_result"]["result"]["score"], True

    template = cm.text_to_program(SPECIFICATION)
    database = ProgramsDatabase(config.ProgramsDatabaseConfig(), template, "priority")
    ev = evaluator.Evaluator(
        database, template, "priority", "evaluate", {"OR3": GROUPS["OR3"]},
        timeout_seconds=30, sandbox_class=ReviewedContainerSandbox)
    return ev.analyse(BODIES[fixture], None, None, origin="reviewed_fixed_fixture",
                      candidate_id=fixture)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="Existing immutable local sha256 image ID; never pulled")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--evaluate-trusted", choices=("first_fit", "best_fit", "reference_seed"))
    parser.add_argument("--validated-run", type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 5:
        parser.error("Only 1 through 5 sequential timing repetitions are allowed.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    directory = ROOT / "runs" / stamp
    directory.mkdir(parents=True)
    readiness = discover()
    files = [p for p in ROOT.iterdir() if p.is_file()
             and (p.suffix in (".py", ".json", ".ps1") or p.name == "Dockerfile")]
    files += list((ROOT / "tests").glob("*.py"))
    files += list((ROOT.parent / "reference").rglob("*.py"))
    files += [ROOT.parent / "reference/specification.txt",
              ROOT.parent / "trusted_cases.py"]
    sources = {p.relative_to(ROOT.parent).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(files)}
    write_json(directory / "manifest.json", {
        "schema_version": 1, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "1C", "readiness": readiness, "policy": POLICY,
        "source_sha256": sources, "image": args.image,
        "proposal_model_selection": "unresolved; Qwen3.8 remains exploratory",
        "python": sys.version, "llm_requests": 0, "llm_generated_code_executed": 0})
    summary = {"schema_version": 1, "run_id": stamp, "decision": "FAIL",
               "validation_scope": "reviewed_container_security_suite",
               "llm_generated_code_execution_may_be_enabled": False,
               "phase1b_generated_execution_gate_changed": False, "llm_requests": 0,
               "runtime_tests": [{"test": p, "status": "NOT_RUN"} for p in PROBES],
               "isolated_baselines": "NOT_RUN", "isolated_overhead": "NOT_MEASURED",
               "run_directory": str(directory)}
    if not readiness["usable"] or not args.image:
        summary["blocker"] = readiness["reason"] if not readiness["usable"] else "No immutable image supplied."
        write_json(directory / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 2
    records = []
    try:
        runner = ContainerRunner(args.image)
        if args.evaluate_trusted:
            if not args.validated_run:
                raise PermissionError("Provide the matching successful isolation-validation run first.")
            previous = json.loads((args.validated_run / "summary.json").read_text(encoding="utf-8"))
            old_manifest = json.loads((args.validated_run / "manifest.json").read_text(encoding="utf-8"))
            require_validation_receipt(previous, old_manifest, args.image, sources)
            result = evaluate_trusted(runner, args.evaluate_trusted)
            write_json(directory / "trusted_evaluation.json", result)
            summary.update(decision="PASS" if result["status"] == "ok" else "FAIL",
                           validation_scope="trusted_evaluator_bridge",
                           isolated_baselines=result["status"],
                           minimal_trusted_evaluation_only=True)
        else:
            for probe in PROBES:
                record = runner.run_probe(probe, 3 if probe in ("infinite_loop", "process_tree") else None)
                record["validation_passed"] = expected_outcome(record)
                records.append(record)
                write_json(directory / (probe + ".json"), record)
                if not record["validation_passed"]:
                    raise RuntimeError("Reviewed probe failed: " + probe)
            timing = []
            for _ in range(args.repeats):
                for probe in ("baseline_first_fit", "baseline_best_fit"):
                    record = runner.run_probe(probe)
                    records.append(record)
                    if not expected_outcome(record):
                        raise RuntimeError("Sequential baseline timing check failed.")
                    pure = record["worker_result"]["result"]["pure_evaluate_seconds"]
                    timing.append({key: record[key] for key in
                                   ("probe", "create_seconds", "policy_inspection_seconds",
                                    "start_attach_wait_seconds", "cleanup_seconds", "total_seconds")})
                    timing[-1].update(pure_evaluate_seconds=pure,
                                      worker_ready_seconds=record.get("worker_ready_seconds"),
                                      non_packing_lifecycle_seconds=record["total_seconds"] - pure)
            write_json(directory / "timing.json", timing)
            write_json(directory / "timing_records.json", records[len(PROBES):])
            summary.update(
                decision="PASS", isolated_baselines="PASS",
                runtime_tests=[{"test": r["probe"], "status": "PASS"} for r in records[:len(PROBES)]],
                isolated_overhead={"samples": len(timing), "sequential": True,
                    "median_total_seconds": statistics.median(t["total_seconds"] for t in timing),
                    "median_worker_ready_seconds": statistics.median(t["worker_ready_seconds"] for t in timing),
                    "median_non_packing_seconds": statistics.median(t["non_packing_lifecycle_seconds"] for t in timing)},
                note="Reviewed container tests passed; generated-code executor is still not implemented or enabled.")
    except Exception as exc:
        summary["blocker"] = type(exc).__name__ + ": " + str(exc)
        summary["runtime_tests"] = [
            {"test": p, "status": next(("PASS" if r.get("validation_passed") else "FAIL"
                                      for r in records if r["probe"] == p), "NOT_RUN")}
            for p in PROBES]
    write_json(directory / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["decision"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
