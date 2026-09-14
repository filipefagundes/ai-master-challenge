import routingModel from "../data/routing-model.ts";

const tokenPattern = /[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9_-]+/g;

export function classifyRoutingTopic(text: string) {
  const scores = [...routingModel.logPriors];
  const tokens = text.match(tokenPattern)?.map((token) => token.toLowerCase()) ?? [];

  for (const token of tokens) {
    const tokenCounts = routingModel.tokenCounts[token];
    if (!tokenCounts) continue;
    for (let index = 0; index < scores.length; index += 1) {
      scores[index] += Math.log(tokenCounts[index] + 1) - routingModel.logDenominators[index];
    }
  }

  const ranked = scores
    .map((score, index) => ({ label: routingModel.labels[index], score }))
    .sort((left, right) => right.score - left.score);
  const maxScore = ranked[0].score;
  const normalizer = ranked.reduce((total, item) => total + Math.exp(item.score - maxScore), 0);
  const probabilities = ranked.map((item) => Math.exp(item.score - maxScore) / normalizer);

  return {
    label: ranked[0].label,
    confidence: probabilities[0],
    margin: probabilities[0] - probabilities[1],
  };
}
