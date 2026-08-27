# Painel de voo: transição drone 3D → mapa, com fonte de telemetria simulada

## Contexto

Hoje `connected` é sempre `false`, porque a conexão real com o FlightHub vive em
outro projeto e só será integrada depois. Consequência: metade da interface nunca
foi vista por ninguém — drone voando, hélices girando, telemetria chegando.

Esta tarefa faz duas coisas. Cria uma **fonte de voo simulada** no backend, que
permite exercitar todo o estado conectado sem hardware. E implementa o
comportamento pedido para o painel do Dashboard:

```
desconectado           → drone 3D parado, hélices imóveis
conexão estabelecida   → hélices aceleram, drone decola
estável por 3s + 5s    → painel troca para o mapa com a posição do drone
desconectou            → volta ao drone 3D
```

A fonte simulada é descartável por construção: quando o código MQTT chegar, ele
implementa a mesma interface `FlightSource` e a troca é uma linha em `deps.py`.

**Área de operação:** Terminal Marítimo de Ponta Ubu, Anchieta/ES.
Centro em `-20.78667, -40.57333`.

## Objetivo

Com `FLIGHT_SOURCE=fake`, subir a aplicação e ver: drone parado, hélices
acelerando, decolagem, troca para o mapa, marcador percorrendo uma rota de
inspeção sobre o terminal, rastro atrás dele — sem nenhum hardware conectado.

---

# Fase 1 — Backend

## Arquivos

| Arquivo | O que muda |
| --- | --- |
| `backend/app/schemas/flight.py` | Novo schema `Telemetry`. |
| `backend/app/integrations/flight_source/__init__.py` | Novo. Protocolo `FlightSource`. |
| `backend/app/integrations/flight_source/base.py` | Novo. `FlightSource` (Protocol) e dataclass `Telemetry`. |
| `backend/app/integrations/flight_source/fake.py` | Novo. `FakeFlightSource` — rota de inspeção sobre Ponta Ubu. |
| `backend/app/integrations/flyhub/client.py` | Em modo `fake`, `probe()` devolve broker e stream no ar. |
| `backend/app/services/flight_service.py` | Expõe `telemetry()`. |
| `backend/app/api/v1/routes/flight.py` | Novo `GET /flight/telemetry`. |
| `backend/app/api/v1/deps.py` | Escolhe a fonte pela configuração. |
| `backend/app/core/config.py` | `flight_source`, `fake_flight_*`. |
| `backend/app/main.py` | Inicia e para a fonte no `lifespan`. |
| `backend/tests/test_flight_source.py` | Novo. |
| `.env.example` | Documenta as variáveis novas. |
| `docs/decisions/006-telemetria-no-evento.md` | Novo ADR. |

## Passos

### 1.1 O contrato

Em `flight_source/base.py`:

```python
@dataclass(slots=True)
class Telemetry:
    at: datetime
    latitude: float
    longitude: float
    altitude_m: float          # relativa ao ponto de decolagem
    heading_deg: float         # 0 = norte, sentido horário
    horizontal_speed_ms: float
    satellites: int
    fix_type: Literal["none", "gps", "rtk"]
```

```python
class FlightSource(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def current(self) -> Telemetry | None: ...
```

A fonte roda uma tarefa em segundo plano, publica cada amostra no `EventBus`
(evento `flight.telemetry`) e guarda a última em memória para o `current()`.
Quem consome não sabe se veio de simulação ou de broker MQTT.

**Esta é a costura.** Ao integrar, `MqttFlightSource` implementa este mesmo
protocolo: assina o broker, publica no bus, cacheia a última. Nada mais muda.

### 1.2 A rota simulada

Rota de inspeção do píer, em varredura. Waypoints em **metros** relativos ao
centro `(-20.78667, -40.57333)`, como `[leste, norte]`:

