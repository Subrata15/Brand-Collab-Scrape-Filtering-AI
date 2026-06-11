"""Evaluasi gaya fraud-detection terhadap labeled fixtures.

Kelas tidak seimbang (endorsement = minoritas), jadi metrics inti:
precision, recall, F1, confusion matrix, dan precision-recall curve.
Akurasi sengaja TIDAK dijadikan metrik utama karena menyesatkan di data
imbalanced.

Definisi positif (level post): post diprediksi endorsement jika ADA minimal
satu deteksi dengan decision='accept'. Brand-level correctness juga dilaporkan
terpisah (apakah brand yang terdeteksi benar).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import FIXTURES_LABELS, FIXTURES_POSTS
from ..detect.pipeline import run_detection
from ..detect.registry import BrandRegistry
from ..ingest.loader import load_from_fixtures


def _load_labels(path: Path = FIXTURES_LABELS) -> dict[str, dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {l["post_id"]: l for l in data["labels"]}


def evaluate(review_counts_as_positive: bool = False) -> dict:
    posts = load_from_fixtures()
    registry = BrandRegistry.load()
    detections = run_detection(posts, registry, use_semantic=True)
    labels = _load_labels()

    positive_decisions = {"accept"} | ({"review"} if review_counts_as_positive else set())

    # prediksi per-post
    pred_pos: dict[str, list] = {}
    for d in detections:
        if d.decision in positive_decisions:
            pred_pos.setdefault(d.post_id, []).append(d)

    tp = fp = fn = tn = 0
    brand_correct = brand_total = 0
    errors = []

    for pid, lab in labels.items():
        is_pos_true = lab["is_endorsement"]
        is_pos_pred = pid in pred_pos

        if is_pos_pred and is_pos_true:
            tp += 1
            brand_total += 1
            if any(d.brand_id == lab["brand_id"] for d in pred_pos[pid]):
                brand_correct += 1
            else:
                errors.append((pid, "brand_mismatch", lab["brand_id"]))
        elif is_pos_pred and not is_pos_true:
            fp += 1
            errors.append((pid, "false_positive", None))
        elif not is_pos_pred and is_pos_true:
            fn += 1
            errors.append((pid, "false_negative", lab["brand_id"]))
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "support": {"positives": sum(1 for l in labels.values() if l["is_endorsement"]),
                    "negatives": sum(1 for l in labels.values() if not l["is_endorsement"]),
                    "total": len(labels)},
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "brand_accuracy_on_tp": round(brand_correct / brand_total, 3) if brand_total else None,
        "errors": errors,
        "policy": "review_as_positive" if review_counts_as_positive else "accept_only",
    }


def _print_report(r: dict):
    c = r["confusion"]
    print("=" * 52)
    print(" EVALUASI ENDORSEMENT DETECTION (fraud-style)")
    print("=" * 52)
    print(f" Support: {r['support']['positives']} pos / "
          f"{r['support']['negatives']} neg  (total {r['support']['total']})")
    print(f" Policy : {r['policy']}")
    print("-" * 52)
    print(f"            Pred POS    Pred NEG")
    print(f" True POS     {c['tp']:>3}         {c['fn']:>3}   (recall = {r['recall']})")
    print(f" True NEG     {c['fp']:>3}         {c['tn']:>3}")
    print("-" * 52)
    print(f" Precision : {r['precision']}")
    print(f" Recall    : {r['recall']}")
    print(f" F1        : {r['f1']}")
    print(f" Brand acc (pada TP): {r['brand_accuracy_on_tp']}")
    if r["errors"]:
        print("-" * 52)
        print(" Kesalahan (untuk inspeksi):")
        for pid, kind, info in r["errors"]:
            print(f"   {pid}: {kind}" + (f" (brand={info})" if info else ""))
    print("=" * 52)


if __name__ == "__main__":
    _print_report(evaluate(review_counts_as_positive=False))
