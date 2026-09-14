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
    │   └── casos anonimizados do Dataset 1
    ├── similaridade por cosseno
    ├── OpenAI Responses API com JSON Schema
    └── política determinística de risco
```

## Uso dos datasets

O repositório não publica nomes, e-mails, idade ou gênero. O script gera apenas agregados e 15 casos anonimizados. Cada identificador público é um hash não reversível do ID original.

O Dataset 2 e o Dataset 1 não são combinados por `join`. A integração ocorre no fluxo:

- Dataset 2 fornece a taxonomia demonstrativa de roteamento.
- Dataset 1 fornece taxonomia operacional, diagnóstico e casos com resoluções.
- O LLM recebe os vizinhos recuperados e produz uma saída estruturada.

## Segurança e confiabilidade

- `OPENAI_API_KEY` existe somente no servidor.
- A API mascara e-mails e sequências numéricas longas antes do envio.
- `store: false` é enviado à Responses API.
- A entrada é limitada a 2.500 caracteres.
- Structured Outputs reduz falhas de contrato.
- Uma regra determinística pode rebaixar a automação proposta.
- Sem chave, o produto declara “Modo demonstração”.

## Evolução para produção

O protótipo calcula embeddings de um corpus pequeno em cada chamada para manter a entrega autocontida. Em produção, os vetores seriam pré-calculados e armazenados em pgvector ou vector store, com filtro por produto, política, validade e tenant. Também seriam necessários autenticação, rate limiting, telemetria, avaliação contínua e uma base de conhecimento aprovada.
