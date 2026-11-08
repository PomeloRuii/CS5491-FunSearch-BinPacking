# Sample-Efficient FunSearch via Behavioral Fingerprinting

CS5491 Artificial Intelligence research project. We compare Standard FunSearch, normalized exact-source filtering, and a stratified 16-state behavioral filter for online bin packing. The objective is fewer full evaluations at matched LLM request budgets while retaining useful search feedback.

| Final evidence | Finding |
| --- | --- |
| Live search | 540 requests in three matched pairs. Standard, Exact and S2-N16 completed 180, 83 and 48 full Development evaluations. |
| Efficiency | S2-N16 used 42.2% fewer full evaluations than Exact. Method-active time was lower in two pairs and higher in one. |
| Audit | 18 independent skip comparisons found two fitness mismatches, seven potential selected-island improvements and zero candidates above the historical global-best threshold. |
| Held-out | Nine incumbent rows map to eight evaluated source identities. Pairs 0 and 1 tied. Pair 2 S2-N16 improved equal-family fitness with more OR3 bins and fewer Weibull bins. |

The timing result applies to these three trajectories and the measured environment. Finite probe agreement does not certify equivalence. The held-out comparison covers five instances and has documented historical OR3 exposure.

- [Final paper PDF](paper/CS5491_FINAL_REPORT.pdf) and [editable source](paper/FINAL_REPORT.md)
- [Repository supplement](paper/SUPPLEMENT.md) and [preserved extended technical report](paper/CS5491_EXTENDED_REPORT.pdf)
- [Proposal scope and deviations](paper/PROPOSAL_SCOPE.md)
- [Main-study data and provenance](results/main_study/) and [paper figures](figures/)
- [Reproducibility and safety](REPRODUCIBILITY.md)
- [Method and earlier phase guide](METHOD.md) · [Project guide](docs/PROJECT_GUIDE.md)

From the repository root, run `python -B tools/verify_release.py` and `python -B tools/reproduce_main_study.py` in the environment declared by `environment.yml`. The first checks the file inventory and archived static candidate classifications. The second recomputes final results from aggregate measurements. The offline checks neither run candidates nor contact an LLM. The older replay and pilot documents retain their phase-specific results and status at the time.

The source export includes the method and trusted workers. The public verification scope is offline analysis; exact runtime reproduction requires the original inputs, checkpoint, model, Docker environment and separate approval. Raw data, new generated programs, private approvals, transcripts and runtime logs are held outside this package. See [data and security](DATA_AND_SECURITY.md), [license](LICENSE) and [upstream attribution](NOTICE).
