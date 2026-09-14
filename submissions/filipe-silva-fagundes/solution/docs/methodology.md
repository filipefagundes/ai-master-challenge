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

CSAT é descrito apenas no subconjunto fechado. Para os fatores canal, tipo, prioridade, assunto e produto, foi calculado eta-quadrado. Todos os efeitos ficaram abaixo de 0,015; o maior, Produto (η²=0,01324), permanece desprezível. Isso não demonstra ausência de drivers em uma operação real.

Também foi auditada a hipótese de concentração de backlog. As 80 combinações de canal × tipo × prioridade têm ao menos 80 tickets. O maior desvio observado foi z=2,94; em 20 mil simulações sob ausência de associação, um máximo ao menos tão extremo ocorreu em 23,4% dos cenários. O status não apresentou associação com canal (V=0,0139; p=0,771), tipo (V=0,0231; p=0,339) ou prioridade (V=0,0219; p=0,227). Assim, rankings por volume permanecem descritivos, mas não identificam um gargalo estatisticamente defensável.

As descrições têm 8.077 strings completas distintas, porém apenas 16 frases iniciais; 69,3% começam com o mesmo template. A associação entre essa frase e `Ticket Type` é V=0,0346, p=0,9746, comparável ao controle com rótulos embaralhados (V=0,0417, p=0,5154). Essa formulação corrige a imprecisão de chamar as descrições completas de “16 textos distintos”.

## Validação do Dataset 2

Foi criado um baseline Multinomial Naive Bayes com tokenização por palavras e suavização de Laplace. A divisão foi estratificada em 80% treino e 20% teste, com seed 42.

- Treino: 38.268 tickets.
- Teste: 9.569 tickets.
- Vocabulário: 11.610 termos.
- Acurácia: 0,769.
- Macro F1: 0,766.

Tokens fora do vocabulário de treino são ignorados na avaliação, evitando favorecer classes com menor total de tokens. O baseline não é apresentado como o modelo de produção. Ele serve para mostrar que há sinal classificável, expor diferenças entre categorias e estabelecer uma referência reproduzível para a camada de embeddings + LLM.

O retrieval do protótipo usa 200 textos do treino do Dataset 2, com amostra determinística de 25 por categoria. Nenhuma `Resolution` do Dataset 1 é enviada ao LLM, pois esse campo contém texto sintético sem valor de precedente.

## Política de decisão

A saída do LLM não controla a automação sozinha. Flags de risco são extraídos do texto original, antes da inferência, e uma regra determinística aplica:

- `Crítica` ou confiança abaixo de 0,72: humano.
- Sinal financeiro ou cancelamento no texto original: no máximo assistido.
- Segurança, perda de dados, jurídico ou acesso privilegiado: humano.
- Baixa prioridade, confiança a partir de 0,90 e intenção de baixo risco confirmada por regra: elegível à automação.
- Demais casos: assistido.

Tentativas explícitas de prompt injection são bloqueadas antes do envio ao provedor. O ticket é delimitado como conteúdo não confiável e a política nunca usa apenas a classe sugerida pelo LLM para liberar automação.

## Avaliação da camada entregue

O script `scripts/evaluate_live.py` seleciona 300 exemplos estratificados do mesmo holdout, sem cherry-picking, e gera o manifesto de avaliação. A rota devolve `routingTopic` dentro do Structured Output, depois de receber o candidato e os vizinhos dos embeddings; assim, a métrica cobre a camada combinada entregue. A execução contra a rota pública é separada porque consome API paga. Antes do PR final, deve ser rodada com autorização e os resultados — favoráveis ou não — comparados ao baseline.

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
