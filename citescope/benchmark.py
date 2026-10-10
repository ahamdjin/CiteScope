"""Human-annotated, reproducible claim-level AI citation benchmarks.

Scores are based on explicit annotations, NOT inferred LLM judgments. The
annotation provenance belongs to dataset authors. Exact evidence quotation
checks only verify occurrence of text, not entailment or factual truth.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import statistics
from typing import Any

from .audit import audit_record

VERDICTS = frozenset({
    "supported", "partially_supported", "unsupported",
    "contradicted", "unreviewed",
})
SUPPORTED = "supported"


def _require(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a nonempty string" % label)
    return value.strip()


def _identifier(value: Any, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("%s must be a positive integer" % label)
    identifier = str(value).strip()
    if not identifier.isdigit() or int(identifier) <= 0:
        raise ValueError("%s must be a positive integer" % label)
    return str(int(identifier))


def _match_excerpt(needle: str, haystack: str) -> bool:
    """Whitespace/case-normalized exact match, NOT semantic matching."""
    norm = lambda text: " ".join(text.split()).casefold()
    return norm(needle) in norm(haystack)


def _mean(numbers: list[float]) -> float | None:
    return round(statistics.fmean(numbers), 5) if numbers else None


def _rate(part: int, total: int) -> float | None:
    return round(part / total, 5) if total else None


def _validate_case(case: Any, case_number: int) -> tuple[str, dict[str, dict], list]:
    if not isinstance(case, dict):
        raise ValueError("Case %d must be an object" % case_number)
    case_id = _require(case.get("id"), "case id")
    _require(case.get("query"), "query for %s" % case_id)
    sources = case.get("sources")
    runs = case.get("runs")
    if not isinstance(sources, list) or not sources:
        raise ValueError("%s: sources must be a nonempty list" % case_id)
    if not isinstance(runs, list) or not runs:
        raise ValueError("%s: runs must be a nonempty list" % case_id)
    source_map = {}
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("%s: source must be an object" % case_id)
        sid = _identifier(source.get("id"), "source ID")
        if sid in source_map:
            raise ValueError("%s: duplicate source ID %s" % (case_id, sid))
        if not isinstance(source.get("text"), str) or not source["text"].strip():
            raise ValueError("%s: source %s has no text" % (case_id, sid))
        source_map[sid] = source
    return case_id, source_map, runs


def _score_run(case: dict, run: dict, source_map: dict, case_id: str) -> dict:
    model = _require(run.get("model"), "%s model" % case_id)
    run_id = _require(run.get("run_id"), "%s/%s run_id" % (case_id, model))
    answer = run.get("answer")
    claims = run.get("claims")
    if not isinstance(answer, str):
        raise ValueError("%s/%s: answer must be a string" % (case_id, model))
    if not isinstance(claims, list):
        raise ValueError("%s/%s: claims must be a list" % (case_id, model))

    basic = audit_record({"answer": answer, "sources": case["sources"]})
    cited_in_answer = set(basic["cited_source_ids"])
    seen_claims: set[str] = set()
    claim_rows = []
    supported = 0
    reviewed = 0
    cited_reviewed = 0
    cited_supported = 0
    checked_evidence = 0
    valid_evidence = 0
    unresolvable_refs = 0
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("%s/%s: claims must be objects" % (case_id, run_id))
        claim_id = _require(claim.get("id"), "claim id")
        if claim_id in seen_claims:
            raise ValueError("%s/%s: duplicate claim %s" % (case_id, run_id, claim_id))
        seen_claims.add(claim_id)
        claim_text = _require(claim.get("text"), "%s claim text" % claim_id)
        verdict = claim.get("verdict", "unreviewed")
        if verdict not in VERDICTS:
            raise ValueError("%s: invalid verdict %r" % (claim_id, verdict))
        citations = claim.get("citations", [])
        evidence = claim.get("evidence", [])
        if not isinstance(citations, list) or not isinstance(evidence, list):
            raise ValueError("%s: citations/evidence must be lists" % claim_id)
        citations = [_identifier(value, "%s citation" % claim_id) for value in citations]
        if len(set(citations)) != len(citations):
            raise ValueError("%s: repeated citation ID" % claim_id)
        for sid in citations:
            if sid not in cited_in_answer:
                raise ValueError(
                    "%s: citation [%s] is not found in the answer" % (claim_id, sid)
                )
        unresolvable = [sid for sid in citations if sid not in source_map]
        unresolvable_refs += len(unresolvable)
        if verdict != "unreviewed":
            _require(claim.get("reviewer"), "%s reviewer" % claim_id)
            reviewed += 1
            if citations:
                cited_reviewed += 1
            if verdict == SUPPORTED:
                supported += 1
                if citations:
                    cited_supported += 1

        evidence_rows = []
        if verdict == "supported" and not evidence:
            raise ValueError(
                "%s: supported labels need at least one quoted source excerpt" % claim_id
            )
        for ev in evidence:
            if not isinstance(ev, dict):
                raise ValueError("%s: evidence must be objects" % claim_id)
            eid = _identifier(ev.get("source_id"), "%s evidence source_id" % claim_id)
            quote = _require(ev.get("quote"), "%s evidence quote" % claim_id)
            if eid not in source_map:
                raise ValueError("%s: evidence references missing source %s" % (claim_id, eid))
            if eid not in citations:
                raise ValueError(
                    "%s: evidence source [%s] must also be cited by claim" % (claim_id, eid)
                )
            match = _match_excerpt(quote, source_map[eid]["text"])
            checked_evidence += 1
            valid_evidence += int(match)
            if not match:
                raise ValueError(
                    "%s: evidence excerpt not found in source [%s]" % (claim_id, eid)
                )
            evidence_rows.append({"source_id": eid, "quote": quote, "exact_match": match})
        claim_rows.append({
            "id": claim_id,
            "text": claim_text,
            "citations": citations,
            "unresolvable_ids": unresolvable,
            "verdict": verdict,
            "reviewer": claim.get("reviewer") if verdict != "unreviewed" else None,
            "evidence": evidence_rows,
        })

    return {
        "case_id": case_id,
        "query": case["query"],
        "model": model,
        "run_id": run_id,
        "metrics": {
            "claims": len(claims),
            "reviewed_claims": reviewed,
            "supported_claims": supported,
            "supported_claim_rate": _rate(supported, reviewed),
            "cited_reviewed_claims": cited_reviewed,
            "cited_supported_claims": cited_supported,
            "cited_supported_rate": _rate(cited_supported, cited_reviewed),
            "unresolvable_claim_references": unresolvable_refs,
            "evidence_excerpts": checked_evidence,
            "evidence_exact_match_rate": _rate(valid_evidence, checked_evidence),
            "citation_resolvability": basic["metrics"]["citation_resolvability"],
            "citation_coverage": basic["metrics"]["citation_coverage"],
            "exact_quote_match_rate": basic["metrics"]["exact_quote_match_rate"],
        },
        "claims": claim_rows,
        "unresolved_answer_citations": basic["unknown_source_ids"],
    }


def evaluate_benchmark(payload: dict) -> dict:
    """Evaluate a benchmark payload. Never label claims using an LLM."""
    if not isinstance(payload, dict):
        raise ValueError("Benchmark must be a JSON object")
    dataset = _require(payload.get("name"), "benchmark name")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Benchmark must include nonempty cases")
    case_seen = set()
    run_keys = set()
    results = []
    for index, case in enumerate(cases):
        case_id, source_map, runs = _validate_case(case, index)
        if case_id in case_seen:
            raise ValueError("Duplicate benchmark case %s" % case_id)
        case_seen.add(case_id)
        for run in runs:
            if not isinstance(run, dict):
                raise ValueError("%s: run must be an object" % case_id)
            row = _score_run(case, run, source_map, case_id)
            key = (case_id, row["model"], row["run_id"])
            if key in run_keys:
                raise ValueError("Duplicate run ID within model and case: %s" % (key,))
            run_keys.add(key)
            results.append(row)

    by_model: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in results:
        metric = row["metrics"]["cited_supported_rate"]
        if metric is not None:
            by_model[row["model"]][row["case_id"]].append(metric)
    summary = {}
    for model in sorted(set(row["model"] for row in results)):
        case_means = {cid: _mean(scores) for cid, scores in by_model[model].items()}
        summary[model] = {
            "evaluated_cases": len(case_means),
            "runs": sum(row["model"] == model for row in results),
            "macro_cited_supported_rate": _mean(list(case_means.values())),
            "case_scores": case_means,
        }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {
        "schema": "citescope-benchmark-v1",
        "name": dataset,
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "label_provenance": payload.get("label_provenance", "unspecified"),
        "sample_type": payload.get("sample_type", "unspecified"),
        "metrics_note": (
            "Claim-level support scores are derived from supplied reviewer labels. "
            "Evidence quotes are checked for occurrence, not for entailment. "
            "Macro averages weight cases equally, not individual runs."
        ),
        "models": summary,
        "results": results,
    }


def compare_models(report: dict, baseline: str, candidate: str,
                   samples: int = 2000, seed: int = 42) -> dict:
    """Paired bootstrap over common cases (candidate - baseline).

    Does not establish statistical significance when cases are very few.
    """
    if baseline == candidate:
        raise ValueError("Compare two different models")
    if not 100 <= samples <= 100000:
        raise ValueError("samples must be between 100 and 100000")
    scores = report.get("models", {})
    if baseline not in scores or candidate not in scores:
        raise ValueError("Both models must occur in the benchmark report")
    a = scores[baseline]["case_scores"]
    b = scores[candidate]["case_scores"]
    common = sorted(set(a) & set(b))
    if not common:
        raise ValueError("No shared reviewed cases for the selected models")
    differences = [b[cid] - a[cid] for cid in common]
    rng = random.Random(seed)
    boot = sorted(
        statistics.fmean(rng.choices(differences, k=len(differences)))
        for _ in range(samples)
    )
    lower = boot[int(0.025 * (samples - 1))]
    upper = boot[int(0.975 * (samples - 1))]
    return {
        "baseline": baseline,
        "candidate": candidate,
        "metric": "macro_cited_supported_rate",
        "shared_cases": len(common),
        "case_ids": common,
        "delta_candidate_minus_baseline": _mean(differences),
        "bootstrap_95_percent_interval": [round(lower, 5), round(upper, 5)],
        "bootstrap_samples": samples,
        "seed": seed,
        "warning": (
            "Small samples and supplied reviewer labels limit interpretation. "
            "A bootstrap interval is not proof of causation, truth, or generalization."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate human-reviewed AI citations")
    parser.add_argument("dataset", type=Path, help="Versioned benchmark JSON")
    parser.add_argument("--output", type=Path, help="Write report JSON")
    parser.add_argument("--baseline", type=str, help="Baseline model for paired comparison")
    parser.add_argument("--candidate", type=str, help="Candidate model")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.dataset.read_text(encoding="utf-8"))
        result = evaluate_benchmark(data)
        if bool(args.baseline) != bool(args.candidate):
            raise ValueError("--baseline and --candidate must be given together")
        if args.baseline:
            result["comparison"] = compare_models(
                result, args.baseline, args.candidate, args.bootstrap_samples, args.seed
            )
        text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, "CiteScope benchmark: %s\n" % error)


if __name__ == "__main__":
    raise SystemExit(main())
