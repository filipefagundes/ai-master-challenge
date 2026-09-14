# Process Log

## Ferramentas usadas

| Ferramenta | Uso |
|---|---|
| ChatGPT / Codex | Decomposição do problema, auditoria, implementação, testes e documentação |
| Claude Code | Code review independente da branch antes da abertura do PR |
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

### 8. Ativação e validação ao vivo

A chave foi cadastrada como Secret na Vercel, sem entrar no código ou no chat. Após novo deploy, o endpoint público retornou `mode: live`, executou embeddings, recuperou três casos anonimizados e gerou triagem estruturada com o snapshot `gpt-5.4-mini-2026-03-17`. Um caso fictício de cobrança duplicada foi classificado como reembolso de alta prioridade e permaneceu no modo assistido por envolver ação financeira.

### 9. Code review independente com Claude Code

Antes de abrir o PR, a branch publicada foi revisada com Claude Code. A revisão encontrou fragilidades reais e também forneceu hipóteses que foram reproduzidas nos dados antes de serem incorporadas.

| Achado da revisão | Decisão e evidência aplicada |
|---|---|
| Prompt injection poderia influenciar os campos usados pela política | Corrigido: flags vêm do texto original; injection é bloqueada antes da API; automação exige intenção de baixo risco independente do modelo |
| CPF, cartão, telefone e RG escapavam da máscara | Corrigido com padrões brasileiros, Luhn e testes automatizados |
| Retrieval usava 15 casos e `Resolution` sintética do Dataset 1 | Corrigido para 200 textos do treino do Dataset 2, 25 por categoria; resoluções removidas |
| Produto entregue não tinha avaliação própria | Protocolo de 300 exemplos estratificados preparado; execução mantida pendente de autorização por consumir API paga |
| Texto dizia η² abaixo de 0,01 | Corrigido para abaixo de 0,015, explicitando Produto=0,01324 |
| “Maior backlog” ignorava múltiplas comparações | Corrigido com 20 mil simulações: z máximo 2,94, p familiar 0,234; nenhuma concentração defensável |
| Corpus fixo era re-embedado em toda chamada | Corrigido com cache por instância quente; cold start permanece documentado |
| Naive Bayes pontuava termos fora do vocabulário | Corrigido; acurácia passou de 0,768 para 0,769 e macro F1 de 0,765 para 0,766 |
| Similaridades do modo demo eram números inventados | Corrigido: o demo exibe “sem score” |
| Regra `/duas vezes/` estava ajustada ao exemplo | Removida; urgência agora usa sinais operacionais gerais |
| `.env.example` podia ser ignorado por `.env*` | Corrigido com exceção explícita |
| `frame.iloc` repetido degradava o script | Corrigido com conversão prévia das colunas para listas |

A revisão mencionava “16 descrições distintas”. A reprodução mostrou 8.077 descrições completas, mas exatamente 16 **frases iniciais**, com 69,3% no mesmo template. A documentação usa a formulação reproduzida. O controle embaralhado também foi recalculado com a seed declarada, por isso seus números podem diferir da execução do revisor.

## Onde a IA errou e como corrigi

- **Interpretação dos campos de tempo:** o enunciado favorecia tratá-los como durações. A validação dos valores corrigiu a hipótese.
- **Escopo anual:** seria fácil tratar 8.469 linhas como 30 mil tickets. O produto distingue amostra observada de contexto anual.
- **Causalidade de satisfação:** uma associação descritiva poderia ser apresentada como causa. Foram calculados tamanhos de efeito e o texto foi limitado ao que a amostra suporta.
- **Automação excessiva:** a primeira arquitetura ainda usava classe, prioridade e confiança sugeridas pelo LLM. Após o review, risco passou a ser derivado do texto original e prompt injection passou a bloquear a chamada externa.
- **Modo sem credencial:** um protótipo poderia falhar silenciosamente ou simular IA. A interface identifica claramente o modo demonstração.

## O que adicionei além da geração da IA

- Critério de bloqueio para métricas inválidas.
- Separação explícita entre dado observado, cenário e hipótese.
- Taxonomia de risco independente da taxonomia de classificação.
- Política de abstention e rebaixamento da automação.
- Tratamento de PII brasileira antes da chamada externa, coberto por testes.
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
9. Deploy e validação da integração LLM + embeddings em produção.
10. Code review independente com Claude Code.
11. Hardening de segurança, retrieval, estatística, performance e testes.

O histórico Git complementa esta narrativa com os artefatos e verificações executadas.
