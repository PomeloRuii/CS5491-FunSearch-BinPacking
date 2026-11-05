# V4 live Mini Pilot closeout

## Research question and setup

Can FunSearch avoid redundant full Online Bin Packing evaluations while retaining useful evolutionary feedback? This development-only pilot ran one six-round live search per method. Each method started from an independently restored copy of the same upstream checkpoint and generated one candidate per round from its own measured feedback and database prompt. All 18 requests completed. The methods shared the original feasible-bin filter, NumPy first-maximum selection and fitness, the negative mean of the two family-level mean bin counts.

- **Standard** fully evaluated every static-valid candidate. **Exact** first checked its own fully evaluated source cache using the existing transport and function-header normalization.
- **S2-N16** used State Policy v2's first 16 S2 states after source checks. C1 propagated verified prior behavioral skips for repeated sources. F1 allowed full evaluation in the same fused worker when a recoverable fingerprint failure required it.
- **Generation** used `qwen3.8:27b-q4_K_M` at Q4_K_M and a 32,768-token resident context, with temperature 0.2, top-p 0.9, a 512-token output cap and reasoning disabled. The V4 prompt contract was `obp-objective-numerical-ast-contract-v4`. Static policy was `phase3-numerical-ast-v2`, runtime validity was `obp-validity-v1`, and the worker was `state-policy-worker-v2.0-runtime-v1`. The model replaces the proposal's Qwen2.5-Coder-7B-Instruct.
- **Schedule** used paired sampling seeds 549200001–549200006, one per round. Method order cycled through Standard → Exact → S2, Exact → S2 → Standard, and S2 → Standard → Exact, then repeated.

## Normal search

| Method | Qwen requests | Docker containers | Full evaluations | Fingerprints | Registered candidates | Best registered fitness |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| Standard | 6 | 6 | 6 | 0 | #1–#6 | −1142.541667 |
| Exact | 6 | 5 | 5 | 0 | #7–#10, #12 | −1142.541667 |
| S2-N16 | 6 | 5 | 2 | 5 | #13, #18 | −1142.541667 |

Exact skipped #11 after matching #10 under source normalization. S2 skipped #14, #15 and #17 on 16-state matches to #13. C1 skipped #16 through #15 because their raw source bytes were identical. Those are four skip events across three unique skipped sources. Skips did not receive fitness or registration.

S2 performed three fewer full evaluations than Exact and four fewer than Standard. S2 and Exact each used five normal containers, and all methods spent the same number of generation requests. Summed host wall time across the six rounds was **95.863 s** for generation steps, including readiness checks, and **61.261 s** for normal processing. These are combined serial measurements with one trajectory per method and variable lifecycle and host overhead. They do not establish an end-to-end speedup.

## Independent audit

After closing the normal rounds, four unique sources received independent full development evaluations and four isolated validation-only fingerprints. The development audit covered 12 OR3 and three Weibull instances, with 21,000 priority calls per source. The frozen 256-state bank was used as a development-side diagnostic. Audit results were kept out of all three search databases. All eight workers completed with verified cleanup. The #13 full worker logged an intermediate division warning and passed output validity and coverage checks.

Representative #13 and each unique skipped source scored **−1142.541667**, with mean bins of **212.4167 on OR3** and **2072.6667 on Weibull**. Each comparison against #13 showed 0/256 validation-decision disagreements, with no disagreement locations, and zero aggregate or family-level fitness differences. The historical global best was −1142.541667 at each skip, so the audit observed no missed global improvement.

| Skip event | Independently measured source | Selected island | Historical island best | Potential improvement |
| --- | --- | ---: | ---: | ---: |
| #14 | #14 | 9 | −2750 | +1607.458333 |
| #15 | #15 | 4 | −2750 | +1607.458333 |
| #16 | #15, identical source | 1 | −2750 | +1607.458333 |
| #17 | #17 | 1 | −2750 | +1607.458333 |

These margins identify four events at which the audited fitness would have exceeded the selected island's recorded best. The audit does not measure the effect of those registrations on later prompts or search quality. Equal best fitness across methods and agreement on the audited bank and development instances describe this pilot only.

The audit took **21.072 s** wall time, including **13.664 s** across the eight container lifecycles. Pilot usage was **18 Qwen requests, 24 containers, 17 full evaluations and 9 fingerprints**. Normal search contributed 18/16/13/5 and the audit contributed 0/8/4/4. V4 ceilings were 18/30/24/12. The known logged pilot total reached 51, including the 30 earlier requests and three rejected V3 responses. Earlier connectivity request counts remain unresolved. The original main allocation remains at **0/540 used**.

## Interruption and comparison limits

The original Round 5 stopped during an empty-message Ollama preload. The CUDA error occurred during Flash Attention warmup before any Round 5 candidate request or worker dispatch. A standalone preload passed after service restart. A separately sealed continuation reconstructed all four closed rounds, kept the original stop immutable, and ran Rounds 5–6 with the original V4 settings, caches and remaining budget. All six normal closures and the stopped-attempt provenance were reverified after the audit.

V4 included candidate IDs and feedback receipt hashes in model-visible prompts. In Round 2 the upstream database prompt and substantive measured feedback matched across methods, yet those fields made the rendered prompts different. Later divergence therefore cannot be attributed solely to filtering. The live study also had one short trajectory per method and used development instances throughout. General behavioral equivalence, held-out quality, and a causal runtime or search-quality advantage remain untested. Earlier controlled studies are reported separately in the [State Policy v2 results](STATE_POLICY_V2_RESULTS.md).

