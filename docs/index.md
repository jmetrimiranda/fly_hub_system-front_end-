# FlyHub System

Plataforma web para acompanhar inspeções feitas por drones conectados ao
**DJI FlightHub 2**. Recebe o stream do voo, coleta frames, organiza datasets,
publica no Roboflow e apresenta os resultados que o modelo de visão
computacional produz.

!!! info "O que este projeto não faz"
    Não treina rede neural, não define arquitetura YOLO e não processa vídeo
    pesado. Essa camada é desenvolvida separadamente. Aqui ficam a interface, a
    API, as integrações, o estado, o banco e o deploy.

## Em cinco minutos

```bash
git clone https://github.com/jmetrimiranda/fly_hub_system-front_end-.git
cd fly_hub_system-front_end-
cp .env.example .env
docker compose up
```

| Serviço | Endereço |
| --- | --- |
| Aplicação | <http://localhost:5173> |
| API + Swagger | <http://localhost:8000/docs> |
| Documentação | <http://localhost:8001> |

No GitHub Codespaces, abrir o repositório já sobe tudo: o `.devcontainer`
executa migrations e popula dados de demonstração.

## Como a documentação está organizada

<div class="grid cards" markdown>

-   **[Arquitetura](architecture.md)** — visão de conjunto, fluxo dos dados e
    os diagramas que explicam quem fala com quem.

-   **[Referência da API](api.md)** — cada rota com método, parâmetros,
    resposta e o código React que a chama.

-   **[Domínios](flight.md)** — voo, datasets, inspeções e Roboflow, cada um
    com a cadeia completa do botão até o banco.

-   **[Decisões (ADR)](decisions/index.md)** — por que TanStack Query, por que
    SSE, por que split temporal. Com as alternativas descartadas.

</div>

## Ponto de partida real

Já existe um protótipo funcional (`M4TD`, em `flyhub_connecting/`) que faz a
fatia vertical: recebe RTMP via MediaMTX, expõe túnel, coleta frames, particiona
e lista datasets. Este projeto **não recomeça do zero** — ele reorganiza aquele
protótipo na arquitetura descrita aqui. O que muda e o que aproveita está em
[Desenvolvimento](development.md#migração-do-protótipo-m4td).