| # | Offset | Altitude | Observação |
| --- | --- | --- | --- |
| 0 | `[0, 0]` | 0 → 60 m | decolagem |
| 1 | `[-150, 80]` | 60 m | entrada na área |
| 2 | `[250, 80]` | 60 m | passada 1 |
| 3 | `[250, 40]` | 60 m | |
| 4 | `[-150, 40]` | 60 m | passada 2 |
| 5 | `[-150, 0]` | 60 m | |
| 6 | `[250, 0]` | 60 m | passada 3 |
| 7 | `[250, -40]` | 60 m | |
| 8 | `[-150, -40]` | 60 m | passada 4 |
| 9 | `[0, 0]` | 60 → 0 m | retorno e pouso |

Ao chegar no fim, reinicia do zero — o loop mantém a tela viva indefinidamente.

Conversão metro → grau nesta latitude:

```python
METERS_PER_DEG_LAT = 110_900.0
METERS_PER_DEG_LON = 111_320.0 * math.cos(math.radians(-20.78667))  # ≈ 104_060
```

Comportamento:

- Velocidade de cruzeiro **6 m/s**, interpolação linear entre waypoints.
- `heading_deg` derivado da direção de deslocamento (`atan2` do vetor,
  convertido para bússola: 0 = norte, horário).
- Publica a **1 Hz**.
- `fix_type="rtk"`, `satellites` oscilando entre 18 e 26 — variação pequena, só
  para a interface não parecer congelada.
- Ruído gaussiano de ~0,4 m na posição. Sem ele o traçado fica artificialmente
  perfeito e não exercita a suavização do mapa.
- Use `random.Random(42)` — o mesmo seed do `seed.py`, para reprodutibilidade.

### 1.3 Modo fake no `FlyHubClient`

Quando `settings.flight_source == "fake"`, o `probe()` devolve, sem tocar a rede:

```python
FlightProbe(
    broker_up=True,
    stream=StreamSnapshot(
        ready=True, resolution="960x720", bitrate_mbps=0.41, codec="H264", readers=1
    ),
)
```

Valores iguais aos que o protótipo M4TD reportava. Isso faz `connected` virar
`true` e destrava toda a interface do estado conectado.

### 1.4 Configuração

```bash
FLIGHT_SOURCE=fake            # fake | mqtt (mqtt ainda não implementado)
FAKE_FLIGHT_INTERVAL=1.0      # segundos entre amostras
FAKE_FLIGHT_SPEED_MS=6.0
FAKE_FLIGHT_CENTER_LAT=-20.78667
FAKE_FLIGHT_CENTER_LON=-40.57333
```

Padrão de `FLIGHT_SOURCE` é `fake`, para que quem clonar o repositório veja a
aplicação funcionando. `mqtt` deve levantar `NotImplementedError` com mensagem
clara, não falhar silenciosamente.

### 1.5 Endpoint e evento

`GET /api/v1/flight/telemetry` → última amostra, ou `204 No Content` se ainda não
houver nenhuma. O mapa usa isto para se posicionar na montagem, sem esperar o
próximo tick.

O evento SSE `flight.telemetry` **carrega o payload completo** da amostra.

### 1.6 ADR 006

Escrever `docs/decisions/006-telemetria-no-evento.md`. O ADR 002 estabelece que
evento SSE não carrega dado — ele avisa e o cliente revalida, o que impede
divergência entre payload e endpoint. Telemetria posicional é a exceção: a 1 Hz,
a regra custaria uma requisição HTTP por segundo por cliente conectado, e o
custo supera o risco que ela evita. Registrar a exceção, o motivo, e que ela vale
**apenas** para `flight.telemetry` — todos os outros eventos seguem o ADR 002.

## Verificação da Fase 1

```bash
cd backend && pytest -q                      # esperado: todos passam
curl -s localhost:8000/api/v1/flight/status | python3 -m json.tool
# esperado: "connected": true

curl -s localhost:8000/api/v1/flight/telemetry | python3 -m json.tool
# esperado: latitude ≈ -20.78, longitude ≈ -40.57

curl -N localhost:8000/api/v1/flight/events | head -20
# esperado: eventos flight.telemetry chegando ~1/s, com lat/lon variando
```

