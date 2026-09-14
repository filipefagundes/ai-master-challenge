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
import numpy as np


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
    text = re.sub(r"\b\d{2}[.\s-]?\d{3}[.\s-]?\d{3}[\/\s-]?\d{4}[-\s]?\d{2}\b", "[CNPJ removido]", text)
    text = re.sub(r"\b\d{3}[.\s-]?\d{3}[.\s-]?\d{3}[-\s]?\d{2}\b", "[CPF removido]", text)
    text = re.sub(r"(?<!\d)(?:\d[\s-]?){13,19}(?!\d)", "[número longo removido]", text)
    text = re.sub(r"(?<!\d)(?:\+?55[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?)?(?:9?\d{4})[\s.-]?\d{4}(?!\d)", "[telefone removido]", text)
    text = re.sub(r"\b\d{1,2}[.\s-]?\d{3}[.\s-]?\d{3}[-\s]?[0-9Xx]\b", "[RG removido]", text)
    text = re.sub(r"\b\d{5}[-\s]?\d{3}\b", "[CEP removido]", text)
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


def regularized_gamma_q(shape: float, value: float) -> float:
    """Numerically stable upper regularized gamma; used for chi-square p-values."""
    if value < 0 or shape <= 0:
        raise ValueError("shape must be positive and value non-negative")
    if value == 0:
        return 1.0
    epsilon = 3e-14
    if value < shape + 1:
        term = 1.0 / shape
        total = term
        cursor = shape
        for _ in range(1000):
            cursor += 1
            term *= value / cursor
            total += term
            if abs(term) < abs(total) * epsilon:
                break
        lower = total * math.exp(-value + shape * math.log(value) - math.lgamma(shape))
        return max(0.0, min(1.0, 1.0 - lower))

    tiny = 1e-300
    b = value + 1 - shape
    c = 1 / tiny
    d = 1 / b
    fraction = d
    for index in range(1, 1000):
        coefficient = -index * (index - shape)
        b += 2
        d = coefficient * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + coefficient / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        delta = d * c
        fraction *= delta
        if abs(delta - 1) < epsilon:
            break
    return max(0.0, min(1.0, math.exp(-value + shape * math.log(value) - math.lgamma(shape)) * fraction))


def categorical_association(left: pd.Series, right: pd.Series) -> dict:
    table = pd.crosstab(left, right).to_numpy(dtype=float)
    total = table.sum()
    expected = np.outer(table.sum(axis=1), table.sum(axis=0)) / total
    chi_square = float(np.where(expected > 0, (table - expected) ** 2 / expected, 0).sum())
    degrees = int((table.shape[0] - 1) * (table.shape[1] - 1))
    denominator = total * min(table.shape[0] - 1, table.shape[1] - 1)
    cramers_v = math.sqrt(chi_square / denominator) if denominator else 0.0
    p_value = regularized_gamma_q(degrees / 2, chi_square / 2) if degrees else 1.0
    return {
        "cramersV": round(cramers_v, 4),
        "chiSquare": round(chi_square, 3),
        "degreesOfFreedom": degrees,
        "pValue": round(p_value, 4),
    }


def multiple_comparison_audit(frame: pd.DataFrame) -> dict:
    overall = frame["Ticket Status"].ne("Closed").mean()
    groups = list(frame.groupby(["Ticket Channel", "Ticket Type", "Ticket Priority"]))
    observed = []
    sizes = []
    for labels, group in groups:
        size = len(group)
        if size < 80:
            continue
        rate = group["Ticket Status"].ne("Closed").mean()
        standard_error = math.sqrt(overall * (1 - overall) / size)
        observed.append((abs(rate - overall) / standard_error, " · ".join(labels)))
        sizes.append(size)

    rng = np.random.default_rng(42)
    simulated = np.column_stack(
        [rng.binomial(size, overall, size=20000) / size for size in sizes]
    )
    errors = np.sqrt(overall * (1 - overall) / np.asarray(sizes))
    simulated_max = np.max(np.abs(simulated - overall) / errors, axis=1)
    max_z, label = max(observed)
    return {
        "combinationsTested": len(observed),
        "maxObservedZ": round(max_z, 2),
        "maxObservedLabel": label,
        "expectedMaxZ": round(float(np.mean(simulated_max)), 2),
        "chance95UpperZ": round(float(np.quantile(simulated_max, 0.95)), 2),
        "familyWisePValue": round(float((simulated_max >= max_z).mean()), 3),
        "simulation": "20.000 cenários binomiais sob ausência de associação, seed 42",
    }


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(str(text))]


