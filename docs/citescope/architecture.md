# CiteScope architecture and contribution map

CiteScope is a separate research layer built alongside, not disguised as, the
upstream GEO experiment.

## Upstream GEO (retained, attributed)

- `src/`: historical optimization and synthetic generative-search experiments
- `GEO-Bench/`: original dataset leaderboard assets and app code
- `docs/GEO/`: upstream paper website
- `geval_prompts/`: original evaluation prompt assets
- `LICENSE` and `UPSTREAM_README.md`: upstream intellectual credit

The upstream runner uses legacy model APIs and contains historic prompt
strategies with artificial quotations or statistics. CiteScope does not invoke
them. They are available only to reproduce the original research.

## CiteScope original modules

- `citescope/audit.py`: check source IDs, coverage, quotation presence
- `citescope/ingest.py`: import real recorded model outputs as **unreviewed**
  claim-review candidates; never silently auto-label correctness
- `citescope/benchmark.py`: evaluate reviewed atomic claims, validate evidence
  excerpts, group cases, run deterministic paired bootstrap comparisons
- `citescope/report.py`: generate self-contained, HTML-escaped dashboards
- `tests/`: offline unit and end-to-end test suite
- `examples/`: **synthetic** demos and JSONL record templates, not findings

## Current data flow

```text
answer + source snapshots -> ingestion -> human labels -> benchmark JSON
                                                        |
                                                        v
                   per-claim evidence checks + structural citation audit
                                                        |
                                                        v
                case-balanced model scores + paired bootstrap interval
                                                        |
                                                        v
                     static report.html (safe, no external dependencies)
```

## Gaps before a publishable benchmark

1. Independent two-reviewer collection and adjudication provenance.
2. Real model outputs from repeatable, documented runs with model versions.
3. Representative question sampling, balanced categories and prompt controls.
4. Model-assisted entailment evaluation calibrated on independently reviewed
   source/claim examples—not treated as a ground truth itself.
5. Hugging Face dataset card, terms and reproducible build instructions.
6. Transparency around drift in live source pages and model behavior.

A high-quality data release is more valuable than inflating an unsupported
leaderboard score. The synthetic examples should never be promoted as research.
