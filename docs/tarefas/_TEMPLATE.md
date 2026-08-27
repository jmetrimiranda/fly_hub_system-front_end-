# [Título curto da tarefa]

## Contexto

Por que esta mudança existe. O que está errado hoje, ou o que falta. Uma ou duas
frases — o CLAUDE.md já cobre as convenções do projeto.

## Objetivo

O estado final desejado, em uma frase verificável.

## Arquivos envolvidos

| Arquivo | O que muda |
| --- | --- |
| `backend/app/services/x_service.py` | Descrição |
| `frontend/src/pages/y/YPage.tsx` | Descrição |

Se um arquivo novo precisa existir, diga o caminho completo.

## Passos

1. Primeiro passo, específico o bastante para não ter ambiguidade.
2. Segundo passo.
3. ...

## Restrições

- O que NÃO pode mudar (contratos de API existentes, nomes de rota, esquema).
- Regras do CLAUDE.md especialmente relevantes aqui.

## Como verificar

Comandos concretos, com a saída esperada:

```bash
cd backend && pytest -q                 # esperado: N passed
curl -s localhost:8000/api/v1/...       # esperado: ...
```

## Pronto quando

- [ ] Critério verificável 1
- [ ] Critério verificável 2
- [ ] `pytest -q` passa
- [ ] `npm run lint` passa
- [ ] Documentação em `docs/` atualizada, se a cadeia mudou
