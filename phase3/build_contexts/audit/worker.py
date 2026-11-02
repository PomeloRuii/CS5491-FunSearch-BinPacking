"""Prepared reviewed-probe worker. Never accepts LLM text or arbitrary source.

Dangerous resource probes refuse to run without verified Linux container context.
Runtime behavior has NOT been validated until the external suite actually runs.
"""
import argparse
import ast
import errno
import json
import os
from pathlib import Path
import signal
import socket
import sys
import time

PROBES = (
    "normal", "exception", "infinite_loop", "memory", "filesystem", "network",
    "pids", "process_tree", "output_limit", "fresh_write", "fresh_clean",
    "baseline_first_fit", "baseline_best_fit", "baseline_seed",
)


def context():
    if sys.platform != "linux" or not Path("/.dockerenv").is_file():
        raise PermissionError("Reviewed resource probes require a Linux Docker container.")
    if os.getuid() != 65532 or os.getgid() != 65532:
        raise PermissionError("Unexpected worker identity.")
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines()
                  if ":" in line)
    if int(status["CapEff"].strip(), 16) or status["NoNewPrivs"].strip() != "1":
        raise PermissionError("Capabilities or no-new-privileges policy not enforced.")
    if status["Seccomp"].strip() != "2":
        raise PermissionError("Seccomp filtering is required.")
    if {name for _, name in socket.if_nameindex()} - {"lo"}:
        raise PermissionError("Non-loopback network interface found.")
    limits = {key: Path("/sys/fs/cgroup/" + key).read_text().strip()
              for key in ("memory.max", "memory.swap.max", "pids.max", "cpu.max")}
    if not 0 < int(limits["memory.max"]) <= 512 * 1024 * 1024:
        raise PermissionError("Finite 512 MiB cgroup memory cap required.")
    if int(limits["memory.swap.max"]) != 0 or not 1 <= int(limits["pids.max"]) <= 64:
        raise PermissionError("Swap or process cap differs.")
    quota, period = map(int, limits["cpu.max"].split())
    if not 0 < quota <= period:
        raise PermissionError("CPU cgroup quota must be at most one CPU.")
    root = next(line.split() for line in Path("/proc/mounts").read_text().splitlines()
                if line.split()[1] == "/")
    if "ro" not in root[3].split(","):
        raise PermissionError("Read-only root filesystem required.")
    return {"uid": os.getuid(), "gid": os.getgid(), "cap_eff": status["CapEff"].strip(),
            "no_new_privileges": True, "seccomp_filtering": True,
            "limits": limits, "root_read_only": True}


def run_probe(name):
    if name == "normal":
        return {"answer": 42}
    if name == "exception":
        raise ValueError("Reviewed exception fixture.")
    if name in ("infinite_loop", "process_tree"):
        if name == "process_tree":
            pid = os.fork()
            if pid == 0:
                time.sleep(60)
                os._exit(0)
        while True:
            pass
    if name == "memory":
        blocks = []
        while True:
            blocks.append(bytearray(64 * 1024 * 1024))
    if name == "output_limit":
        while True:
            os.write(1, b"x" * 8192)
    if name == "filesystem":
        denied = []
        for path in ("/app/forbidden-write", "/etc/forbidden-write"):
            try:
                Path(path).write_text("reviewed fixture")
            except OSError as exc:
                if exc.errno not in (errno.EROFS, errno.EACCES, errno.EPERM):
                    raise
                denied.append(path)
            else:
                raise AssertionError("Read-only filesystem write succeeded.")
        private_paths = ["/host_phase1c_canary", "/host_private_canary",
                         "/run/desktop/mnt/host", "/var/run/docker.sock"]
        if any(Path(path).exists() for path in private_paths):
            raise AssertionError("Unexpected host path or control socket exposed.")
        return {"write_denied": denied, "host_paths_absent": private_paths}
    if name == "network":
        with socket.socket() as connection:
            connection.settimeout(0.5)
            code = connection.connect_ex(("1.1.1.1", 443))
        if code not in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN,
                        errno.EACCES, errno.EPERM):
            raise AssertionError("Network denial not established: errno=" + str(code))
        return {"outbound_denied": True, "errno": code}
    if name == "pids":
        children = []
        denied = False
        try:
            for _ in range(96):
                try:
                    pid = os.fork()
                except OSError as exc:
                    if exc.errno != errno.EAGAIN:
                        raise
                    denied = True
                    break
                if pid == 0:
                    time.sleep(60)
                    os._exit(0)
                children.append(pid)
        finally:
            for pid in children:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for pid in children:
                os.waitpid(pid, 0)
        if not denied:
            raise AssertionError("Process-count ceiling did not deny another child.")
        return {"fork_denied": True, "children_created": len(children)}
    if name in ("fresh_write", "fresh_clean"):
        marker = Path("/tmp/candidate-marker")
        if marker.exists():
            raise AssertionError("Previous candidate filesystem state found.")
        if name == "fresh_write":
            marker.write_text("must disappear with this container")
        return {"fresh_tmp": True, "marker_written": name == "fresh_write"}
    if name.startswith("baseline_"):
        # Use the same literal specification and data as Phase 1B, no fitness edits.
        tree = ast.parse(Path("/app/specification.txt").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                node.decorator_list = []
                if node.name == "priority" and name != "baseline_seed":
                    body = ("return -bins" if name == "baseline_best_fit"
                            else "return -np.arange(len(bins), dtype=float)")
                    node.body = ast.parse(body).body
        ast.fix_missing_locations(tree)
        namespace = {}
        preparation = time.perf_counter()
        exec(compile(tree, "<reviewed-reference-fixture>", "exec"), namespace)
        instances = json.loads(Path("/app/development_or3.json").read_text(encoding="utf-8"))
        setup_seconds = time.perf_counter() - preparation
        start = time.perf_counter()
        score = float(namespace["evaluate"](instances))
        return {"score": score, "pure_evaluate_seconds": time.perf_counter() - start,
                "numpy_and_data_setup_seconds": setup_seconds}
    raise ValueError("Unknown reviewed fixture.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", choices=PROBES, required=True)
    args = parser.parse_args()
    try:
        verified_context = context()
        print(json.dumps({"kind": "context", "context": verified_context}), file=sys.stderr,
              flush=True)
        result = run_probe(args.probe)
        print(json.dumps({"kind": "result", "probe": args.probe, "result": result},
                         allow_nan=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"kind": "error", "probe": args.probe,
                          "error": {"type": type(exc).__name__, "message": str(exc)}}),
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
