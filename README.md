# Sample-Efficient FunSearch via Behavioral Fingerprinting

CS5491 individual research project: can sampled bin-selection behavior avoid
redundant Online Bin Packing evaluations while preserving useful search feedback?
The proposed pipeline is **static validity → exact-source filter → behavioral
fingerprint → complete evaluation when needed → database registration**.
All methods preserve `priority(item, bins)`, feasible-bin filtering, first-maximum
NumPy `argmax`, original fitness and real upstream island/prompt machinery.

This repository is a clean source/results export. Start with the
[project and phase guide](docs/PROJECT_GUIDE.md), [method](METHOD.md),
[Milestone update](docs/MILESTONE_2026-11-19.md) and [security/data limits](DATA_AND_SECURITY.md).

## Measured findings, including negative results

The same authentic 16-request Qwen pool was replayed; these are fixed-pool
comparisons, **not a completed multi-seed live evolutionary experiment**.

| Study | Exact mean wall | Behavioral mean wall | Observation |
| --- | ---: | ---: | --- |
| Original separate-worker N16/N64/N128 | 15.055s | 16.346 / 16.339 / 16.474s | 8.5–9.4% slower despite fewer full evaluations |
| Recovery v1.2, same-candidate fused N16 | 15.778s | 14.598s | 7.48% lower normal wall in two paired timing blocks |
| State Policy v2, S0-N16 C1/F1 | 15.275s | 12.867s | Three timing repetitions; original collision retained |
| State Policy v2, S2-N16 C1/F1 | 15.275s | 13.211s | 13.51% lower normal wall than concurrent Exact; 2.67% higher than S0-N16 |

These are separate experiments with their own concurrently measured Exact controls;
do not pool them or interpret the cross-study difference as a causal estimate.
The original separate-worker and fused v1.2 studies completed two full evaluations versus Exact's eight
per block. The fused study used ten containers versus Exact's nine: its measured
exact cache only indexes fully evaluated representatives. Identical source 15
therefore still ran a fingerprint after source 14 was behaviorally skipped.
See the [filter-order audit](docs/FILTER_ORDER_AUDIT.md). No historical count is changed.

The fused blocks were Exact/Fused 15.835/14.581s and 15.721/14.614s in reversed
orders. All modes kept best fitness −1142.541667 (OR3 212.416667 bins; Weibull
2072.666667), but registration and later prompts diverged. Candidate 10 falsely
matched 8 at N16/N64/N128 and on the old reserved 256-state audit, despite
different complete fitness. Six later development boundary challenges distinguish
their selected bins. Those post-hoc diagnostics are not independent validation.
Equal incumbent scores do not prove equivalent behavior or search trajectories.

See [original results](results/RESULTS.md),
[paired fused measurements](docs/FUSED_V12_MEASURED_RESULTS.md), and
[CSV/JSON evidence](results/fused_v12/). Only two timing repeats of one pool,
no final held-out verification, no demonstrated reduction in LLM calls, and no
540-call campaign support a general superiority claim. The unchanged main
campaign remains **NO-GO** pending predeclared controls and a frozen main
protocol. The [historical state-policy design](docs/NEXT_STATE_POLICY_V2.md)
was subsequently implemented and measured; see the completed [State Policy v2 study](docs/STATE_POLICY_V2_RESULTS.md).

S2-N16/64/128 each distinguished Candidate 10 from 8 and completed three full
evaluations per arm, versus S0's two and Exact's eight. Independent development
validation found 22/256 decision disagreements for that pair. S2 had zero observed
decision/fitness false matches among its audited skips in this known pool; skipped
island-improvement opportunities remain. All settings retained the same global
best, which does not establish preserved evolutionary quality. The 241-container
study used three timing repeats of one known 16-source pool, not three independent
live searches. S2 costs 2.7–3.5% more normal wall than S0, with no additional
discrimination from larger N here. These observations support later confirmation
of the smallest qualifying N16, not general superiority or a new execution grant.

The [V4 live Mini Pilot closeout](docs/V4_MINI_PILOT_CLOSEOUT.md) reports six live
rounds per method and the independent audit. S2-N16 completed two full evaluations
versus Exact's five and Standard's six. All three reached the same development
best. The audit found four potential island-level improvements among the skips,
and Round 2 exposed a prompt-metadata fairness confound.

## Verify evidence without executing candidate code

Validated private environment: Windows 11, WSL2/Docker Linux Engine, Python
3.10.22, NumPy 1.26.4, SciPy 1.13.1, absl-py 2.1.0. Dependencies are declared
in `environment.yml`. With that environment already available, run from the root:

```powershell
python -B tools/verify_release.py
python -B tools/reproduce_analysis.py --output ../recomputed_original_summary.json
python -B tools/analyze_fused_v12_results.py
python -B tools/analyze_state_policy_v2.py
```

These check inventory/static sources and recompute published CSV/JSON statistics;
they do not run candidate functions, call a model or start Docker workers.
Generation-time candidate ledger statuses are historical metadata, not current
execution permissions. Source files remain byte-preserved.

## Runtime reproduction and provenance limits

Raw development, reserved and held-out values, private approvals, dispatch logs,
credentials, Docker images and private Git history are excluded. Data redistribution
rights were not independently established. Dataset identifiers/hashes remain in
`phase2/data/manifest.json` and `data/DATA_REQUIREMENTS.json`; the original Weibull
generator seed is unavailable, so do not synthesize substitute data as a reproduction.

[Runtime reproduction limits](docs/FUSED_V12_REPRODUCTION.md) distinguish the
tested private controller from the public path projections. Fresh-machine runtime
reproduction is **not validated**. It requires independently obtained exact inputs,
equivalent local image/isolation checks and new finite source-bound permissions.
No reserved audit data is needed merely to recompute the public results. An image
ID records a tested local image, not a pullable registry image. Ordinary Docker
does not safely isolate arbitrary hostile Python.

Selected model: `qwen3.8:27b-q4_K_M`, Q4_K_M. See `model.json` for the model digest
and `candidates/` for the original replay pool's prompts, responses and sources.
The V4 closeout lists its settings and source hashes. This replaces the submitted
Qwen2.5-Coder-7B-Instruct plan. There are 51 known logged pilot requests, including
three rejected V3 responses and 18 completed V4 requests. Earlier connectivity
activity remains unresolved. Main experimental calls: 0/540.
No new calls or execution rights are conveyed by this release.

Upstream RayZhhh/FunSearch commit `4b8b4e7d43287998500983d709dfa44be58fca91`
derives from DeepMind FunSearch (2023). Original Apache-2.0 attribution, headers,
[LICENSE](LICENSE) and [NOTICE](NOTICE) are retained. See
[source provenance](SOURCE_PROVENANCE.json) for public projections.
