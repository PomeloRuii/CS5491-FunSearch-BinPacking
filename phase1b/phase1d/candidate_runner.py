"""Guarded body-transfer extension of the existing Phase 1C container policy.

Always a fresh container. No generated candidate can enter this transport until
a later explicit user-authorized implementation enables that path.
"""
import copy
import hashlib
import json
import subprocess
import threading
import time
import uuid

import bootstrap
from container_runner import ContainerRunner, POLICY, cli, create_args, verify_created
from candidates import trusted_permit
from interface import parse_candidate


def require_permit(candidate):
    if not trusted_permit(candidate):
        raise PermissionError("LLM-generated candidate execution awaits explicit user authorization.")


def candidate_args(image, name):
    original = create_args(image, name, "normal")
    return original[:-5] + ["--interactive", "--label=cs5491.phase1d=true",
                            image, "-I", "/app/candidate_worker.py"]


def verify_candidate_config(item, image):
    cfg = item["Config"]
    if cfg.get("Cmd") != ["-I", "/app/candidate_worker.py"] or not cfg.get("OpenStdin"):
        raise PermissionError("Unexpected candidate transport entry point or stdin policy.")
    adapted = copy.deepcopy(item)
    adapted["Config"]["Cmd"] = ["-I", "/app/worker.py", "--probe", "normal"]
    verify_created(adapted, image, "normal")


class CandidateRunner(ContainerRunner):
    def _request_payload(self, candidate, parsed, body, job_id, body_hash):
        """Default wire format retained; reviewed task adapters may add fixed metadata."""
        return {"job_id": job_id, "body": body, "body_sha256": body_hash}

    def _require_candidate_permission(self, candidate):
        """Default remains reviewed fixtures only; scoped adapters must recheck identity."""
        require_permit(candidate)

    def run_candidate(self, candidate, parsed, wall_seconds=30):
        # Provenance is checked before Docker create/inspect/start.
        self._require_candidate_permission(candidate)
        checked = parse_candidate(candidate.text, parsed.function_name, candidate.finish_reason)
        if checked.body != parsed.body:
            raise PermissionError("Parsed body differs from the permitted source.")
        from implementation import code_manipulation
        body = code_manipulation.rename_function_calls(
            parsed.body, parsed.function_name, "priority")
        if not 0 < wall_seconds <= 30:
            raise ValueError("Candidate wall deadline must be in (0,30].")
        name = "cs5491-phase1c-" + uuid.uuid4().hex
        job_id = uuid.uuid4().hex
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        payload = (json.dumps(self._request_payload(candidate, parsed, body, job_id, body_hash),
                              ensure_ascii=False) + "\n").encode()
        if len(payload) > 65536:
            raise ValueError("Candidate request exceeds its wire size limit.")
        result = {"status": "controller_error", "container_name": name,
                  "job_id": job_id, "body_sha256": body_hash,
                  "image": self.image, "cleanup_verified": False}
        started, process = time.perf_counter(), None
        try:
            stage = time.perf_counter()
            cli(self.docker, candidate_args(self.image, name))
            result["create_seconds"] = time.perf_counter() - stage
            stage = time.perf_counter()
            item = json.loads(cli(self.docker, ["inspect", name]).stdout)[0]
            verify_candidate_config(item, self.image)
            result["policy_inspection_seconds"] = time.perf_counter() - stage
            result["inspected_configuration"] = item
            buffers = [bytearray(), bytearray()]
            count, lock, overflow = [0], threading.Lock(), threading.Event()
            stage = time.perf_counter()
            process = subprocess.Popen(
                [self.docker, "start", "--attach", "--interactive", name],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                shell=False)

            def consume(stream, index):
                while True:
                    chunk = stream.read1(4096)
                    if not chunk:
                        break
                    with lock:
                        remaining = POLICY["combined_output_limit_bytes"] - count[0]
                        buffers[index].extend(chunk[:max(remaining, 0)])
                        count[0] += len(chunk)
                        if count[0] > POLICY["combined_output_limit_bytes"]:
                            overflow.set()
                        if index == 1 and "worker_ready_seconds" not in result:
                            for line in buffers[1].splitlines():
                                try:
                                    message = json.loads(line)
                                except ValueError:
                                    continue
                                if message.get("kind") == "context":
                                    result["worker_ready_seconds"] = time.perf_counter() - stage
                                    break

            def send():
                try:
                    process.stdin.write(payload)
                    process.stdin.flush()
                except (OSError, BrokenPipeError):
                    pass
                finally:
                    process.stdin.close()

            threads = [threading.Thread(target=consume, args=(stream, i), daemon=True)
                       for i, stream in enumerate((process.stdout, process.stderr))]
            threads.append(threading.Thread(target=send, daemon=True))
            for thread in threads:
                thread.start()
            while process.poll() is None:
                if overflow.is_set() or time.perf_counter() - stage >= wall_seconds:
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
                raise RuntimeError("Candidate input/output collectors did not stop.")
            result["start_attach_wait_seconds"] = time.perf_counter() - stage
            result["stdout"] = buffers[0].decode("utf-8", errors="replace")
            result["stderr"] = buffers[1].decode("utf-8", errors="replace")
            result["output_bytes_seen"] = count[0]
            state = json.loads(cli(self.docker, ["inspect", name]).stdout)[0]["State"]
            result["container_state"] = state
            result["worker_messages"] = []
            for line in result["stderr"].splitlines():
                try:
                    result["worker_messages"].append(json.loads(line))
                except ValueError:
                    pass
            if result["status"] == "controller_error":
                result["status"] = "oom_killed" if state.get("OOMKilled") else "runtime_error"
                if state.get("ExitCode") == 0:
                    response = json.loads(result["stdout"])
                    value = response.get("result", {})
                    if (response.get("kind") != "result" or value.get("job_id") != job_id
                            or value.get("body_sha256") != body_hash):
                        raise ValueError("Result identity or checksum mismatch.")
                    result["result"] = value
                    result["status"] = "ok"
        except (OSError, ValueError, RuntimeError, PermissionError,
                subprocess.TimeoutExpired) as exc:
            result.update(status="controller_error", error_type=type(exc).__name__, message=str(exc))
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            stage = time.perf_counter()
            try:
                cli(self.docker, ["rm", "--force", "--volumes", name], check=False)
                leftovers = cli(self.docker, ["ps", "--all", "--quiet", "--filter",
                                              "name=^/" + name + "$"])
                result["cleanup_verified"] = not leftovers.stdout.strip()
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                result["cleanup_error"] = str(exc)
            result["cleanup_seconds"] = time.perf_counter() - stage
            result["total_seconds"] = time.perf_counter() - started
        return result
