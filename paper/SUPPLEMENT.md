# Technical supplement

The [final paper](CS5491_FINAL_REPORT.pdf) has four substantive pages and a separate references page. This repository supplement indexes the full evidence tables and operational accounting. The earlier seven-page [extended technical report](CS5491_EXTENDED_REPORT.pdf) and its [Markdown](EXTENDED_REPORT.md) are preserved as originally rendered. They retain their original draft label and all-pair trajectory figure.

## Frozen replay and live comparison

The state-policy replay fed the same ordered 16-request candidate pool to every arm in each of three timing blocks. The blocks used the prescribed seeded order, reversed order and rotation. This was a fixed input comparison with no new generation. Independent live databases evolved only in the matched main-study runs.

| Replay arm | Completed full evaluations per block | Mean normal wall time (s) | Final incumbent fitness |
| --- | ---: | ---: | ---: |
| Exact | 8 | 15.275 | −1142.542 |
| S2-N16 | 3 | 13.211 | −1142.542 |
| S2-N64 | 3 | 13.143 | −1142.542 |
| S2-N128 | 3 | 13.224 | −1142.542 |

All three S2 sizes separated the known #10/#8 false match from S0 on this pool. They had the same full-evaluation count and best fitness. N16 supplied the same observed discrimination with fewer probes. Mean measured time did not strictly decrease with probe size, and this replay was a single candidate pool. The earlier separate-worker replay had slower end-to-end time than Exact even though it reduced full evaluations. [State Policy v2 report](../docs/STATE_POLICY_V2_RESULTS.md) · [Replay measurements](../results/state_policy_v2/comparison_summary.csv)

The main study tested S2-N16, Exact and Standard at equal request budgets. [Nine matched-run rows](../results/main_study/matched_runs.csv) include generation active time, evaluation active time, Docker lifecycle, pure packing, fingerprint phase and pure fingerprint computation. Lifecycle and computation are nested within the active intervals. Human approval waits, shared orchestration and downtime are separate. [All nine trajectories](../results/main_study/trajectories.csv) · [Pair 2 full and zoomed view](../figures/fitness_pair2.png)

## Audit and held-out provenance

- [All 18 audit events](../results/main_study/audit_events.csv) identify candidate, representative, selection island, fitness delta, validation disagreement count and historical margins. The [extended report appendix](CS5491_EXTENDED_REPORT.pdf) renders the full table. Potential island margins refer to the historical selected-island threshold at the skip, with future counterfactual trajectories unobserved.
- [All nine held-out rows](../results/main_study/heldout.csv) carry source and body hashes, shared task identity and both family outcomes. Pair 0 Exact and S2-N16 share task 2. Four retrospective OR3 instances and one Weibull instance were frozen; historical whole-OR3 evaluation and legacy initialization limit the interpretation.
- [Provenance and resource bindings](../results/main_study/provenance.json) give the frozen protocol, model, image and input identities, 540-call study/audit archive digest, independent audit closure and Recovery v1.2 closure. The receipts and full instance values remain in the private archive.

## Generation and execution accounting

| Scope | Generation requests | What the number covers |
| --- | ---: | --- |
| Proposal estimate | ~570 | Nominal 30 pilot plus 540 formal main requests |
| Earlier logged diagnostics and pilots | 30 | The earlier logged pool and diagnostic usage, including failed charged generation attempts |
| V3 mini-pilot | 3 | Rejected responses that remain charged |
| Revised-prompt V4 mini-pilot | 18 | Logged prompt revision and pilot usage, separate from the main study |
| Known pre-main subtotal | 51 | 30 + 3 + 18 |
| Matched live main study | 540 | 60 × three methods × three pairs |
| Classified logged total | 591 | Includes pre-main and main; earlier connectivity total remains unknown |

Infrastructure repair and readiness preloads have separate records. The empty-message preload that interrupted the V4 pilot occurred before its candidate request and was accounted as readiness. The archived earlier HTTP event without a request body remains unclassified. The ledger provides neither an exact lifetime call total nor a separate invented number of repair calls. [V4 pilot closeout](../docs/V4_MINI_PILOT_CLOSEOUT.md) · [Earlier generation ledger](../results/RESULTS.md)

The proposal planned Qwen2.5-Coder-7B-Instruct with a conditional DeepSeek fallback. The actual fixed main generator was Qwen3.8 27B Q4_K_M via local Ollama on an NVIDIA GeForce RTX 5090, with paired sampling seeds, temperature 0.2, top-p 0.9, 512 output tokens, a 32,768-token context and reasoning disabled. All 540 archived main request settings used the pinned Qwen model and a loopback endpoint. The recorded runs show no DeepSeek fallback and $0 in external API charges. Earlier unclassified connectivity, equipment and electricity lack a complete cost record.

| Measured scope | Research containers | Full charges | Completed full evaluations | Fingerprints |
| --- | ---: | ---: | ---: | ---: |
| Formal main study | 362 | 311 | 311 | 99 |
| Independent audit | 48 | 24 | 24 | 24 |
| Original held-out startup failure | 1 | 1 | 0 | 0 |
| Held-out v1.1 guard stop | 0 | 0 | 0 | 0 |
| Held-out v1.2 completion | 8 | 8 | 8 | 0 |

The independent audit used zero generation and took 112.635 seconds of audit-loop wall time. Held-out v1.2 used zero generation and recorded 19.260 seconds after claiming its approval. Cumulative held-out research totals are nine containers and nine charges for eight full evaluations. One prior inert diagnostic container is separately recorded with zero full evaluations. Both failed held-out attempts retain their original state digests and charges. [Offline verification and safety](../REPRODUCIBILITY.md)
