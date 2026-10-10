# CiteScope

**Reproducible evidence intelligence for AI-generated answers.**

CiteScope is an open-source Python toolkit for auditing numbered AI citations,
reviewing claim-level support against source snapshots, and comparing systems
on a versioned benchmark. Its goal is to make AI search evaluation transparent,
inspectable and honest about uncertainty—not to promise better rankings.

> **What makes CiteScope different?** It connects source provenance → claim-level
> human labels → model comparisons → reproducible, offline reports. The original
> GEO work provided a research foundation; these evaluation tools are CiteScope's
> own, separately developed extensions.

## What works now

| Capability | What it measures | Maturity |
|---|---|---|
| Citation reference audit | Unresolved source IDs and citation coverage | Tested |
| Exact quotation audit | Whether cited source text contains quoted excerpts | Tested |
| Recorded-answer ingestion | Turns archived model outputs into an **unreviewed** claim review queue | Tested |
| Claim-level rubric | Explicit supported / partial / unsupported / contradicted / unreviewed labels | Tested; labels supplied by reviewers |
| Evidence integrity | Rejects labeled-support excerpts missing from the cited source snapshot | Tested; **not** semantic entailment |
| Case-balanced comparisons | Paired bootstrap intervals across shared questions | Tested on synthetic examples |
| Offline HTML reports | Responsive, inspectable output with source-level evidence | Tested; no trackers or paid API |
| Modern model collection | Optional OpenAI-compatible Responses/Chat APIs, source-controlled GEO experiments | Implemented; live provider not yet tested |
| Independently reviewed research benchmark | Gold labels and published results | Planned |
| Hugging Face Space | Published demo and dataset | Planned; static demo export is ready |

## Quick start — no API keys

Python 3.10+ is required. No dependencies are required for the CiteScope
citation evaluation package.

```bash
# First, install the package from your CiteScope checkout
python -m pip install -e .

# 1. Check a single AI answer against provided source text
python -m citescope examples/citation-audit.json --output citation-report.json

# 2. Turn recorded outputs into unreviewed cases for human labeling
python -m citescope.ingest examples/recorded-responses.jsonl --output draft-benchmark.json

# 3. Evaluate explicitly labeled claims (SYNTHETIC demo only)
python -m citescope.benchmark examples/benchmark-synthetic.json \
  --baseline baseline --candidate candidate --output synthetic-results.json

# 4. Produce a standalone interactive-by-disclosure HTML report
python -m citescope.report synthetic-results.json --output report.html

# 5. Compare original and revised source variants using saved example answers
python -m citescope.geo_experiment examples/geo-experiment-synthetic.json \
  --control control --candidate evidence-first --output synthetic-geo.json

# 6. Preview an actual model collection experiment WITHOUT network access
python -m citescope.collect examples/geo-experiment-plan.json \
  --model YOUR_MODEL_IDENTIFIER --max-calls 12

# 7. Test the code
python -m unittest discover -s tests -v
```

Open `report.html` locally. To share it, upload it as a static web page **only
if the underlying dataset and its license permit redistribution**.

## Running a controlled modern-model experiment

`citescope.collect` accepts a controlled source-variant plan and can collect
responses using an OpenAI-compatible **Responses** or **Chat Completions** API.
By default it performs a safe dry run. Actual provider calls require all of:
`--execute`, a configured `CITESCOPE_API_KEY`, and a defined maximum call
budget. **Live API calls may incur charges and have not been exercised here.**

```bash
export CITESCOPE_API_KEY="your_api_key"   # do not commit credentials
python -m citescope.collect examples/geo-experiment-plan.json \
  --model YOUR_MODEL_IDENTIFIER --protocol responses \
  --repeats 2 --max-calls 12 --execute --output collected.json
python -m citescope.geo_experiment collected.json \
  --control control --candidate evidence-first --output comparison.json
```

This measures a controlled **citation-share proxy**, not how ChatGPT,
Gemini or another live search system ranks websites. Changing source text is
not the same as controlling source retrieval, ranking, or citations in search.

## Typical research pipeline

```text
Versioned source snapshots + user questions
                 │
Saved AI outputs from named models/runs
                 │
CiteScope recorded-answer ingestion
                 │
Human review: atomic claims, citations, evidence snippets, verdicts
                 │
Deterministic scoring and failure taxonomy
                 │
Case-balanced comparisons / confidence intervals
                 │
Self-contained reproducible HTML report
```

### What CiteScope cannot yet claim

A source ID that exists is **not** evidence that a citation is relevant.
A quotation matching source text is **not** proof that the source supports an
entire claim. Automated claim extraction currently provides annotation
candidates, not verified atomic claims. Comparative results from the bundled
synthetic examples are **not** real research results or model rankings.

The meaning of each label and recommended review procedure is in
[Research protocol](docs/citescope/research-protocol.md).

## Original GEO research and license

CiteScope incorporates the complete source of
[GEO: Generative Engine Optimization](https://github.com/GEO-optim/GEO)
at revision `c9e985f2bc4b539a01e8e9d226ff2a3d8d29a888`, preserving its
[Apache 2.0 license](LICENSE), original code under `src/`, data and assets.
The original root README is preserved unchanged as
[UPSTREAM_README.md](UPSTREAM_README.md), and the upstream SHA is recorded in
[UPSTREAM_SOURCE.txt](UPSTREAM_SOURCE.txt).

The original GEO research is by Pranjal Aggarwal, Vishvak Murahari, Tanmay
Rajpurohit, Ashwin Kalyan, Karthik R. Narasimhan and Ameet Deshpande. Its
paper is [GEO: Generative Engine Optimization](https://arxiv.org/abs/2311.09735).
Their historical experiments include rewriting techniques we **do not use** in
CiteScope's evaluator (for instance, generating unsupported quotes or numbers).
The repository retains the original experiments for attribution and historical
reproducibility, but CiteScope's own tools do not rely on them.

## Contributing

See [research protocol](docs/citescope/research-protocol.md) and
[project architecture](docs/citescope/architecture.md). Include test cases and
explicit limitations with proposed new evaluation metrics. No fabricated
citations, rankings, dates, or benchmark improvements are acceptable.

**Maintained in the [CiteScope repository](https://github.com/ahamdjin/CiteScope).**
