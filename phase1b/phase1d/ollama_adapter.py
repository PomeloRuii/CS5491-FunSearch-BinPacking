"""Minimal local OpenAI-compatible HTTP adapter, with explicit bounded retries.

Uses standard-library HTTP to avoid hidden SDK retries. No candidate execution.
"""
from dataclasses import dataclass, asdict
import hashlib
import json
import math
import socket
import time
from urllib import error, parse, request

from candidates import Candidate

MAX_RESPONSE_BYTES = 1024 * 1024
SELECTED_MODEL = "qwen3.8:27b-q4_K_M"
SELECTED_DIGEST = "25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e"


class HTTPFailure(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__("HTTP " + str(status))


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(url, payload, timeout):
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except error.HTTPError as exc:
        raise HTTPFailure(exc.code) from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("API response exceeds the byte limit.")
    return json.loads(raw)


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = "qwen3.8:27b-q4_K_M"
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 512
    seed: int = 5491
    reasoning_effort: str = "none"
    request_timeout_seconds: float = 120.0
    metadata_timeout_seconds: float = 8.0
    max_attempts: int = 2
    retry_backoff_seconds: float = 0.25
    expected_digest: str = SELECTED_DIGEST
    expected_quantization: str = "Q4_K_M"

    def __post_init__(self):
        url = parse.urlsplit(self.base_url)
        if (url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1")
                or url.path.rstrip("/") != "/v1" or url.query or url.fragment
                or url.username or url.password):
            raise ValueError("Only a credential-free local /v1 Ollama endpoint is allowed.")
        if self.model != SELECTED_MODEL or self.expected_digest != SELECTED_DIGEST or self.expected_quantization != "Q4_K_M":
            raise ValueError("The selected project model/digest/quantization must remain pinned.")
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int) or not 1 <= self.max_attempts <= 3:
            raise ValueError("max_attempts must be 1 through 3.")
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or not 1 <= self.max_tokens <= 2048:
            raise ValueError("Smoke-test max_tokens must be 1 through 2048.")
        numeric = (self.temperature, self.top_p, self.request_timeout_seconds,
                   self.metadata_timeout_seconds, self.retry_backoff_seconds)
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in numeric):
            raise ValueError("Configuration contains non-finite numbers.")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("Seed must be a nonnegative integer.")
        if not 0 <= self.temperature <= 2 or not 0 < self.top_p <= 1:
            raise ValueError("Invalid generation sampling parameters.")
        if not 0 < self.request_timeout_seconds <= 180 or not 0 < self.metadata_timeout_seconds <= 15:
            raise ValueError("Request/metadata timeout outside the smoke-test limits.")
        if not 0 <= self.retry_backoff_seconds <= 2:
            raise ValueError("Retry backoff must be 0 through 2 seconds.")

    @classmethod
    def load(cls, path):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("generated_execution_enabled") is not False:
            raise PermissionError("Generated execution cannot be enabled in this phase.")
        if value.get("retired"):
            raise ValueError("This historical preset is retired; use the pinned project config.")
        names = cls.__dataclass_fields__
        return cls(**{key: value[key] for key in names if key in value})


