"""No external model weights downloaded during these tests."""
import copy
import unittest
from citescope.nli import (
    passages, plan_candidates, suggest_relations, lexical_terms
)


def fixture():
    return {
        "name": "Synthetic NLI reference pairs",
        "sample_type": "synthetic_demo_not_research",
        "cases": [{
            "id": "case-1",
            "query": "How do Zaps work?",
            "sources": [
                {"id": 1, "text": "Zapier supports multiple actions in one workflow. Filters and paths are also supported."},
                {"id": 2, "text": "The moon orbits the Earth."},
            ],
            "runs": [{
                "model": "fake-model", "run_id": "r1",
                "answer": "Zapier only supports one action [1].",
                "claims": [{
                    "id": "c1", "text": "Zapier only supports one action.",
                    "citations": [1], "verdict": "unreviewed", "evidence": [],
                }],
            }],
        }],
    }


class NLISuggestionTests(unittest.TestCase):
    def test_terms_and_passage_ranking(self):
        self.assertIn("zapier", lexical_terms("Does Zapier support actions?"))
        chunks = passages(
            "Cats sleep. Zapier supports multi-step automation. The sky is blue.",
            "Zapier automation", limit=2,
        )
        self.assertIn("Zapier", chunks[0])

    def test_default_dry_run_has_zero_network(self):
        def fail(_):
            raise AssertionError("Should never run a scorer in dry-run")
        report = suggest_relations(fixture(), execute=False, scorer=fail)
        self.assertFalse(report["executed"])
        self.assertEqual(report["claims"], 1)
        self.assertGreater(report["pairs_considered"], 0)
        self.assertIsNone(report["suggestions"][0]["top_candidate"])

    def test_injected_scorer_proposes_but_does_not_label_truth(self):
        inp = fixture()
        def scorer(pairs):
            self.assertGreater(len(pairs), 0)
            return [
                {"contradiction": 0.85, "entailment": 0.1, "neutral": 0.05}
                for _ in pairs
            ]
        result = suggest_relations(inp, execute=True, scorer=scorer)
        self.assertEqual(result["suggestions"][0]["model_preference"], "contradiction")
        self.assertEqual(result["suggestions"][0]["human_label_unchanged"], "unreviewed")
        self.assertEqual(inp["cases"][0]["runs"][0]["claims"][0]["verdict"], "unreviewed")
        self.assertIn("NOT human", result["limitations"][0])

    def test_missing_citation_prevents_model_suggestion(self):
        inp = fixture()
        inp["cases"][0]["runs"][0]["claims"][0]["citations"] = []
        result = suggest_relations(inp, execute=True, scorer=lambda pairs: [])
        self.assertEqual(result["suggestions"][0]["status"], "no_citations")

    def test_missing_source_is_not_silently_supported(self):
        inp = fixture()
        inp["cases"][0]["runs"][0]["claims"][0]["citations"] = [99]
        result = suggest_relations(inp)
        self.assertEqual(result["suggestions"][0]["status"], "no_resolvable_source_passages")

    def test_duplicate_source_rejected(self):
        inp = fixture()
        inp["cases"][0]["sources"].append(copy.deepcopy(inp["cases"][0]["sources"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate source"):
            suggest_relations(inp)

    def test_max_claims_enforced(self):
        inp = fixture()
        inp["cases"][0]["runs"][0]["claims"].append({
            "id": "c2", "text": "A second claim", "citations": [1]
        })
        with self.assertRaisesRegex(ValueError, "Too many claims"):
            suggest_relations(inp, max_claims=1)

    def test_max_pairs_enforced(self):
        with self.assertRaisesRegex(ValueError, "Too many source/claim pairs"):
            suggest_relations(fixture(), max_pairs=1)

    def test_invalid_scores_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid NLI"):
            suggest_relations(fixture(), execute=True, scorer=lambda p: [{"entailment":1} for _ in p])

    def test_mismatched_scorer_results_rejected(self):
        with self.assertRaisesRegex(ValueError, "different number"):
            suggest_relations(fixture(), execute=True, scorer=lambda p: [])


if __name__ == "__main__":
    unittest.main()
