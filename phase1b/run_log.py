"""Append-only UTF-8 JSONL with run manifests and no environment secret dump."""
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter
import uuid

ROOT = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                    + "\n", encoding="utf-8")


def source_hashes():
    files = [*ROOT.glob("*.py"), *ROOT.glob("*.json"), ROOT / "requirements-cpu.txt",
             *ROOT.joinpath("reference").rglob("*.py"),
             ROOT / "reference/specification.txt", *ROOT.joinpath("tests").glob("*.py")]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}


class RunLog:
    def __init__(self, output_root=None):
        self.started = perf_counter()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.run_id = stamp + "_" + uuid.uuid4().hex[:8]
        self.directory = Path(output_root or ROOT / "runs") / self.run_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.events = []
        self.stream = (self.directory / "events.jsonl").open("x", encoding="utf-8")

    def emit(self, event, **fields):
        record = {"event_sequence": len(self.events) + 1,
                  "utc": datetime.now(timezone.utc).isoformat(),
                  "since_run_start_seconds": perf_counter() - self.started,
                  "event": event, **fields}
        self.stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.events.append(record)

    def manifest(self, **fields):
        packages = {d.metadata["Name"]: d.version for d in metadata.distributions()
                    if d.metadata.get("Name")}
        value = {
            "schema_version": 1, "run_id": self.run_id,
            "python_executable": sys.executable, "python": sys.version,
            "platform": platform.platform(), "packages": dict(sorted(packages.items())),
            "source_sha256": source_hashes(),
            "connectivity_record": json.loads((ROOT / "connectivity_record.json").read_text(encoding="utf-8")),
            "upstream": json.loads((ROOT / "upstream_manifest.json").read_text(encoding="utf-8")),
            **fields,
        }
        write_json(self.directory / "manifest.json", value)

    def finish(self, status, **fields):
        self.emit("run_finished", status=status, **fields)
        summary = {"schema_version": 1, "run_id": self.run_id, "status": status,
                   "run_wall_seconds": perf_counter() - self.started, **fields}
        write_json(self.directory / "summary.json", summary)
        self.stream.close()
        return summary
