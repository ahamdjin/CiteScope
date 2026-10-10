"""Test the entire offline intake → evaluate → HTML pipeline."""
import unittest
from citescope.ingest import prepare_benchmark
from citescope.benchmark import evaluate_benchmark
from citescope.report import render_html


def recording():
    return {
        "case_id": "a1",
        "query": "What happened?",
        "sources": [{"id": 1, "text": "A trial began in 2024."}],
        "model": "demo-model",
        "run_id": "r1",
        "answer": "A trial began in 2024 [1]. No further data exists [1].",
    }


class IngestAndReportTests(unittest.TestCase):
    def test_unreviewed_claims_produced(self):
        benchmark = prepare_benchmark([recording()])
        claims = benchmark["cases"][0]["runs"][0]["claims"]
        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[0]["citations"], ["1"])
        self.assertEqual(claims[0]["verdict"], "unreviewed")

    def test_no_fake_scores_for_unreviewed_data(self):
        benchmark = prepare_benchmark([recording()])
        evaluated = evaluate_benchmark(benchmark)
        self.assertIsNone(evaluated["models"]["demo-model"]["macro_cited_supported_rate"])

    def test_duplicate_runs_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            prepare_benchmark([recording(), recording()])

    def test_conflicting_snapshots_rejected(self):
        second = recording().copy()
        second["run_id"] = "r2"
        second["sources"] = [{"id": 1, "text": "Different snapshot"}]
        with self.assertRaisesRegex(ValueError, "conflicting"):
            prepare_benchmark([recording(), second])

    def test_report_uses_html_escaping(self):
        entry = recording()
        entry["query"] = '<script>alert("x")</script>'
        entry["answer"] = '<script>alert("x")</script> [1].'
        report = evaluate_benchmark(prepare_benchmark([entry], name="<unsafe>"))
        html = render_html(report)
        self.assertNotIn('<script>', html)
        self.assertIn("&lt;unsafe&gt;", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Demonstration data only.", html)

    def test_report_has_details_and_source_sha(self):
        report = evaluate_benchmark(prepare_benchmark([recording()]))
        html = render_html(report)
        self.assertIn('<details class="run">', html)
        self.assertIn(report["sha256"], html)
        self.assertIn('Not reviewed', html)
        self.assertIn('name="robots" content="noindex,nofollow"', html)

    def test_comparison_section_renders(self):
        from citescope.benchmark import compare_models
        from tests.test_benchmark import fixture
        report = evaluate_benchmark(fixture())
        report["comparison"] = compare_models(report, "baseline", "candidate", samples=200)
        html = render_html(report)
        self.assertIn("PAIRED COMPARISON", html)
        self.assertIn("95% bootstrap interval", html)

    def test_invalid_report_rejected(self):
        with self.assertRaisesRegex(ValueError, "CiteScope"):
            render_html({"models": {}})


if __name__ == "__main__":
    unittest.main()