class OllamaAdapter:
    def __init__(self, config, logger, transport=http_json, sleep=time.sleep):
        self.config, self.logger, self.transport, self.sleep = config, logger, transport, sleep
        self.request_attempts = 0
        self.metadata_requests = 0
        self.metadata = None

    def model_metadata(self):
        origin = self.config.base_url.rstrip("/").rsplit("/v1", 1)[0]
        self.metadata_requests += 1
        version = self.transport(origin + "/api/version", None, self.config.metadata_timeout_seconds)
        self.metadata_requests += 1
        tags = self.transport(origin + "/api/tags", None, self.config.metadata_timeout_seconds)
        matches = [m for m in tags.get("models", []) if m.get("name") == self.config.model]
        if len(matches) != 1:
            raise ValueError("Configured exact model tag is not uniquely installed; no model is pulled.")
        model = matches[0]
        if model.get("remote_host") or model.get("remote_model") or not model.get("digest"):
            raise ValueError("Remote model or missing model digest is unsupported.")
        if (model["digest"] != self.config.expected_digest
                or model.get("details", {}).get("quantization_level") != self.config.expected_quantization):
            raise ValueError("Installed model digest/quantization differs from the selected project model.")
        self.metadata_requests += 1
        shown = self.transport(origin + "/api/show", {"model": self.config.model},
                               self.config.metadata_timeout_seconds)
        self.metadata = {
            "model_identifier": self.config.model, "digest": model["digest"],
            "details": model.get("details"), "size": model.get("size"),
            "ollama_version": version.get("version"), "capabilities": shown.get("capabilities"),
            "model_default_parameters": shown.get("parameters"),
            "model_info": shown.get("model_info"),
            "template_sha256": hashlib.sha256(shown.get("template", "").encode()).hexdigest(),
            "system_sha256": hashlib.sha256(shown.get("system", "").encode()).hexdigest(),
            "thinking": shown.get("thinking"),
            "renderer": shown.get("renderer"), "parser": shown.get("parser"),
            "template_source": shown.get("template_source"),
            "model_role": "selected_project_model",
            "proposal_initial_model": "Qwen2.5-Coder-7B-Instruct",
            "formal_model_selection": "user_selected; professor_approval_not_evidenced",
        }
        self.logger.emit("model_metadata", **self.metadata)
        return self.metadata

    def draw(self, prompt, messages):
        if self.metadata is None:
            raise RuntimeError("Record model identity before any generation request.")
        cfg = self.config
        payload = {"model": cfg.model, "messages": messages, "n": 1, "stream": False,
                   "temperature": cfg.temperature, "top_p": cfg.top_p,
                   "max_tokens": cfg.max_tokens, "seed": cfg.seed,
                   "reasoning_effort": cfg.reasoning_effort}
        prompt_hash = hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False,
                                               separators=(",", ":")).encode()).hexdigest()
        self.logger.emit("generation_request", payload=payload,
                         request_timeout_seconds=cfg.request_timeout_seconds,
                         max_attempts=cfg.max_attempts, model_digest=self.metadata["digest"],
                         prompt_sha256=prompt_hash,
                         budget_class="phase1d_diagnostic_not_formal_experiment")
        start = time.perf_counter()
        for attempt in range(1, cfg.max_attempts + 1):
            self.request_attempts += 1
            self.logger.emit("api_attempt_started", attempt=attempt,
                             total_request_attempts=self.request_attempts)
            try:
                response = self.transport(cfg.base_url.rstrip("/") + "/chat/completions",
                                          payload, cfg.request_timeout_seconds)
            except (HTTPFailure, error.URLError, TimeoutError, socket.timeout, OSError) as exc:
                retryable = (not isinstance(exc, HTTPFailure)
                             or exc.status in (429, 500, 502, 503, 504))
                self.logger.emit("api_attempt_failed", attempt=attempt,
                                 error_type=type(exc).__name__, message=str(exc),
                                 delivery_status="unknown",
                                 retry_scheduled=retryable and attempt < cfg.max_attempts)
                if not retryable or attempt == cfg.max_attempts:
                    raise
                self.sleep(cfg.retry_backoff_seconds * attempt)
                continue
            # A response is a completed draw, even if its candidate is malformed.
            # Never silently regenerate on syntax, finish-reason or contract errors.
            self.logger.emit("api_response_received", raw_response=response)
            if not isinstance(response, dict):
                raise ValueError("API response must be a JSON object.")
            choices = response.get("choices", [])
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("Expected exactly one response choice.")
            choice = choices[0]
            if not isinstance(choice, dict):
                raise ValueError("Response choice must be an object.")
            message = choice.get("message") or {}
            if not isinstance(message, dict):
                raise ValueError("Assistant message must be an object.")
            if message.get("tool_calls") or message.get("function_call"):
                raise ValueError("Tool calls are not candidate source and are unsupported.")
            text = message.get("content")
            if text is None:
                text = ""
            if not isinstance(text, str):
                raise ValueError("Model message content must be a string.")
            if response.get("model") != cfg.model:
                raise ValueError("Response model identifier differs from the requested model.")
            elapsed = time.perf_counter() - start
            receipt = {"response_id": response.get("id"), "response_model": response.get("model"),
                       "created": response.get("created"), "usage": response.get("usage"),
                       "finish_reason": choice.get("finish_reason"),
                       "message": message, "request_attempts": attempt,
                       "raw_response": response}
            self.logger.emit("generation_response", generation_seconds=elapsed, **receipt)
            return Candidate(text, "ollama", choice.get("finish_reason"), elapsed,
                             response.get("usage"), receipt)
        raise AssertionError("Unreachable retry state.")
