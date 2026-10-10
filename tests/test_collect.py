"""No external HTTP is performed in these tests."""
import copy
import json
import unittest

from citescope.collect import collect, request_answer, _extract_response
from citescope.geo_experiment import evaluate_experiment


def plan():
    return {
        "name": "Synthetic call plan",
        "cases": [{
            "id": "q1", "query": "What is a workflow?", "target_source_id": 1,
            "variants": [
                {"id": "baseline", "sources": [
                    {"id": 1, "text": "Workflows are sequences of steps."},
                    {"id": 2, "text": "An unchanged source."},
                ]},
                {"id": "rewrite", "sources": [
                    {"id": 1, "text": "Workflows connect triggers to actions."},
                    {"id": 2, "text": "An unchanged source."},
                ]},
            ],
        }],
    }


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class CollectionTests(unittest.TestCase):
    def test_dry_run_never_sends_request(self):
        def fail(*args, **kwargs):
            raise AssertionError("Network request made in dry-run")
        output = collect(plan(), model="test-model", api_key="",
                         execute=False, transport=fail)
        self.assertTrue(output["dry_run"])
        self.assertEqual(output["planned_calls"], 2)

    def test_request_limit_blocks_execution(self):
        with self.assertRaisesRegex(ValueError, "above"):
            collect(plan(), model="test", api_key="key", repeats=5, max_calls=2,
                    execute=True)

    def test_requires_key_before_execution(self):
        with self.assertRaisesRegex(ValueError, "API key"):
            collect(plan(), model="test", api_key="", execute=True)

    def test_local_insecure_http_only(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            collect(plan(), model="test", api_key="", base_url="http://example.org/v1")

    def test_responses_format_recorded(self):
        requests = []
        def stub(request, timeout):
            requests.append(request)
            return DummyResponse({
                "id": "resp-demo", "model": "test", "output": [{
                    "content": [{"type": "output_text", "text": "Steps are connected [1]."}]
                }],
            })
        collected = collect(plan(), model="test", api_key="fake",
                            execute=True, transport=stub)
        self.assertEqual(len(requests), 2)
        self.assertIn("/responses", requests[0].full_url)
        self.assertEqual(collected["cases"][0]["variants"][0]["runs"][0]["answer"],
                         "Steps are connected [1].")
        self.assertEqual(evaluate_experiment(collected)["variants"]["baseline"]["cases"], 1)

    def test_chat_completions_supported(self):
        def stub(request, timeout):
            self.assertIn("/chat/completions", request.full_url)
            return DummyResponse({
                "choices": [{"message": {"content": "A step begins [1]."}}],
                "usage": {"total_tokens": 12},
            })
        result = collect(plan(), model="test", api_key="fake", execute=True,
                         protocol="chat", transport=stub)
        self.assertEqual(result["cases"][0]["variants"][0]["runs"][0]["provenance"]["usage"]["total_tokens"], 12)

    def test_reject_invalid_output(self):
        with self.assertRaisesRegex(ValueError, "missing expected text"):
            _extract_response({"choices": []}, "chat")

    def test_no_uncontrolled_source_change(self):
        request_plan = plan()
        request_plan["cases"][0]["variants"][1]["sources"][1]["text"] = "changed!"
        with self.assertRaisesRegex(ValueError, "non-target"):
            collect(request_plan, model="test", api_key="", execute=False)

    def test_key_not_in_returned_data(self):
        def stub(request, timeout):
            return DummyResponse({"output_text": "Data [1].", "id": "xyz"})
        result = collect(plan(), model="test", api_key="do-not-record-this",
                         execute=True, transport=stub)
        self.assertNotIn("do-not-record-this", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