Testes em `test_flight_source.py`:

- Todas as amostras caem dentro de ~500 m do centro configurado.
- `heading_deg` sempre em `[0, 360)`.
- A rota fecha o ciclo e reinicia sem salto de posição.
- `current()` devolve `None` antes do `start()`.
- Distância entre amostras consecutivas é compatível com a velocidade e o
  intervalo configurados, dentro de uma tolerância.

---

# Fase 2 — Frontend

## Arquivos

| Arquivo | O que muda |
| --- | --- |
| `frontend/src/components/flightpanel/FlightPanel.tsx` | Novo. Máquina de estados e alternância. |
| `frontend/src/components/flightpanel/useFlightPanelState.ts` | Novo. A máquina, isolada e testável. |
| `frontend/src/components/map/FlightMap.tsx` | Novo. Leaflet, carregado sob demanda. |
| `frontend/src/hooks/useTelemetry.ts` | Novo. Consome o evento SSE e mantém posição + rastro. |
| `frontend/src/hooks/useServerEvents.ts` | Trata `flight.telemetry` sem invalidar cache. |
| `frontend/src/services/api/flightService.ts` | `getTelemetry()`. |
| `frontend/src/types/api.ts` | Tipo `Telemetry`. |
| `frontend/src/pages/dashboard/DashboardPage.tsx` | Usa `FlightPanel` no lugar de `DroneViewer`. |
| `frontend/src/components/flightpanel/useFlightPanelState.test.ts` | Novo. |
| `frontend/vite.config.ts` | Leaflet em `manualChunks` próprio. |
| `frontend/package.json` | `leaflet`, `react-leaflet`, `@types/leaflet`. |

## Passos

### 2.1 A máquina de estados

Em `useFlightPanelState.ts`. Estados: `grounded`, `spinning-up`, `flying`, `map`.

```
grounded    --connected=true-------------> spinning-up
spinning-up --estável por STABLE_MS------> flying
spinning-up --connected=false------------> grounded
flying      --após HOLD_MS---------------> map
flying      --connected=false------------> grounded
map         --connected=false------------> grounded
qualquer    --alternância manual---------> map ou flying (trava o automático)
```

```ts
export const PANEL_TIMING = {
  STABLE_MS: 3000,   // conexão precisa se sustentar antes de contar
  HOLD_MS: 5000,     // tempo vendo o drone antes de trocar para o mapa
} as const;
```

Quatro regras:

- **Qualquer `connected: false` derruba para `grounded` na hora**, e zera os dois
  temporizadores. É isso que impede o painel de piscar com sinal instável.
- **Já conectado na primeira renderização → entra direto em `map`.** A cerimônia
  marca a transição, não deve ser pedágio a cada recarga.
- **Alternância manual trava o automático** até desconectar. Quem escolheu ver o
  drone não deve ser arrastado de volta ao mapa em 5 s.
- **Desconectar destrava** e volta a `grounded`.

Limpar os timers no cleanup do efeito. Timer vazado aqui dispara troca de tela
depois que o componente saiu.

### 2.2 O painel

`FlightPanel.tsx` renderiza `DroneViewer` em `grounded`/`spinning-up`/`flying`, e
`FlightMap` em `map`. Transição com opacidade (~240 ms), sem deslocamento —
conteúdo pulando em painel pequeno lê como falha de carregamento.

Botão de alternância no canto superior direito, ícone só (`Map` / `Box` do
lucide-react), com `aria-label`. Fundo `blackAlpha.600` com `backdropFilter`,
igual ao rótulo de estado que já existe.

O rótulo inferior acompanha: `EM SOLO` → `DECOLANDO` → `EM VOO`.

### 2.3 O mapa

`react-leaflet`, `import()` dinâmico dentro de `<Suspense>` — só baixa quando o
mapa aparece pela primeira vez, o que é grátis, já que só acontece após 8 s de
conexão.

- Tiles: OpenStreetMap padrão, com a atribuição obrigatória visível.
  Deixar a URL em constante nomeada e comentada, para trocar por satélite depois
  (num terminal portuário, imagem de satélite é mais legível que mapa de ruas).
