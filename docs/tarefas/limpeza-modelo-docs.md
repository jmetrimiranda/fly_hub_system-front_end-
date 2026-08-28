# Limpeza dos dados de demonstração, fluxo do modelo e documentação

## Contexto

A plataforma passa a ser usada de verdade. Três frentes:

1. Sair dos dados de demonstração — as telas Inspeção e Dataset ainda mostram
   registros do `seed.py`, misturados com as coletas reais.
2. Estabelecer o fluxo de entrega do modelo de visão. Existe uma divisão clara
   de responsabilidade que a arquitetura precisa respeitar.
3. Documentar como rodar e como entregar o modelo, no MkDocs que já existe.

### A divisão de responsabilidade

Uma pessoa cuida **apenas** de treinar o modelo e entregar o arquivo de pesos.
Ela não mexe em código da aplicação, não edita configuração, não roda migration.
O fluxo dela, do começo ao fim:

```
treina no notebook → copia o .pt para uma pasta → commit → develop → release → main
```

**Se o processo exigir mais que isso, ele está errado.** Toda a detecção,
validação e carregamento acontece do lado da aplicação, sem intervenção.

---

# Parte 1 — Sair dos dados de demonstração

## O problema

`app/db/seed.py` popula 45 inspeções, 4 datasets e métricas fictícias. Com
coletas reais entrando, as duas fontes se misturam e ninguém distingue o que é
voo de verdade — a tela Dataset já mostra `v0.0` a `v0.3` do seed ao lado de
`v0.7` e `v0.8` reais.

## O que fazer

**Não apague o `seed.py`.** Ele é útil para desenvolvimento e para os testes.
Torne-o explícito e reversível:

1. `python -m app.db.seed --clear` remove **apenas** o que o seed criou, sem
   tocar em dados reais. Para isso, marque a origem: acrescente
   `source: Literal["seed", "collected"]` em `datasets`, `inspections`,
   `model_metrics` e `sap_notes`, com migration e padrão `"collected"` para o
   que já existe. Sem essa marca, distinguir depois vira adivinhação.

2. O `post-create.sh` continua populando em ambiente novo — a aplicação recém
   clonada não pode abrir vazia e parecer quebrada. Mas registre no log que os
   dados são de demonstração.

3. Na interface, dataset ou inspeção com `source="seed"` recebe um selo discreto
   **demonstração**. Sem selo, alguém treina em cima de dado fictício.

4. `DELETE /api/v1/admin/seed` remove os dados de demonstração pela API, e a
   tela Dataset ganha a ação correspondente. Modal de confirmação exigindo
   digitar `remover demonstração`.

5. **Limpeza de coleta vazia.** Existem `v0.4`, `v0.5` e `v0.6` com zero imagens
   — coletas que iniciaram e não salvaram nada. Ao encerrar uma coleta sem
   nenhum quadro, apague a pasta e o registro, e não consuma número de versão.
   Registre no log o motivo.

---

# Parte 2 — Fluxo do modelo de visão

## `notebooks/`

Crie na raiz, com:

- `README.md` — como treinar, onde os pesos saem, o que fazer com eles
- `treino-yolo.ipynb` — notebook base parametrizado: baixa o dataset anotado do
  Roboflow, treina, gera as métricas, copia os pesos para o destino
- `.gitignore` local ignorando `.ipynb_checkpoints/` e artefatos de treino

Leia `/workspaces/flyhub_connecting/train/` e
`/workspaces/flyhub_connecting/docs/treino/` — o M4TD já tem esse script e a
documentação do ciclo. Porte, não reinvente.

## O destino dos pesos

```
models/
├── README.md          instruções, versionado
├── .gitkeep
├── best.pt            ← o arquivo entregue (ignorado pelo Git)
└── metrics.json       ← métricas do treino (ignorado pelo Git)
```

`models/*.pt` e `models/metrics.json` entram no `.gitignore`.

**Justifique isso no README da pasta:** peso de YOLO tem dezenas de MB e muda a
cada treino. No Git, o repositório incharia rápido e todo `clone` pagaria por
cada treino já feito, para sempre. Se depois for preciso versionar, o caminho é
Git LFS ou um registry de modelos — não o Git comum.

Monte `./models` no container do backend, em `docker-compose.yml` e no override
do Dev Container. `MODEL_WEIGHTS` passa a apontar para `/models/best.pt`.

## Detecção automática

O `Detector` já recarrega por `mtime`. Estenda para que, ao aparecer ou mudar o
arquivo, ele:

1. Carregue os pesos
2. Leia `models/metrics.json`, se existir, e grave em `model_metrics`
3. Publique um evento SSE `model.changed`
4. Registre no log qual arquivo, qual data de treino, quais classes

A pessoa que treina copia o arquivo e **nada mais**. Sem reiniciar, sem
endpoint, sem comando.

Se o `.pt` estiver corrompido ou for incompatível, **não derrube a aplicação**:
volte ao passthrough, registre o erro e mostre na interface o que houve. Um peso
ruim não pode tirar a plataforma do ar.

## Toggle de inferência

Botão na tela Voo, ao lado do painel Pipeline.

```
POST /api/v1/model/toggle    {enabled: bool}
GET  /api/v1/model           estado, pesos, métricas, classes
POST /api/v1/model/reload    força releitura do disco
```