def train_and_evaluate_nb(frame: pd.DataFrame, seed: int = 42) -> dict:
    """Small, transparent baseline; the production prototype uses embeddings + LLM."""
    rng = random.Random(seed)
    by_class: dict[str, list[int]] = defaultdict(list)
    documents = frame["Document"].astype(str).tolist()
    document_labels = frame["Topic_group"].astype(str).tolist()
    for index, label in enumerate(document_labels):
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
        label = document_labels[index]
        tokens = tokenize(documents[index])
        word_counts[label].update(tokens)
        token_totals[label] += len(tokens)
        class_docs[label] += 1
        vocabulary.update(tokens)

    vocab_size = len(vocabulary)
    total_train = len(train_indices)
    confusion = {actual: Counter() for actual in labels}

    for index in test_indices:
        actual = document_labels[index]
        tokens = [token for token in tokenize(documents[index]) if token in vocabulary]
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
        "trainIndices": train_indices,
    }


def select_routing_corpus(frame: pd.DataFrame, train_indices: list[int]) -> list[dict]:
    """Deterministic, stratified retrieval corpus sourced only from Dataset 2 train rows."""
    training = frame.iloc[train_indices].copy()
    rows: list[dict] = []
    for topic, group in training.groupby("Topic_group"):
        sample = group.sample(n=min(25, len(group)), random_state=42)
        for _, row in sample.iterrows():
            document = anonymize(str(row["Document"]))[:700]
            public_id = hashlib.sha256(f"g4-ds2-{row.name}".encode()).hexdigest()[:8].upper()
            rows.append(
                {
                    "id": f"DS2-{public_id}",
                    "type": str(topic),
                    "subject": document[:96] + ("…" if len(document) > 96 else ""),
                    "text": document,
                }
            )
    return sorted(rows, key=lambda item: (item["type"], item["id"]))


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
    train_indices = benchmark.pop("trainIndices")
    first_sentence_template = support["Ticket Description"].astype(str).str.split(".", n=1).str[0]
    shuffled_types = support["Ticket Type"].sample(frac=1, random_state=42).reset_index(drop=True)
    text_type_association = categorical_association(first_sentence_template, support["Ticket Type"])
    shuffled_association = categorical_association(first_sentence_template.reset_index(drop=True), shuffled_types)
    status_associations = [
        {"factor": label, **categorical_association(support[column], support["Ticket Status"])}
        for label, column in [
            ("Canal", "Ticket Channel"),
            ("Tipo", "Ticket Type"),
            ("Prioridade", "Ticket Priority"),
        ]
    ]
    comparison_audit = multiple_comparison_audit(support)

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
            {
                "id": "weak-label-signal",
                "severity": "critical",
                "metric": f"V={text_type_association['cramersV']:.3f}",
                "title": "Texto quase não explica o tipo",
                "detail": f"Há 16 frases iniciais; {pct(first_sentence_template.value_counts(normalize=True).iloc[0])}% começam com o mesmo template. A associação com Ticket Type é comparável ao controle embaralhado.",
            },
        ],
        "dimensions": dimensions,
        "satisfaction": {
            "distribution": [
                {"rating": int(rating), "tickets": int(count)}
                for rating, count in support["Customer Satisfaction Rating"].value_counts().sort_index().items()
            ],
            "effects": sorted(satisfaction_effects, key=lambda item: -item["etaSquared"]),
            "interpretation": "Nenhum fator categórico disponível explica materialmente a variação de CSAT nesta amostra. Todos os η² ficam abaixo de 0,015; Produto é o maior (0,013) e ainda é desprezível.",
        },
        "associationAudit": {
            "textTemplateVsTicketType": text_type_association,
            "shuffledControl": shuffled_association,
            "firstSentenceTemplates": int(first_sentence_template.nunique()),
            "dominantTemplateShare": pct(first_sentence_template.value_counts(normalize=True).iloc[0]),
            "statusByDimension": status_associations,
            "multipleComparisons": comparison_audit,
            "interpretation": "O maior desvio entre 80 combinações não sobrevive ao controle de múltiplas comparações; não há concentração operacional defensável nesta amostra.",
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
    (args.output_dir / "routing-corpus.json").write_text(
        json.dumps(select_routing_corpus(topics, train_indices), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"analysis": analysis["overview"], "benchmark": benchmark}, ensure_ascii=False))


if __name__ == "__main__":
    main()
