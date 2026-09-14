"use client";

import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bot,
  Check,
  ChevronDown,
  CircleDollarSign,
  Database,
  Gauge,
  Headphones,
  LoaderCircle,
  LockKeyhole,
  MessageSquareText,
  Route,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
} from "lucide-react";
import { useMemo, useState } from "react";

type GroupRow = {
  label: string;
  tickets: number;
  share: number;
  backlog: number;
  backlogRate: number;
  closed: number;
  csat: number | null;
};

type Analysis = {
  overview: {
    supportRows: number;
    classifiedRows: number;
    closedTickets: number;
    backlogTickets: number;
    backlogRate: number;
    ratedTickets: number;
    meanCsat: number;
  };
  dataQuality: Array<{
    id: string;
    severity: string;
    metric: string;
    title: string;
    detail: string;
  }>;
  dimensions: Record<string, GroupRow[]>;
  satisfaction: {
    effects: Array<{ factor: string; etaSquared: number }>;
    interpretation: string;
  };
  associationAudit: {
    textTemplateVsTicketType: { cramersV: number; pValue: number };
    shuffledControl: { cramersV: number; pValue: number };
    firstSentenceTemplates: number;
    dominantTemplateShare: number;
    statusByDimension: Array<{ factor: string; cramersV: number; pValue: number }>;
    multipleComparisons: {
      combinationsTested: number;
      maxObservedZ: number;
      expectedMaxZ: number;
      chance95UpperZ: number;
      familyWisePValue: number;
    };
    interpretation: string;
  };
  topicDataset: {
    rows: number;
    categories: Array<{ label: string; tickets: number; share: number }>;
  };
  benchmark: {
    method: string;
    purpose: string;
    split: string;
    trainRows: number;
    testRows: number;
    accuracy: number;
    macroF1: number;
    perClass: Array<{ label: string; precision: number; recall: number; f1: number; support: number }>;
  };
  roiDefaults: {
    annualTickets: number;
    autoShare: number;
    assistShare: number;
    minutesAuto: number;
    minutesAssist: number;
    hourlyCostBrl: number;
  };
  methodology: { blockedMetrics: string[]; usableMetrics: string[] };
};

type TriageResult = {
  mode: "live" | "demo" | "guarded";
  model?: string;
  operationalType: string;
  routingTopic: string;
  routingSource: "naive_bayes" | "policy";
  routingConfidence: number;
  priority: string;
  decision: "Automatizar" | "Assistir" | "Humano";
  confidence: number;
  owner: string;
  rationale: string;
  draftReply: string;
  safeguards: string[];
  similarCases: Array<{ id: string; subject: string; type: string; similarity: number | null }>;
};

type EvaluationSummary = {
  summary: {
    llmAndEmbeddings: { completed: number; errors: number; accuracy: number; accuracyWilson95: number[]; macroF1: number };
    naiveBayesSame300: { completed: number; errors: number; accuracy: number; accuracyWilson95: number[]; macroF1: number };
    pairedComparison: { baselineCorrectLlmWrong: number; llmCorrectBaselineWrong: number; mcnemarExactPValue: number };
    modes: Record<string, number>;
  };
};

const formatNumber = new Intl.NumberFormat("pt-BR");
const formatMoney = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const dimensionLabels: Record<string, string> = {
  combinations: "Combinação",
  channels: "Canal",
  types: "Tipo",
  priorities: "Prioridade",
  subjects: "Assunto",
};

const exampleTicket =
  "Fiz a cobrança da assinatura duas vezes este mês e ainda não recebi o estorno. Preciso de ajuda porque o fechamento do cartão é amanhã.";

