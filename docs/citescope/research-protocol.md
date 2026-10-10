# CiteScope research and annotation protocol (v1)

**Status:** A methodology, not a published study. The bundled data are synthetic.

## The research question

Given a user's question, archived source snapshots and an AI-generated answer,
how often do the answer's cited claims have **human-verified evidence** that
actually supports their meaning? How do two models differ on the *same* questions?

## Collecting an evaluation set

1. Pre-register the use case, time window, model identifiers and source policy.
2. Choose realistic questions using a reproducible, documented sampling method.
3. Archive source text, original URL, publication/retrieval date and permissions.
4. Obtain independently generated model answers under comparable conditions.
5. Archive actual model IDs, dates, prompts, settings and run identifiers.
6. Keep evaluation questions disjoint from any prompts used to tune models.
7. Use `python -m citescope.ingest` to prepare unreviewed claim candidates.
8. Split composite sentences into **atomic, independently falsifiable claims**.
9. Label and adjudicate independently, then freeze the dataset version.
10. Run the benchmark and publish both findings and failure cases.

## Labeling rubric

| Label | Operational definition |
|---|---|
| `supported` | Cited evidence directly backs the entire atomic claim, including qualifiers, entity, numerical values and timeframe. |
| `partially_supported` | Cited material backs part but not all meaningful aspects of a claim. |
| `unsupported` | The cited material exists but does not establish the claim. |
| `contradicted` | The cited material affirmatively conflicts with an essential part of the claim. |
| `unreviewed` | No completed, trustworthy assessment. Never count as correct or incorrect. |

Review the **actual source text** rather than judging claims from general knowledge.
Inspect surrounding passages to avoid cherry-picked quotations. Exact excerpt
presence is mechanically checked; whether it *entails* the claim is a human
judgment. A citationless answer may still contain factual statements, but it
is not source-grounded for this benchmark.

Every labeled claim needs a reviewer ID. A `supported` label additionally
requires at least one exact excerpt from a cited source. Reviewers must not
infer support merely from the fact that the excerpt exists.

## Independence and quality control

Use two reviewers for a representative subset, ideally all cases. Annotators
should not see which model produced a candidate while labeling. Track agreement
and report disagreements. Resolve contested labels with a third reviewer or
an adjudication record. Our v1 JSON uses **one final verdict and reviewer
field per claim**, so a separate annotation log is necessary for multi-rater
agreement until the multi-annotator schema is implemented. Do not describe
single-person labels as independently validated.

## Primary metric

`cited_supported_rate` = fully supported, cited, reviewed claims / all cited,
reviewed claims. Partial labels are **not** counted as fully supported.
Unreviewed and uncited claims are excluded from that rate and separately
reported. We also show citation resolvability, citation coverage, and exact
quotation matches; these are distinct and must not be conflated.

Scores are averaged within each case across repeated runs, then across cases,
so a question with ten repetitions does not outweigh another question with one.
The paired bootstrap resamples **shared cases**, not individual sentences.
Small case sets yield unstable intervals; report the number of shared cases.

## Reporting requirements

Always publish the dataset hash, sampling protocol, model versions, evaluation
window, number of questions, answers and reviewed claims, annotation agreement,
label balance, confidence intervals, error examples, and known limitations.
Do **not** publish a synthetic example's numbers as model performance.
Do not call a model “best” without uncertainty and a defined, relevant benchmark.

## Ethical handling

Never include private CRM records, API credentials or personal messages without
proper rights and consent. Respect website and dataset licenses. Quotes from
third-party sources should be limited to properly licensed or permitted uses.
Avoid creating fake reviews, fabricated statistics, or artificial citations.

## Controlled GEO optimization experiments

A CiteScope GEO experiment changes only the **target source** while keeping the
other cited candidate sources fixed. Test both variants using the same model,
same instructions, identical query and comparable sampling conditions, and
collect multiple independent runs. CiteScope validates that non-target source
snapshots do not change between variants.

Primary visibility proxy: target-source citation mentions divided by total
numbered citation mentions in the generated response; a run with no citations
gets zero target share. Values are averaged per question before comparison.
Bootstrap resampling is paired by question. This cannot measure source
retrieval probability or actual visibility in ChatGPT/Gemini/Perplexity search,
and cannot establish whether content rewriting *caused* performance changes
outside the controlled experiment.

The optional collector uses a bounded number of API requests and defaults to
a no-network dry-run. Provider charges can apply with `--execute`. Test one
question first, save model version and dated output, then scale a study.
