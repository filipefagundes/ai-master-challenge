import type { RiskFlag } from "./privacy";

export type Decision = "Automatizar" | "Assistir" | "Humano";

export function enforcedDecision(input: {
  modelPriority: string;
  modelConfidence: number;
  riskFlags: RiskFlag[];
  lowRiskIntent: boolean;
}): Decision {
  const { modelPriority, modelConfidence, riskFlags, lowRiskIntent } = input;
  if (riskFlags.includes("prompt_injection")) return "Humano";
  if (riskFlags.some((flag) => ["security", "data_loss", "legal", "privileged_access"].includes(flag))) return "Humano";
  if (modelPriority === "Crítica" || modelConfidence < 0.72) return "Humano";
  if (riskFlags.some((flag) => ["financial", "cancellation"].includes(flag))) return "Assistir";
  if (lowRiskIntent && modelPriority === "Baixa" && modelConfidence >= 0.9) return "Automatizar";
  return "Assistir";
}
