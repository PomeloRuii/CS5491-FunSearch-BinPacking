# Copyright 2023 DeepMind Technologies Limited
# Modified for CS5491 Phase 1B on 2026-10-27; see reference_changes.patch.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""Class for sampling new programs."""
from __future__ import annotations
from abc import ABC, abstractmethod

from typing import Collection, Sequence, Type
import numpy as np
import time

from implementation import evaluator
from implementation import programs_database


class LLM(ABC):
    """Language model that predicts continuation of provided source code.

    RZ: The sampled function code must be trimmed! Especially using instruct-based LLM.
    -For example, the sampled function code (with description) is:
    ------------------------------------------------------------------------------------------------------------------
    Here is the function.
    def priority_v2(..., ...) -> Any:
        a = np.array([1, 2, 3])
        if len(a) > 2:
            return a / a.sum()
        else:
            return a / a.mean()
    This function is going to ..., and returns ...[Descriptions by LLM]
    ------------------------------------------------------------------------------------------------------------------
    -The descriptions above the function's signature, and the function's signature must be removed.
    -The above code must be trimmed as follows:
    ------------------------------------------------------------------------------------------------------------------
        a = np.array([1, 2, 3])
            if len(a) > 2:
                return a / a.sum()
            else:
                return a / a.mean()
        Here is the function. This function is going to ..., and returns ...[Descriptions by LLM]
    ------------------------------------------------------------------------------------------------------------------
    Please note that the indent must be preserved. And the additional descriptions can also be preserved,
    which will be trimmed by Evaluator.
    """

    def __init__(self, samples_per_prompt: int) -> None:
        self._samples_per_prompt = samples_per_prompt

    def _draw_sample(self, prompt: str) -> str:
        """Returns a predicted continuation of `prompt`."""
        raise NotImplementedError('Must provide a language model.')

    @abstractmethod
    def draw_samples(self, prompt: str) -> Collection[str]:
        """Returns multiple predicted continuations of `prompt`."""
        return [self._draw_sample(prompt) for _ in range(self._samples_per_prompt)]


class Sampler:
    """Phase 1B modification: finite, run-local budget, one candidate per draw."""

    def __init__(self, database, evaluators, samples_per_prompt,
                 max_sample_nums=None, llm_class=LLM):
        if samples_per_prompt != 1:
            raise ValueError("Phase 1B requires exactly one candidate per draw.")
        if (isinstance(max_sample_nums, bool) or not isinstance(max_sample_nums, int)
                or max_sample_nums < 0):
            raise ValueError("A finite nonnegative candidate budget is required.")
        self._database = database
        self._evaluators = evaluators
        self._llm = llm_class(1)
        self._max_sample_nums = max_sample_nums
        self._sample_count = 0
        self._draw_count = 0

    def sample(self, **kwargs):
        logger = kwargs.get("audit_logger")
        while self._sample_count < self._max_sample_nums:
            prompt = self._database.get_prompt()
            start = time.perf_counter()
            self._draw_count += 1
            try:
                samples = list(self._llm.draw_samples(prompt.code))
            except Exception as exc:
                if logger:
                    logger.emit("generation_failed", draw_id=self._draw_count,
                                error_type=type(exc).__name__, message=str(exc),
                                source=getattr(self._llm, "origin", "unspecified"))
                raise
            draw_seconds = time.perf_counter() - start
            if len(samples) != 1:
                if logger:
                    logger.emit("generation_contract_failed", draw_id=self._draw_count,
                                returned_candidates=len(samples))
                raise ValueError("One draw must return exactly one candidate.")
            self._sample_count += 1
            candidate_id = self._sample_count
            origin = getattr(self._llm, "origin", "unspecified")
            if logger:
                logger.emit(
                    "candidate_generated", candidate_id=candidate_id,
                    draw_id=self._draw_count, source=origin,
                    prompt=prompt.code, raw_response=samples[0],
                    version_generated=prompt.version_generated,
                    island_id=int(prompt.island_id),
                    generation_seconds=draw_seconds)
            chosen = np.random.choice(self._evaluators)
            chosen.analyse(
                samples[0], prompt.island_id, prompt.version_generated,
                **kwargs, candidate_id=candidate_id, origin=origin,
                global_sample_nums=candidate_id, sample_time=draw_seconds)
        return {"candidate_count": self._sample_count, "draw_count": self._draw_count}

    def _get_global_sample_nums(self):
        """Compatibility accessor; count is local to this sampler/run."""
        return self._sample_count