## Compact provenance

The hashes below identify the verified local artifacts. This export provides scalar results and identities. Reconstructing the live execution also requires the exact inputs, worker images and private prompt, response and execution artifacts. See the [data and security limits](../DATA_AND_SECURITY.md).

| Artifact | SHA-256 |
| --- | --- |
| V4 research protocol | `b05846ea81615a885a08f2a76e6ac4ca7ef102b04de3b419340fe61a17b1a46c` |
| Original V4 execution plan | `b90aa5033dddd736cb19f7e979a01f70a23478b74080a44676fee9e46de4314b` |
| Original Round 5 stop receipt | `80c2a3990dcadf3d96f4336fe96c1e8fd09299c18b9ea96cba30b47c558c46ce` |
| Round 5–6 continuation plan | `b8b7ad4321b08f2c142e234eb69030742b6e94856a3d0fbac6d4d23ebf41820c` |
| Final audit manifest | `e9a71a6da46e27872e0e9e9c719c4e61fad6dcbca11038d1ce29bdc5250e22c2` |
| Final audit result receipt | `c62ed079953f3093952aa2d7420568175359dd62f341184dc7db9dbf4c90b9d7` |
| Campaign closure receipt | `5c0b5dfed1c7a130325ee232ab5034337c119351117dd3622b6904b10dfa3ef1` |
| Qwen model digest | `25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e` |
| Initial database checkpoint | `6c2cda71aee1f2a1764318903cd3134ef8a7dc366b9a232629623d3c951e6905` |
| Development dataset, canonical | `a9709f23f17aaf0e083a989e1b5ccf53ac91221987128d5480ff1093f594c401` |
| S2 state bank, canonical | `f3772d53d6e54907b77bb90e99761d48d31e10d569edb4fbdacaf62ec34af874` |
| Audit validation bank, canonical | `ecb5259c5f398508bdc486f6f8f919eee9a84143939822feec5aca7fabe4ff4d` |

Raw source SHA-256 by round. Standard uses IDs #1–#6, Exact #7–#12 and S2-N16 #13–#18.

| Round | Standard | Exact | S2-N16 |
| --- | --- | --- | --- |
| 1 | `e51311a0dd234c124cb731e77c4970ff6eb857e0b548463c9eb3f9ef9ef43549` | `e51311a0dd234c124cb731e77c4970ff6eb857e0b548463c9eb3f9ef9ef43549` | `e51311a0dd234c124cb731e77c4970ff6eb857e0b548463c9eb3f9ef9ef43549` |
| 2 | `ee8ffda6b2fdc030c816b9ccb945809fbcbed59a19454516c9f395251a5945c3` | `93e7acebe7d25999dae3ace3a5a9840aafe1990823c8ec19156dc4be967b2f57` | `b0d0a4b076273e598129b6c1ee98e8fa818e4d4a88b727fecae72aff025972ce` |
| 3 | `bfd5f9111d0b209f2104e47579c64ac6d92e5a0d329a34a8124e810e779d0069` | `bfd5f9111d0b209f2104e47579c64ac6d92e5a0d329a34a8124e810e779d0069` | `9d20d487c945d9962a80bad1f738fbc2bc77fa15ae1f4566afdd45e89afb156f` |
| 4 | `104a6ae21fd6aa834368b4253645a38aa19961833405bfa60cca2014e37776d3` | `9d20d487c945d9962a80bad1f738fbc2bc77fa15ae1f4566afdd45e89afb156f` | `9d20d487c945d9962a80bad1f738fbc2bc77fa15ae1f4566afdd45e89afb156f` |
| 5 | `2b3391efd9d3d04d50f7bfeeefba4b7184927d2afacf841c0decd758f3fb59d3` | `93f40fac009fca81ac6472d5e0267366eec591efb032af73e4e9d00b4a4f51a9` | `ca6c8cd6ba24e5cfea64f496f5c0bb09ee3a3e41563e120187572e8734414c12` |
| 6 | `baf20892891d53cbf4b56d18cc18d7c5a78b4ea95f808227f17147666856e118` | `8e8453addd3537af19b1413000529edcacab80eff80abbf96ae587fed4bbe1de` | `b15def3341563b785eeaa6d95186fb49f556607331dbcba8d11fa90929d8d4d9` |

## Pre-main decision memo

**GO for preparing the original matched-budget study. NO-GO for dispatch.** Retain three configurations, three paired runs and 60 calls per run. Before sealing a separate main protocol:

1. **Prompt fairness.** Keep candidate IDs and receipt hashes in provenance only. Use an offline prompt comparison to verify that equivalent selected programs, database prompts and substantive measured feedback render identical model messages. Verify that genuine score or database differences remain visible.
2. **Island-level quality.** Predefine global and selected-island improvement opportunities against the pre-skip thresholds, per-island registration and unique-program diversity, and incumbent fitness at matched call counts. Keep the original skip policy fixed. Use independent development audits to measure missed opportunities and the paired live trajectories to measure downstream outcomes.
3. **Runtime.** Time generation, readiness, parsing, filtering, Docker lifecycle, evaluation and database updates in complete search wall time. Report pure computation, audit time and operator-approval pauses separately. Predeclare the measurement boundaries, seed schedule and comparison summaries before dispatch.

Keep the frozen held-out split sealed. Main execution and any held-out evaluation require separate authorization.
