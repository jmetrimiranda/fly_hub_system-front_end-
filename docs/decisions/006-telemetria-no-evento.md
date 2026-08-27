# ADR 006 — Telemetria posicional viaja dentro do evento

**Estado:** aceita · **Data:** 2026-08-27

## Problema

O ADR 002 fixou uma regra: **o evento SSE não carrega o dado**. Ele diz "isto
mudou" e o TanStack Query busca a versão atual. A regra existe para eliminar uma
classe inteira de bug — payload do evento e resposta do endpoint divergirem, com
a tela mostrando uma versão que o backend não confirma.

A telemetria de voo quebra a economia dessa regra. Ela chega a **1 Hz**, e cada
amostra é uma posição nova. Seguir o ADR 002 à risca significaria, por cliente
conectado, uma requisição HTTP por segundo a `/flight/telemetry` — só para
buscar os mesmos ~200 bytes que o evento acabou de anunciar. Com o mapa aberto
em quatro estações de operação, é o polling que o ADR 002 descartou, com um
passo a mais.

## Decisão

O evento `flight.telemetry` **carrega o payload completo** da amostra. É a única
exceção. Todos os outros eventos seguem o ADR 002 sem alteração.

`useServerEvents()` mantém o mapa `evento → chaves de cache`; `flight.telemetry`
simplesmente não aparece nele. Quem consome é `useTelemetry()`, que guarda
posição e rastro em estado local do próprio hook.

## Por que a exceção é segura aqui

O risco que o ADR 002 evita é divergência entre duas representações do mesmo
dado. Neste caso ela não se sustenta:

- **Não há segunda representação viva.** `GET /flight/telemetry` devolve
  exatamente a última amostra em memória — a mesma que foi publicada. Os dois
  caminhos saem do mesmo `FlightSource.current()`.
- **O dado é descartável por natureza.** Uma amostra atrasada não tem valor;
  a próxima chega em um segundo. Não existe "estado defasado" a convergir, ao
  contrário de status de coleta ou de pipeline.
- **Nada é persistido a partir do evento.** Posição não vira registro de banco,
  não invalida cache, não dispara mutação.

O endpoint continua existindo, mas para outro propósito: o mapa se posiciona na
montagem sem esperar o próximo tick. É uma leitura, não um loop.

## Descartadas

- **Seguir o ADR 002 também aqui** — 1 requisição/segundo/cliente para transportar
  o dado que o evento já anunciou. Custo real, benefício nulo neste caso.
- **Baixar a frequência para 0,2 Hz** e revalidar por HTTP — o marcador do mapa
  andaria a saltos de 30 m. Interpolar cinco segundos de posição é inventar
  trajetória.
- **Escrever a amostra no cache do TanStack Query** — a 1 Hz, invalidaria
  dependentes sem parar e transformaria estado de alta frequência em estado de
  servidor cacheável, que ele não é (ADR 001).

## Limite da exceção

Vale **apenas** para `flight.telemetry`. Qualquer evento novo carrega só o aviso.
Se um segundo evento de alta frequência aparecer, a discussão volta a este ADR —
duas exceções deixam de ser exceção e viram a regra por acidente.
