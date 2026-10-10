"""Unit and CLI checks; never require network or API credentials."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from citescope.audit import audit_record


def sample(answer):
    return {
        "query": "What does the documentation say?",
        "answer": answer,
        "sources": [
            {"id": 1, "url": "https://example.org/1", "text": "The API launched in 2024. Use verified sources for research."},
            {"id": 2, "text": "Another independent source."},
        ],
    }


class AuditTest(unittest.TestCase):
    def test_known_reference(self):
        self.assertEqual(audit_record(sample("Launched in 2024 [1]."))["metrics"]["citation_resolvability"], 1)

    def test_unknown_reference(self):
        result = audit_record(sample("Launched in 2024 [5]."))
        self.assertEqual(result["unknown_source_ids"], ["5"])
        self.assertEqual(result["metrics"]["citation_resolvability"], 0)

    def test_multiple_references(self):
        result = audit_record(sample("Launched in 2024 [1, 2]."))
        self.assertEqual(result["cited_source_ids"], ["1", "2"])

    def test_two_sentences_one_cited(self):
        result = audit_record(sample("Something happened. Another claim [1]."))
        self.assertEqual(result["metrics"]["citation_coverage"], 0.5)

    def test_empty_answer(self):
        result = audit_record(sample(""))
        self.assertIsNone(result["metrics"]["citation_coverage"])

    def test_no_citations(self):
        self.assertIsNone(audit_record(sample("No refs."))["metrics"]["citation_resolvability"])

    def test_exact_quote(self):
        result = audit_record(sample('The text says “Use verified sources” [1].'))
        self.assertEqual(result["quotes"][0]["status"], "matched_exact_text")

    def test_quote_wrong_source(self):
        result = audit_record(sample('The text says “Use verified sources” [2].'))
        self.assertEqual(result["quotes"][0]["status"], "not_found_in_cited_sources")

    def test_quote_uncited(self):
        result = audit_record(sample('The text says “Use verified sources”.'))
        self.assertEqual(result["quotes"][0]["status"], "uncited")

    def test_quote_unresolvable(self):
        result = audit_record(sample('The text says “Use verified sources” [3].'))
        self.assertEqual(result["quotes"][0]["status"], "unresolvable_citation")

    def test_repeated_citations(self):
        result = audit_record(sample("One claim [1]. Another claim [1]."))
        self.assertEqual(result["metrics"]["citation_mentions"], 2)

    def test_duplicate_source_ids_invalid(self):
        item = sample("Answer [1].")
        item["sources"].append({"id": "1", "text": "A duplicate"})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit_record(item)

    def test_invalid_answer(self):
        with self.assertRaisesRegex(ValueError, "answer"):
            audit_record({"answer": None, "sources": []})

    def test_whitespace_normalization(self):
        item = sample('The text says "Use verified sources" [1].')
        item["sources"][0]["text"] = "Use   verified\nsources"
        self.assertEqual(audit_record(item)["metrics"]["exact_quote_matches"], 1)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "test.json"
            dst = Path(tmp) / "out.json"
            src.write_text(json.dumps(sample("Launched in 2024 [1].")), encoding="utf-8")
            run = subprocess.run([sys.executable, "-m", "citescope", str(src), "--output", str(dst)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(dst.read_text())["metrics"]["citation_resolvability"], 1)


if __name__ == "__main__":
    unittest.main()
