# Metodologia

## Perguntas de decisão

A análise foi organizada em quatro perguntas:

1. Quais recortes concentram tickets ainda não fechados?
2. A base permite medir tempo, SLA e desperdício observado?
3. Quais decisões podem ser assistidas ou automatizadas com risco controlado?
4. Como provar utilidade sem esconder os limites dos dados?

## Validação do Dataset 1

O script lê o ZIP diretamente e verifica volume, unicidade, valores ausentes, status, datas, texto e sequência temporal. “Backlog” foi definido como `Open + Pending Customer Response`. Ele mede estoque na amostra, não atraso.

As colunas `First Response Time` e `Time to Resolution` são timestamps. Não existe timestamp de abertura. Além disso, 1.365 dos 2.769 tickets fechados têm `Time to Resolution < First Response Time`. Dessa forma:

- tempo de primeira resposta é indisponível;
- tempo total de resolução é indisponível;
- comparações de SLA por grupo são bloqueadas;
- horas desperdiçadas não podem ser observadas diretamente.

CSAT é descrito apenas no subconjunto fechado. Para os fatores canal, tipo, prioridade, assunto e produto, foi calculado eta-quadrado. Todos os efeitos ficaram abaixo de 0,01, sem poder explicativo material na amostra. Isso não demonstra ausência de drivers em uma operação real.

## Validação do Dataset 2

Foi criado um baseline Multinomial Naive Bayes com tokenização por palavras e suavização de Laplace. A divisão foi estratificada em 80% treino e 20% teste, com seed 42.

- Treino: 38.268 tickets.
- Teste: 9.569 tickets.
- Vocabulário: 11.610 termos.
- Acurácia: 0,768.
- Macro F1: 0,765.

O baseline não é apresentado como o modelo de produção. Ele serve para mostrar que há sinal classificável, expor diferenças entre categorias e estabelecer uma referência reproduzível para a camada de embeddings + LLM.

## Política de decisão

A saída do LLM não controla a automação sozinha. Depois da inferência, uma regra determinística aplica:

- `Crítica` ou confiança abaixo de 0,72: humano.
- Cobrança, reembolso ou cancelamento: no máximo assistido.
- Baixa prioridade e confiança a partir de 0,90: elegível à automação.
- Demais casos: assistido.

Os limiares são hipóteses de piloto. Devem ser calibrados por categoria e custo do erro.

## Métricas do piloto

- Acurácia e macro F1 por categoria.
- Cobertura acima do limiar.
- Taxa de abstention.
- Override do agente por categoria e risco.
- Tempo ativo do agente por ticket.
- Transferência, reabertura e resolução no primeiro contato.
- CSAT e incidentes no grupo assistido contra controle.
- Custo de inferência por ticket e capacidade recuperada.
