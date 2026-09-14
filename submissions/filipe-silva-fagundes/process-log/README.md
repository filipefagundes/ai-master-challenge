# Process Log

## Ferramentas usadas

| Ferramenta | Uso |
|---|---|
| ChatGPT / Codex | Decomposição do problema, auditoria, implementação, testes e documentação |
| Python + pandas | Leitura dos ZIPs, validação, agregações e baseline reproduzível |
| OpenAI API | Arquitetura do protótipo para embeddings e triagem estruturada |
| Next.js | Aplicação, rota server-side e preparação para deploy |
| Navegador automatizado | Revisão visual, acessibilidade, responsividade e teste do fluxo |

## Workflow

### 1. Entendimento antes da implementação

O README geral, o Challenge 002, o guia de submissão e as regras do PR foram lidos. O problema foi dividido em diagnóstico, automação, protótipo, ROI e evidência do processo.

### 2. Auditoria dos arquivos reais

A primeira leitura dos ZIPs mostrou 8.469 tickets operacionais e 47.837 tickets classificados. Antes de criar gráficos, foram validados tipos, nulos, datas, status, duplicatas e qualidade textual.

### 3. Correção de uma hipótese perigosa

A descrição do challenge chama `First Response Time` e `Time to Resolution` de tempos. A hipótese inicial era transformá-los em durações. A verificação mostrou que são timestamps, não há criação do ticket e 49,3% dos intervalos entre resposta e resolução são negativos. A decisão foi bloquear os KPIs de SLA em vez de aplicar valor absoluto, descartar casos ou inventar uma data de abertura.

### 4. Diagnóstico recuperável

Foram mantidas métricas defensáveis: volume, status, backlog, distribuição por dimensões e CSAT apenas entre fechados. O ROI virou um cenário editável com premissas expostas.

### 5. Baseline sem cherry-picking

Foi implementado um Multinomial Naive Bayes simples, sem dependências de machine learning, com split 80/20 estratificado. O resultado foi 76,8% de acurácia e macro F1 0,765. A análise por classe revelou risco maior em `Administrative rights`.

### 6. Desenho da automação

A proposta foi separada em automatizar, assistir e escalar. Confiança baixa, criticidade e ações financeiras limitam a decisão independentemente do texto gerado pelo LLM.

### 7. Construção e revisão visual

O protótipo foi construído como uma sala de decisão operacional. A interface foi revisada em desktop e viewport móvel. O fluxo de triagem foi executado ponta a ponta no modo demonstração e a API foi testada por HTTP.

## Onde a IA errou e como corrigi

- **Interpretação dos campos de tempo:** o enunciado favorecia tratá-los como durações. A validação dos valores corrigiu a hipótese.
- **Escopo anual:** seria fácil tratar 8.469 linhas como 30 mil tickets. O produto distingue amostra observada de contexto anual.
- **Causalidade de satisfação:** uma associação descritiva poderia ser apresentada como causa. Foram calculados tamanhos de efeito e o texto foi limitado ao que a amostra suporta.
- **Automação excessiva:** a primeira arquitetura poderia deixar a saída do LLM decidir a ação. Uma política determinística passou a impor o limite final.
- **Modo sem credencial:** um protótipo poderia falhar silenciosamente ou simular IA. A interface identifica claramente o modo demonstração.

## O que adicionei além da geração da IA

- Critério de bloqueio para métricas inválidas.
- Separação explícita entre dado observado, cenário e hipótese.
- Taxonomia de risco independente da taxonomia de classificação.
- Política de abstention e rebaixamento da automação.
- Tratamento de PII antes da chamada externa.
- Avaliação com holdout completo, por classe e sem exemplos escolhidos manualmente.
- Plano de piloto com grupo de controle e métricas de segurança.

## Iterações registradas

1. Leitura e decomposição do brief.
2. Descoberta da divergência de volume.
3. Descoberta das sequências temporais negativas.
4. Redefinição do diagnóstico para backlog e qualidade.
5. Baseline reproduzível de classificação.
6. Arquitetura LLM + embeddings + política determinística.
7. Interface operacional e simulador.
8. Testes de compilação, API, acessibilidade e responsividade.

O histórico Git complementa esta narrativa com os artefatos e verificações executadas.
