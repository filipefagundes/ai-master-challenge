#!/usr/bin/env python3
"""Prepare or execute a 300-row stratified evaluation of the deployed routing layer.

Preparation is local and free. Execution must be explicitly enabled because every
row calls the public endpoint and therefore consumes the configured API quota.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


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


def holdout_indices(frame: pd.DataFrame, seed: int = 42) -> list[int]:
    rng = random.Random(seed)
    by_class: dict[str, list[int]] = defaultdict(list)
    for index, label in enumerate(frame["Topic_group"].astype(str).tolist()):
        by_class[label].append(index)
    test: list[int] = []
    for indices in by_class.values():
        rng.shuffle(indices)
        test.extend(indices[int(len(indices) * 0.8):])
    return test


def make_evaluation_set(frame: pd.DataFrame, size: int = 300) -> list[dict]:
    holdout = frame.iloc[holdout_indices(frame)].copy()
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


def summarize(results: list[dict]) -> dict:
    valid = [row for row in results if row.get("predicted")]
    labels = sorted({row["expected"] for row in valid})
    confusion = {label: Counter() for label in labels}
    for row in valid:
        confusion[row["expected"]][row["predicted"]] += 1
    per_class = []
    for label in labels:
        true_positive = confusion[label][label]
        support = sum(confusion[label].values())
        predicted = sum(confusion[actual][label] for actual in labels)
        precision = true_positive / predicted if predicted else 0
        recall = true_positive / support if support else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        per_class.append({"label": label, "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3), "support": support})
    correct = sum(row["expected"] == row["predicted"] for row in valid)
    return {
        "requested": len(results),
        "completed": len(valid),
        "errors": len(results) - len(valid),
        "accuracy": round(correct / len(valid), 3) if valid else None,
        "macroF1": round(sum(row["f1"] for row in per_class) / len(per_class), 3) if per_class else None,
        "perClass": per_class,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--endpoint", default="https://sinal-002.vercel.app/api/triage")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--i-understand-this-uses-paid-api", action="store_true")
    args = parser.parse_args()

    topics = load_topics(args.data_dir / "all_tickets_processed_improved_v3.csv.zip")
    evaluation_set = make_evaluation_set(topics, args.size)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    set_path = args.output_dir / "evaluation-set.json"
    set_path.write_text(json.dumps(evaluation_set, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"prepared": len(evaluation_set), "path": str(set_path)}, ensure_ascii=False))

    if not args.execute:
        return
    if not args.i_understand_this_uses_paid_api:
        raise SystemExit("Execution blocked: add --i-understand-this-uses-paid-api after obtaining authorization.")

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(call_endpoint, args.endpoint, item) for item in evaluation_set]
        for future in as_completed(futures):
            results.append(future.result())
    report = {"endpoint": args.endpoint, "dataset": "Dataset 2 stratified holdout", "summary": summarize(results), "results": sorted(results, key=lambda row: row["id"])}
    report_path = args.output_dir / "evaluation-results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
