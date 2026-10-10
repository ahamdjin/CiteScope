# Model-assisted evidence review

CiteScope separates three levels of evaluation:

1. Deterministic checks: does a citation point to a supplied source and do
   literal quotations appear in that source?
2. NLI suggestions: does a cited passage appear to entail, contradict or be
   neutral toward an atomic claim?
3. Human verdicts: does the cited source actually support the full claim
   including scope, dates, qualifications, numbers and context?

Only the third is a human-assigned support label. NLI suggestions never
automatically change or replace review verdicts.

## Model choice

Default: `cross-encoder/nli-deberta-v3-small`, trained on SNLI/MultiNLI.
https://huggingface.co/cross-encoder/nli-deberta-v3-small

This is a general natural-language-inference model, not a citation-specific
verifier calibrated on CiteScope data. Model probabilities are **not** the
probability that a claim is factually true.

## Selection pipeline

For each claim, inspect only the sources explicitly cited by that claim;
split the supplied source snapshots into short candidate passages;
rank candidates by lexical overlap (a recall-limited heuristic);
compare each passage as the premise with the claim as the hypothesis;
return the strongest directional NLI signal and the actual passage text.

The evaluator can miss semantic matches or context outside the selected
passages. Sentences above 1200 characters and model inputs above 512 tokens
can be truncated. Always inspect the full source before labeling.

## Run

Zero-network dry run (uses standard library only):

    python -m citescope.nli examples/benchmark-synthetic.json --output plan.json

Optional local model weights:

    python -m pip install -e '.[nli]'
    python -m citescope.nli examples/benchmark-synthetic.json --execute --output suggestions.json

Model download happens only when `--execute` is given, never during a dry
run or unit tests. Source text is processed locally, not sent to an AI API.
Large models may use substantial CPU time, memory and disk. A specific
`--revision` commit SHA should be used to reproduce the same model.

## Required validation before publishing AI quality claims

Collect a real, independently human-labeled and adjudicated sample with
representative topics and negative examples. Measure precision/recall,
calibration, false positives, reviewer agreement, and performance by type.
Compare against deterministic baselines; record exact weights and versions.
The repository's synthetic tests are **not evidence of NLI accuracy**.
