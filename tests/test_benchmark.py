"""Tests exercise scoring, validation, reproducibility, and pairing."""
import copy
import json
import unittest

from citescope.benchmark import evaluate_benchmark, compare_models


def fixture():
    return {
        "name": "Synthetic Demo",
        "label_provenance": "Synthetic, authored for unit tests",
        "sample_type": "synthetic_demo_not_research",
        "cases": [
            {
                "id": "case-one",
                "query": "When did product X launch?",
                "sources": [{"id": 1, "text": "Product X launched in 2024."}],
                "runs": [
                    {"model": "baseline", "run_id": "a1",
                     "answer": "Product X launched in 2024 [1].",
                     "claims": [{"id": "c1", "text": "X launched in 2024", "citations": [1],
                                 "verdict": "supported", "reviewer": "synthetic",
                                 "evidence": [{"source_id": 1, "quote": "launched in 2024"}]}]},
                    {"model": "candidate", "run_id": "b1",
                     "answer": "X launched in 2023 [1].",
                     "claims": [{"id": "c1", "text": "X launched in 2023", "citations": [1],
                                 "verdict": "contradicted", "reviewer": "synthetic"}]},
                ],
            },
            {
                "id": "case-two",
                "query": "What does product Y support?",
                "sources": [{"id": 2, "text": "Product Y supports JSON exports."}],
                "runs": [
                    {"model": "baseline", "run_id": "a2",
                     "answer": "Product Y supports XML [2].",
                     "claims": [{"id": "c1", "text": "Y supports XML", "citations": [2],
                                 "verdict": "unsupported", "reviewer": "synthetic"}]},
                    {"model": "candidate", "run_id": "b2",
                     "answer": "Product Y supports JSON exports [2].",
                     "claims": [{"id": "c1", "text": "Y supports JSON", "citations": [2],
                                 "verdict": "supported", "reviewer": "synthetic",
                                 "evidence": [{"source_id": 2, "quote": "supports JSON exports"}]}]},
                ],
            },
        ],
    }


class BenchmarkTests(unittest.TestCase):
    def test_evaluates_model_runs(self):
        result = evaluate_benchmark(fixture())
        self.assertEqual(len(result["results"]), 4)
        self.assertEqual(result["models"]["baseline"]["evaluated_cases"], 2)

    def test_macro_rates_are_case_balanced(self):
        result = evaluate_benchmark(fixture())
        self.assertEqual(result["models"]["baseline"]["macro_cited_supported_rate"], .5)
        self.assertEqual(result["models"]["candidate"]["macro_cited_supported_rate"], .5)

    def test_paired_bootstrap_reproducible(self):
        result = evaluate_benchmark(fixture())
        left = compare_models(result, "baseline", "candidate", samples=500, seed=10)
        right = compare_models(result, "baseline", "candidate", samples=500, seed=10)
        self.assertEqual(left, right)
        self.assertEqual(left["delta_candidate_minus_baseline"], 0)

    def test_dataset_fingerprint_is_stable(self):
        self.assertEqual(evaluate_benchmark(fixture())["sha256"],
                         evaluate_benchmark(copy.deepcopy(fixture()))["sha256"])

    def test_invalid_excerpt_rejected(self):
        dataset = fixture()
        dataset["cases"][0]["runs"][0]["claims"][0]["evidence"][0]["quote"] = "invented evidence"
        with self.assertRaisesRegex(ValueError, "not found"):
            evaluate_benchmark(dataset)

    def test_supported_requires_excerpt(self):
        dataset = fixture()
        dataset["cases"][0]["runs"][0]["claims"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "need at least one"):
            evaluate_benchmark(dataset)

    def test_unsupported_needs_reviewer(self):
        dataset = fixture()
        del dataset["cases"][1]["runs"][0]["claims"][0]["reviewer"]
        with self.assertRaisesRegex(ValueError, "reviewer"):
            evaluate_benchmark(dataset)

    def test_invalid_citation_reference_in_answer_rejected(self):
        dataset = fixture()
        dataset["cases"][1]["runs"][0]["claims"][0]["citations"] = [99]
        with self.assertRaisesRegex(ValueError, "not found in the answer"):
            evaluate_benchmark(dataset)

    def test_unknown_citation_is_measured(self):
        dataset = fixture()
        dataset["cases"][1]["runs"][0]["answer"] = "Product Y supports XML [99]."
        dataset["cases"][1]["runs"][0]["claims"][0]["citations"] = [99]
        result = evaluate_benchmark(dataset)
        bad = [row for row in result["results"] if row["run_id"] == "a2"][0]
        self.assertEqual(bad["metrics"]["unresolvable_claim_references"], 1)

    def test_duplicate_case_rejected(self):
        dataset = fixture()
        dataset["cases"].append(copy.deepcopy(dataset["cases"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate benchmark case"):
            evaluate_benchmark(dataset)

    def test_duplicate_runs_rejected(self):
        dataset = fixture()
        dataset["cases"][0]["runs"].append(copy.deepcopy(dataset["cases"][0]["runs"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate run ID"):
            evaluate_benchmark(dataset)

    def test_unreviewed_excluded_from_denominator(self):
        dataset = fixture()
        claim = dataset["cases"][0]["runs"][0]["claims"][0]
        claim.update({"verdict": "unreviewed", "evidence": []})
        del claim["reviewer"]
        result = evaluate_benchmark(dataset)
        row = [x for x in result["results"] if x["run_id"] == "a1"][0]
        self.assertIsNone(row["metrics"]["cited_supported_rate"])

    def test_missing_shared_cases_rejected(self):
        result = evaluate_benchmark(fixture())
        result["models"]["candidate"]["case_scores"] = {"separate": 0.3}
        with self.assertRaisesRegex(ValueError, "No shared"):
            compare_models(result, "baseline", "candidate")

    def test_no_hallucinated_performance_claim(self):
        result = evaluate_benchmark(fixture())
        self.assertEqual(result["sample_type"], "synthetic_demo_not_research")


if __name__ == "__main__":
    unittest.main()
