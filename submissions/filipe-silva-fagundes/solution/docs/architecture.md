# Arquitetura

## Componentes

```text
Next.js App Router
├── Dashboard estático
│   └── analysis.json agregado e reproduzível
├── Bancada de triagem no navegador
└── POST /api/triage
    ├── validação e mascaramento de PII
    ├── Naive Bayes compilado do treino do Dataset 2
    ├── OpenAI Embeddings API
    │   └── 200 textos de treino do Dataset 2 (25 por tema)
    ├── similaridade por cosseno, filtrada pelo tema previsto
    ├── OpenAI Responses API com JSON Schema para assistência e rascunho
    └── política determinística de risco
```

## Uso dos datasets

O repositório não publica nomes, e-mails, idade ou gênero. O script gera apenas agregados e 200 textos já processados do Dataset 2. Cada identificador público é um hash não reversível do índice original.

O Dataset 2 e o Dataset 1 não são combinados por `join`. A integração ocorre no fluxo:

- Dataset 2 fornece taxonomia, roteador Naive Bayes e corpus de retrieval estratificado, retirado apenas do treino.
- Dataset 1 fornece taxonomia operacional, diagnóstico e auditoria de qualidade; suas resoluções sintéticas não entram no prompt.
- O Naive Bayes define `routingTopic`; embeddings recuperam vizinhos apenas nesse tema; o LLM produz os demais campos estruturados e o rascunho.

## Segurança e confiabilidade

- `OPENAI_API_KEY` existe somente no servidor.
- A API mascara e-mail, CPF, CNPJ, RG, telefone, CEP e cartão (com validação Luhn) antes do envio.
- `store: false` é enviado à Responses API.
- A entrada é limitada a 2.500 caracteres.
- Structured Outputs reduz falhas de contrato.
- Flags de risco são derivadas do texto original e uma regra determinística pode rebaixar a automação proposta; para decisão, vale a menor confiança entre roteamento e assistência.
- Tentativas explícitas de prompt injection são interrompidas antes de qualquer chamada externa.
- Sem chave, o produto declara “Modo demonstração”.

## Evolução para produção

O protótipo mantém os vetores fixos em cache no escopo da função: em instâncias quentes, cada ticket gera apenas o embedding da consulta; em cold start, o lote fixo é recalculado uma vez. O modelo Naive Bayes é compilado pelo script de análise em um artefato TypeScript e não depende de Python em runtime. O próximo passo de produção é pré-calcular os vetores e armazená-los em pgvector ou vector store, com filtro por produto, política, validade e tenant.

A avaliação de 300 tickets mostrou que o roteamento LLM + embeddings (41,0%) perde para o Naive Bayes nos mesmos exemplos (77,7%). A arquitetura foi corrigida: `routingTopic` vem exclusivamente do baseline e o schema do LLM nem sequer contém esse campo. Um teste de regressão reproduz as 300 previsões históricas e confirma 233 acertos (77,7%) sem novas chamadas pagas. Para uma operação real ainda seriam necessários autenticação, rate limiting distribuído, telemetria, avaliação contínua e uma base de conhecimento aprovada.
