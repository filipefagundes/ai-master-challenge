import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { enforcedDecision } from "../lib/policy.ts";
import { classifyRoutingTopic } from "../lib/routing.ts";

type EvaluationCase = {
  id: string;
  expected: string;
  text: string;
  baselinePrediction: string;
};

const evaluationSet = JSON.parse(
  readFileSync(new URL("../data/evaluation-set.json", import.meta.url), "utf8"),
) as EvaluationCase[];

test("production router reproduces the frozen baseline on all 300 evaluation cases", () => {
  assert.equal(evaluationSet.length, 300);
  let correct = 0;

  for (const item of evaluationSet) {
    const prediction = classifyRoutingTopic(item.text);
    assert.equal(prediction.label, item.baselinePrediction, item.id);
    assert.ok(prediction.confidence >= 0 && prediction.confidence <= 1, item.id);
    assert.ok(prediction.margin >= 0 && prediction.margin <= 1, item.id);
    if (prediction.label === item.expected) correct += 1;
  }

  assert.equal(correct, 233);
  assert.equal(Number((correct / evaluationSet.length).toFixed(3)), 0.777);
});

test("low routing confidence prevents automation even when assistance is confident", () => {
  const routing = classifyRoutingTopic("Preciso de ajuda com uma cobrança da assinatura.");
  assert.ok(routing.confidence < 0.72);
  assert.equal(
    enforcedDecision({
      modelPriority: "Baixa",
      modelConfidence: Math.min(0.99, routing.confidence),
      riskFlags: [],
      lowRiskIntent: true,
    }),
    "Humano",
  );
});
