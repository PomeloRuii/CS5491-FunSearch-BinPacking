# Reproducibility and safety

## Reproduce the public analysis offline

From the repository root with the recorded Python environment:

```text
conda env create -f environment.yml
conda run -n cs5491-funsearch python -B tools/verify_release.py
conda run -n cs5491-funsearch python -B tools/reproduce_main_study.py
```

The release checker verifies file inventory and parses the earlier, already-published replay pool for static validity. The main-study checker recomputes counts, timing contrasts and fitness from the new CSVs. These commands need neither a model nor Docker. For the final paper figures and the extended all-pair trajectory, install Matplotlib 3.8 or newer in an analysis environment and run `python -B tools/reproduce_main_study.py --figures ../cs5491-reproduced-figures`. Pixel-level PNG hashes can vary across Matplotlib/font versions; the plotted data are the verified CSV values. The Pair 2 figure uses both the full fitness axis and an explicitly labeled view from wave 4.

The files in `results/main_study/` are receipt-derived outputs with fixed meanings:

| File | Unit and contents |
| --- | --- |
| `matched_runs.csv` | Nine method-by-pair runs with resource counts, timing and final Development fitness |
| `trajectories.csv` | Nine series of 61 rows including checkpoint zero, full evaluation counts and family means |
| `audit_events.csv` | 18 sampled skip events, candidate/representative fitness, validation differences and margins |
| `heldout.csv` | Nine incumbent provenance rows, eight source/body identities, task number and family outcomes |
| `provenance.json` | Frozen input and result receipt digests and the separate research, audit and held-out budgets |

Higher fitness means fewer bins under equal-family weighting. The audit compares each skipped candidate against the representative and the historical global and selected-island thresholds. It preserves repeats as distinct events. Method-active time sums method-owned intervals; worker lifecycle and pure computation are nested measurements. Held-out OR3 total is mean × four; Weibull covers one instance.

## Inspect the implementation

- `phase2/filters.py` contains normalized exact-source matching and evaluated representatives.
- `phase3/state_policy_v2/states.py`, `replay.py` and `terminal_index.py` implement probe construction, decisions and C1 terminal reuse. `worker_v2.py` implements the trusted fused worker, validation-only tasks and F1 fallback.
- `phase1b/phase1c/container_runner.py`, `phase1b/phase1d/candidate_runner.py` and `phase2/research_worker.py` provide the reviewed transport and evaluator code. The public host runner locates Docker through PATH or normal installation locations. The held-out full-only worker entry point is `phase3/final_test_v1/worker.py`.
- The public `trusted_cases.py` and `backend.py` load Development fixtures only when the caller requests them, so method modules can be imported for inspection before data is materialized. Requesting the fixtures still requires the original hash and coverage checks.
- `NOTICE` and `LICENSE` preserve the upstream implementation attribution and license. `data/DATA_REQUIREMENTS.json` and `phase2/data/manifest.json` identify frozen input requirements. Rights to redistribute the raw dataset literals have not been independently established.

## Scope of runtime reproduction

The archived study ran on Windows with a Linux Docker backend, Python 3.10, NumPy 1.26.4, SciPy 1.13.1 and absl-py 2.1.0. The main search used local Ollama on an NVIDIA RTX 5090, a pinned Qwen3.8 27B Q4_K_M digest and a context length of 32,768. [Research accounting](paper/SUPPLEMENT.md) separates the formal request budget, exploratory usage and infrastructure. `results/main_study/provenance.json` links the main protocol and held-out closure by digest. The production image identifiers refer to tested local images.

Full runtime reconstruction on a fresh machine is unverified. It would require lawfully obtained exact inputs, the verified checkpoint and state banks, pinned model/worker artifacts, compatible GPU and host resources, and separately reviewed finite execution authority. The original Weibull generator seed is unavailable. Alternate generated inputs are a new study. The public package supplies code inspection and offline analysis; production orchestration, raw inputs, private journals and live approvals stay in the historical local archive.

Generated code belongs only in reviewed disposable workers. The archived path checked pinned Linux images, no network, a read-only root, nonroot UID/GID, no added capabilities or privilege escalation, and explicit CPU, memory, process, output and time limits. A worker reservation remains charged on uncertainty. Stop on an integrity, validity or cleanup failure, preserve the receipt, and obtain fresh bounded authorization for any later execution. These controls reduce exposure; ordinary containers are not a general-purpose security boundary for arbitrary hostile programs.
