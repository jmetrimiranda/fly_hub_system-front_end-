# Onde colocar o peso do modelo

Esta página é para quem **treina o modelo** e não mexe na aplicação. Ela não
supõe que você conheça o resto do sistema.

O que você precisa fazer, inteiro:

```
1. Treine em notebooks/treino-yolo.ipynb
2. Copie best.pt e metrics.json para models/
3. Confira em Voo que o badge mostra o nome do arquivo
4. Commit e push do notebook — os pesos NÃO vão para o Git
5. develop → release → main
```

**Se algum passo pedir para editar código, editar configuração ou rodar um
comando na aplicação, o desenho falhou** — abra uma issue em vez de contornar.
Não existe endpoint de upload, migration a rodar nem serviço a reiniciar.

**Toda linha de comando aqui é marcada com onde ela roda:**

- 🖥️ **HOST** — seu terminal normal, na pasta do repositório
- 🐳 **CONTAINER** — terminal dentro do Dev Container, prompt `flyhub@...`

---

## O caminho exato

Na raiz do repositório:

```
models/
├── README.md
├── .gitkeep
├── best.pt        ← você copia este
└── metrics.json   ← e este
```

```bash
# 🖥️ HOST — a partir da pasta do repositório
cp /caminho/do/treino/runs/detect/SEU_RUN/weights/best.pt models/
cp /caminho/do/treino/metrics.json models/
ls -l models/
```

O notebook já faz essa cópia na última célula. O comando acima é para quando o
treino aconteceu noutra máquina.

Dentro do container a pasta aparece como `/models`, montada a partir daí. Os
dois caminhos são o mesmo conteúdo:

```bash
# 🐳 CONTAINER
ls -l /models
```

`metrics.json` é **opcional**. Um `best.pt` copiado à mão, sem métricas,
funciona igual — a tela apenas não mostra mAP. A ausência de métrica não é erro
de modelo.

---

## Como confirmar que carregou

### Na tela

Abra <http://localhost:5173/voo>. Duas coisas mudam, em segundos, sem você
reiniciar nada:

**O badge sobre o vídeo**, no canto inferior esquerdo:

| Você vê | Significa |
| --- | --- |
| `SEM MODELO — vídeo cru` | não há `best.pt` em `models/` |
| `MODELO NÃO CARREGOU — vídeo cru` | o arquivo existe e a carga falhou (o motivo aparece no painel) |
| `MODELO DESLIGADO — vídeo cru` | pesos carregados, inferência desligada **de propósito** |
| `MODELO best.pt` | inferindo — é este que você quer ver |

Os três primeiros produzem a **mesma imagem**: vídeo passando, nenhuma caixa
desenhada. É por isso que o badge nunca fica em silêncio — ver vídeo cru
achando que o modelo não achou nada é pior que não ver vídeo.

**O painel Modelo**, na coluna da direita: nome do arquivo, data do treino,
classes, mAP@50, precisão e recall.

### No log

```bash
# 🐳 CONTAINER, no terminal do uvicorn
```

Procure a linha `detector_carregado`:

```
detector_carregado weights=/models/best.pt treinado_em=2026-08-20T10:00:00-0300
                   classes=['corrosão', 'trinca'] metricas=/models/metrics.json
```

Se o arquivo não carregou, a linha é `detector_falhou` com o motivo. Se não há
arquivo, é `detector_sem_pesos` — e isso não é erro.

### Pela API

```bash
# 🖥️ HOST
curl -s localhost:8000/api/v1/model | python3 -m json.tool
```

O campo `message` é uma frase pronta que diz em qual dos quatro estados o
modelo está. `active: true` significa que o próximo quadro passa mesmo pelo
modelo.

---

## Testar sem drone

Você não precisa de aeronave nem de FlightHub para ver a inferência rodando.
Basta publicar um vídeo sintético no broker.

### 1. Suba o MediaMTX

```bash
# 🖥️ HOST
docker compose --profile stream up -d mediamtx
```

### 2. Publique um padrão de teste com o ffmpeg

```bash
# 🖥️ HOST
ffmpeg -re -f lavfi -i testsrc=size=960x720:rate=30 \
       -c:v libx264 -preset veryfast -tune zerolatency -pix_fmt yuv420p \
       -f flv rtmp://localhost:1935/live/m4td
```

Deixe rodando. Para um vídeo de verdade em vez do padrão colorido, troque o
`-f lavfi -i testsrc=...` por `-stream_loop -1 -i seu_video.mp4`.

### 3. Aponte a aplicação para o broker

```bash
# 🖥️ HOST — no .env
FLIGHT_SOURCE=real
MEDIAMTX_API_URL=http://mediamtx:9997
MEDIAMTX_RTSP_URL=rtsp://mediamtx:8554
```

```bash
# 🖥️ HOST
docker compose -f docker-compose.yml \
               -f .devcontainer/docker-compose.devcontainer.yml \
               up -d --force-recreate backend
```

Editar o `.env` com o container de pé **não** basta: o `env_file` é lido só na
criação. É o `--force-recreate` que resolve; `restart` não.

