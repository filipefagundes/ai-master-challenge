# Arquitetura

## Componentes

```text
Next.js App Router
├── Dashboard estático
│   └── analysis.json agregado e reproduzível
├── Bancada de triagem no navegador
└── POST /api/triage
    ├── validação e mascaramento de PII
    ├── OpenAI Embeddings API
    │   ├── oito protótipos do Dataset 2
    │   └── 200 textos de treino do Dataset 2 (25 por tema)
    ├── similaridade por cosseno
    ├── OpenAI Responses API com JSON Schema
    └── política determinística de risco
```

## Uso dos datasets

O repositório não publica nomes, e-mails, idade ou gênero. O script gera apenas agregados e 200 textos já processados do Dataset 2. Cada identificador público é um hash não reversível do índice original.

O Dataset 2 e o Dataset 1 não são combinados por `join`. A integração ocorre no fluxo:

- Dataset 2 fornece taxonomia, baseline e corpus de retrieval estratificado, retirado apenas do treino.
- Dataset 1 fornece taxonomia operacional, diagnóstico e auditoria de qualidade; suas resoluções sintéticas não entram no prompt.
- O LLM recebe os vizinhos recuperados e produz uma saída estruturada.

## Segurança e confiabilidade

- `OPENAI_API_KEY` existe somente no servidor.
- A API mascara e-mail, CPF, CNPJ, RG, telefone, CEP e cartão (com validação Luhn) antes do envio.
- `store: false` é enviado à Responses API.
- A entrada é limitada a 2.500 caracteres.
- Structured Outputs reduz falhas de contrato.
- Flags de risco são derivados do texto original e uma regra determinística pode rebaixar a automação proposta.
- Tentativas explícitas de prompt injection são interrompidas antes de qualquer chamada externa.
- Sem chave, o produto declara “Modo demonstração”.

## Evolução para produção

O protótipo mantém os vetores fixos em cache no escopo da função: em instâncias quentes, cada ticket gera apenas o embedding da consulta; em cold start, o lote fixo é recalculado uma vez. O próximo passo de produção é pré-calcular esses vetores e armazená-los em pgvector ou vector store, com filtro por produto, política, validade e tenant.

A avaliação de 300 tickets mostrou que o roteamento LLM + embeddings (41,0%) perde para o Naive Bayes nos mesmos exemplos (77,7%). Portanto, a arquitetura-alvo deve atribuir `routingTopic` ao baseline e restringir o LLM a enriquecimento e redação assistida. Essa mudança reduz custo e melhora a qualidade medida. Também seriam necessários autenticação, rate limiting distribuído, telemetria, avaliação contínua e uma base de conhecimento aprovada.
