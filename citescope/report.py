"""Produce one self-contained accessible HTML report from evaluated CiteScope JSON.

All user-provided content is HTML-escaped. The report contains no remote
resources, JavaScript, trackers, cookies, or network calls.
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path


def _safe(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _percent(number: float | None) -> str:
    if number is None:
        return "Not reviewed"
    return "%.1f%%" % (number * 100)


def _status(value: str) -> str:
    # Only fixed CSS classes are emitted.
    return {
        "supported": "good",
        "partially_supported": "partial",
        "contradicted": "bad",
        "unsupported": "bad",
        "unreviewed": "neutral",
    }.get(value, "neutral")


def render_html(report: dict) -> str:
    if not isinstance(report, dict) or report.get("schema") != "citescope-benchmark-v1":
        raise ValueError("Expected a CiteScope benchmark-v1 report")
    name = _safe(report.get("name", "Untitled benchmark"))
    source_sha = _safe(report.get("sha256", "unknown"))
    sample_type = _safe(report.get("sample_type", "unspecified"))
    label_provenance = _safe(report.get("label_provenance", "unspecified"))
    models = report.get("models", {})
    results = report.get("results", [])
    if not isinstance(models, dict) or not isinstance(results, list):
        raise ValueError("Invalid benchmark report shape")

    cards = []
    for model_name in sorted(models):
        summary = models[model_name]
        score = summary.get("macro_cited_supported_rate")
        score_display = _percent(score)
        width = max(0, min(100, (score or 0) * 100))
        cards.append(
            '<article class="model-card"><div class="eyebrow">MODEL</div>'
            '<h3>%s</h3><div class="big-number">%s</div>'
            '<div class="meter" role="img" aria-label="Citation-supported rate %s">'
            '<div class="meter-fill" style="width: %.2f%%"></div></div>'
            '<p>Case-balanced, reviewed cited-claim support. %s evaluated cases; %s runs.</p>'
            '</article>' % (
                _safe(model_name), score_display, score_display, width,
                _safe(summary.get("evaluated_cases", 0)), _safe(summary.get("runs", 0)),
            )
        )

    comparison = report.get("comparison")
    comparison_html = ""
    if isinstance(comparison, dict):
        interval = comparison.get("bootstrap_95_percent_interval", [0, 0])
        delta = comparison.get("delta_candidate_minus_baseline")
        delta_text = "Unavailable" if delta is None else "%+.1f pp" % (delta * 100)
        interval_text = "[%+.1f, %+.1f] pp" % (interval[0] * 100, interval[1] * 100)
        comparison_html = (
            '<section class="comparison" aria-labelledby="comparison-heading">'
            '<div class="eyebrow">PAIRED COMPARISON</div>'
            '<h2 id="comparison-heading">%s → %s</h2>'
            '<div class="comparison-value">%s</div>'
            '<p>95%% bootstrap interval: %s across %s shared cases '
            '(seed %s, %s resamples).</p>'
            '<p class="fine">The interval describes this labeled sample; it does not '
            'prove statistical generalization or establish causation.</p></section>' % (
                _safe(comparison.get("baseline")), _safe(comparison.get("candidate")),
                delta_text, interval_text,
                _safe(comparison.get("shared_cases", 0)), _safe(comparison.get("seed")),
                _safe(comparison.get("bootstrap_samples")),
            )
        )

    run_cards = []
    for run in results:
        metrics = run.get("metrics", {})
        claims = run.get("claims", [])
        claim_html = []
        for claim in claims:
            verdict = str(claim.get("verdict", "unreviewed"))
            evidence = claim.get("evidence", [])
            citations = " ".join("[%s]" % _safe(cid) for cid in claim.get("citations", []))
            evidence_html = "".join(
                '<div class="evidence"><span>Source [%s]</span><blockquote>%s</blockquote></div>'
                % (_safe(item.get("source_id")), _safe(item.get("quote")))
                for item in evidence
            )
            claim_html.append(
                '<li><div class="claim-head"><span class="verdict %s">%s</span>'
                '<span class="refs">%s</span></div><p>%s</p>%s</li>'
                % (_status(verdict), _safe(verdict.replace("_", " ")),
                   citations or "No citation", _safe(claim.get("text")), evidence_html)
            )
        run_cards.append(
            '<details class="run"><summary><span class="run-title">%s</span>'
            '<span class="meta">%s / %s</span>'
            '<span class="score">%s</span></summary>'
            '<div class="run-content"><p class="question">%s</p>'
            '<div class="mini-metrics">Reviewed %s / %s · Unresolved references %s · '
            'Citation resolvability %s</div><ol class="claims">%s</ol></div></details>'
            % (
                _safe(run.get("model")), _safe(run.get("case_id")),
                _safe(run.get("run_id")),
                _percent(metrics.get("cited_supported_rate")),
                _safe(run.get("query")),
                _safe(metrics.get("reviewed_claims")),
                _safe(metrics.get("claims")),
                _safe(metrics.get("unresolvable_claim_references")),
                _percent(metrics.get("citation_resolvability")),
                "".join(claim_html),
            )
        )
    if not run_cards:
        run_cards = ['<p class="empty">No results available.</p>']
    if not cards:
        cards = ['<p class="empty">No evaluated models yet.</p>']
    banner = (
        '<div class="warning"><strong>Demonstration data only.</strong> '
        'This dataset is synthetic or unreviewed. Do not report these as '
        'independent model performance results.</div>'
        if sample_type in ("synthetic_demo_not_research", "unreviewed_records")
        else '<div class="notice">Results depend on the provenance and reliability '
             'of the supplied human annotations. This report does not verify '
             'the claims independently.</div>'
    )
    html = HTML_TEMPLATE.replace("__NAME__", name)
    html = html.replace("__SAMPLE_TYPE__", sample_type)
    html = html.replace("__PROVENANCE__", label_provenance)
    html = html.replace("__SHA__", source_sha)
    html = html.replace("__BANNER__", banner)
    html = html.replace("__MODEL_CARDS__", "".join(cards))
    html = html.replace("__COMPARISON__", comparison_html)
    html = html.replace("__RUN_CARDS__", "".join(run_cards))
    return html


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="robots" content="noindex,nofollow">
<title>__NAME__ — CiteScope Benchmark</title>
<style>
:root{--bg:#f6f8fb;--paper:#ffffff;--ink:#132036;--sub:#53657c;--line:#dfe5ed;--accent:#195bc7;--soft:#edf3ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
a{color:var(--accent)}.container{max-width:1140px;margin:auto;padding:0 28px}
header{background:#10223e;color:#fff;padding:26px 0 44px}
nav{display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap}
.logo{font-size:21px;font-weight:790;letter-spacing:-.04em;color:#fff}
.meta-pill{border:1px solid #56708c;border-radius:50px;padding:5px 12px;color:#c7d7ed;font-size:12px;letter-spacing:.03em}
header h1{font-size:clamp(33px,5vw,56px);line-height:1.11;max-width:790px;letter-spacing:-.055em;margin:68px 0 17px}
header p{color:#c7d5e5;max-width:725px;margin:0}
.eyebrow{font-size:11px;font-weight:850;letter-spacing:.11em;color:#52719a}
header .eyebrow{color:#9dc1ff}main{padding:36px 0 64px}
.warning,.notice{border:1px solid #e6c88a;background:#fff7df;border-radius:10px;padding:16px 20px;margin-bottom:27px}
.notice{border-color:#bbd3f7;background:#eef5ff}
section{margin:0 0 37px}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;flex-wrap:wrap;margin-bottom:16px}
h2{font-size:24px;letter-spacing:-.028em;line-height:1.2;margin:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,255px),1fr));gap:14px}
.model-card,.comparison,.run{background:var(--paper);border:1px solid var(--line);border-radius:13px}
.model-card{padding:21px 23px}
.model-card h3{font-size:18px;margin:7px 0 17px;overflow-wrap:anywhere}
.big-number{font-size:35px;font-weight:800;letter-spacing:-.05em}
.meter{margin:10px 0 16px;background:#e6edf6;border-radius:20px;height:9px;overflow:hidden}
.meter-fill{background:#2262c5;height:100%;border-radius:20px}
.model-card p{font-size:13px;color:var(--sub);margin:0}
.comparison{padding:26px;background:#ebf2fe}
.comparison h2{margin:6px 0 12px}.comparison-value{font-size:44px;font-weight:800;letter-spacing:-.04em}
.comparison p{margin:6px 0;color:#314863;font-size:14px}.comparison .fine{color:#5f7188}
.run{margin-bottom:10px;overflow:hidden}
.run summary{cursor:pointer;padding:19px 22px;display:grid;grid-template-columns:1fr 1fr auto;align-items:center;gap:16px}
.run summary:hover{background:#f9fbfe}
.run summary:focus-visible{outline:3px solid #4382f3;outline-offset:-3px}
.run-title{font-weight:750;overflow-wrap:anywhere}
.meta{color:var(--sub);font-size:13px;overflow-wrap:anywhere}
.score{font-weight:750;color:#174e98}
.run-content{border-top:1px solid var(--line);padding:12px 22px 22px}
.question{font-size:16px;font-weight:630}
.mini-metrics{font-size:12px;color:var(--sub);padding:10px 0;border-bottom:1px solid var(--line)}
.claims{list-style:none;padding:0;margin:0}
.claims li{padding:16px 0;border-bottom:1px solid var(--line)}
.claims li:last-child{border:0}
.claim-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.verdict{font-size:11px;border-radius:6px;padding:4px 9px;font-weight:800;text-transform:capitalize}
.verdict.good{background:#daf4e6;color:#155b36}.verdict.partial{background:#fff1ce;color:#805515}
.verdict.bad{background:#fee2e2;color:#952e31}.verdict.neutral{background:#e9edf2;color:#596578}
.refs{font-size:12px;color:var(--sub)}.claims li p{margin:10px 0}
.evidence{border-left:3px solid #a5bfe5;padding:5px 0 6px 14px;margin-top:8px}
.evidence span{font-size:11px;font-weight:700;color:var(--sub)}
blockquote{margin:5px 0 0;font-size:14px;color:#394b63}
.methodology{border-top:1px solid var(--line);padding-top:24px;color:var(--sub);font-size:13px}
.methodology p{overflow-wrap:anywhere}
footer{color:var(--sub);padding:22px 0 38px;font-size:12px;border-top:1px solid var(--line)}
.empty{color:var(--sub)}
@media(max-width:660px){.container{padding:0 16px}header{padding-bottom:30px}header h1{margin-top:42px}.run summary{grid-template-columns:1fr auto}.meta{grid-column:1/-1;order:3}.run-content{padding:12px 16px 20px}}
@media(prefers-reduced-motion:no-preference){.run summary{transition:background-color .1s ease}}
</style>
</head>
<body>
<header><div class="container"><nav><span class="logo">CiteScope<span style="color:#8fb3ff">.</span></span>
<span class="meta-pill">EVIDENCE INTELLIGENCE / V1</span></nav>
<div class="eyebrow" style="margin-top:42px">REPRODUCIBLE CITATION RESEARCH</div>
<h1>__NAME__</h1>
<p>Measure how faithfully AI-generated answers reference documented sources. Claim support is reviewed; reference existence is machine-checked.</p>
</div></header>
<main class="container">
__BANNER__
<section aria-labelledby="model-heading">
<div class="section-head"><h2 id="model-heading">Model evidence scores</h2></div>
<div class="grid">__MODEL_CARDS__</div></section>
__COMPARISON__
<section aria-labelledby="detail-heading">
<div class="section-head"><h2 id="detail-heading">Evidence review</h2></div>
__RUN_CARDS__
</section>
<section class="methodology" aria-labelledby="methodology-heading">
<h2 id="methodology-heading">Read these scores carefully</h2>
<p><strong>Dataset type:</strong> __SAMPLE_TYPE__. <strong>Label provenance:</strong> __PROVENANCE__.</p>
<p><strong>Dataset SHA-256:</strong> <code>__SHA__</code></p>
<p>Numbers reflect submitted reviewer verdicts, not independent factual verification by CiteScope. Even an exact excerpt match does not prove entailment. Scores average across cases to avoid overweighting questions with more repeated runs. Unreviewed claims are excluded.</p>
<p>Made with the open-source CiteScope evaluation engine. Upstream foundation: GEO: Generative Engine Optimization, attributed to its original authors.</p>
</section>
</main>
<footer><div class="container">CiteScope · Reproducible research over growth claims · Offline HTML report</div></footer>
</body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render local CiteScope evaluation report as HTML")
    parser.add_argument("report", type=Path, help="Evaluated benchmark JSON")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        args.output.write_text(render_html(report), encoding="utf-8")
        print("Wrote CiteScope report to %s" % args.output)
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, "CiteScope report: %s\n" % exc)


if __name__ == "__main__":
    raise SystemExit(main())
