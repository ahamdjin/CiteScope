"""Optional local NLI suggestion layer over human-review CiteScope datasets.

This module never assigns human-reviewed verdicts, edits claims or rewrites
sources. Loading Hugging Face model weights requires --execute and optional
dependencies; dry-run planning uses only the standard library.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-small"
LABELS = ("contradiction", "entailment", "neutral")
STOPWORDS = frozenset("""
a an and are as at be been being by can do does for from has have how in into is it
of on or should that the their them there these they this to was were what when
where which who why will with would you your
""".split())
TOKEN = re.compile(r"[\w-]+", flags=re.UNICODE)
BREAKS = re.compile(r"(?<=[.!?])\s+|\n+")


def lexical_terms(value: str) -> set[str]:
    return {term.lower() for term in TOKEN.findall(value) if len(term) > 2 and term.lower() not in STOPWORDS}


def passages(text: str, claim: str, *, limit: int = 4) -> list[str]:
    """Get likely source passages without LLM calls or external search.

    Lexical ranking is a *recall-limited heuristic*, not proof of relevance.
    Long passages are truncated; a semantic match can be missed.
    """
    if not 1 <= limit <= 20:
        raise ValueError("passage limit must be between 1 and 20")
    chunks = []
    seen = set()
    for segment in BREAKS.split(text):
        segment = " ".join(segment.split())
        if not segment:
            continue
        # Cap to avoid huge remote weight model inputs; truncation is disclosed.
        if len(segment) > 1200:
            segment = segment[:1200]
        if segment not in seen:
            seen.add(segment)
            chunks.append(segment)
    claim_terms = lexical_terms(claim)
    ranked = sorted(
        enumerate(chunks),
        key=lambda pair: (
            -len(claim_terms.intersection(lexical_terms(pair[1]))),
            pair[0],
        ),
    )
    return [chunk for _, chunk in ranked[:limit]]


def _source_id(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("Source ID cannot be boolean")
    if not isinstance(value, (str, int)):
        raise ValueError("Source ID must be numeric")
    result = str(value).strip()
    if not result.isdigit() or int(result) < 1:
        raise ValueError("Source ID must be a positive integer")
    return str(int(result))


def plan_candidates(data: dict, *, max_passages_per_source: int = 4,
                    max_claims: int = 100, max_pairs: int = 800) -> list[dict]:
    """Plan source–claim pairs from an existing CiteScope benchmark export."""
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list) or not data["cases"]:
        raise ValueError("Input must be a CiteScope benchmark object with cases")
    if not 1 <= max_claims <= 10000:
        raise ValueError("max_claims must be 1-10000")
    if not 1 <= max_pairs <= 10000:
        raise ValueError("max_pairs must be 1-10000")
    rows = []
    pair_count = 0
    for case in data["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("sources"), list):
            raise ValueError("Every case must include sources")
        sid_map = {}
        for source in case["sources"]:
            if not isinstance(source, dict) or not isinstance(source.get("text"), str):
                raise ValueError("Each source must contain snapshot text")
            source_id = _source_id(source.get("id"))
            if source_id in sid_map:
                raise ValueError("Duplicate source ID")
            sid_map[source_id] = source
        for run in case.get("runs", []):
            if not isinstance(run, dict) or not isinstance(run.get("claims"), list):
                raise ValueError("Every run must contain claims")
            for claim in run["claims"]:
                if len(rows) >= max_claims:
                    raise ValueError(
                        "Too many claims. Adjust --max-claims to explicitly allow this dataset."
                    )
                if not isinstance(claim, dict) or not isinstance(claim.get("text"), str) or not claim["text"].strip():
                    raise ValueError("Claims must have text")
                cited = [_source_id(i) for i in claim.get("citations", [])]
                candidates = []
                for sid in dict.fromkeys(cited):
                    if sid not in sid_map:
                        continue
                    source = sid_map[sid]
                    for passage in passages(source["text"], claim["text"], limit=max_passages_per_source):
                        candidates.append({
                            "source_id": sid, "text": passage,
                            "source_url": source.get("url"),
                        })
                pair_count += len(candidates)
                if pair_count > max_pairs:
                    raise ValueError("Too many source/claim pairs; increase --max-pairs deliberately")
                reason = "ready" if candidates else (
                    "no_citations" if not cited else "no_resolvable_source_passages"
                )
                rows.append({
                    "case_id": case.get("id"),
                    "model_output_name": run.get("model"),
                    "run_id": run.get("run_id"),
                    "claim_id": claim.get("id"),
                    "claim_text": claim["text"],
                    "cited_source_ids": cited,
                    "human_label_unchanged": claim.get("verdict", "unreviewed"),
                    "status": reason,
                    "candidates": candidates,
                })
    return rows


def score_local_pairs(pairs: list[tuple[str, str]], *, model_id: str,
                      revision: str = "main", batch_size: int = 8) -> list[dict[str, float]]:
    """Run the cited-premise / claim-hypothesis pairs through local NLI weights.

    The model is downloaded from Hugging Face on first use; only --execute
    calls this method. Labels are obtained from the loaded model's config.
    """
    if not pairs:
        return []
    if not 1 <= batch_size <= 32:
        raise ValueError("batch_size must be between 1 and 32")
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as err:
        raise RuntimeError(
            "Install optional dependencies with: pip install '.[nli]'"
        ) from err

    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_id, revision=revision, trust_remote_code=False
    )
    label_map = {int(i): str(label).lower() for i, label in model.config.id2label.items()}
    if set(label_map.values()) != set(LABELS):
        raise RuntimeError("The chosen NLI model lacks contradiction, entailment and neutral labels")
    model.eval()
    out = []
    with torch.no_grad():
        for index in range(0, len(pairs), batch_size):
            batch = pairs[index:index + batch_size]
            features = tokenizer(
                [pair[0] for pair in batch],
                [pair[1] for pair in batch],
                padding=True, truncation=True, max_length=512,
                return_tensors="pt",
            )
            logits = model(**features).logits
            probabilities = torch.nn.functional.softmax(logits, dim=-1).tolist()
            for vector in probabilities:
                out.append({
                    label_map[j]: round(float(p), 6) for j, p in enumerate(vector)
                })
    return out


def suggest_relations(data: dict, *, model_id: str = DEFAULT_MODEL,
                      revision: str = "main", scorer: Callable | None = None,
                      execute: bool = False, max_passages_per_source: int = 4,
                      max_claims: int = 100, max_pairs: int = 800) -> dict:
    """Produce annotated suggestions, without altering reviewer labels.

    The scorer dependency can be injected in tests, avoiding network/model
    downloads. Returned probabilities are *not calibrated accuracy estimates*.
    """
    rows = plan_candidates(
        data, max_passages_per_source=max_passages_per_source,
        max_claims=max_claims, max_pairs=max_pairs,
    )
    flat_pairs = [
        (entry["text"], row["claim_text"])
        for row in rows for entry in row["candidates"]
    ]
    if execute:
        if scorer is None:
            scorer = lambda pairs: score_local_pairs(
                pairs, model_id=model_id, revision=revision
            )
        scores = scorer(flat_pairs) if flat_pairs else []
        if len(scores) != len(flat_pairs):
            raise ValueError("NLI scorer returned a different number of results")
        offset = 0
        for row in rows:
            enriched = []
            for candidate in row.pop("candidates"):
                prediction = scores[offset]
                offset += 1
                if not isinstance(prediction, dict) or any(
                    label not in prediction or not 0 <= prediction[label] <= 1
                    for label in LABELS
                ):
                    raise ValueError("Scorer returned invalid NLI probabilities")
                confidence = max(prediction["entailment"], prediction["contradiction"])
                enriched.append({
                    **candidate, "nli_scores": prediction,
                    "signal_strength": round(confidence, 6),
                })
            best = max(enriched, key=lambda item: item["signal_strength"]) if enriched else None
            row["candidate_count"] = len(enriched)
            row["top_candidate"] = best
            row["status"] = "suggested" if best else row["status"]
            if best:
                row["model_preference"] = max(best["nli_scores"], key=best["nli_scores"].get)
        # The reader may inspect the top candidate but not claim that an
        # unsupported label is "verified" from the NLI prediction.
    else:
        for row in rows:
            row["candidate_count"] = len(row.pop("candidates"))
            row["top_candidate"] = None

    return {
        "schema": "citescope-local-nli-suggestions-v1",
        "experiment_name": data.get("name"),
        "input_sample_type": data.get("sample_type", "unspecified"),
        "model_id": model_id,
        "model_revision_requested": revision,
        "executed": bool(execute),
        "claims": len(rows),
        "pairs_considered": len(flat_pairs),
        "suggestions": rows,
        "limitations": [
            "These are NLI suggestions, NOT human support verdicts or verified facts.",
            "Only cited source snippets are considered; lexical retrieval can omit needed context.",
            "Passages may be truncated at 1200 characters and model inputs at 512 tokens.",
            "Three-way NLI probabilities are not calibrated confidence in truth.",
            "Review actual source context manually before assigning supported/contradicted labels.",
            "No live AI search ranking, retrieval visibility or source freshness is measured.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan or locally run Hugging Face NLI suggestions on CiteScope benchmarks"
    )
    parser.add_argument("dataset", type=Path, help="CiteScope benchmark JSON")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default="main", help="Pin a model commit SHA for reproducibility")
    parser.add_argument("--max-claims", type=int, default=100)
    parser.add_argument("--max-pairs", type=int, default=800)
    parser.add_argument("--passages-per-source", type=int, default=4)
    parser.add_argument("--execute", action="store_true",
                        help="Download and run local Hugging Face model weights")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.dataset.read_text(encoding="utf-8"))
        result = suggest_relations(
            data, model_id=args.model, revision=args.revision,
            execute=args.execute, max_claims=args.max_claims,
            max_pairs=args.max_pairs,
            max_passages_per_source=args.passages_per_source,
        )
        text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0
    except (OSError, ValueError, RuntimeError) as err:
        parser.exit(2, "CiteScope NLI: %s\n" % err)


if __name__ == "__main__":
    raise SystemExit(main())
