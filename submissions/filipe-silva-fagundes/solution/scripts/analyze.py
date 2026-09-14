#!/usr/bin/env python3
"""Reproducible analysis for Challenge 002.

Reads the two original Kaggle ZIP files without extracting them, validates the
operational fields, trains a dependency-free Multinomial Naive Bayes baseline,
and writes only aggregated/anonymized artifacts consumed by the web app.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9_-]+")


def load_zipped_csv(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        csv_members = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(csv_members) != 1:
            raise ValueError(f"Expected one CSV inside {path}, found {csv_members}")
        return pd.read_csv(archive.open(csv_members[0]))


def pct(value: float) -> float:
    return round(float(value) * 100, 1)


def anonymize(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removido]", str(text))
    text = re.sub(r"\b\d{5,}\b", "[número removido]", text)
    return re.sub(r"\s+", " ", text).strip()


def grouped_metrics(frame: pd.DataFrame, column: str) -> list[dict]:
    rows = []
    for label, group in frame.groupby(column, dropna=False):
        resolved = group["Ticket Status"].eq("Closed")
        ratings = group["Customer Satisfaction Rating"].dropna()
        rows.append(
            {
                "label": str(label),
                "tickets": int(len(group)),
                "share": pct(len(group) / len(frame)),
                "backlog": int((~resolved).sum()),
                "backlogRate": pct((~resolved).mean()),
                "closed": int(resolved.sum()),
                "csat": round(float(ratings.mean()), 2) if len(ratings) else None,
            }
        )
    return sorted(rows, key=lambda row: (-row["backlog"], row["label"]))


def combination_metrics(frame: pd.DataFrame) -> list[dict]:
    rows = []
    keys = ["Ticket Channel", "Ticket Type", "Ticket Priority"]
    for labels, group in frame.groupby(keys):
        resolved = group["Ticket Status"].eq("Closed")
        ratings = group["Customer Satisfaction Rating"].dropna()
        rows.append(
            {
                "label": " · ".join(labels),
                "tickets": int(len(group)),
                "share": pct(len(group) / len(frame)),
                "backlog": int((~resolved).sum()),
                "backlogRate": pct((~resolved).mean()),
                "closed": int(resolved.sum()),
                "csat": round(float(ratings.mean()), 2) if len(ratings) else None,
            }
        )
    # Avoid elevating unstable tiny cells. All returned groups have at least 80 tickets.
    return sorted((row for row in rows if row["tickets"] >= 80), key=lambda row: (-row["backlog"], row["label"]))


def eta_squared(frame: pd.DataFrame, column: str) -> float:
    valid = frame[[column, "Customer Satisfaction Rating"]].dropna()
    overall = valid["Customer Satisfaction Rating"].mean()
    total = ((valid["Customer Satisfaction Rating"] - overall) ** 2).sum()
    between = sum(
        len(group) * (group["Customer Satisfaction Rating"].mean() - overall) ** 2
        for _, group in valid.groupby(column)
    )
    return round(float(between / total), 5) if total else 0.0


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(str(text))]


def train_and_evaluate_nb(frame: pd.DataFrame, seed: int = 42) -> dict:
    """Small, transparent baseline; the production prototype uses embeddings + LLM."""
    rng = random.Random(seed)
    by_class: dict[str, list[int]] = defaultdict(list)
    for index, label in enumerate(frame["Topic_group"]):
        by_class[str(label)].append(index)

    train_indices: list[int] = []
    test_indices: list[int] = []
    for indices in by_class.values():
        rng.shuffle(indices)
        boundary = int(len(indices) * 0.8)
        train_indices.extend(indices[:boundary])
        test_indices.extend(indices[boundary:])

    labels = sorted(by_class)
    vocabulary: set[str] = set()
    word_counts = {label: Counter() for label in labels}
    token_totals = Counter()
    class_docs = Counter()

    for index in train_indices:
        label = str(frame.iloc[index]["Topic_group"])
        tokens = tokenize(frame.iloc[index]["Document"])
        word_counts[label].update(tokens)
        token_totals[label] += len(tokens)
        class_docs[label] += 1
        vocabulary.update(tokens)

    vocab_size = len(vocabulary)
    total_train = len(train_indices)
    confusion = {actual: Counter() for actual in labels}

    for index in test_indices:
        actual = str(frame.iloc[index]["Topic_group"])
        tokens = tokenize(frame.iloc[index]["Document"])
        scores: dict[str, float] = {}
        for label in labels:
            score = math.log(class_docs[label] / total_train)
            denominator = token_totals[label] + vocab_size
            counts = word_counts[label]
            score += sum(math.log((counts[token] + 1) / denominator) for token in tokens)
            scores[label] = score
        predicted = max(scores, key=scores.get)
        confusion[actual][predicted] += 1

    correct = sum(confusion[label][label] for label in labels)
    total = len(test_indices)
    per_class = []
    for label in labels:
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        predicted_total = sum(confusion[actual][label] for actual in labels)
        precision = tp / predicted_total if predicted_total else 0
        recall = tp / support if support else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        per_class.append(
            {
                "label": label,
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
                "support": support,
            }
        )

    macro_f1 = sum(item["f1"] for item in per_class) / len(per_class)
    return {
        "method": "Multinomial Naive Bayes, palavras, Laplace α=1",
        "purpose": "baseline auditável; o protótipo online usa embeddings e LLM",
        "split": "80/20 estratificado, seed 42",
        "trainRows": len(train_indices),
        "testRows": total,
        "vocabulary": vocab_size,
        "accuracy": round(correct / total, 3),
        "macroF1": round(macro_f1, 3),
        "perClass": sorted(per_class, key=lambda item: item["f1"]),
        "confusion": {
            actual: {predicted: confusion[actual][predicted] for predicted in labels}
            for actual in labels
        },
    }


def select_cases(frame: pd.DataFrame) -> list[dict]:
    candidates = frame[
        frame["Ticket Status"].eq("Closed")
        & frame["Resolution"].notna()
        & frame["Ticket Description"].notna()
    ].copy()
    candidates["length"] = candidates["Ticket Description"].str.len()
    candidates = candidates[(candidates["length"] >= 120) & (candidates["length"] <= 700)]

    rows: list[dict] = []
    for ticket_type, group in candidates.groupby("Ticket Type"):
        sample = group.sample(n=min(3, len(group)), random_state=42)
        for _, row in sample.iterrows():
            public_id = hashlib.sha256(f"g4-{row['Ticket ID']}".encode()).hexdigest()[:8].upper()
            description = anonymize(row["Ticket Description"]).replace(
                "{product_purchased}", str(row["Product Purchased"])
            )
            rows.append(
                {
                    "id": f"CASE-{public_id}",
                    "type": ticket_type,
                    "subject": row["Ticket Subject"],
                    "channel": row["Ticket Channel"],
                    "priority": row["Ticket Priority"],
                    "description": description,
                    "resolution": anonymize(row["Resolution"]),
                    "rating": int(row["Customer Satisfaction Rating"]),
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    support = load_zipped_csv(args.data_dir / "customer_support_tickets.csv.zip")
    topics = load_zipped_csv(args.data_dir / "all_tickets_processed_improved_v3.csv.zip")

    support["First Response Time"] = pd.to_datetime(support["First Response Time"], errors="coerce")
    support["Time to Resolution"] = pd.to_datetime(support["Time to Resolution"], errors="coerce")
    closed = support[support["Ticket Status"].eq("Closed")].copy()
    closed["response_to_resolution_hours"] = (
        closed["Time to Resolution"] - closed["First Response Time"]
    ).dt.total_seconds() / 3600

    negative_intervals = int((closed["response_to_resolution_hours"] < 0).sum())
    status_counts = support["Ticket Status"].value_counts()
    backlog = int(status_counts.get("Open", 0) + status_counts.get("Pending Customer Response", 0))

    dimensions = {
        "channels": grouped_metrics(support, "Ticket Channel"),
        "types": grouped_metrics(support, "Ticket Type"),
        "priorities": grouped_metrics(support, "Ticket Priority"),
        "subjects": grouped_metrics(support, "Ticket Subject"),
        "products": grouped_metrics(support, "Product Purchased")[:12],
        "combinations": combination_metrics(support),
    }

    satisfaction_effects = [
        {"factor": label, "etaSquared": eta_squared(support, column)}
        for label, column in [
            ("Canal", "Ticket Channel"),
            ("Tipo", "Ticket Type"),
            ("Prioridade", "Ticket Priority"),
            ("Assunto", "Ticket Subject"),
            ("Produto", "Product Purchased"),
        ]
    ]

    topic_counts = topics["Topic_group"].value_counts()
    benchmark = train_and_evaluate_nb(topics)

    analysis = {
        "generatedAt": pd.Timestamp.now(tz="UTC").isoformat(),
        "overview": {
            "supportRows": len(support),
            "classifiedRows": len(topics),
            "closedTickets": int(status_counts.get("Closed", 0)),
            "backlogTickets": backlog,
            "backlogRate": pct(backlog / len(support)),
            "ratedTickets": int(support["Customer Satisfaction Rating"].notna().sum()),
            "meanCsat": round(float(support["Customer Satisfaction Rating"].mean()), 2),
        },
        "dataQuality": [
            {
                "id": "volume-mismatch",
                "severity": "warning",
                "metric": "8.469",
                "title": "A amostra não contém 30 mil tickets",
                "detail": "O enunciado descreve a operação anual. O CSV entregue contém 8.469 linhas; não extrapolamos resultados sem rotular a premissa.",
            },
            {
                "id": "invalid-time-order",
                "severity": "critical",
                "metric": f"{pct(negative_intervals / len(closed))}%",
                "title": "Sequência temporal inválida",
                "detail": f"{negative_intervals:,} de {len(closed):,} tickets fechados têm resolução anterior à primeira resposta. Tempos e SLA ficam bloqueados.",
            },
            {
                "id": "missing-outcomes",
                "severity": "warning",
                "metric": f"{pct(support['Customer Satisfaction Rating'].isna().mean())}%",
                "title": "CSAT ausente por desenho do status",
                "detail": "A nota existe apenas para tickets fechados. Comparar fechados com o backlog introduziria viés de seleção.",
            },
            {
                "id": "template-text",
                "severity": "critical",
                "metric": f"{pct(support['Ticket Description'].str.contains(r'{product_purchased}', regex=False).mean())}%",
                "title": "Texto contém placeholder",
                "detail": "Todas as descrições preservam {product_purchased}; isso confirma conteúdo sintético e exige cautela ao generalizar.",
            },
        ],
        "dimensions": dimensions,
        "satisfaction": {
            "distribution": [
                {"rating": int(rating), "tickets": int(count)}
                for rating, count in support["Customer Satisfaction Rating"].value_counts().sort_index().items()
            ],
            "effects": sorted(satisfaction_effects, key=lambda item: -item["etaSquared"]),
            "interpretation": "Nenhum fator categórico disponível explica materialmente a variação de CSAT nesta amostra. η² abaixo de 0,01 é efeito desprezível.",
        },
        "topicDataset": {
            "rows": len(topics),
            "categories": [
                {"label": label, "tickets": int(count), "share": pct(count / len(topics))}
                for label, count in topic_counts.items()
            ],
            "duplicateDocuments": int(topics["Document"].duplicated().sum()),
        },
        "benchmark": benchmark,
        "roiDefaults": {
            "annualTickets": 30000,
            "autoShare": 0.25,
            "assistShare": 0.45,
            "minutesAuto": 9,
            "minutesAssist": 4,
            "hourlyCostBrl": 45,
        },
        "methodology": {
            "blockedMetrics": [
                "Tempo até primeira resposta: não há timestamp de criação do ticket.",
                "Tempo total de resolução: 49,3% das sequências fechadas são negativas.",
                "Causalidade de CSAT: o dataset é observacional e a nota só existe para fechados.",
            ],
            "usableMetrics": [
                "Volume, distribuição e backlog por canal, tipo, prioridade e assunto.",
                "CSAT descritivo apenas entre tickets fechados.",
                "Classificação supervisionada no Dataset 2 com holdout estratificado.",
                "ROI por cenários editáveis, nunca apresentado como economia observada.",
            ],
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "cases.json").write_text(
        json.dumps(select_cases(support), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"analysis": analysis["overview"], "benchmark": benchmark}, ensure_ascii=False))


if __name__ == "__main__":
    main()
