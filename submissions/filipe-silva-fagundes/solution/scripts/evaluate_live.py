#!/usr/bin/env python3
"""Prepare or execute a 300-row stratified evaluation of the deployed routing layer.

Preparation is local and free. Execution must be explicitly enabled because every
row calls the public endpoint and therefore consumes the configured API quota.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9_-]+")


def sanitize_for_manifest(value: str) -> str:
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removido]", value)
    value = re.sub(r"(?<!\d)(?:\d[\s-]?){8,19}(?!\d)", "[número removido]", value)
    return re.sub(r"\s+", " ", value).strip()


def load_topics(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"Expected one CSV inside {path}")
        return pd.read_csv(archive.open(members[0]))


def split_indices(frame: pd.DataFrame, seed: int = 42) -> tuple[list[int], list[int]]:
    rng = random.Random(seed)
    by_class: dict[str, list[int]] = defaultdict(list)
    for index, label in enumerate(frame["Topic_group"].astype(str).tolist()):
        by_class[label].append(index)
    train: list[int] = []
    test: list[int] = []
    for indices in by_class.values():
        rng.shuffle(indices)
        boundary = int(len(indices) * 0.8)
        train.extend(indices[:boundary])
        test.extend(indices[boundary:])
    return train, test


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value)]


def baseline_predictions(frame: pd.DataFrame, evaluation_set: list[dict]) -> dict[str, str]:
    train_indices, _ = split_indices(frame)
    documents = frame["Document"].astype(str).tolist()
    labels_by_row = frame["Topic_group"].astype(str).tolist()
    labels = sorted(set(labels_by_row))
    vocabulary: set[str] = set()
    word_counts = {label: Counter() for label in labels}
    token_totals = Counter()
    class_docs = Counter()
    for index in train_indices:
        label = labels_by_row[index]
        tokens = tokenize(documents[index])
        word_counts[label].update(tokens)
        token_totals[label] += len(tokens)
        class_docs[label] += 1
        vocabulary.update(tokens)

    predictions = {}
    for item in evaluation_set:
        tokens = [token for token in tokenize(item["text"]) if token in vocabulary]
        scores = {}
        for label in labels:
            denominator = token_totals[label] + len(vocabulary)
            scores[label] = math.log(class_docs[label] / len(train_indices)) + sum(
                math.log((word_counts[label][token] + 1) / denominator) for token in tokens
            )
        predictions[item["id"]] = max(scores, key=scores.get)
    return predictions


def make_evaluation_set(frame: pd.DataFrame, size: int = 300) -> list[dict]:
    _, test_indices = split_indices(frame)
    holdout = frame.iloc[test_indices].copy()
    counts = holdout["Topic_group"].value_counts()
    allocations = (counts / counts.sum() * size).astype(int)
    for label in (counts / counts.sum() * size - allocations).sort_values(ascending=False).index:
        if allocations.sum() >= size:
            break
        allocations[label] += 1

    rows = []
    for label, amount in allocations.items():
        sample = holdout[holdout["Topic_group"].eq(label)].sample(n=int(amount), random_state=42)
        for index, row in sample.iterrows():
            rows.append({
                "id": "EVAL-" + hashlib.sha256(f"g4-eval-{index}".encode()).hexdigest()[:8].upper(),
                "expected": str(label),
                "text": sanitize_for_manifest(str(row["Document"]))[:2500],
            })
    return sorted(rows, key=lambda item: item["id"])


def call_endpoint(endpoint: str, item: dict) -> dict:
    payload = json.dumps({"text": item["text"], "channel": "Email"}).encode()
    request = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)
            return {"id": item["id"], "expected": item["expected"], "predicted": result.get("routingTopic"), "mode": result.get("mode")}
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 2:
                return {"id": item["id"], "expected": item["expected"], "error": str(error)}
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def summarize(results: list[dict], prediction_key: str) -> dict:
    valid = [row for row in results if row.get(prediction_key)]
    labels = sorted({row["expected"] for row in valid})
    confusion = {label: Counter() for label in labels}
    for row in valid:
        confusion[row["expected"]][row[prediction_key]] += 1
    per_class = []
    for label in labels:
        true_positive = confusion[label][label]
        support = sum(confusion[label].values())
        predicted = sum(confusion[actual][label] for actual in labels)
        precision = true_positive / predicted if predicted else 0
        recall = true_positive / support if support else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        per_class.append({"label": label, "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3), "support": support})
    correct = sum(row["expected"] == row[prediction_key] for row in valid)
    accuracy = correct / len(valid) if valid else None
    if accuracy is None:
        interval = [None, None]
    else:
        z = 1.96
        denominator = 1 + z * z / len(valid)
        center = (accuracy + z * z / (2 * len(valid))) / denominator
        margin = z * math.sqrt(accuracy * (1 - accuracy) / len(valid) + z * z / (4 * len(valid) ** 2)) / denominator
        interval = [round(center - margin, 3), round(center + margin, 3)]
    return {
        "requested": len(results),
        "completed": len(valid),
        "errors": len(results) - len(valid),
        "accuracy": round(accuracy, 3) if accuracy is not None else None,
        "accuracyWilson95": interval,
        "macroF1": round(sum(row["f1"] for row in per_class) / len(per_class), 3) if per_class else None,
        "perClass": per_class,
        "confusion": {actual: dict(confusion[actual]) for actual in labels},
    }


def paired_comparison(results: list[dict]) -> dict:
    baseline_only = sum(row["baselinePrediction"] == row["expected"] and row.get("predicted") != row["expected"] for row in results)
    llm_only = sum(row.get("predicted") == row["expected"] and row["baselinePrediction"] != row["expected"] for row in results)
    discordant = baseline_only + llm_only
    if discordant:
        tail = sum(math.comb(discordant, value) for value in range(0, min(baseline_only, llm_only) + 1)) / (2 ** discordant)
        p_value = min(1.0, 2 * tail)
    else:
        p_value = 1.0
    return {
        "baselineCorrectLlmWrong": baseline_only,
        "llmCorrectBaselineWrong": llm_only,
        "mcnemarExactPValue": p_value,
        "interpretation": "A diferença favorece o baseline no mesmo conjunto; o teste exato usa apenas pares discordantes.",
    }


def write_report(output_dir: Path, report: dict) -> None:
    (output_dir / "evaluation-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {key: report[key] for key in ["summarizedAt", "endpoint", "dataset", "models", "summary"]}
    (output_dir / "evaluation-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--endpoint", default="https://sinal-002.vercel.app/api/triage")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--reuse-results", action="store_true")
    parser.add_argument("--i-understand-this-uses-paid-api", action="store_true")
    args = parser.parse_args()

    topics = load_topics(args.data_dir / "all_tickets_processed_improved_v3.csv.zip")
    evaluation_set = make_evaluation_set(topics, args.size)
    baseline_by_id = baseline_predictions(topics, evaluation_set)
    for item in evaluation_set:
        item["baselinePrediction"] = baseline_by_id[item["id"]]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    set_path = args.output_dir / "evaluation-set.json"
    set_path.write_text(json.dumps(evaluation_set, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"prepared": len(evaluation_set), "path": str(set_path)}, ensure_ascii=False))

    results_path = args.output_dir / "evaluation-results.json"
    if args.reuse_results:
        existing = json.loads(results_path.read_text(encoding="utf-8"))
        results = existing["results"]
        for row in results:
            row["baselinePrediction"] = baseline_by_id[row["id"]]
        report = {
            "summarizedAt": datetime.now(timezone.utc).isoformat(),
            "endpoint": existing["endpoint"],
            "dataset": "300 tickets do holdout estratificado do Dataset 2",
            "models": {"llm": "produção (verificado separadamente: gpt-5.4-mini-2026-03-17)", "embeddings": "text-embedding-3-small", "baseline": "Multinomial Naive Bayes"},
            "summary": {
                "llmAndEmbeddings": summarize(results, "predicted"),
                "naiveBayesSame300": summarize(results, "baselinePrediction"),
                "pairedComparison": paired_comparison(results),
                "modes": dict(Counter(row.get("mode", "unknown") for row in results)),
            },
            "results": sorted(results, key=lambda row: row["id"]),
        }
        write_report(args.output_dir, report)
        print(json.dumps(report["summary"], ensure_ascii=False))
        return

    if not args.execute:
        return
    if not args.i_understand_this_uses_paid_api:
        raise SystemExit("Execution blocked: add --i-understand-this-uses-paid-api after obtaining authorization.")

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(call_endpoint, args.endpoint, item) for item in evaluation_set]
        for future in as_completed(futures):
            results.append(future.result())
    for row in results:
        row["baselinePrediction"] = baseline_by_id[row["id"]]
    report = {
        "summarizedAt": datetime.now(timezone.utc).isoformat(),
        "endpoint": args.endpoint,
        "dataset": "300 tickets do holdout estratificado do Dataset 2",
        "models": {"llm": "produção", "embeddings": "text-embedding-3-small", "baseline": "Multinomial Naive Bayes"},
        "summary": {
            "llmAndEmbeddings": summarize(results, "predicted"),
            "naiveBayesSame300": summarize(results, "baselinePrediction"),
            "pairedComparison": paired_comparison(results),
            "modes": dict(Counter(row.get("mode", "unknown") for row in results)),
        },
        "results": sorted(results, key=lambda row: row["id"]),
    }
    write_report(args.output_dir, report)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
