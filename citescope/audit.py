"""CiteScope V1: reproducible citation provenance, not semantic truth verification."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

CITE = re.compile(r"\[((?:\d+\s*,\s*)*\d+)\]")
QUOTE = re.compile(r'["“]([^"”]+)["”]')
SPLIT = re.compile(r'(?<=[.!?])\s+(?=[\w"“(])|\n+')


def _units(answer: str) -> list[str]:
    return [part.strip() for part in SPLIT.split(answer) if part.strip()]


def _refs(text: str) -> list[str]:
    ids = []
    for group in CITE.findall(text):
        ids.extend(str(int(num.strip())) for num in group.split(","))
    return ids


def _squash(text: str) -> str:
    return " ".join(text.split())


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def audit_record(record: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a saved answer with numbered citations against source snapshots.

    A source has {"id": 1, "text": "...", "url": "optional"}.
    This function NEVER decides that a paraphrased claim is factually true.
    """
    if not isinstance(record, dict):
        raise ValueError("Expected a JSON object")
    answer = record.get("answer")
    sources = record.get("sources")
    if not isinstance(answer, str):
        raise ValueError("'answer' must be a string")
    if not isinstance(sources, list):
        raise ValueError("'sources' must be a list")

    known: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError("Source %d must be an object" % index)
        number = source.get("id")
        if isinstance(number, bool) or not isinstance(number, (str, int)):
            raise ValueError("Source %d must have a positive numeric ID" % index)
        identifier = str(number).strip()
        if not identifier.isdigit() or int(identifier) < 1:
            raise ValueError("Source %d must have a positive numeric ID" % index)
        identifier = str(int(identifier))
        if identifier in known:
            raise ValueError("Duplicate source ID %s" % identifier)
        if not isinstance(source.get("text"), str):
            raise ValueError("Source %s must have text" % identifier)
        if "url" in source and not isinstance(source["url"], str):
            raise ValueError("Source %s has a non-string URL" % identifier)
        known[identifier] = source

    sentences = []
    quotations = []
    refs = []
    covered = 0
    for sentence in _units(answer):
        citations = _refs(sentence)
        refs.extend(citations)
        valid = [cid for cid in citations if cid in known]
        unknown = [cid for cid in citations if cid not in known]
        covered += bool(citations)
        sentences.append({
            "text": sentence, "citation_ids": citations,
            "resolvable_ids": valid, "unknown_ids": unknown,
        })
        for quote in QUOTE.findall(sentence):
            if len(_squash(quote)) < 8:
                continue
            matching = [
                cid for cid in dict.fromkeys(valid)
                if _squash(quote) in _squash(known[cid]["text"])
            ]
            status = (
                "uncited" if not citations else
                "unresolvable_citation" if not valid else
                "matched_exact_text" if matching else
                "not_found_in_cited_sources"
            )
            quotations.append({
                "quote": quote,
                "citation_ids": list(dict.fromkeys(citations)),
                "matched_source_ids": matching,
                "status": status,
            })
    resolved = sum(ref in known for ref in refs)
    matched_quotes = sum(q["status"] == "matched_exact_text" for q in quotations)
    return {
        "query": record.get("query"),
        "method": "deterministic_provenance_v1",
        "metrics": {
            "sentence_units": len(sentences),
            "units_with_citations": covered,
            "citation_coverage": _ratio(covered, len(sentences)),
            "citation_mentions": len(refs),
            "resolvable_citation_mentions": resolved,
            "citation_resolvability": _ratio(resolved, len(refs)),
            "quoted_passages_checked": len(quotations),
            "exact_quote_matches": matched_quotes,
            "exact_quote_match_rate": _ratio(matched_quotes, len(quotations)),
        },
        "unknown_source_ids": list(dict.fromkeys(ref for ref in refs if ref not in known)),
        "cited_source_ids": list(dict.fromkeys(refs)),
        "sentences": sentences,
        "quotes": quotations,
        "limitations": [
            "Citations to existing sources are not proof that claims are supported.",
            "Matching exact quotations does not prove correct quotation context.",
            "Paraphrase entailment, factuality, recency and URLs are not checked.",
            "Source snapshots are supplied by the caller: no live search is used.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit AI citations against snapshots")
    parser.add_argument("input", type=Path, help="JSON object or array of objects")
    parser.add_argument("--output", type=Path, help="Path for JSON output")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        results = [audit_record(p) for p in payload] if isinstance(payload, list) else audit_record(payload)
        output = json.dumps(results, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
    except (OSError, ValueError) as error:
        print("CiteScope: %s" % error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
