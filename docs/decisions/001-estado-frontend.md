# ADR 001 — Estado no frontend

**Estado:** aceita · **Data:** 2026-08-26

## Problema

A aplicação precisa gerenciar conexão com o FlightHub, coleta, pipeline,
datasets, inspeções, notificações, carregamento e erros. As opções na mesa eram
Context, Zustand, Redux Toolkit e TanStack Query.

## Observação que muda a pergunta

Quase tudo nessa lista é **estado de servidor**, não estado de aplicação. O
status do voo não pertence ao React — pertence ao backend, e o React tem uma
cópia que pode estar velha. O problema real não é "onde guardar", é
"quando revalidar".

Redux, Zustand e Context resolvem bem o segundo problema e nada do primeiro.
Usar qualquer um deles para dados de API significa reimplementar cache,
deduplicação, revalidação e invalidação à mão.

## Decisão

**TanStack Query** para tudo que vem da API. **Zustand** para o que é só do
cliente. **`useState`** para o que é só do componente.

| Tipo | Onde | Exemplo |
| --- | --- | --- |
| Servidor | TanStack Query | status, datasets, inspeções |
| Cliente | `stores/uiStore.ts` | sidebar, SSE conectado, toasts |
| Local | `useState` | campo de endereço sendo digitado |

**Regra:** resposta de API não é copiada para dentro de um store. Essa cópia é
a origem clássica de tela desatualizada — dois lugares com a mesma informação e
nenhum dos dois sabendo que o outro mudou.

## Descartadas

- **Redux Toolkit** — a quantidade de estado global genuinamente compartilhado
  é pequena (sidebar e toasts). O boilerplate não se paga.
- **Só Context** — re-renderiza toda a árvore a cada mudança. Com telemetria
  chegando a cada poucos segundos, isso custa caro.
- **Só Zustand** — resolveria, mas exigiria escrever cache, deduplicação e
  revalidação, que é exatamente o que o TanStack Query já faz.

## Consequências

Erro de invalidação passa a ser o modo de falha mais provável. Mitigação: todas
as chaves ficam em `lib/queryKeys.ts`, hierárquicas, e cada mutation declara o
que invalida.
