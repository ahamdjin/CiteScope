# Deploy a CiteScope static demo to Hugging Face

CiteScope can produce a **static HTML research report** that needs no server.
Hugging Face Static Spaces support hosting plain HTML for free.

## Prepare the demo

```bash
python -m citescope.benchmark examples/benchmark-synthetic.json \
  --baseline baseline --candidate candidate --output scores.json
python -m citescope.report scores.json --output index.html
```

## Publish

1. Create a new Hugging Face **Static Space** (SDK: `static`).
2. Use a Space README with YAML metadata:

```yaml
---
title: CiteScope Evidence Demo
emoji: 📚
sdk: static
app_file: index.html
license: apache-2.0
---
```

3. Upload the generated `index.html` with the README. Add a description
   that it uses **synthetic demonstration data**, not real model rankings.
4. When independent human-reviewed benchmark data is ready, publish a
   versioned Hugging Face **Dataset** with its full license, methodology, and
   limitations; then regenerate the report from those results.

Static reports deliberately do not execute or store user queries. Avoid
publishing private source snapshots or any customer data.

Reference: https://huggingface.co/docs/hub/main/spaces-sdks-static
