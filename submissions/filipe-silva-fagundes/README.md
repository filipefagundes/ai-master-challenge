# Submissão — Filipe Silva Fagundes — Challenge 002

## Sobre mim

- **Nome:** Filipe Silva Fagundes
- **LinkedIn:** [linkedin.com/in/filipefagundes](https://www.linkedin.com/in/filipefagundes/)
- **Challenge escolhido:** 002 — Redesign de Suporte

## Executive Summary

Construí o **Sinal**, uma aplicação web que combina diagnóstico operacional, política de automação, simulador de capacidade e uma bancada de triagem com LLM e embeddings. A principal descoberta foi uma limitação estrutural: 49,3% dos tickets fechados registram a resolução antes da primeira resposta e o dataset não contém a criação do ticket. Por isso, o produto bloqueia métricas de SLA que seriam enganosas. Um baseline reproduzível atingiu 76,9% de acurácia no holdout completo. Em 300 tickets estratificados enviados à rota pública, a camada LLM + embeddings atingiu 41,0%, contra 77,7% do Naive Bayes nos mesmos exemplos. A decisão recomendada é usar o modelo simples para roteamento e reservar o LLM para redação e assistência sob política humana.

> **Aplicação pública:** [sinal-002.vercel.app](https://sinal-002.vercel.app)

## Solução

### O que foi construído

O Sinal tem três áreas:

1. **Operação:** backlog por combinação, canal, tipo, prioridade ou assunto; qualidade dos dados; política de automação e cenário de ROI.
2. **Triagem IA:** recebe texto e canal, mascara dados sensíveis, recupera casos similares com embeddings, classifica com LLM e aplica uma política determinística de risco.
3. **Método:** mostra o que os dados permitem afirmar, o que foi bloqueado e os erros do classificador por categoria.

O protótipo usa os dois datasets de maneira complementar:

- O Dataset 1 sustenta volume, backlog, satisfação descritiva e a auditoria de qualidade operacional.
- O Dataset 2 sustenta o baseline supervisionado e um corpus de retrieval com 200 textos, 25 por categoria, separado do holdout.

### Findings principais

| Finding | Evidência | Consequência |
|---|---:|---|
| Backlog elevado na amostra | 5.700 de 8.469 tickets, ou 67,3% | Priorizar triagem, roteamento e visibilidade da fila |
| Tempos operacionais inválidos | 1.365 de 2.769 fechados têm intervalo negativo | Não calcular SLA nem “tempo economizado observado” |
| CSAT incompleto | Nota somente nos 2.769 tickets fechados | Evitar comparação com backlog e alegação causal |
| Texto sintético | 100% das descrições contêm `{product_purchased}` | Validar o piloto com tickets reais antes de produção |
| Rótulos operacionais sem sinal defensável | Texto × tipo: V=0,0346; p=0,9746 | Não inferir gargalo por canal, tipo ou prioridade nesta amostra |
| Classificação é viável, mas não perfeita | 76,9% de acurácia e macro F1 0,766 | Usar confiança, abstention e revisão humana |
| Direitos administrativos são o maior risco do baseline | F1 0,650 | Exigir revisão humana ou limiar mais alto nessa categoria |
| LLM não justifica o roteamento | 41,0% vs. 77,7% do baseline nos mesmos 300 tickets | Baseline roteia; LLM redige e assiste |

Foram testadas as 80 combinações de canal × tipo × prioridade. O maior desvio observado (z=2,94) é compatível com acaso após considerar a família de testes (p simulado=0,234; 20 mil cenários). Status também é independente de canal (V=0,0139; p=0,771), tipo (p=0,339) e prioridade (p=0,227). Portanto, a amostra não sustenta a narrativa de um gargalo específico.

### O que automatizar

- Classificação e roteamento inicial.
- Recuperação de textos rotulados semelhantes do Dataset 2.
- Detecção de baixa confiança e encaminhamento.
- Sugestão de prioridade.
- Rascunho de resposta para revisão.
- Respostas automáticas apenas quando a política for conhecida, o risco for baixo e a confiança superar o limiar do piloto.

### O que não automatizar

- Estornos, cancelamentos, alteração de cobrança ou qualquer ação financeira.
- Tickets críticos ou com baixa confiança.
- Concessões comerciais e exceções de política.
- Segurança, privacidade, direitos administrativos e perda de dados.
- Casos sem evidência suficiente na base de conhecimento.

### Fluxo proposto

```text
Ticket recebido
   ↓
Mascaramento de PII
   ↓
Embeddings: tema próximo + exemplos rotulados do Dataset 2
   ↓
LLM: classificação, prioridade, responsável e rascunho
   ↓
Política determinística de confiança e risco
   ├── baixo risco + alta confiança → automatizar
   ├── risco moderado              → agente confirma
   └── crítico/baixa confiança     → especialista humano
   ↓
Feedback do agente retorna para avaliação e melhoria
```

### ROI como cenário, não como fato

O app parte de uma hipótese editável para 30 mil tickets anuais:

- 25% automatizados, poupando 9 minutos por ticket.
- 45% assistidos, poupando 4 minutos por ticket.
- Custo de capacidade de R$ 45/hora.

O cenário resulta em **2.025 horas/ano** e **R$ 91.125/ano** de capacidade recuperada. Esses valores não foram observados nos dados e só devem virar business case após um piloto medir tempo antes/depois, taxa de override, reabertura e CSAT.

## Como executar

Pré-requisitos: Node.js 20.9+ e Python com `pandas` apenas para regenerar a análise.

```bash
cd submissions/filipe-silva-fagundes/solution
npm install
cp .env.example .env.local
npm run dev
```

Configure `OPENAI_API_KEY` no `.env.local`. A chave é usada somente pela rota server-side. Sem chave, o protótipo entra em modo demonstração e identifica isso na interface. A versão pública está configurada e foi validada com LLM e embeddings ao vivo.

Para reproduzir os números a partir dos ZIPs baixados do Kaggle:

```bash
python scripts/analyze.py --data-dir ../../../ --output-dir data
```

Mais detalhes em [metodologia](./docs/methodology.md), [arquitetura](./docs/architecture.md) e [deploy](./docs/deployment.md).

## Recomendações

1. Instrumentar criação, primeira resposta, resolução, reabertura, transferência e tempo ativo de agente.
2. Rodar um piloto de quatro semanas com 10% da fila e grupo de controle.
3. Usar o Naive Bayes para roteamento e manter o LLM no modo assistido para rascunhos; medir override, tempo e incidentes.
4. Liberar automação por política, nunca apenas pela classe prevista.
5. Monitorar drift, custo por ticket e erros de alto risco antes de ampliar cobertura.

## Limitações

- O Dataset 1 tem 8.469 registros, não os aproximadamente 30 mil descritos no contexto.
- Não existe timestamp de criação e os timestamps restantes são inconsistentes.
- A satisfação só existe em tickets fechados e não permite conclusão causal.
- Os datasets têm taxonomias e contextos diferentes; não há chave para cruzamento linha a linha.
- A avaliação de 300 tickets mede `routingTopic` na taxonomia do Dataset 2; não mede a qualidade textual dos rascunhos nem resultados operacionais reais.
- O IC95% da camada LLM + embeddings foi 35,6%–46,6%; o do baseline nos mesmos exemplos, 72,6%–82,0%. A diferença pareada favoreceu o baseline (129 acertos exclusivos contra 19; McNemar exato p=2,77×10⁻²¹).
- O cenário de ROI depende de premissas editáveis e não substitui um experimento operacional.

## Process Log — Como usei IA

O registro completo está em [process-log/README.md](./process-log/README.md). O histórico Git preserva a evolução de auditoria, protótipo, documentação e validação.

## Evidências

- [x] Narrativa escrita do processo
- [x] Script reproduzível de análise
- [x] Holdout de 9.569 exemplos, sem cherry-picking
- [x] Git history com evolução da solução
- [x] Aplicação funcional e responsiva
- [x] Integração pública com LLM e embeddings validada ao vivo
- [x] Code review independente com Claude Code e correções registradas
- [x] Avaliação da rota pública em 300 exemplos estratificados, sem erros de execução
- [x] Link público — publicado na Vercel
- [ ] Gravação curta do fluxo — recomendada antes do PR final

_Submissão preparada em: 14/09/2026_
