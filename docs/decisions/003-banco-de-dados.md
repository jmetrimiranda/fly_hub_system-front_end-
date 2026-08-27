# ADR 003 — Banco de dados

**Estado:** aceita · **Data:** 2026-08-26

## Decisão

**PostgreSQL 16**, com SQLAlchemy 2.0 assíncrono e migrations em Alembic.
**Imagens em disco**, não no banco.

## Por quê

Os dados são relacionais e as perguntas da interface são agregações —
inspeções por dia, avarias por inspeção, notas abertas por status. É
exatamente o que SQL faz melhor.

Sobre as imagens: um voo de 20 minutos a 30 fps são 36 mil frames. Guardá-los
como `bytea` destrói backup, replicação e tempo de dump, e não traz nenhuma
vantagem — ninguém consulta o conteúdo binário de um JPEG por SQL. O banco
guarda o caminho e os metadados que importam: `captured_at`, `frame_number`,
`split`, `embargoed`.

## Descartadas

- **SQLite em produção** — cria divergência entre o que roda na máquina do
  desenvolvedor e o que roda no servidor. Fica só nos testes, onde a
  velocidade compensa.
- **MongoDB** — o esquema é estável e as consultas são agregações relacionais.
  A flexibilidade de documento não ajuda e a integridade referencial ajudaria.
- **TimescaleDB agora** — só vale quando `telemetry_samples` crescer de fato.
  Como é uma extensão do próprio Postgres, adotá-la depois é aditivo, não uma
  migração de banco.

## Consequências

Sobe um container a mais no `docker-compose`, o que é aceitável dado que o
projeto já roda em Docker.

O diretório `/data` precisa ser um volume persistente em produção — se ele for
efêmero, os datasets somem no primeiro deploy. Está documentado em
[Docker](../docker.md).
