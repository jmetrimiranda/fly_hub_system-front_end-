# Migração M4TD — Fases 2, 3 e 4: coleta, split e Roboflow

## Contexto

As Fases 0 e 1 estão prontas: o backend fala com o MediaMTX real e a tela Voo
mostra o vídeo com inferência. Falta o ciclo que dá sentido à plataforma —
**voa → coleta → split → Roboflow → anota → treina**.

`/workspaces/flyhub_connecting` está montado **somente leitura**. O M4TD já
implementa tudo isto, em FastAPI + Jinja2 + SQLite. Porte a lógica; a UI, o
SQLite e as rotas dele ficam de fora.

### Leia antes de escrever código

1. `/workspaces/flyhub_connecting/PROMPT_PLATAFORMA.md` — §1.3, §1.4, §2
2. `/workspaces/flyhub_connecting/SPEC_ATUAL.md` — estado real
3. `/workspaces/flyhub_connecting/app/` — a implementação
4. `/workspaces/flyhub_connecting/docs/plataforma/` e `docs/treino/01-dataset.md`
5. Nesta plataforma: `backend/app/services/splitting.py` — a função de split já
   existe, é pura e tem testes. **Use-a, não reimplemente.**

## Objetivo

Clicar em "Coletar imagens do voo" grava quadros originais com deduplicação.
Clicar em Salvar particiona em train/valid/test e o dataset aparece na tela
Dataset, onde é possível ver as imagens, excluí-las e enviar ao Roboflow
preservando a partição.

---

## Decisões já tomadas

**Fonte dos quadros.** A coleta puxa do **mesmo leitor** de `integrations/vision/`,
tomando o quadro *antes* do detector — a imagem gravada é a original, nunca a
processada. O `reader.py` já tem contadores de consumidores (`mjpeg`, `collect`);
com a coleta ativa o leitor não desliga mesmo que a aba do navegador feche.

**Onde grava.** Arquivos em disco durante a gravação, banco apenas ao salvar.
Um INSERT por quadro durante o voo põe I/O no caminho crítico, e uma sessão
interrompida deixaria dataset meio gravado. O `session.json` incremental é o que
permite recuperar.

**Deduplicação durante, split ao salvar.** Deduplicar depois do split quebraria
as proporções recém-calculadas.

---

# Fase 2 — Coleta

## Guarda de pré-condição

O botão só habilita com os indicadores verdes. Se algum estiver vermelho, **modal
listando exatamente o que falta e o que fazer**, no formato da §1.3 da
especificação:

```
Não é possível iniciar a coleta

✕ Stream — nenhum path ativo
  Confira o endereço no FlightHub e religue o toggle do canal.

✓ MediaMTX
✓ Túnel
```

Validado no cliente **e** revalidado no servidor. Novo endpoint
`GET /api/v1/flight/collection/preflight` devolvendo cada condição e a instrução
correspondente. Não deixe o botão clicável e falhando depois.

## Modal de confirmação

Ao clicar com tudo verde:

| Parâmetro | Opções | Padrão |
| --- | --- | --- |
| Intervalo de amostragem | 0,5 / 1 / 2 / 5 s | 2 s |
| Limite de quadros | número ou ilimitado | 500 |
| Deduplicação | on/off | on |

Mostrar também a versão que será criada. Botões **Confirmar** e **Cancelar**.

## Versionamento

`vMAJOR.MINOR`, com MINOR de 0 a 9 rolando para o próximo MAJOR:
`v0.0 → v0.1 → … → v0.9 → v1.0`. Varra `datasets/`, ache a maior versão, crie a
próxima. Primeira execução cria `v0.0`.

## Máquina de estados

```
 ocioso ──Confirmar──▶ gravando ⇄ pausado
                          │          │
                          └──Salvar──┘
                                │
                                ▼
                        salvo ──▶ ocioso
```

| Botão | Efeito |
| --- | --- |
| Pausar | para de salvar quadros; o vídeo continua; a sessão permanece aberta |
| Continuar | volta a salvar na mesma sessão |
| Salvar | encerra, dispara o split, volta a ocioso |

Durante a gravação, mostrar: quadros salvos, tempo decorrido, espaço em disco e
o estado atual de forma inequívoca. O `CollectionService` desta plataforma já tem
o formato dessa máquina — preencha a lógica real.

## Deduplicação

