import json
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from score_ads import apply_deltas, score_creatives  # noqa: E402


class ScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pull = json.loads((ROOT / "data" / "pull_2026-11-11.json").read_text(encoding="utf-8"))
        cls.creatives = score_creatives(cls.pull["ads"], date(2026, 11, 11))

    def test_winner_and_order(self):
        got = [
            (row["representative_id"], row["score"], row["copies"], row["max_days"])
            for row in self.creatives
        ]
        self.assertEqual(
            got,
            [
                ("1112422725088441", 85, 11, 217),
                ("1843111363320189", 70, 7, 163),
                ("2823814924671305", 63, 5, 93),
                ("1109916984937035", 58, 3, 81),
                ("2966208700429750", 52, 2, 18),
                ("1461355659421928", 41, 1, 19),
            ],
        )

    def test_competitor_is_not_ranked(self):
        ids = {library_id for row in self.creatives for library_id in row["library_ids"]}
        self.assertNotIn("1800149651432201", ids)

    def test_a_later_rank_survives_when_earlier_rows_were_filtered(self):
        ads = [
            {
                "library_id": "early",
                "position": 1,
                "started_on": "2026-11-01",
                "page_name": "MySivi",
                "primary_text": "Speak English fluently with the power of AI! Start at ₹1.",
            },
            {
                "library_id": "late",
                "position": 20,
                "started_on": "2026-11-01",
                "page_name": "MySivi",
                "primary_text": "Practice in Bangla for 15 minute every day.",
            },
        ]
        scored = score_creatives(ads, date(2026, 11, 11))
        self.assertTrue(all(row["parts"]["delivery"] >= 0 for row in scored))
        late = next(row for row in scored if row["representative_id"] == "late")
        self.assertEqual(late["parts"]["delivery"], 0)
        early = next(row for row in scored if row["representative_id"] == "early")
        self.assertEqual(early["parts"]["delivery"], 30)

    def test_delta_must_quote_the_ad_and_is_clamped(self):
        ignored = apply_deltas(
            self.creatives,
            [{"creative_id": "1112422725088441", "score_delta": 40, "quote": "made up"}],
        )
        self.assertEqual(ignored[0]["model_delta"], 0)
        self.assertEqual(ignored[0]["final_score"], 85)
        clamped = apply_deltas(
            self.creatives,
            [{"creative_id": "1112422725088441", "score_delta": 40, "quote": "₹1"}],
        )
        self.assertEqual(clamped[0]["model_delta"], 8)
        self.assertEqual(clamped[0]["final_score"], 93)

    def test_javascript_scorer_matches(self):
        completed = subprocess.run(
            ["node", "analysis/check_score.mjs"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)

    def test_workflow_contains_the_live_path_and_the_saved_winner(self):
        workflow = json.loads((ROOT / "workflow" / "mysivi_ad_library.json").read_text(encoding="utf-8"))
        names = {node["name"] for node in workflow["nodes"]}
        self.assertIn("Score the pull", names)
        self.assertIn("Start Apify run", names)
        self.assertIn("1112422725088441", json.dumps(workflow))
        score = next(node for node in workflow["nodes"] if node["name"] == "Score the pull")
        self.assertIn("function scoreCreatives", score["parameters"]["jsCode"])
        start = next(node for node in workflow["nodes"] if node["name"] == "Start Apify run")
        self.assertIn("scrapeAdDetails: false", start["parameters"]["jsonBody"])
        self.assertNotIn("RESIDENTIAL", json.dumps(start))
        ask = next(node for node in workflow["nodes"] if node["name"] == "Ask Gemini")
        self.assertEqual(ask["onError"], "continueRegularOutput")
        self.assertTrue(ask["parameters"]["options"]["response"]["neverError"])
        apply = next(node for node in workflow["nodes"] if node["name"] == "Apply the model delta")
        self.assertIn("parseModelPayload", apply["parameters"]["jsCode"])
        report = next(node for node in workflow["nodes"] if node["name"] == "Build the read")
        self.assertIn("hook_en", report["parameters"]["jsCode"])
        shape = next(node for node in workflow["nodes"] if node["name"] == "Shape Apify rows")
        self.assertIn("rankSpan", shape["parameters"]["jsCode"])


if __name__ == "__main__":
    unittest.main()
