# Sample-Efficient FunSearch via Behavioral Fingerprinting for Online Bin Packing

CS5491 individual research project. This release contains the implemented
Standard/Exact/Behavioral baseline, shared numerical validation, disposable Docker
worker controls, real Qwen candidate artifacts and measured pilot results.
It is a clean source/results export, with no private Git history or active grants.

**Observed result:** Behavioral16/64/128 completed2 full evaluations per block
versus Exact's8, but took8.5–9.4% longer end to end. A score-changing false match
occurred at every size. No missed current-best improvement was observed in this
fixed stream. See [measured results](results/RESULTS.md) and the CSV/JSON files.
This is not proof of fewer LLM calls, general statistical superiority or a
completed live evolutionary campaign. The540-call main campaign has not started.

## Reproduce the public evidence without executing model code

Validated development environment: Windows11, WSL2/Docker Linux Engine,
Python3.10.22, NumPy1.26.4, SciPy1.13.1 and absl-py2.1.0.
Create the environment using `environment.yml`, then from the repository root:

```powershell
conda env create -f environment.yml
conda run -n cs5491-funsearch python tools/verify_release.py
conda run -n cs5491-funsearch python tools/reproduce_analysis.py --output ../recomputed_summary.json
```

The first command is needed only when the environment does not exist. The two
Python commands check inventory/source/static policy and recompute the published
comparison/audit statistics. They do not call Ollama or run candidate functions.

## Reproduce runtime experiments

Raw instance/state values are deliberately **not distributed**: data redistribution
rights were not independently established, and held-out values must not leak.
Frozen IDs, split seeds and hashes are in `phase2/data/manifest.json` and
`data/DATA_REQUIREMENTS.json`. Obtain the exact licensed inputs independently.
Do not synthesize substitute Weibull instances: their original generator seed
is unavailable. With separately supplied minimized frozen inputs:

```powershell
python tools/materialize_data.py --development-data ../local-inputs/development/research_data.json --development-states ../local-inputs/development/states.json --audit-states ../local-inputs/audit/states.json
```

The helper verifies content hashes and materializes only development data and
development/reserved state banks. It neither imports a data Python file nor
executes a model function. Resulting local data files are Git-ignored.

Source layout is preserved under `phase1b/`, `phase2/`, and `phase3/`.
`phase3/multicandidate_pilot/final_replay.py` is the actual bounded replay entry
point; `supervised_replay.py` adds read-only receipt/history/block checks.
The byte-preserved original comparison checkpoint and fixed replay protocol are
under `research/`, preserving actual islands, scores and random state. Original
private authorization/generation-proof bundles and consumed execution state
are intentionally nonportable and absent. A clone is not an execution grant.
To rerun runtime measurements, prepare local checkpoints/configuration and
new source/image/data-bound authorizations, build and equivalently validate the
task images, and run a fresh finite campaign. Original image configuration IDs
record the tested local images; they are not registry pull references.
**Fresh-machine runtime reproduction is not validated by this release.**

The public `bin_packing_utils.py` withholds dataset literals and loads only locally
materialized development groups. Docker path lookup/probe targets are anonymized
in publication copies. Every change is declared in `RELEASE_INVENTORY.json`;
these copies were not used to create the private runtime results. They require
fresh validation before any new runtime experiment.

## Model and budget

Selected model: `qwen3.8:27b-q4_K_M`, digest and frozen controls in `model.json`.
Q4_K_M, temperature0.2, top-p0.9,512 output tokens, context32768, distinct declared
sampling seeds, one candidate/call, no retries or replacements. Genuine upstream
database prompts and verified actual feedback were used. Exact payloads, raw
responses and byte-preserved candidate sources are under `candidates/`.
Qwen3.8 replaces the Proposal's original Qwen2.5-Coder-7B-Instruct plan.
There are30 logged pilot calls, plus unknown earlier connectivity (at least two);
this does not certify the nominal lifetime30/570 budget. Both finite grants are
exhausted. No generation or code execution is enabled by this export.

## Method, limitations and attribution

See [METHOD.md](METHOD.md), [DATA_AND_SECURITY.md](DATA_AND_SECURITY.md),
[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json), [NOTICE](NOTICE) and [LICENSE](LICENSE).
Upstream RayZhhh/FunSearch commit4b8b4e7d43287998500983d709dfa44be58fca91
derives from DeepMind FunSearch2023; original Apache2.0 headers are retained.
No complete-hostile-Python security claim is made for ordinary Docker.
