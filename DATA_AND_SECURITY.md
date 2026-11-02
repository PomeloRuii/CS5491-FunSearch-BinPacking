# Data, provenance, privacy and execution boundaries

The public export contains no raw development, reserved-audit or held-out
instances and no numerical fingerprint state capacities/items. Frozen split
identifiers, selection configuration, counts and hashes are metadata, not inputs.
Model prompts contain numerical heuristic code, not instance values.

The audited upstream source contains OR3/Weibull literals. OR-Library's
[official bin-packing page](https://people.brunel.ac.uk/~mastjjb/jeb/orlib/binpackinfo.html)
attributes its benchmark files to Falkenauer and describes their format. An
explicit redistribution grant for this project's exact inherited literals was
not established in this audit; the page alone does not resolve that question.
Software Apache licensing is not asserted as separate data ownership.
This is an evidence gap, not a legal conclusion that redistribution is forbidden.
Obtain any needed inputs independently subject to their applicable terms.
The original Weibull generator seed is missing; no replacement seed is invented.

Partition/state seeds remain5491/5492/5493. OR's final holdout had historical
aggregate infrastructure exposure before the retrospective split; it is not
claimed historically untouched. No final held-out instances were used in this
pilot or to choose fingerprint size/collision handling.

There is a stricter controller-side limitation in the original private run:
`trusted_cases.py` imports the legacy `bin_packing_utils.py`, whose module
initialization loads all upstream literals and computes L1 bounds, including
the retrospective held-out partition. Those bounds were not used in the
packing fitness, fingerprint construction, prompts, tuning or worker payloads.
Nevertheless, a strict host-level no-load/no-access condition was not met;
only the isolated worker input/evaluation boundary is verified. This is a
data-provenance deviation to resolve before a main campaign, not something
the successful container tests prove away. The publication-only local-data
loader removes those bundled literals, but was not used for the measured run
and needs equivalent runtime validation before future experiments.

The private project, original Proposal, user approval text, active grants,
consumed reservation state, host/Ollama/GPU logs, personal paths, credentials,
image tarballs and private Git history are excluded. Public metrics/provenance
are explicit projections; exact original hashes identify their private receipts.
Candidate sources and raw model responses are byte-preserved, not repaired.

Current private results used pinned minimized development/audit Linux images,
non-root65532, read-only root, no network, no host mounts/credentials/socket/GPU,
one CPU,512MiB memory/swap,64 PIDs,16MiB tmpfs, bounded output, an external
10-second task deadline and verified cleanup. No fused execution, parallel audit,
new architecture or unrestricted model-code execution was used.

Ordinary Docker retains shared-kernel/controller/resource/output/score-integrity
and crash risks. AST screening cannot prove safety, bounded cost or semantic
equivalence. Execution requires a fresh finite source/image/data authorization
and locally validated images. Publication source anonymization is not equivalent
runtime-validation evidence, and cloning these files does not inherit old grants.
