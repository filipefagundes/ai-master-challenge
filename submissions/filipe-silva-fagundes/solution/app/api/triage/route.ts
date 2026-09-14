import { NextResponse } from "next/server";
import cases from "@/data/cases.json";

export const runtime = "nodejs";

const categoryPrototypes = [
  { label: "Hardware", text: "physical device computer laptop screen keyboard mouse printer battery broken hardware" },
  { label: "HR Support", text: "employee payroll vacation benefits onboarding human resources work contract" },
  { label: "Access", text: "login password account authentication permission access locked user" },
  { label: "Miscellaneous", text: "general question unknown request other help information" },
  { label: "Storage", text: "disk storage quota drive files backup capacity space" },
  { label: "Purchase", text: "buy purchase order vendor invoice procurement quote payment" },
  { label: "Internal Project", text: "internal project application development deployment team initiative" },
  { label: "Administrative rights", text: "administrator admin rights elevated privileges installation permission" },
];

const schema = {
  type: "object",
  additionalProperties: false,
  properties: {
    operationalType: { type: "string", enum: ["Problema técnico", "Cobrança", "Reembolso", "Cancelamento", "Dúvida de produto"] },
    priority: { type: "string", enum: ["Baixa", "Média", "Alta", "Crítica"] },
    confidence: { type: "number", minimum: 0, maximum: 1 },
    owner: { type: "string" },
    rationale: { type: "string" },
    draftReply: { type: "string" },
    safeguards: { type: "array", items: { type: "string" }, minItems: 2, maxItems: 4 },
  },
  required: ["operationalType", "priority", "confidence", "owner", "rationale", "draftReply", "safeguards"],
};

function sanitize(text: string) {
  return text
    .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g, "[email removido]")
    .replace(/\b\d{5,}\b/g, "[número removido]")
    .slice(0, 2500);
}

function cosine(a: number[], b: number[]) {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let index = 0; index < a.length; index += 1) {
    dot += a[index] * b[index];
    normA += a[index] ** 2;
    normB += b[index] ** 2;
  }
  return dot / (Math.sqrt(normA) * Math.sqrt(normB) || 1);
}

function enforcedDecision(priority: string, confidence: number, type: string) {
  if (priority === "Crítica" || confidence < 0.72) return "Humano" as const;
  if (["Cobrança", "Reembolso", "Cancelamento"].includes(type)) return "Assistir" as const;
  if (priority === "Baixa" && confidence >= 0.9) return "Automatizar" as const;
  return "Assistir" as const;
}

