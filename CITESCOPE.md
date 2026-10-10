# CiteScope — evidence-first AI citation evaluation

CiteScope extends the open-source **GEO: Generative Engine Optimization**
research project ([original repository](https://github.com/GEO-optim/GEO)).
The original Apache-2.0 license, upstream research files and attribution
remain preserved. See [UPSTREAM_SOURCE.txt](UPSTREAM_SOURCE.txt).

## First original contribution: reproducible citation provenance

CiteScope adds a zero-dependency Python checker for AI answers that cite
numbered sources, using **snapshots** provided by the evaluator.

- **Citation coverage:** fraction of simple sentence units with citations
- **Citation resolvability:** fraction of numbered citations pointing to a
  supplied source ID
- **Exact quote checks:** quoted text present verbatim, ignoring whitespace
  differences, in a source that the claim cited

It does **not** automatically check whether a paraphrased claim is true, whether
a source actually supports a claim, or whether a URL is live.

### Run locally

\`\`\`bash
python -m citescope examples/citation-audit.json --output report.json
python -m unittest discover -s tests -v
\`\`\`

No OpenAI key, model download, or network access is needed.

Input format:

\`\`\`json
{
  "query": "When did the example launch?",
  "answer": "The example launched in 2024 [1].",
  "sources": [
    {"id": 1, "url": "https://example.org", "text": "It launched in 2024."}
  ]
}
\`\`\`

A list of records can also be supplied.

### Method limitations

The V1 parser recognizes inline citations such as \`[1]\` and \`[1, 2]\`.
The sentence splitter is deliberately simple and can miscount abbreviations.
Quote checks are exact substring matches, not semantic entailment.
The checker reads saved source text; it does not access live search engines.

## Roadmap

- [x] Reproduce the complete GEO working tree (original files intact)
- [x] Add citation provenance checks, sample, CLI and unit tests
- [ ] Define claim-level annotation rubric and publish human-labeled dataset
- [ ] Calibrate model-assisted citation support against human labels
- [ ] Add multiple model/provider adapters and repeated-run experiments
- [ ] Publish versioned benchmark data and an interactive Hugging Face Space
- [ ] Publish reproducible findings with limitations and provenance

## Research integrity

Historical GEO prompts include methods that request hypothetical numbers or
artificial quotes. CiteScope's evaluator does not use these prompts, and they
should never be used to generate evidence presented as factual.
No benchmark improvement or AI-search ranking gain is claimed without
measurements, proper baselines, and independent replication.
