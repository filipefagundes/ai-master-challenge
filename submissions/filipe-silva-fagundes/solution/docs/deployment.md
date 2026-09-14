# Deploy público

## Vercel

1. Importe o fork do GitHub na Vercel.
2. Defina o Root Directory como `submissions/filipe-silva-fagundes/solution`.
3. Adicione `OPENAI_API_KEY` nas variáveis de ambiente de Production e Preview.
4. Opcionalmente ajuste `OPENAI_MODEL` e `OPENAI_EMBEDDING_MODEL`.
5. Faça o deploy e teste a badge “LLM + embeddings ao vivo”.

Não use o prefixo `NEXT_PUBLIC_` para a chave. Ele exporia o segredo no bundle do navegador.

## Verificação antes da entrega

```bash
npm run typecheck
npm run build
```

Teste os três modos de decisão, uma entrada curta inválida e uma falha de credencial. O modo ao vivo exige uma chave válida e acesso aos modelos configurados.