Compare a diferença média absoluta com o **último quadro salvo**, não com o
anterior lido. Limiar configurável (`DEDUP_THRESHOLD`, padrão a definir lendo o
M4TD). Registre quantos foram descartados por dedup — o número precisa aparecer
na interface, senão a contagem não bate e alguém perde tempo procurando.

Motivo: com o drone pairando, 30 quadros por segundo do mesmo enquadramento
inflam o dataset sem acrescentar informação e distorcem a distribuição de treino.

## Em disco durante a gravação

```
data/datasets/v0.3/
├── raw/
│   ├── 000001_t0.00.jpg
│   ├── 000002_t2.00.jpg
│   └── …
└── session.json
```

O timestamp relativo no nome **não é decorativo** — é o que permite o split sem
reabrir o banco. Grave o `session.json` incrementalmente.

## Requisitos não funcionais

- A coleta nunca bloqueia a exibição: escrita de arquivos em thread pool.
- Disco acima de 90% → pare a coleta e avise na interface.
- Sessão interrompida por queda fica consistente.

---

# Fase 3 — Split ao salvar

**Não reimplemente.** `backend/app/services/splitting.py` tem
`assign_temporal_splits`, função pura com testes de propriedade, na mesma
estratégia que a especificação do M4TD exige: blocos contíguos 70/15/15 na ordem
cronológica, com faixa de embargo nas fronteiras.

```
[──────── train 70% ────────][─ valid 15% ─][─ test 15% ─]
t=0                                                   t=fim
```

Confirme que os parâmetros batem com os do M4TD (`SPLIT_EMBARGO_SECONDS`). Se
divergirem, use os do M4TD e registre a mudança.

Por que blocos contíguos, e não split aleatório: quadros consecutivos são quase
idênticos. Aleatório coloca o quadro *N* em treino e o *N+1* em validação — o
modelo memoriza em vez de generalizar, e a métrica sobe para valores que não se
sustentam em voo novo. É vazamento de dados, e é silencioso.

Resultado:

```
data/datasets/v0.3/
├── train/images/
├── valid/images/
├── test/images/
├── raw/                    (mantido, permite refazer o split)
├── session.json
└── split_manifest.json
```

O manifesto registra estratégia, proporções, margem aplicada, contagem por
partição e o mapeamento de cada arquivo. Sem ele não há como reproduzir nem
auditar o experimento.

Ao salvar, popule as tabelas `datasets` e `dataset_images` — os campos `split` e
`embargoed` já existem no modelo.

---

# Fase 4 — Tela Dataset e Roboflow

## Detalhe e galeria

Clicar num dataset abre o detalhe com abas **train**, **valid** e **test**, cada
uma com contagem e galeria de miniaturas.

- Clicar numa miniatura abre a imagem em tamanho real
- Excluir imagem, com confirmação
- Seleção múltipla com exclusão em lote
- Excluir o dataset inteiro, exigindo digitar a versão para confirmar

**Ao excluir imagens depois do split, as proporções mudam.** Mostre as contagens
atualizadas e ofereça **refazer o split** a partir de `raw/` — é por isso que a
pasta original é mantida.

Servir miniaturas, não as imagens inteiras, na grade. Uma galeria que baixa 500
JPEGs em tamanho real trava o navegador.

## Credenciais do Roboflow

O pedido: poder gravar a chave e, no acesso seguinte, escolher numa lista
suspensa.

Nova tabela `roboflow_credentials`: `id`, `label`, `workspace`, `project`,
`api_key_encrypted`, `created_at`, `last_used_at`.

**Requisitos de segurança, sem exceção:**

- A chave é **cifrada em repouso**. Use `cryptography.fernet` com uma chave
  derivada de `SECRET_KEY` do ambiente. Nunca em texto claro no banco.
- O endpoint de listagem **nunca** devolve a chave, nem parcial, nem mascarada.
  Devolve `id`, `label`, `workspace`, `project`, `last_used_at`.
- A chave nunca aparece em log, nem em mensagem de erro, nem em resposta de API.
- No formulário, campo do tipo `password`.
- Se `SECRET_KEY` não estiver definida, a aplicação **não** salva credencial e
  explica o motivo na interface. Não invente chave padrão.

```
GET    /api/v1/roboflow/credentials          lista (sem a chave)
POST   /api/v1/roboflow/credentials          grava nova
DELETE /api/v1/roboflow/credentials/{id}
```

Na tela de envio: lista suspensa com as credenciais salvas, mais a opção de
inserir uma nova. Ao escolher uma salva, workspace e projeto preenchem sozinhos.

