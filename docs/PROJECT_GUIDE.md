# Project guide: implementation, evidence and open research

## Research question and shared contract

Standard evaluates every static-valid candidate. Exact skips previously fully
evaluated identical sources under the documented transport/header normalization.
Behavioral checks Exact first, then selected-bin decisions on fixed development
states, and evaluates nonmatches completely. Matching sampled decisions is only
suspected equivalence; skipped programs never receive independent fitness or
registration. See [method](../METHOD.md) and [filter coverage](FILTER_ORDER_AUDIT.md).

## Phase map

| Stage | What it establishes | What it does not establish |
| --- | --- | --- |
| Infrastructure / trusted replay | Shared validity, Docker restrictions, database lifecycle, handcrafted comparisons | Qwen discovery or research generalization |
| Genuine two-wave pool | 16 actual Qwen requests with intervening real measured feedback; all outcomes retained | Matched-budget live search in every comparison arm |
| Original five-setting replay | Standard / Exact / N16 / N64 / N128, independent skip audits, negative timing result | Universal quality preservation or a speedup |
| Post-publication diagnosis | Structural sampling blind spot and lifecycle accounting | A measured fused speedup at that earlier stage |
| Completed fused v1.2 | Fresh paired Exact/Fused16 timings, owned restores, 43 disposable tasks and boundary decisions | A collision fix, fresh-machine certification or a main campaign |
| Completed State Policy v2 | S0/S2 at N16/64/128 with shared C1/F1, three timing repeats, 241 tasks and independent audits | General superiority, live multi-seed search or a pristine held-out validation |
| Completed V4 live Mini Pilot | Six live-feedback rounds per method, independent skip audits and a prompt-metadata fairness finding | Matched multi-seed quality, held-out performance or end-to-end speedup |

The dated [post-publication findings](POST_PUBLICATION_FINDINGS_V1.md) are historical
analysis; their then-proposed experiment was later completed as v1.2. Failed v1
and v1.1 attempts remain preserved privately and are not successful timing runs.

## Evidence navigation

- [Original measured comparison and audits](../results/RESULTS.md), with raw
  scalar CSV/JSON projections under `results/`.
- [Fused report](FUSED_V12_MEASURED_RESULTS.md): paired blocks, task accounting,
  quality and cleanup; `results/fused_v12/paired_comparison.csv` and
  `arm_measurements.csv` are the timing inputs.
- `candidate_outcomes.csv`, `trajectory_differences.csv` and `quality_checks.csv`
  expose registrations, prompt differences and concurrent-arm quality checks.
- `boundary_decisions.csv` contains the six measured candidate 8/10 decision pairs.
- [Filter audit](FILTER_ORDER_AUDIT.md) and `filter_order_evidence.csv` explain
  source 15's extra fingerprint. `island_opportunity_checks.json` is a post-hoc
  comparison, not independent new evaluations or an executed counterfactual.
- [Milestone](MILESTONE_2026-11-19.md), [future policy](NEXT_STATE_POLICY_V2.md),
  and [runtime limits](FUSED_V12_REPRODUCTION.md) describe scope and next decisions.
- [V4 live Mini Pilot closeout](V4_MINI_PILOT_CLOSEOUT.md) covers the live trajectories,
  independent audit, provenance and main-study readiness criteria.

## Source navigation

`phase1b/` supplies trusted scoring and development-only loading. `phase2/`
contains shared validity, filtering, frozen dataset metadata and trusted replay.
`phase3/` integrates real database prompts, Qwen artifacts, source-bound execution
and controlled replay. `phase3/fused_followup_v1/` adds the separately versioned
worker/controller; `recovery_v1_2` uses independently owned checkpoint state and
the Windows-compatible observer. Public protocols are descriptive projections,
not private execution manifests. Data-free analysis tools live in `tools/`.

The original published commit remains the historical baseline. This incremental
export changes source and explanations through normal scoped commits, never a
rewrite of that history. No raw dataset, grant or private repository history is
needed to read or recompute the exported scalar evidence.

## State Policy v2: completed follow-up

The [measured report](STATE_POLICY_V2_RESULTS.md) separates state coverage (S0/S2),
terminal-source propagation (C1) and same-worker validity fallback (F1). Scalar
evidence is under `results/state_policy_v2/`; source is under
`phase3/state_policy_v2/`. `tools/analyze_state_policy_v2.py` recomputes timing
statistics and audit counts without raw inputs or candidate execution. S2 retained
Candidate 10 but did not resolve island-registration losses. The subsequent
[live Mini Pilot](V4_MINI_PILOT_CLOSEOUT.md) exercised generation, evaluation and
database feedback. The matched multi-seed main study remains unrun.
