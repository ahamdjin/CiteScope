"""Convert recorded answers into *unreviewed* CiteScope benchmark cases.

No LLM judges are involved. All extracted claim units must be checked and
edited by a human annotator before trustworthy claim-support metrics exist.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from .audit import audit_record

NUMBERED_REF = re.compile(r"\[(?:\d+\s*,\s*)*\d+\]")


def prepare_benchmark(records: list[dict[str, Any]], name: str = "Unreviewed responses") -> dict:
    if not isinstance(records, list) or not records:
        raise ValueError("Records must be a nonempty JSON array or JSONL file")
    cases: dict[str, dict] = {}
    keys: set[tuple[str, str, str]] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each recorded response must be a JSON object")
        for key in ("case_id", "query", "model", "run_id"):
            if not isinstance(record.get(key), str) or not record[key].strip():
                raise ValueError("Each record requires nonempty %s" % key)
        answer = record.get("answer")
        sources = record.get("sources")
        if not isinstance(answer, str) or not isinstance(sources, list):
            raise ValueError("Each record requires answer:string and sources:list")
        cid = record["case_id"]
        run_key = (cid, record["model"], record["run_id"])
        if run_key in keys:
            raise ValueError("Duplicate response record for %s" % (run_key,))
        keys.add(run_key)
        if cid not in cases:
            cases[cid] = {
                "id": cid, "query": record["query"],
                "sources": sources, "runs": [],
            }
        elif cases[cid]["sources"] != sources or cases[cid]["query"] != record["query"]:
            raise ValueError("%s has conflicting query or source snapshots" % cid)
        structural = audit_record({"answer": answer, "sources": sources})
        claims = []
        for index, sentence in enumerate(structural["sentences"], 1):
            # Sentence segmentation is only an annotation STARTER.
            clean_text = NUMBERED_REF.sub("", sentence["text"]).strip()
            if not clean_text:
                continue
            claims.append({
                "id": "c%d" % index,
                "text": clean_text,
                "citations": list(dict.fromkeys(sentence["citation_ids"])),
                "verdict": "unreviewed",
                "evidence": [],
            })
        cases[cid]["runs"].append({
            "model": record["model"], "run_id": record["run_id"],
            "answer": answer, "claims": claims,
        })
    return {
        "name": name,
        "sample_type": "unreviewed_records",
        "label_provenance": "Not annotated. All claim labels are placeholders.",
        "cases": list(cases.values()),
    }


def _read_records(path: Path) -> list:
    if path.suffix.lower() == ".jsonl":
        records = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError("Invalid JSONL line %d: %s" % (line_number, exc))
        return records
    content = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(content, list):
        raise ValueError("A .json recording must contain an array")
    return content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare blank benchmark for human review")
    parser.add_argument("recordings", type=Path, help="Saved responses JSON array or JSONL")
    parser.add_argument("--name", default="Unreviewed responses")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        benchmark = prepare_benchmark(_read_records(args.recordings), args.name)
        args.output.write_text(
            json.dumps(benchmark, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("Prepared %d unreviewed cases at %s" % (len(benchmark["cases"]), args.output))
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, "CiteScope ingest: %s\n" % exc)


if __name__ == "__main__":
    raise SystemExit(main())