## Envio

Formulário: credencial (lista ou nova), batch name (padrão: a versão) e tags
(padrão: versão + `drone`).

**Preserve a partição.** O Roboflow aceita o parâmetro `split`. Enviar tudo como
`train` e deixar o Roboflow dividir desfaz todo o cuidado da Fase 3 — ele usa
split aleatório.

```python
for split in ("train", "valid", "test"):
    for img in sorted((base / split / "images").glob("*.jpg")):
        project.upload(str(img), split=split,
                       batch_name=batch_name, tag_names=tags)
```

O `batch_name` e as tags com a versão do dataset são a única resposta possível
quando alguém perguntar, meses depois, de qual voo veio determinada imagem.

Requisitos: thread separada, nunca bloqueie o event loop. Progresso visível e
possibilidade de cancelar. **Falha parcial não aborta o lote** — se 300 de 500
subiram, registre isso e permita retomar de onde parou. O `roboflow_service.py`
desta plataforma já trata falha parcial; confirme e complete.

---

## Restrições

- Não porte a UI Jinja2, o SQLite nem as rotas do M4TD.
- Não modifique `/workspaces/flyhub_connecting` — é read-only.
- Nenhum `fetch`/`axios` fora de `services/api/` — o ESLint bloqueia.
- Chaves de cache só em `lib/queryKeys.ts`.
- Rotas finas; regra em service.
- Sem `localStorage`/`sessionStorage`.
- **Dataset mostra imagem original. Voo mostra imagem processada.** A coleta
  grava o quadro antes do detector.
- Modais para tudo destrutivo ou irreversível: iniciar coleta, excluir imagens,
  excluir dataset, enviar ao Roboflow.
- Rótulos pelo que o operador controla, não pela implementação.

## Duas pendências para resolver junto

1. **`npm test` entra em watch e trava.** Troque o script para `vitest run` e
   crie `test:watch` para o modo interativo.
2. **`FlightConnection.stream_path` (banco) e `FLYHUB_STREAM_PATH` (leitor) são
   fontes diferentes do mesmo path.** Hoje coincidem. Com a coleta gravando, um
   path divergente significa gravar o voo errado — unifique, ou faça o leitor ler
   do banco.

## Como verificar

Com o stream sintético publicando:

```bash
ffmpeg -re -f lavfi -i testsrc=size=960x720:rate=30 \
  -c:v libx264 -preset ultrafast -f flv rtmp://localhost:1935/live/m4td
```

```bash
cd backend  && pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
```

Na aplicação:

1. Com o stream fora, o botão de coleta está bloqueado e o modal lista o que falta
2. Com tudo verde, o modal de confirmação abre com os parâmetros editáveis
3. Confirmar grava em `data/datasets/v0.0/raw/`, com nomes `NNNNNN_tS.SS.jpg`
4. Pausar para de gravar; o vídeo continua; Continuar retoma na mesma sessão
5. Salvar cria `train/`, `valid/`, `test/` e `split_manifest.json`
6. O dataset aparece na tela Dataset com a distribuição correta
7. O detalhe mostra a galeria; excluir imagem atualiza as contagens
8. Salvar uma credencial do Roboflow e reabrir: aparece na lista suspensa, sem
   a chave em lugar nenhum

Testes novos:

- O split não coloca quadros adjacentes em partições diferentes
- A guarda impede iniciar coleta com stream vermelho
- Pausar realmente para de gravar; continuar retoma na mesma sessão
- Dedup descarta quadro quase idêntico e mantém quadro diferente
- Credencial salva não é recuperável em texto por nenhum endpoint
- Falha parcial de upload é registrada e permite retomar

## Pronto quando

- [ ] Coleta grava quadros originais com dedup
- [ ] Guarda e modais funcionando
- [ ] Split ao salvar, com manifesto, usando `assign_temporal_splits`
- [ ] Galeria com exclusão individual e em lote
- [ ] Refazer split a partir de `raw/` após exclusões
- [ ] Credenciais do Roboflow cifradas, com lista suspensa
- [ ] Upload preservando `split`, com progresso e retomada
- [ ] `pytest -q`, `npm run lint`, `npx tsc --noEmit`, `npm test` passam
- [ ] `docs/datasets.md` e `docs/roboflow.md` com a cadeia completa
- [ ] `docs/migracao-m4td.md` atualizado com o que foi portado e o que falta