Três estados possíveis, cada um com rótulo próprio:

| Estado | Badge no vídeo |
| --- | --- |
| Sem pesos | `SEM MODELO — vídeo cru` |
| Pesos carregados, inferência desligada | `MODELO DESLIGADO — vídeo cru` |
| Pesos carregados, inferência ligada | nome do arquivo e versão |

**Desligar não descarrega os pesos.** São ações distintas: `toggle` liga e
desliga a inferência; `reload` relê o disco. Juntá-las impediria comparar
detecção ligada e desligada no mesmo voo, que é exatamente o teste que se quer
fazer ao receber um modelo novo.

O estado do toggle persiste em `app_settings` (tabela nova, chave-valor) — não
em memória. Reiniciar o backend não pode ligar sozinho um modelo que o operador
desligou de propósito.

## O contrato, escrito

`models/README.md` precisa dizer, sem ambiguidade:

```
1. Treine em notebooks/treino-yolo.ipynb
2. Copie best.pt e metrics.json para models/
3. Confira em Voo que o badge mostra o nome do arquivo
4. Commit e push do notebook — os pesos NÃO vão para o Git
5. develop → release → main
```

Se algum passo exigir editar código, configuração ou rodar comando na
aplicação, o desenho falhou e precisa ser corrigido.

---

# Parte 3 — Documentação

O MkDocs já existe (`mkdocs.yml`, `docs/`). O `starting_aplication.md` na raiz
tem o procedimento de execução, mas **está fora do MkDocs** — MkDocs não segue
caminho para fora de `docs/`.

## Duas seções novas na nav

**`docs/rodar/index.md` — Como rodar a aplicação**

Traga o conteúdo do `starting_aplication.md` para dentro de `docs/`, mantendo
tudo: a separação entre comandos de host e de container, o `sleep infinity` do
backend, os dois `-f` do Compose, a tabela de quando reiniciar o quê, e os
problemas conhecidos. Deixe um `starting_aplication.md` curto na raiz apontando
para a documentação, para quem chega pelo repositório.

**`docs/modelo/index.md` — Onde colocar o peso do modelo**

O passo a passo para quem só treina:

- Onde colocar o arquivo, com o caminho exato
- Como confirmar que carregou — o que olhar na tela, o que olhar no log
- Como testar sem drone, com o stream sintético do ffmpeg
- O que fazer quando o badge não muda
- Como o toggle funciona e por que ele não descarrega os pesos
- Por que os pesos não vão para o Git

Escreva para alguém que não conhece o resto do sistema. Comando por comando,
marcando 🖥️ HOST ou 🐳 CONTAINER como o resto da documentação.

## Fluxo de branches

Em `docs/rodar/branches.md`: `main` é o que roda em produção, `develop` recebe
as features, `release` é a preparação. Descreva o caminho de um peso novo do
notebook até a produção, e o que cada branch dispara.

---

## Restrições

- Não porte a UI Jinja2, o SQLite nem as rotas do M4TD.
- `/workspaces/flyhub_connecting` é read-only.
- Nenhum `fetch`/`axios` fora de `services/api/`.
- Rotas finas; regra em service.
- Sem `localStorage`/`sessionStorage`.
- Importação de `ultralytics` continua preguiçosa — a aplicação sobe sem torch.
- Migration para `source`, `app_settings` e o que mais surgir. Commite junto.

## Como verificar

```bash
cd backend  && pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
```

Roteiro manual:

1. `python -m app.db.seed --clear` remove só os dados de demonstração; `v0.7` e
   `v0.8`, que são reais, permanecem
2. Datasets de demonstração aparecem com selo; os reais, não
3. Coleta que salva zero quadros não deixa pasta nem registro
4. Sem `models/best.pt`: badge `SEM MODELO — vídeo cru`, aplicação normal
5. Copiar um `.pt` para `models/`: em segundos o badge muda, sem reiniciar nada
6. Toggle desliga a inferência e o badge vira `MODELO DESLIGADO`; os pesos
   continuam carregados — `GET /api/v1/model` confirma
7. Reiniciar o backend preserva o estado do toggle
8. Um arquivo `.pt` inválido volta ao passthrough e explica o erro na tela
9. `make docs` mostra as duas seções novas na navegação

Testes novos:

- `seed --clear` não remove registro com `source="collected"`
- Toggle desligado não descarrega os pesos
- Estado do toggle sobrevive a reinício
- `.pt` corrompido cai em passthrough sem levantar exceção
- Coleta com zero quadros não cria registro

## Pronto quando

- [ ] Dados de demonstração distinguíveis e removíveis por comando e pela tela
- [ ] Coleta vazia não deixa resíduo
- [ ] `notebooks/` com README e notebook de treino
- [ ] `models/` monta no container e é detectada automaticamente
- [ ] Toggle funcionando, persistido, separado do reload
- [ ] Peso inválido não derruba a aplicação
- [ ] MkDocs com "Como rodar" e "Onde colocar o peso do modelo"
- [ ] `docs/rodar/branches.md` com o fluxo main/develop/release
- [ ] Testes, lint e tsc passam
- [ ] `models/README.md` com o contrato de cinco passos