export default function SupportCockpit({ analysis, evaluation }: { analysis: Analysis; evaluation: EvaluationSummary }) {
  const [view, setView] = useState<"operation" | "triage" | "method">("operation");
  const [dimension, setDimension] = useState("types");
  const [annualTickets, setAnnualTickets] = useState(analysis.roiDefaults.annualTickets);
  const [hourlyCost, setHourlyCost] = useState(analysis.roiDefaults.hourlyCostBrl);
  const [ticket, setTicket] = useState(exampleTicket);
  const [channel, setChannel] = useState("Email");
  const [triageResult, setTriageResult] = useState<TriageResult | null>(null);
  const [triageError, setTriageError] = useState("");
  const [loading, setLoading] = useState(false);

  const roi = useMemo(() => {
    const autoHours =
      (annualTickets * analysis.roiDefaults.autoShare * analysis.roiDefaults.minutesAuto) / 60;
    const assistHours =
      (annualTickets * analysis.roiDefaults.assistShare * analysis.roiDefaults.minutesAssist) / 60;
    return {
      hours: Math.round(autoHours + assistHours),
      value: Math.round((autoHours + assistHours) * hourlyCost),
      monthlyHours: Math.round((autoHours + assistHours) / 12),
    };
  }, [annualTickets, hourlyCost, analysis.roiDefaults]);

  const rows = analysis.dimensions[dimension];
  const maxBacklog = Math.max(...rows.map((row) => row.backlog));

  async function runTriage() {
    if (ticket.trim().length < 20) {
      setTriageError("Descreva o problema em pelo menos 20 caracteres.");
      return;
    }
    setLoading(true);
    setTriageError("");
    try {
      const response = await fetch("/api/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: ticket, channel }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Não foi possível analisar o ticket.");
      setTriageResult(payload);
    } catch (error) {
      setTriageError(error instanceof Error ? error.message : "Falha inesperada na triagem.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="shell">
      <aside className="rail">
        <button className="brand" onClick={() => setView("operation")} aria-label="Ir para visão geral">
          <span className="brand-mark">S</span>
          <span>
            <strong>Sinal</strong>
            <small>Support intelligence</small>
          </span>
        </button>

        <nav aria-label="Navegação principal">
          <button className={view === "operation" ? "active" : ""} onClick={() => setView("operation")}>
            <BarChart3 size={18} /> Operação
          </button>
          <button className={view === "triage" ? "active" : ""} onClick={() => setView("triage")}>
            <Sparkles size={18} /> Triagem IA
          </button>
          <button className={view === "method" ? "active" : ""} onClick={() => setView("method")}>
            <ShieldCheck size={18} /> Método
          </button>
        </nav>

        <div className="rail-status">
          <span className="pulse" />
          <div>
            <strong>{analysis.overview.supportRows.toLocaleString("pt-BR")} tickets auditados</strong>
            <small>Dataset 1 carregado</small>
          </div>
        </div>
        <div className="rail-footer">Challenge 002<br />Filipe Silva Fagundes</div>
      </aside>

      <main>
        <header className="topbar">
          <div className="mobile-brand">Sinal / 002</div>
          <div className="context">
            <span>Operações de suporte</span>
            <strong>{view === "operation" ? "Diagnóstico" : view === "triage" ? "Bancada de triagem" : "Evidências e limites"}</strong>
          </div>
          <div className="scope-pill"><Database size={14} /> 56.306 registros analisados</div>
        </header>

        {view === "operation" && (
          <div className="page">
            <section className="decision-hero">
              <div className="hero-copy">
                <span className="section-kicker">Decisão recomendada</span>
                <h1>Começar pela triagem. Não prometer SLA com este dado.</h1>
                <p>
                  A amostra permite atacar o backlog e validar classificação, mas não mede tempo de
                  resposta com integridade. A automação entra primeiro como copiloto, com saída humana
                  obrigatória nos casos de risco.
                </p>
                <button className="text-action" onClick={() => setView("triage")}>
                  Testar a decisão com um ticket <ArrowRight size={17} />
                </button>
              </div>
              <div className="hero-signal" aria-label={`${analysis.overview.backlogRate}% dos tickets estão em backlog`}>
                <div className="signal-ring" style={{ "--progress": `${analysis.overview.backlogRate * 3.6}deg` } as React.CSSProperties}>
                  <div><strong>{analysis.overview.backlogRate}%</strong><span>sem resolução</span></div>
                </div>
                <p>{formatNumber.format(analysis.overview.backlogTickets)} tickets abertos ou aguardando cliente</p>
              </div>
            </section>

            <section className="metric-strip">
              <Metric label="Amostra operacional" value={formatNumber.format(analysis.overview.supportRows)} note="tickets no CSV" />
              <Metric label="Base classificada" value={formatNumber.format(analysis.overview.classifiedRows)} note="textos em 8 temas" />
              <Metric label="CSAT observado" value={`${analysis.overview.meanCsat}/5`} note="somente fechados" />
              <Metric label="Acurácia do baseline" value={`${Math.round(analysis.benchmark.accuracy * 100)}%`} note={`${formatNumber.format(analysis.benchmark.testRows)} tickets de teste`} />
            </section>

            <section className="panel bottleneck-panel">
              <div className="panel-heading">
                <div>
                  <span className="section-kicker">Onde o fluxo acumula</span>
                  <h2>Backlog por recorte operacional</h2>
                </div>
                <label className="select-wrap">
                  <span>Comparar por</span>
                  <select value={dimension} onChange={(event) => setDimension(event.target.value)}>
                    {Object.entries(dimensionLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                  </select>
                  <ChevronDown size={15} />
                </label>
              </div>
              <div className="bar-table" role="table" aria-label={`Backlog por ${dimensionLabels[dimension]}`}>
                <div className="bar-row bar-head" role="row">
                  <span>Grupo</span><span>Backlog</span><span>Taxa</span><span>CSAT</span>
                </div>
                {rows.slice(0, dimension === "subjects" || dimension === "combinations" ? 8 : 10).map((row) => (
                  <div className="bar-row" role="row" key={row.label}>
                    <div className="bar-label"><strong>{row.label}</strong><small>{formatNumber.format(row.tickets)} tickets</small></div>
                    <div className="bar-value">
                      <span style={{ width: `${(row.backlog / maxBacklog) * 100}%` }} />
                      <strong>{formatNumber.format(row.backlog)}</strong>
                    </div>
                    <span>{row.backlogRate.toFixed(1)}%</span>
                    <span>{row.csat?.toFixed(2) ?? "n.d."}</span>
                  </div>
                ))}
              </div>
              <p className="source-note">Fonte: Dataset 1. “Backlog” = Open + Pending Customer Response. Recortes descritivos; o teste conjunto não encontrou concentração além do acaso.</p>
            </section>

            <div className="two-column">
              <section className="panel runway-panel">
                <div className="panel-heading">
                  <div><span className="section-kicker">Política de automação</span><h2>Três pistas, um limite claro</h2></div>
                </div>
                <div className="runway">
                  <RunwayRow tone="auto" icon={<Bot size={18} />} share="25%" label="Automatizar" detail="Alta confiança, baixo risco, resposta reversível" />
                  <RunwayRow tone="assist" icon={<Headphones size={18} />} share="45%" label="Assistir" detail="IA classifica e redige; agente confirma" />
                  <RunwayRow tone="human" icon={<UserRoundCheck size={18} />} share="30%" label="Humano" detail="Crítico, financeiro sensível, baixa confiança" />
                </div>
                <p className="source-note">Percentuais são premissas de piloto, não resultado observado.</p>
              </section>

              <section className="panel roi-panel">
                <div className="panel-heading">
                  <div><span className="section-kicker">Cenário editável</span><h2>Capacidade recuperável</h2></div>
                  <CircleDollarSign size={24} />
                </div>
                <div className="roi-result"><strong>{formatNumber.format(roi.hours)} h</strong><span>por ano</span></div>
                <p>{formatNumber.format(roi.monthlyHours)} horas/mês · {formatMoney.format(roi.value)} de capacidade anual</p>
                <div className="assumptions">
                  <label>Tickets/ano<input type="number" min="1000" step="1000" value={annualTickets} onChange={(e) => setAnnualTickets(Number(e.target.value))} /></label>
                  <label>Custo/hora<input type="number" min="1" step="5" value={hourlyCost} onChange={(e) => setHourlyCost(Number(e.target.value))} /></label>
                </div>
                <p className="source-note">Cenário: 25% automatizados × 9 min + 45% assistidos × 4 min. Validar em piloto.</p>
              </section>
            </div>

            <section className="quality-section">
              <div className="section-heading-wide">
                <div><span className="section-kicker">Qualidade antes da velocidade</span><h2>{analysis.dataQuality.length} alertas mudam a leitura do case</h2></div>
                <button className="quiet-button" onClick={() => setView("method")}>Ver método completo</button>
              </div>
              <div className="quality-grid">
                {analysis.dataQuality.map((item) => (
                  <article className={`quality-item ${item.severity}`} key={item.id}>
                    <div><AlertTriangle size={18} /><strong>{item.metric}</strong></div>
                    <h3>{item.title}</h3><p>{item.detail}</p>
                  </article>
                ))}
              </div>
            </section>
          </div>
        )}

        {view === "triage" && (
          <div className="page triage-page">
            <section className="triage-intro">
              <span className="section-kicker">Protótipo funcional</span>
              <h1>Um ticket entra. A IA propõe. A política decide.</h1>
              <p>Naive Bayes roteia. Embeddings recuperam casos apenas dentro do tema. O LLM estrutura a assistência e redige uma resposta; a política controla a ação.</p>
            </section>

            <div className="triage-grid">
              <section className="ticket-composer panel">
                <div className="composer-head"><MessageSquareText size={20} /><strong>Novo ticket</strong><span>Entrada não estruturada</span></div>
                <label className="field-label">Mensagem do cliente</label>
                <textarea value={ticket} onChange={(e) => setTicket(e.target.value)} maxLength={2500} />
                <div className="composer-meta">
                  <label className="select-wrap"><span>Canal</span><select value={channel} onChange={(e) => setChannel(e.target.value)}><option>Email</option><option>Chat</option><option>Phone</option><option>Social media</option></select><ChevronDown size={15} /></label>
                  <span>{ticket.length}/2.500</span>
                </div>
                {triageError && <p className="error-message">{triageError}</p>}
                <button className="primary-button" disabled={loading} onClick={runTriage}>
                  {loading ? <LoaderCircle className="spin" size={18} /> : <Sparkles size={18} />}
                  {loading ? "Analisando contexto" : "Executar triagem"}
                </button>
                <div className="privacy-note"><LockKeyhole size={15} /> E-mail, CPF, CNPJ, RG, telefone, CEP e cartão são mascarados no servidor. A chave nunca vai para o navegador.</div>
              </section>

              <section className={`triage-output panel ${triageResult ? "has-result" : ""}`} aria-live="polite">
                {!triageResult ? (
                  <div className="empty-result"><Route size={34} /><h2>A rota aparecerá aqui</h2><p>Teste o exemplo ou cole um ticket. Sem chave configurada, a aplicação sinaliza e executa uma demonstração determinística.</p></div>
                ) : (
                  <>
                    <div className="result-head">
                      <div><span className={`mode-badge ${triageResult.mode}`}>{triageResult.mode === "live" ? "Arquitetura híbrida ao vivo" : triageResult.mode === "guarded" ? "Bloqueado pela política" : "Roteador local · modo demo"}</span><h2>{triageResult.operationalType}</h2></div>
                      <Confidence value={triageResult.confidence} />
                    </div>
                    <div className="routing-line">
                      <ResultField label={triageResult.routingSource === "naive_bayes" ? `Tema · Naive Bayes ${Math.round(triageResult.routingConfidence * 100)}%` : "Tema · política"} value={triageResult.routingTopic} />
                      <ResultField label="Prioridade" value={triageResult.priority} />
                      <ResultField label="Responsável" value={triageResult.owner} />
                    </div>
                    <div className={`decision-box ${triageResult.decision.toLowerCase()}`}>
                      <span>Decisão</span><strong>{triageResult.decision}</strong><p>{triageResult.rationale}</p>
                    </div>
                    <div className="draft"><span>Resposta sugerida</span><p>{triageResult.draftReply}</p><button onClick={() => navigator.clipboard?.writeText(triageResult.draftReply)}><Check size={15} /> Copiar rascunho</button></div>
                    <div className="evidence-row">
                      <div><span>Exemplos rotulados recuperados</span>{triageResult.similarCases.length ? triageResult.similarCases.map((item) => <p key={item.id}><strong>{item.id}</strong> {item.subject}<em>{item.similarity === null ? "sem score no demo" : `${Math.round(item.similarity * 100)}%`}</em></p>) : <p>Nenhum texto foi enviado ao modelo.</p>}</div>
                      <div><span>Controles aplicados</span>{triageResult.safeguards.map((item) => <p key={item}><ShieldCheck size={14} /> {item}</p>)}</div>
                    </div>
                  </>
                )}
              </section>
            </div>

            <section className="flow-map">
              <FlowStep icon={<MessageSquareText />} title="1. Entrada" text="Texto e canal" />
              <FlowStep icon={<Route />} title="2. Roteamento" text="Naive Bayes medido" />
              <FlowStep icon={<Database />} title="3. Recuperação" text="Embeddings no tema" />
              <FlowStep icon={<Sparkles />} title="4. Assistência" text="LLM + política" />
              <FlowStep icon={<UserRoundCheck />} title="5. Ação" text="Auto, assistido ou humano" />
            </section>
          </div>
        )}

        {view === "method" && (
          <div className="page method-page">
            <section className="method-hero"><span className="section-kicker">Método e evidências</span><h1>O dado define o que podemos afirmar.</h1><p>Esta camada separa observação, hipótese e cenário. O objetivo é impedir que precisão visual seja confundida com precisão analítica.</p></section>
            <div className="method-grid">
              <section className="panel evidence-panel">
                <span className="section-kicker">Dataset 1</span><h2>Diagnóstico operacional</h2>
                <EvidenceLine status="usable" title="Volume e backlog" text="Usáveis por canal, tipo, prioridade e assunto." />
                <EvidenceLine status="blocked" title="Tempos e SLA" text="Bloqueados: falta criação e 49,3% das sequências são negativas." />
                <EvidenceLine status="limited" title="Satisfação" text="Descritiva apenas entre fechados; não suporta inferência causal." />
              </section>
              <section className="panel evidence-panel">
                <span className="section-kicker">Dataset 2</span><h2>Validação de classificação</h2>
                <div className="benchmark-number"><strong>{Math.round(analysis.benchmark.accuracy * 100)}%</strong><span>acurácia holdout</span></div>
                <div className="benchmark-number secondary"><strong>{analysis.benchmark.macroF1.toFixed(3)}</strong><span>macro F1</span></div>
                <p>{analysis.benchmark.method}. {analysis.benchmark.split}. Sem escolher exemplos manualmente.</p>
              </section>
            </div>
            <section className="panel eval-panel">
              <div className="panel-heading">
                <div><span className="section-kicker">Avaliação em produção</span><h2>O baseline venceu o roteamento generativo</h2></div>
                <span className="eval-sample">{evaluation.summary.llmAndEmbeddings.completed}/300 chamadas válidas</span>
              </div>
              <div className="eval-comparison">
                <div className="eval-card underperforming">
                  <span>LLM + embeddings</span>
                  <strong>{(evaluation.summary.llmAndEmbeddings.accuracy * 100).toFixed(1)}%</strong>
                  <small>F1 {evaluation.summary.llmAndEmbeddings.macroF1.toFixed(3)} · IC95% {(evaluation.summary.llmAndEmbeddings.accuracyWilson95[0] * 100).toFixed(1)}–{(evaluation.summary.llmAndEmbeddings.accuracyWilson95[1] * 100).toFixed(1)}%</small>
                </div>
                <div className="eval-versus">vs.</div>
                <div className="eval-card baseline">
                  <span>Roteamento atual · Naive Bayes</span>
                  <strong>{(evaluation.summary.naiveBayesSame300.accuracy * 100).toFixed(1)}%</strong>
                  <small>F1 {evaluation.summary.naiveBayesSame300.macroF1.toFixed(3)} · IC95% {(evaluation.summary.naiveBayesSame300.accuracyWilson95[0] * 100).toFixed(1)}–{(evaluation.summary.naiveBayesSame300.accuracyWilson95[1] * 100).toFixed(1)}%</small>
                </div>
              </div>
              <p className="eval-verdict">Em pares discordantes, o baseline acertou sozinho {evaluation.summary.pairedComparison.baselineCorrectLlmWrong} tickets; a camada generativa, {evaluation.summary.pairedComparison.llmCorrectBaselineWrong}. McNemar exato p&lt;10⁻²⁰. Aplicado: Naive Bayes roteia; embeddings recuperam dentro do tema; LLM redige e assiste sob política.</p>
            </section>
            <section className="panel class-panel">
              <div className="panel-heading"><div><span className="section-kicker">Onde o modelo erra</span><h2>Desempenho por categoria</h2></div><Gauge size={24} /></div>
              <div className="class-list">
                {analysis.benchmark.perClass.map((item) => <div key={item.label}><strong>{item.label}</strong><span><i style={{ width: `${item.f1 * 100}%` }} /></span><em>F1 {item.f1.toFixed(3)}</em><small>n={formatNumber.format(item.support)}</small></div>)}
              </div>
              <p className="source-note">“Administrative rights” tem o menor F1. O piloto deve elevar o limiar de confiança ou exigir revisão humana nesse tema.</p>
            </section>
            <section className="panel csat-panel">
              <div><span className="section-kicker">Satisfação</span><h2>Não encontramos um driver material</h2><p>{analysis.satisfaction.interpretation}</p></div>
              <div className="effect-list">{analysis.satisfaction.effects.map((item) => <div key={item.factor}><span>{item.factor}</span><strong>{item.etaSquared.toFixed(4)}</strong></div>)}</div>
            </section>
            <section className="panel csat-panel">
              <div><span className="section-kicker">Controle estatístico</span><h2>O “maior backlog” é compatível com acaso</h2><p>{analysis.associationAudit.interpretation}</p></div>
              <div className="effect-list">
                <div><span>Combinações testadas</span><strong>{analysis.associationAudit.multipleComparisons.combinationsTested}</strong></div>
                <div><span>z máximo observado</span><strong>{analysis.associationAudit.multipleComparisons.maxObservedZ.toFixed(2)}</strong></div>
                <div><span>p familiar simulado</span><strong>{analysis.associationAudit.multipleComparisons.familyWisePValue.toFixed(3)}</strong></div>
                <div><span>Texto × tipo (V)</span><strong>{analysis.associationAudit.textTemplateVsTicketType.cramersV.toFixed(4)}</strong></div>
              </div>
            </section>
            <section className="limits">
              <div><h3>Pode orientar decisão</h3>{analysis.methodology.usableMetrics.map((item) => <p key={item}><Check size={15} />{item}</p>)}</div>
              <div><h3>Não pode virar promessa</h3>{analysis.methodology.blockedMetrics.map((item) => <p key={item}><AlertTriangle size={15} />{item}</p>)}</div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <div><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}

function RunwayRow({ tone, icon, share, label, detail }: { tone: string; icon: React.ReactNode; share: string; label: string; detail: string }) {
  return <div className={`runway-row ${tone}`}><div className="runway-icon">{icon}</div><strong>{share}</strong><div><b>{label}</b><span>{detail}</span></div></div>;
}

function Confidence({ value }: { value: number }) {
  return <div className="confidence"><span>assistência</span><strong>{Math.round(value * 100)}%</strong></div>;
}

function ResultField({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function FlowStep({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <div><span>{icon}</span><strong>{title}</strong><small>{text}</small></div>;
}

function EvidenceLine({ status, title, text }: { status: string; title: string; text: string }) {
  return <div className="evidence-line"><span className={status} /><div><strong>{title}</strong><p>{text}</p></div></div>;
}
