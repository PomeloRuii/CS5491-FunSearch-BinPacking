"""Prepared host controller for fixed reviewed probes only.

No host execution fallback, arbitrary source API, image pulling, or installations.
The Docker runtime path remains UNVALIDATED until it runs on an available backend.
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parent
POLICY = json.loads((ROOT / "policy.json").read_text(encoding="utf-8"))
PROBES = ("normal", "exception", "infinite_loop", "memory", "filesystem", "network",
          "pids", "process_tree", "output_limit", "fresh_write", "fresh_clean",
          "baseline_first_fit", "baseline_best_fit", "baseline_seed")


def docker_path():
    executable = shutil.which("docker")
    if executable:
        return executable
    for path in (Path(os.environ.get("ProgramFiles", "/unavailable")) / "Docker/Docker/resources/bin/docker.exe",
                 Path.home() / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"):
        if path.is_file():
            return str(path)
    return None


def cli(docker, args, timeout=15, check=True):
    process = subprocess.run([docker, *args], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=timeout,
                             shell=False)
    if check and process.returncode:
        raise RuntimeError("Docker operation failed: " + process.stderr[:2000])
    return process


def discover():
    docker = docker_path()
    result = {"docker_executable": docker, "usable": False,
              "reason": "Docker CLI not found", "image_build_checked": False}
    if not docker:
        return result
    try:
        info = json.loads(cli(docker, ["info", "--format", "{{json .}}"]).stdout)
        result["daemon"] = {key: info.get(key) for key in
                            ("ServerVersion", "OSType", "CgroupVersion", "SecurityOptions",
                             "MemoryLimit", "SwapLimit", "PidsLimit", "NCPU", "MemTotal")}
        options = " ".join(info.get("SecurityOptions") or [])
        result["usable"] = (
            info.get("OSType") == "linux" and info.get("CgroupVersion") == "2"
            and "seccomp" in options and "unconfined" not in options
            and all(info.get(key) for key in ("MemoryLimit", "SwapLimit", "PidsLimit")))
        result["reason"] = ("Linux daemon with required controls found" if result["usable"]
                            else "Linux/cgroup-v2/seccomp/resource-limit prerequisites not met")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result["reason"] = str(exc)
    return result


def create_args(image, name, probe):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("An immutable local image ID is required, not a mutable tag.")
    if not re.fullmatch(r"cs5491-phase1c-[0-9a-f]{32}", name) or probe not in PROBES:
        raise ValueError("Unexpected container identity or fixture.")
    args = [
        "create", "--name", name, "--label", "cs5491.phase=1c", "--pull=never",
        "--network=none", "--read-only", "--user=65532:65532", "--cap-drop=ALL",
        "--security-opt=no-new-privileges=true", "--cgroupns=private",
        "--cpus=1", "--memory=536870912", "--memory-swap=536870912",
        "--pids-limit=64", "--init", "--restart=no", "--log-driver=none",
        "--tmpfs=/tmp:" + POLICY["tmpfs_options"], "--workdir=/tmp",
        "--entrypoint=python",
    ]
    for kind, (soft, hard) in POLICY["ulimits"].items():
        args.append("--ulimit=" + kind + "=" + str(soft) + ":" + str(hard))
    return args + [image, "-I", "/app/worker.py", "--probe", probe]


def verify_created(item, image, probe):
    host, cfg = item["HostConfig"], item["Config"]
    assertions = [
        item["Image"] == image, item["State"]["Status"] == "created",
        not host.get("Privileged"), host.get("NetworkMode") == "none",
        host.get("ReadonlyRootfs") is True, cfg.get("User") == "65532:65532",
        host.get("Memory") == 536870912, host.get("MemorySwap") == 536870912,
        host.get("NanoCpus") == 1000000000, host.get("PidsLimit") == 64,
        host.get("Init") is True, host.get("CgroupnsMode") == "private",
        host.get("RestartPolicy", {}).get("Name") == "no",
        host.get("LogConfig", {}).get("Type") == "none",
        {x.upper() for x in host.get("CapDrop") or []} == {"ALL"},
        not host.get("CapAdd"), not host.get("Binds"),
        all(m.get("Type") == "tmpfs" and m.get("Destination") == "/tmp"
            and not m.get("Source") for m in item.get("Mounts") or []),
        not host.get("Devices"), not host.get("DeviceRequests"),
        not host.get("PortBindings"), not host.get("VolumesFrom"),
        not host.get("PidMode"), not host.get("IpcMode") == "host",
        not host.get("UTSMode") == "host",
        cfg.get("Entrypoint") == ["python"],
        cfg.get("Cmd") == ["-I", "/app/worker.py", "--probe", probe],
        host.get("Tmpfs") == {"/tmp": POLICY["tmpfs_options"]},
    ]
    options = host.get("SecurityOpt") or []
    assertions.append(options in (["no-new-privileges=true"], ["no-new-privileges"]))
    expected = {key: tuple(value) for key, value in POLICY["ulimits"].items()}
    actual = {v["Name"]: (v["Soft"], v["Hard"]) for v in host.get("Ulimits") or []}
    assertions.append(actual == expected)
    allowed_env = {"PATH", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256",
                   "PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED", "OPENBLAS_NUM_THREADS",
                   "OMP_NUM_THREADS", "MKL_NUM_THREADS", "HOME"}
    assertions.append(all(e.split("=", 1)[0] in allowed_env for e in cfg.get("Env") or []))
    if not all(assertions):
        raise PermissionError("Created container failed the host-side policy inspection.")


class ContainerRunner:
    def __init__(self, image):
        # Validate immutable image syntax before any daemon operation.
        create_args(image, "cs5491-phase1c-" + "0" * 32, "normal")
        readiness = discover()
        if not readiness["usable"]:
            raise RuntimeError(readiness["reason"])
        self.docker, self.image = readiness["docker_executable"], image
        inspected = json.loads(cli(self.docker, ["image", "inspect", image]).stdout)[0]
        if inspected.get("Os") != "linux" or inspected.get("Id") != image:
            raise PermissionError("Expected local Linux image not found.")
        self.readiness = readiness

    def run_probe(self, probe, wall_seconds=None):
        name = "cs5491-phase1c-" + uuid.uuid4().hex
        command = create_args(self.image, name, probe)
        result = {"probe": probe, "container_name": name, "image": self.image,
                  "status": "controller_error", "cleanup_verified": False}
        total_start = time.perf_counter()
        deadline = wall_seconds or POLICY["execution_wall_seconds"]
        process = None
        try:
            start = time.perf_counter()
            cli(self.docker, command)
            result["create_seconds"] = time.perf_counter() - start
            start = time.perf_counter()
            inspected = json.loads(cli(self.docker, ["inspect", name]).stdout)[0]
            verify_created(inspected, self.image, probe)
            result["policy_inspection_seconds"] = time.perf_counter() - start
            result["inspected_configuration"] = inspected
            # Bounded streaming avoids unbounded host RAM/disk consumption.
            buffers = [bytearray(), bytearray()]
            size, lock, overflow = [0], threading.Lock(), threading.Event()

            def consume(stream, index):
                while True:
                    chunk = stream.read1(4096)
                    if not chunk:
                        break
                    with lock:
                        remaining = POLICY["combined_output_limit_bytes"] - size[0]
                        buffers[index].extend(chunk[:max(0, remaining)])
                        size[0] += len(chunk)
                        if size[0] > POLICY["combined_output_limit_bytes"]:
                            overflow.set()
                        if index == 1 and "worker_ready_seconds" not in result:
                            for line in buffers[1].splitlines():
                                try:
                                    message = json.loads(line)
                                except ValueError:
                                    continue
                                if message.get("kind") == "context":
                                    result["worker_ready_seconds"] = time.perf_counter() - start
                                    break

            start = time.perf_counter()
            process = subprocess.Popen(
                [self.docker, "start", "--attach", name], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, shell=False)
            threads = [threading.Thread(target=consume, args=(stream, i), daemon=True)
                       for i, stream in enumerate((process.stdout, process.stderr))]
            for thread in threads:
                thread.start()
            while process.poll() is None:
                if overflow.is_set() or time.perf_counter() - start >= deadline:
                    result["status"] = "output_limit" if overflow.is_set() else "timeout"
                    cli(self.docker, ["kill", name], check=False)
                    break
                time.sleep(0.02)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=2)
            if any(thread.is_alive() for thread in threads):
                raise RuntimeError("Output collectors did not stop.")
            result["start_attach_wait_seconds"] = time.perf_counter() - start
            result["stdout"] = buffers[0].decode("utf-8", errors="replace")
            result["stderr"] = buffers[1].decode("utf-8", errors="replace")
            result["output_bytes_seen"] = size[0]
            final = json.loads(cli(self.docker, ["inspect", name]).stdout)[0]
            result["container_state"] = final["State"]
            if result["status"] == "controller_error":
                result["status"] = ("oom_killed" if final["State"].get("OOMKilled")
                                    else "completed")
            try:
                result["worker_result"] = json.loads(result["stdout"])
            except ValueError:
                result["worker_result"] = None
            result["worker_messages"] = []
            for line in result["stderr"].splitlines():
                try:
                    result["worker_messages"].append(json.loads(line))
                except ValueError:
                    pass
        except (OSError, ValueError, RuntimeError, PermissionError,
                subprocess.TimeoutExpired) as exc:
            result.update(status="controller_error", error_type=type(exc).__name__,
                          message=str(exc))
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            cleanup_start = time.perf_counter()
            try:
                cli(self.docker, ["rm", "--force", "--volumes", name], check=False)
                remaining = cli(self.docker, ["ps", "--all", "--quiet", "--filter",
                                "name=^/" + name + "$"])
                result["cleanup_verified"] = not remaining.stdout.strip()
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                result["cleanup_error"] = str(exc)
            result["cleanup_seconds"] = time.perf_counter() - cleanup_start
            result["total_seconds"] = time.perf_counter() - total_start
        return result
