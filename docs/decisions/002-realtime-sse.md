# ADR 002 — Tempo real com SSE

**Estado:** aceita · **Data:** 2026-08-26

## Problema

Conexão de voo, coleta e pipeline mudam por conta própria. A tela precisa
refletir isso sem que ninguém aperte F5. E o protótipo M4TD já mostrava
`SSE: conectado` no canto — a escolha tem precedente na casa.

## Decisão

**Server-Sent Events** em `GET /api/v1/flight/events`.

O tráfego é de mão única: servidor → cliente. Comando vai por `POST` REST, que
já tem resposta, código de status e tratamento de erro. Um canal bidirecional
resolveria um problema que não existe.

Vantagens concretas do SSE aqui:

- O `EventSource` **reconhece queda e reconecta sozinho**, sem uma linha de
  código. Com WebSocket, reconexão com backoff é código que alguém escreve,
  testa e mantém.
- É HTTP comum: atravessa proxy corporativo, funciona com nginx e não precisa
  de upgrade de protocolo.
- Um `heartbeat` a cada 15 s impede que proxies fechem a conexão ociosa.

## Descartadas

- **WebSocket** — capacidade bidirecional sem uso, complexidade de reconexão
  por conta própria, e mais atrito com infraestrutura corporativa.
- **Polling curto** — quatro telas × vários endpoints × 2 s gera carga
  constante e ainda assim mostra estado defasado.
- **Polling longo** — o pior dos dois: complexidade de streaming com latência
  de polling.

## Implementação

O `EventBus` (`core/events.py`) é em memória, com fila por assinante e descarte
do evento mais antigo quando o cliente não acompanha — telemetria atrasada não
tem valor.

No cliente, `useServerEvents()` mapeia cada evento para as chaves de cache que
ele invalida. O evento **não carrega o dado novo**; ele diz "isto mudou" e o
Query busca a versão atual. Assim não há como o payload do evento e a resposta
do endpoint divergirem.

## Consequência conhecida

Memória de processo: com mais de uma réplica do backend, um evento publicado na
réplica A não chega ao navegador conectado na B. A troca é substituir o
`EventBus` por Redis Pub/Sub mantendo a mesma interface — nenhuma outra parte
do código muda.

Rede de segurança enquanto isso: `useFlightStatus` faz `refetchInterval` de
15 s. Se o SSE cair sem que ninguém perceba, a tela ainda converge.
