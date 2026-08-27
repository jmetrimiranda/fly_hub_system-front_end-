# ADR 005 — Design system

**Estado:** aceita · **Data:** 2026-08-26

## Problema

A referência visual é o **Purity UI Dashboard Pro**. O requisito pedia
aparência de dashboard moderno, sem criar dependência de template proprietário.

## Restrição de licença

O **Purity UI Dashboard PRO é comercial**. Usar seu código sem comprar a
licença não é opção. A versão gratuita é MIT, mas foi construída sobre Chakra
UI v1 — várias versões atrás — e adotá-la significaria herdar um débito de
migração no dia um.

## Decisão

Reconstruir a linguagem visual com **Chakra UI v3**, que é a base sobre a qual
o Purity foi feito. O resultado tem a mesma leitura — fundo claro e frio, cards
brancos com sombra difusa, cantos generosos, acento em teal — sem código de
terceiro e sem risco de licença.

Tudo vem de tokens em `src/theme/index.ts`. Componente com hex escrito à mão
não passa em revisão.

## O que foi acrescentado à referência

O Purity é um dashboard de SaaS: bom para métricas de negócio. Este produto é
um painel de operação, e a diferença aparece em um detalhe:

**Todo valor de telemetria usa fonte monoespaçada com algarismos tabulares.**
Quando o bitrate oscila de `0.41` para `0.39`, o número não empurra o resto da
linha. Rótulos ficam em versalete espaçado, como legenda de instrumento. Isso
também dá continuidade visual com o protótipo M4TD, que já usava mono nas
métricas.

O ponto de ousadia fica concentrado em um lugar só: **o drone que decola quando
a conexão sobe**. Ele carrega o estado mais importante da aplicação de um jeito
que nenhum badge carregaria. Ao redor dele, tudo é deliberadamente quieto.

## Descartadas

- **Material UI** — competente, mas a estética Material é reconhecível demais e
  se afasta da referência pedida.
- **Tailwind + shadcn/ui** — excelente combinação, porém entrega um conjunto de
  componentes para copiar e manter, não um sistema de tokens. Mais trabalho para
  chegar ao mesmo lugar.
- **Purity UI free** — Chakra v1, débito de migração desde o primeiro dia.

## Consequências

Chakra v3 mudou bastante em relação ao v2 (componentes compostos, `gap` no
lugar de `spacing`, sem prefixo `is` em booleanas). Exemplos antigos da internet
não colam direto — vale conferir a documentação da versão antes de copiar.
