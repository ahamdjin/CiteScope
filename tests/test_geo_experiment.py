"""GEO experiment fixtures are synthetic. No live rank claims."""
import copy
import unittest
from citescope.geo_experiment import evaluate_experiment, compare_variants


def test_payload():
    return {
        "name": "Synthetic source rewrite experiment",
        "sample_type": "synthetic_demo_not_research",
        "cases": [
            {
                "id": "q1",
                "query": "Which tool is appropriate?",
                "model": "example-model-v1",
                "target_source_id": 1,
                "variants": [
                    {"id": "control",
                     "sources": [
                         {"id": 1, "text": "The tool has filters."},
                         {"id": 2, "text": "A distinct source is unchanged."},
                     ],
                     "runs": [{"run_id": "r1", "answer": "The tool has filters [1]. Another source matters [2]."}]},
                    {"id": "revised",
                     "sources": [
                         {"id": 1, "text": "The tool has filters, paths, and logs."},
                         {"id": 2, "text": "A distinct source is unchanged."},
                     ],
                     "runs": [{"run_id": "r1", "answer": "The tool has filters [1]. It also has logs [1]."}]},
                ],
            },
            {
                "id": "q2",
                "query": "What else is important?",
                "model": "example-model-v1",
                "target_source_id": 1,
                "variants": [
                    {"id": "control",
                     "sources": [
                         {"id": 1, "text": "Production requires error handling."},
                         {"id": 2, "text": "Other sources remain unchanged."},
                     ],
                     "runs": [{"run_id": "r1", "answer": "Error handling is critical [2]."}]},
                    {"id": "revised",
                     "sources": [
                         {"id": 1, "text": "Production requires error handling and retry policies."},
                         {"id": 2, "text": "Other sources remain unchanged."},
                     ],
                     "runs": [{"run_id": "r1", "answer": "Error handling is critical [1]."}]},
                ],
            },
        ],
    }


class GeoExperimentTests(unittest.TestCase):
    def test_target_visibility_proxy(self):
        report = evaluate_experiment(test_payload())
        self.assertEqual(report["variants"]["control"]["macro_target_citation_share"], .25)
        self.assertEqual(report["variants"]["revised"]["macro_target_citation_share"], 1.0)

    def test_variant_comparison(self):
        report = evaluate_experiment(test_payload())
        result = compare_variants(report, "control", "revised", samples=500, seed=8)
        self.assertEqual(result["shared_cases"], 2)
        self.assertEqual(result["delta_candidate_minus_control"], .75)

    def test_bootstrap_reproducible(self):
        report = evaluate_experiment(test_payload())
        self.assertEqual(
            compare_variants(report, "control", "revised", samples=200, seed=5),
            compare_variants(report, "control", "revised", samples=200, seed=5),
        )

    def test_non_target_mutation_rejected(self):
        dataset = test_payload()
        dataset["cases"][0]["variants"][1]["sources"][1]["text"] = "Secretly altered"
        with self.assertRaisesRegex(ValueError, "non-target"):
            evaluate_experiment(dataset)

    def test_missing_variant_rejected(self):
        dataset = test_payload()
        dataset["cases"][0]["variants"] = dataset["cases"][0]["variants"][:1]
        with self.assertRaisesRegex(ValueError, "at least two"):
            evaluate_experiment(dataset)

    def test_duplicate_run_rejected(self):
        dataset = test_payload()
        duplicate = copy.deepcopy(dataset["cases"][0]["variants"][0]["runs"][0])
        dataset["cases"][0]["variants"][0]["runs"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "repeated run"):
            evaluate_experiment(dataset)

    def test_missing_target_rejected(self):
        dataset = test_payload()
        dataset["cases"][0]["target_source_id"] = 99
        with self.assertRaisesRegex(ValueError, "missing"):
            evaluate_experiment(dataset)

    def test_claim_support_optional(self):
        report = evaluate_experiment(test_payload())
        self.assertIsNone(report["variants"]["control"]["macro_reviewed_cited_supported_rate"])

    def test_labelled_support_included(self):
        dataset = test_payload()
        case = dataset["cases"][0]
        for variant in case["variants"]:
            variant["runs"][0]["claims"] = [
                {"id": "c1", "text": "The tool has filters", "citations": [1],
                 "verdict": "supported", "reviewer": "synthetic-demo",
                 "evidence": [{"source_id": 1, "quote": "The tool has filters"}]}
            ]
        result = evaluate_experiment(dataset)
        self.assertEqual(result["variants"]["control"]["macro_reviewed_cited_supported_rate"], 1.0)

    def test_synthetic_labeled_not_real_rank(self):
        report = evaluate_experiment(test_payload())
        self.assertIn("NOT live AI search ranking", report["metric_description"])


if __name__ == "__main__":
    unittest.main()
