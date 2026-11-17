"""Score reviewed AI evaluation results offline. Never connects to a DB/provider."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs/ai-reference/cases-20261115.json"


def sentiment_metrics(expected, predictions):
    """Offline only. Rows are reference labels, columns are predicted labels."""
    labels = ("positive", "neutral", "negative")
    if not expected or len(expected) != len(predictions) or any(x not in labels for x in [*expected, *predictions]):
        raise ValueError("Invalid sentiment evaluation labels")
    matrix = [[0 for _ in labels] for _ in labels]
    for actual, predicted in zip(expected, predictions):
        matrix[labels.index(actual)][labels.index(predicted)] += 1
    per_class = {}
    for i, label in enumerate(labels):
        tp = matrix[i][i]
        support = sum(matrix[i])
        predicted_count = sum(row[i] for row in matrix)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        per_class[label] = {"support": support, "precision": precision, "recall": recall,
                            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    correct = sum(matrix[i][i] for i in range(len(labels)))
    return {"correct": correct, "incorrect": len(expected) - correct, "accuracy": correct / len(expected),
            "labels": list(labels), "confusion_matrix": matrix, "per_class": per_class,
            "macro": {key: sum(v[key] for v in per_class.values()) / len(labels)
                      for key in ("precision", "recall", "f1")},
            "weighted_f1": sum(v["f1"] * v["support"] for v in per_class.values()) / len(expected)}


def score(reference, outputs):
    def unique(rows):
        if not isinstance(rows, list) or any(not isinstance(r, dict) or not isinstance(r.get("id"), str) for r in rows):
            raise ValueError("Invalid evaluation rows")
        ids = [r["id"] for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate evaluation IDs")
        return {r["id"]: r for r in rows}
    chat = unique(outputs.get("chat", []))
    reviews = unique(outputs.get("reviews", []))
    expected_chat = {r["id"] for r in reference["chat"]}
    expected_reviews = {r["id"]: r for r in reference["reviews"]}
    if set(chat) - expected_chat or set(reviews) - expected_reviews.keys():
        raise ValueError("Unknown evaluation IDs")
    real = outputs.get("provider_mode") == "real"
    reviewed = outputs.get("human_reviewed") is True
    complete_chat = set(chat) == expected_chat and all(type(r.get("correct")) is bool and type(r.get("grounded")) is bool for r in chat.values())
    complete_reviews = set(reviews) == set(expected_reviews) and all(r.get("sentiment") in {"positive", "neutral", "negative"} for r in reviews.values())
    chat_accuracy = sum(r.get("correct") is True and r.get("grounded") is True for r in chat.values()) / len(expected_chat)
    review_accuracy = sum(r.get("sentiment") == expected_reviews[k]["sentiment"] for k, r in reviews.items()) / len(expected_reviews)
    return {
        "provider_mode": outputs.get("provider_mode", "not_run"), "human_reviewed": reviewed,
        "chat": {"received": len(chat), "required": 30, "target": .8,
                 "accuracy": chat_accuracy if complete_chat else None,
                 "status": ("PASS" if chat_accuracy >= .8 else "FAIL") if real and reviewed and complete_chat else "NOT TESTED"},
        "reviews": {"received": len(reviews), "required": 50, "target": .75,
                    "accuracy": review_accuracy if complete_reviews else None,
                    "metrics": sentiment_metrics([r["sentiment"] for r in reference["reviews"]],
                                                 [reviews[r["id"]]["sentiment"] for r in reference["reviews"]])
                               if real and reviewed and complete_reviews else None,
                    "misclassified": [{"id": r["id"], "expected": r["sentiment"],
                                       "predicted": reviews[r["id"]]["sentiment"], "cause": "requires_human_review"}
                                      for r in reference["reviews"] if reviews[r["id"]]["sentiment"] != r["sentiment"]]
                                     if real and reviewed and complete_reviews else None,
                    "status": ("PASS" if review_accuracy >= .75 else "FAIL") if real and reviewed and complete_reviews else "NOT TESTED"},
        "note": "Mock outputs cannot establish real AI quality. Themes, summaries, priorities, actions and hallucinations require human review.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, help="Previously collected, human-reviewed output JSON")
    args = parser.parse_args()
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    outputs = json.loads(args.results.read_text(encoding="utf-8")) if args.results else {}
    print(json.dumps(score(reference, outputs), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