Depois, reinicie o uvicorn no terminal do container. A tela Voo passa a mostrar
o vídeo, e com `best.pt` em `models/` as caixas aparecem sobre ele.

---

## O que fazer quando o badge não muda

Na ordem, do mais comum ao mais raro:

**1. O arquivo está no lugar certo?**

```bash
# 🖥️ HOST
ls -l models/best.pt
```

Tem de ser `models/` na **raiz do repositório**, não `backend/models/`, nem
`data/models/` — este último era o caminho antigo, antes de a pasta sair do
volume do Docker.

**2. O container enxerga o arquivo?**

```bash
# 🐳 CONTAINER
ls -l /models
```

Vazio aqui com o arquivo presente no host significa que o volume não está
montado — confira `./models:/models` no `docker-compose.yml` e recrie o
container.

**3. A inferência está desligada?**

O badge diz `MODELO DESLIGADO — vídeo cru`. O toggle da tela Voo está desligado,
e ele **sobrevive a reinício de propósito** (veja a seção seguinte). Ligue no
painel Modelo.

**4. O que a API diz?**

```bash
# 🖥️ HOST
curl -s localhost:8000/api/v1/model | python3 -m json.tool
```

- `weights_exists: false` → a aplicação está procurando noutro caminho.
  `weights_path` diz qual, e ele vem de `MODEL_WEIGHTS`/`MODELS_DIR` no `.env`.
- `error` preenchido → o arquivo existe e não carregou. A mensagem traz o
  motivo: peso corrompido, incompatível, ou `ultralytics` ausente na máquina.

**5. O arquivo foi reescrito com o mesmo `mtime`?**

Raro, mas acontece com algumas ferramentas de cópia. A detecção é por `mtime`,
então nada muda. Use **Recarregar**, no painel Modelo.

Nada disso derruba a aplicação: um peso corrompido volta ao passthrough, o vídeo
continua passando e o erro aparece na tela. **Um modelo ruim não pode tirar a
plataforma do ar.**

---

## Como o toggle funciona, e por que ele não descarrega os pesos

O botão fica no painel **Modelo**, na tela Voo.

**Desligar mantém os pesos em memória.** Religar volta a detectar no quadro
seguinte, sem os segundos de carga. São duas ações distintas:

| Ação | O que faz | O que **não** faz |
| --- | --- | --- |
| **Inferência** (toggle) | liga e desliga a detecção sobre o vídeo | não descarrega, não relê o disco |
| **Recarregar** | relê `best.pt` do disco agora | não liga nem desliga nada |

Juntar as duas num botão só impediria o teste que se faz sempre ao receber um
modelo novo: alternar durante o **mesmo voo** e comparar a imagem com e sem
detecção. Se desligar descarregasse, cada alternância pagaria de novo a carga do
modelo e a comparação deixaria de ser prática.

**O estado do toggle é gravado no banco**, não numa variável do processo.
Reiniciar o backend não religa sozinho um modelo que alguém desligou de
propósito — se religasse, um `docker compose restart` no meio de um teste
mudaria silenciosamente o que está sendo medido.

```bash
# 🖥️ HOST — as três rotas, se você preferir a linha de comando
curl -s localhost:8000/api/v1/model
curl -s -X POST localhost:8000/api/v1/model/toggle -H 'Content-Type: application/json' -d '{"enabled": false}'
curl -s -X POST localhost:8000/api/v1/model/reload
```

---

## Por que os pesos não vão para o Git

Um `best.pt` de YOLO tem dezenas de MB e **muda a cada treino**. O Git guarda
cada versão para sempre: em um ano de iteração o repositório passaria de alguns
MB para vários GB, e todo `git clone` — de qualquer pessoa, para qualquer
finalidade — pagaria por cada treino já feito, inclusive os descartados. O
histórico também não ajudaria: o diff de dois binários de pesos não é legível.

Por isso `models/*.pt` e `models/metrics.json` estão no `.gitignore`. O que vai
para o Git é o **notebook que os produz** — que é texto, tem diff legível e é o
que de fato explica o modelo.

Se um dia for preciso versionar os pesos mesmo assim, o caminho é **Git LFS** ou
um **registry de modelos** (MLflow, W&B, um bucket versionado). Não o Git comum:
ele não devolve o espaço depois, e reescrever histórico para remover binários
quebra o clone de todo mundo.

---

## Antes de treinar: preserve a partição

Ao gerar a versão no Roboflow, escolha **manter a divisão existente**
(*Keep existing split*), nunca *Rebalance*. O rebalanceamento redistribui as
imagens aleatoriamente e desfaz o split temporal — quadros vizinhos no tempo
voltam a cair em partições diferentes, o modelo memoriza, e a métrica de
validação sobe para um número que não se sustenta em voo novo. Nada no treino
indica que aconteceu.

O notebook confere isso sozinho e registra o resultado em
`metrics.json → dataset.split_check_ok`. Quando ele é `false`, o painel Modelo
mostra o aviso junto das métricas. O porquê está no
[ADR 004](../decisions/004-split-temporal.md) e em
[`notebooks/README.md`](https://github.com/jmetrimiranda/fly_hub_system-front_end-/blob/main/notebooks/README.md).
