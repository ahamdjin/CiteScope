# CiteScope Evidence Review — browser app

Use this app to review **real source snapshots** in a browser. It does not
send content anywhere, fetch URLs, call AI models, or track users.

## Run it locally

Because this is an ES-module application, serve the directory over HTTP:

\`\`\`bash
cd web
python -m http.server 8000
\`\`\`

Open http://localhost:8000 in your browser. Click **Load example** to see
what a structurally valid, but factually misleading, citation looks like.

### Workflow

1. Paste an AI-generated answer with numbered references (e.g. \`[1]\`).
2. Add each cited source's *actual text snapshot* plus its optional URL.
3. Inspect for missing reference IDs, uncited candidate sentences and exact
   quotation mismatches.
4. Review each candidate claim yourself; select one of supported, partially
   supported, unsupported, contradicted or unreviewed.
5. For *supported* claims, paste a literal excerpt that appears in the cited
   source. Other labels may also carry an evidence excerpt.
6. Export a structured \`citescope-benchmark-v1\`-compatible JSON dataset or a
   Markdown research report.
7. Run the exported JSON through the Python evaluator:

\`\`\`bash
python -m citescope.benchmark citescope-case-001.json --output result.json
python -m citescope.report result.json --output report.html
\`\`\`

A matching quote does not automatically prove claim truth or entailment. The
tool creates candidate claim units, not perfectly atomic claims. Edit or split
compound claims before publishing independently validated benchmark data.

## Run web tests

\`\`\`bash
node --test web/tests/*.test.mjs
\`\`\`

The test suite includes a browser-generated Python benchmark fixture. The
GitHub Actions workflow runs that fixture through the Python evaluator.

## Hosting on Hugging Face

This static app can be hosted as a **free Static Space**. See
[Hugging Face Space setup](../docs/citescope/hugging-face.md).
A Space can host the same \`index.html\`, \`style.css\`, \`app.mjs\` and
\`audit-core.mjs\` without a backend or paid AI model. The Space's README must
contain \`sdk: static\` and \`app_file: index.html\`.

## Limits

- Does not follow a URL or retrieve a web page (source text is provided).
- Numbered \`[1]\` references only. Other provider citation formats need
  normalization.
- Quotations are matched as whitespace-normalized substrings.
- Composite or ambiguous sentences require a human reviewer.
- Outputs do not constitute real-world model rankings or live GEO measurement.
- Browser review data is in memory; export your file before closing the tab.

Copyright of original GEO sources remains with the original GEO authors.
CiteScope extensions are credited separately.