- Centro inicial `[-20.78667, -40.57333]`, zoom 16.
- Marcador do drone: `divIcon` com SVG de seta, rotacionada por `heading_deg`.
  Não usar imagem — a seta precisa girar e herdar a cor do tema.
- Rastro: `Polyline` com as últimas 120 posições (2 min a 1 Hz).
- **Interpolação:** a 1 Hz o marcador andaria aos saltos. Interpolar entre a
  amostra anterior e a atual com `requestAnimationFrame`, ao longo do intervalo
  esperado. Sem isso a leitura é de travamento, não de voo.
- Recentrar só quando o drone sair dos 60% centrais da viewport — recentrar a
  cada amostra impede o operador de arrastar o mapa.
- Sobreposição com `latitude`, `longitude` (6 casas), `altitude_m`, `heading_deg`
  e `fix_type`, em `textStyle="readout"`. Números de telemetria usam a fonte
  monoespaçada com algarismos tabulares que já está no tema.

### 2.4 Telemetria no cliente

`useTelemetry.ts` guarda posição atual e rastro em `useState` local do hook —
**não** no TanStack Query e **não** no Zustand. É dado de alta frequência que não
é estado de servidor cacheável nem estado de aplicação; escrever no cache do
Query a 1 Hz invalidaria dependentes sem parar.

Em `useServerEvents.ts`, `flight.telemetry` é o único evento que **não** dispara
invalidação de cache: ele carrega o dado. Comentar isso no código, apontando o
ADR 006.

## Verificação da Fase 2

```bash
cd frontend
npm run lint && npx tsc --noEmit && npm test
```

Testes de `useFlightPanelState`, com timers falsos:

- `connected` cai antes de `STABLE_MS` → permanece em `grounded`, não avança.
- Conexão estável → `map` após `STABLE_MS + HOLD_MS`.
- Já conectado na montagem → `map` imediatamente.
- Alternância manual para `flying` → não volta sozinho para `map`.
- Desconectar → `grounded` e o travamento manual é liberado.
- Desmontar no meio da contagem não deixa timer pendente.

Na aplicação, com `FLIGHT_SOURCE=fake`:

1. Recarregue com o backend parado: drone parado, `EM SOLO`.
2. Suba o backend: hélices aceleram, drone decola, rótulo muda.
3. Aguarde: painel troca para o mapa sobre Ponta Ubu, marcador percorrendo a
   varredura do píer com rastro atrás.
4. Botão de alternância volta ao drone e ele permanece lá.
5. Derrube o backend: volta a `grounded`.

## Restrições

- `DroneViewer` mantém `isFlying` como única entrada. Nada em `drone3d/` importa
  hooks de dados, services ou tipos da API.
- Nenhum `fetch`/`axios` fora de `services/api/` — o ESLint bloqueia.
- Sem `localStorage` ou `sessionStorage`.
- Chaves de cache novas só em `lib/queryKeys.ts`.
- Respeitar `prefers-reduced-motion`: sem interpolação animada do marcador, sem
  flutuação do drone; o painel ainda troca de estado, só não anima.
- A tarefa **não** implementa MQTT. `FLIGHT_SOURCE=mqtt` levanta
  `NotImplementedError` com mensagem indicando onde implementar.

## Pronto quando

- [ ] `FLIGHT_SOURCE=fake` faz a aplicação inteira se comportar como conectada
- [ ] A sequência completa funciona ponta a ponta
- [ ] Sinal instável não faz o painel piscar
- [ ] Alternância manual funciona e é respeitada
- [ ] Marcador se move de forma contínua, não aos saltos
- [ ] `pytest -q`, `npm run lint`, `npx tsc --noEmit`, `npm test` passam
- [ ] `docs/decisions/006-telemetria-no-evento.md` escrito
- [ ] `docs/flight.md` documenta a máquina de estados e a interface `FlightSource`
- [ ] `.env.example` documenta as variáveis novas
