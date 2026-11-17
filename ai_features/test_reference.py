import copy
import json

from django.test import SimpleTestCase

from tools.score_ai_reference import REFERENCE, score


class EvaluationTests(SimpleTestCase):
    def test_reference_inventory_is_synthetic_and_complete(self):
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
        self.assertEqual(len(reference["chat"]), 30)
        self.assertEqual(len(reference["reviews"]), 50)
        self.assertEqual(len({r["id"] for r in reference["chat"]}), 30)
        self.assertIn("Synthetic", reference["notice"])
        self.assertEqual(score(reference, {})["chat"]["status"], "NOT TESTED")

    def test_mock_and_unreviewed_outputs_never_claim_quality_acceptance(self):
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
        outputs = {"provider_mode": "mock", "human_reviewed": True,
                   "chat": [{"id": r["id"], "correct": True, "grounded": True} for r in reference["chat"]],
                   "reviews": copy.deepcopy(reference["reviews"])}
        result = score(reference, outputs)
        self.assertEqual(result["chat"]["status"], "NOT TESTED")
        self.assertEqual(result["reviews"]["status"], "NOT TESTED")
        outputs.update(provider_mode="real", human_reviewed=False)
        self.assertEqual(score(reference, outputs)["chat"]["status"], "NOT TESTED")

    def test_duplicate_or_unknown_results_rejected(self):
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
        for rows in ([{"id": "Q01"}]*2, [{"id": "UNKNOWN"}]):
            with self.assertRaises(ValueError):
                score(reference, {"chat": rows})

    def test_confusion_matrix_precision_recall_f1(self):
        from tools.score_ai_reference import sentiment_metrics
        result = sentiment_metrics(["positive", "positive", "neutral", "negative"],
                                   ["positive", "negative", "neutral", "negative"])
        self.assertEqual(result["confusion_matrix"], [[1, 0, 1], [0, 1, 0], [0, 0, 1]])
        self.assertEqual(result["correct"], 3)
        self.assertEqual(result["incorrect"], 1)
        self.assertEqual(result["accuracy"], .75)
        self.assertEqual(result["per_class"]["positive"]["recall"], .5)
        self.assertAlmostEqual(result["per_class"]["negative"]["f1"], 2/3)
        self.assertAlmostEqual(result["macro"]["f1"], 7/9)

    def test_metrics_require_real_complete_human_reviewed_results(self):
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
        outputs = {"provider_mode": "mock", "human_reviewed": True, "reviews": copy.deepcopy(reference["reviews"])}
        self.assertIsNone(score(reference, outputs)["reviews"]["metrics"])
        outputs.update(provider_mode="real", human_reviewed=False)
        self.assertIsNone(score(reference, outputs)["reviews"]["metrics"])
        outputs["human_reviewed"] = True
        result = score(reference, outputs)["reviews"]
        self.assertEqual(result["metrics"]["correct"], 50)
        self.assertEqual(result["misclassified"], [])
        outputs["reviews"].pop()
        self.assertIsNone(score(reference, outputs)["reviews"]["metrics"])

    def test_hours_questions_are_already_in_thirty_question_suite(self):
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
        self.assertEqual(next(r for r in reference["chat"] if r["id"] == "Q19")["question"], "Giờ mở cửa của spa?")
        self.assertEqual(next(r for r in reference["chat"] if r["id"] == "Q20")["expected"], "spa")