function demoResult(text: string) {
  const normalized = text.toLowerCase();
  const billing = /cobran|cartão|fatura|pagamento|estorno/.test(normalized);
  const cancellation = /cancel/.test(normalized);
  const refund = /reembols|estorno/.test(normalized);
  const technical = /erro|bug|não funciona|falha|acesso|senha/.test(normalized);
  const operationalType = cancellation ? "Cancelamento" : refund ? "Reembolso" : billing ? "Cobrança" : technical ? "Problema técnico" : "Dúvida de produto";
  const urgent = /urgente|amanhã|hoje|bloquead|duas vezes/.test(normalized);
  const priority = urgent ? "Alta" : "Média";
  const confidence = billing || cancellation || refund || technical ? 0.84 : 0.68;
  return {
    mode: "demo" as const,
    operationalType,
    routingTopic: billing ? "Purchase" : technical ? "Access" : "Miscellaneous",
    priority,
    decision: enforcedDecision(priority, confidence, operationalType),
    confidence,
    owner: billing ? "Financeiro N2" : technical ? "Suporte técnico" : "Atendimento geral",
    rationale: billing
      ? "Há impacto financeiro e urgência explícita. A IA prepara a resposta, mas um agente deve validar cobrança e estorno."
      : "A categoria tem sinal suficiente para roteamento, mas a resposta ainda precisa de confirmação humana.",
    draftReply: "Olá! Entendi o impacto e registrei seu caso para análise prioritária. Vou confirmar os dados necessários com a equipe responsável antes de qualquer alteração e retorno com o próximo passo pelo mesmo canal.",
    safeguards: ["Revisão humana antes do envio", "Nenhuma ação financeira automática", "Dados sensíveis mascarados"],
    similarCases: cases.slice(0, 3).map((item, index) => ({ id: item.id, subject: item.subject, type: item.type, similarity: 0.84 - index * 0.05 })),
  };
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const text = sanitize(String(body.text ?? "").trim());
    const channel = String(body.channel ?? "Email").slice(0, 30);
    if (text.length < 20) return NextResponse.json({ error: "Ticket curto demais para uma triagem confiável." }, { status: 400 });

    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) return NextResponse.json(demoResult(text));

    const caseCorpus = cases.map((item) => `${item.type}. ${item.subject}. ${item.description}`);
    const embeddingInput = [text, ...categoryPrototypes.map((item) => item.text), ...caseCorpus];
    const embeddingResponse = await fetch("https://api.openai.com/v1/embeddings", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: process.env.OPENAI_EMBEDDING_MODEL || "text-embedding-3-small",
        input: embeddingInput,
        dimensions: 512,
        encoding_format: "float",
      }),
    });
    if (!embeddingResponse.ok) throw new Error(`Embedding API respondeu ${embeddingResponse.status}.`);
    const embeddingPayload = await embeddingResponse.json();
    const vectors = embeddingPayload.data.map((item: { embedding: number[] }) => item.embedding);
    const queryVector = vectors[0];
    const categoryOffset = 1;
    const caseOffset = categoryOffset + categoryPrototypes.length;

    const routing = categoryPrototypes
      .map((item, index) => ({ ...item, similarity: cosine(queryVector, vectors[categoryOffset + index]) }))
      .sort((a, b) => b.similarity - a.similarity);
    const similarCases = cases
      .map((item, index) => ({ ...item, similarity: cosine(queryVector, vectors[caseOffset + index]) }))
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, 3);

    const context = similarCases
      .map((item) => `[${item.id}] tipo=${item.type}; assunto=${item.subject}; resolução=${item.resolution}`)
      .join("\n");

    const response = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: process.env.OPENAI_MODEL || "gpt-5.4-mini",
        store: false,
        reasoning: { effort: "low" },
        text: { format: { type: "json_schema", name: "support_triage", strict: true, schema } },
        instructions: [
          "Você é um copiloto de suporte conservador. Responda em português do Brasil.",
          "Classifique e sugira, mas não alegue ter executado estornos, cancelamentos ou alterações.",
          "Não invente políticas. Faça uma resposta curta que reconheça o problema e explique o próximo passo.",
          "Confiança mede clareza da classificação, não certeza sobre os fatos do cliente.",
        ].join(" "),
        input: `CANAL: ${channel}\nTICKET MASCARADO: ${text}\nTEMA MAIS PRÓXIMO NO DATASET 2: ${routing[0].label} (${routing[0].similarity.toFixed(3)})\nCASOS REAIS ANONIMIZADOS DO DATASET 1:\n${context}`,
      }),
    });
    if (!response.ok) throw new Error(`Responses API respondeu ${response.status}.`);
    const payload = await response.json();
    const outputText = payload.output_text || payload.output?.flatMap((item: { content?: Array<{ type: string; text?: string }> }) => item.content ?? []).find((item: { type: string }) => item.type === "output_text")?.text;
    if (!outputText) throw new Error("O modelo não retornou texto estruturado.");
    const result = JSON.parse(outputText);

    return NextResponse.json({
      mode: "live",
      model: payload.model,
      ...result,
      routingTopic: routing[0].label,
      decision: enforcedDecision(result.priority, result.confidence, result.operationalType),
      similarCases: similarCases.map((item) => ({ id: item.id, subject: item.subject, type: item.type, similarity: Number(item.similarity.toFixed(3)) })),
    });
  } catch (error) {
    console.error("triage_error", error instanceof Error ? error.message : error);
    return NextResponse.json({ error: "A triagem ao vivo falhou. Verifique a chave, os modelos configurados e tente novamente." }, { status: 502 });
  }
}
