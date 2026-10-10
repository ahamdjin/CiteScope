"""CiteScope controlled GEO experiments: citation visibility versus evidence quality.

V1 analyzes ARCHIVED model responses against fixed source snapshots.
It never claims a gain in live ChatGPT, Gemini, or Google AI rankings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from pathlib import Path
from typing import Any

from .audit import audit_record
from .benchmark import _score_run


def _named(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a nonempty string" % label)
    return value.strip()


def _source_map(sources: Any, context: str) -> dict[str, dict]:
    if not isinstance(sources, list) or not sources:
        raise ValueError("%s: sources must be a nonempty array" % context)
    known = {}
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("text"), str):
            raise ValueError("%s: sources need text" % context)
        identifier = source.get("id")
        if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
            raise ValueError("%s: source ids must be positive integers" % context)
        sid = str(identifier).strip()
        if not sid.isdigit() or int(sid) <= 0:
            raise ValueError("%s: invalid source id %s" % (context, sid))
        sid = str(int(sid))
        if sid in known:
            raise ValueError("%s: duplicate source %s" % (context, sid))
        known[sid] = source
    return known


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 5) if values else None


def _score_answer(answer: str, sources: list[dict], target: str) -> dict:
    audit = audit_record({"answer": answer, "sources": sources})
    citations = [
        cid
        for sentence in audit["sentences"]
        for cid in sentence["citation_ids"]
    ]
    target_mentions = sum(cid == target for cid in citations)
    share = target_mentions / len(citations) if citations else 0.0
    return {
        "citation_mentions": len(citations),
        "target_mentions": target_mentions,
        "target_cited": target_mentions > 0,
        "target_share": round(share, 5),
        "citation_resolvability": audit["metrics"]["citation_resolvability"],
        "exact_quote_match_rate": audit["metrics"]["exact_quote_match_rate"],
        "unknown_source_ids": audit["unknown_source_ids"],
    }


def evaluate_experiment(payload: dict) -> dict:
    """Check controlled experiments and score recorded answers, no API calls."""
    if not isinstance(payload, dict):
        raise ValueError("Experiment must be a JSON object")
    name = _named(payload.get("name"), "Experiment name")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Experiment must have cases")
    case_names: set[str] = set()
    rows = []
    aggregate: dict[str, dict[str, list]] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Cases must be objects")
        case_id = _named(case.get("id"), "Case ID")
        query = _named(case.get("query"), "Case query")
        model = _named(case.get("model"), "Case model identifier")
        if case_id in case_names:
            raise ValueError("Duplicate case %s" % case_id)
        case_names.add(case_id)
        target = str(case.get("target_source_id", "")).strip()
        variants = case.get("variants")
        if not isinstance(variants, list) or len(variants) < 2:
            raise ValueError("%s: supply at least two variants" % case_id)
        first_sources = None
        variant_ids = set()
        for variant in variants:
            if not isinstance(variant, dict):
                raise ValueError("%s: variants must be objects" % case_id)
            variant_id = _named(variant.get("id"), "Variant ID")
            if variant_id in variant_ids:
                raise ValueError("%s: duplicate variant %s" % (case_id, variant_id))
            variant_ids.add(variant_id)
            sources = variant.get("sources")
            source_map = _source_map(sources, case_id + "/" + variant_id)
            if target not in source_map:
                raise ValueError("%s: target source %s missing" % (case_id, target))
            if first_sources is None:
                first_sources = source_map
            else:
                if set(first_sources) != set(source_map):
                    raise ValueError(
                        "%s: variant source IDs must be identical" % case_id
                    )
                for sid in source_map:
                    if sid != target and source_map[sid] != first_sources[sid]:
                        raise ValueError(
                            "%s: non-target source [%s] changed across variants"
                            % (case_id, sid)
                        )
            runs = variant.get("runs")
            if not isinstance(runs, list) or not runs:
                raise ValueError("%s/%s: runs must be nonempty" % (case_id, variant_id))
            run_ids = set()
            for run in runs:
                if not isinstance(run, dict):
                    raise ValueError("Run must be an object")
                run_id = _named(run.get("run_id"), "Run ID")
                answer = run.get("answer")
                if not isinstance(answer, str):
                    raise ValueError("%s/%s: answer must be text" % (case_id, run_id))
                if run_id in run_ids:
                    raise ValueError("%s/%s: repeated run ID" % (case_id, variant_id))
                run_ids.add(run_id)
                measured = _score_answer(answer, sources, target)
                reviewed_rate = None
                if "claims" in run:
                    reviewed = _score_run(
                        {"sources": sources, "query": query},
                        {
                            "model": model, "run_id": run_id,
                            "answer": answer, "claims": run["claims"],
                        },
                        source_map,
                        case_id,
                    )
                    reviewed_rate = reviewed["metrics"]["cited_supported_rate"]
                rows.append({
                    "case_id": case_id, "query": query, "model": model,
                    "variant": variant_id, "run_id": run_id,
                    "target_source_id": target, "metrics": measured,
                    "reviewed_cited_supported_rate": reviewed_rate,
                })
                aggregate.setdefault(variant_id, {}).setdefault(case_id, []).append(
                    {
                        "visibility": measured["target_share"],
                        "supported": reviewed_rate,
                    }
                )
    variants_summary = {}
    for variant_id, case_runs in sorted(aggregate.items()):
        case_shares = {
            cid: _mean([run["visibility"] for run in runs])
            for cid, runs in case_runs.items()
        }
        quality_scores = {
            cid: _mean([
                run["supported"] for run in runs if run["supported"] is not None
            ])
            for cid, runs in case_runs.items()
        }
        quality_scores = {cid: value for cid, value in quality_scores.items() if value is not None}
        variants_summary[variant_id] = {
            "cases": len(case_shares),
            "runs": sum(len(runs) for runs in case_runs.values()),
            "macro_target_citation_share": _mean(list(case_shares.values())),
            "macro_reviewed_cited_supported_rate": _mean(list(quality_scores.values())),
            "case_scores": case_shares,
            "quality_case_scores": quality_scores,
        }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {
        "schema": "citescope-geo-experiment-v1",
        "name": name,
        "sample_type": payload.get("sample_type", "unspecified"),
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "metric_description": (
            "Target citation share = references to the target / all numbered source "
            "references in recorded model answers; averaged within cases, then "
            "across cases. NOT live AI search ranking or model truthfulness. "
            "Support scores, when present, are supplied human reviewer labels."
        ),
        "variants": variants_summary,
        "runs": rows,
    }


def compare_variants(report: dict, control: str, candidate: str,
                     samples: int = 2000, seed: int = 42) -> dict:
    """Paired bootstrap of citation share using *common questions*."""
    if control == candidate:
        raise ValueError("Choose two different variants")
    if not 100 <= samples <= 100000:
        raise ValueError("Bootstrap samples must be between 100 and 100000")
    by_id = report.get("variants", {})
    if control not in by_id or candidate not in by_id:
        raise ValueError("Both variants must occur in this experiment")
    left = by_id[control]["case_scores"]
    right = by_id[candidate]["case_scores"]
    shared = sorted(set(left) & set(right))
    if not shared:
        raise ValueError("Variants have no shared cases")
    delta = [right[cid] - left[cid] for cid in shared]
    rng = random.Random(seed)
    boot = sorted(
        statistics.fmean(rng.choices(delta, k=len(delta)))
        for _ in range(samples)
    )
    return {
        "metric": "macro_target_citation_share",
        "control": control, "candidate": candidate,
        "case_ids": shared, "shared_cases": len(shared),
        "delta_candidate_minus_control": _mean(delta),
        "bootstrap_95_percent_interval": [
            round(boot[int(.025 * (samples - 1))], 5),
            round(boot[int(.975 * (samples - 1))], 5),
        ],
        "bootstrap_samples": samples, "seed": seed,
        "warning": (
            "This is a synthetic/controlled answer-level visibility proxy. "
            "It cannot establish improved performance in real AI search systems. "
            "Small samples do not justify broad population conclusions."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controlled truth-aware GEO experiments")
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--control", type=str)
    parser.add_argument("--candidate", type=str)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    args = parser.parse_args(argv)
    try:
        experiment = json.loads(args.experiment.read_text(encoding="utf-8"))
        result = evaluate_experiment(experiment)
        if bool(args.control) != bool(args.candidate):
            raise ValueError("Use --control and --candidate together")
        if args.control:
            result["comparison"] = compare_variants(
                result, args.control, args.candidate, args.bootstrap_samples, args.seed
            )
        contents = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(contents, encoding="utf-8")
        else:
            print(contents, end="")
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, "CiteScope GEO experiment: %s\n" % error)


if __name__ == "__main__":
    raise SystemExit(main())
