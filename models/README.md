# Onde o peso do modelo mora

Esta pasta é o **ponto de entrega** do modelo de visão. Quem treina copia dois
arquivos para cá e não faz mais nada.

```
models/
├── README.md       este arquivo, versionado
├── .gitkeep        mantém a pasta no Git mesmo vazia
├── best.pt         ← o peso entregue        (ignorado pelo Git)
└── metrics.json    ← as métricas do treino  (ignorado pelo Git)
```

Dentro do container ela aparece como `/models`, e é para lá que
`MODELS_DIR` aponta. A aplicação lê `MODELS_DIR/best.pt`.

---

## O contrato, em cinco passos

```
1. Treine em notebooks/treino-yolo.ipynb
2. Copie best.pt e metrics.json para models/
3. Confira em Voo que o badge mostra o nome do arquivo
4. Commit e push do notebook — os pesos NÃO vão para o Git
5. develop → release → main
```

**Se algum passo exigir editar código, editar configuração ou rodar um comando
na aplicação, o desenho falhou e precisa ser corrigido** — não contornado com
uma instrução a mais aqui. Não há endpoint de upload, não há migration, não há
reinício: a aplicação confere o arquivo sozinha, no máximo uma vez por segundo,
e recarrega quando o `mtime` muda.

O passo 3 é a verificação, não uma formalidade: é ele que separa "copiei o
arquivo" de "a aplicação está usando o arquivo". O passo a passo com telas está
em [Onde colocar o peso do modelo](../docs/modelo/index.md).

---

## Por que os pesos não vão para o Git

Um `best.pt` de YOLO tem dezenas de MB e **muda a cada treino**. O Git guarda
cada versão para sempre: em um ano de iteração o repositório passaria de
alguns MB para vários GB, e todo `git clone` — de qualquer pessoa, para
qualquer finalidade — pagaria por cada treino já feito, inclusive os
descartados. O histórico também não ajudaria a entender nada: o diff de dois
arquivos binários de pesos não é legível.

Por isso `models/*.pt` e `models/metrics.json` estão no `.gitignore`, e o que
vai para o Git é o **notebook que os produz** — que é texto, tem diff legível e
é o que de fato explica o modelo.

Se um dia for preciso versionar os pesos mesmo assim, o caminho é **Git LFS**
ou um **registry de modelos** (MLflow, W&B, um bucket versionado). Não o Git
comum: ele não tem como devolver o espaço depois, e reescrever histórico para
remover binários é uma operação que quebra o clone de todo mundo.

---

## O que a aplicação faz com cada arquivo

| Arquivo | Obrigatório | O que acontece |
| --- | --- | --- |
| `best.pt` | sim, para inferir | carregado no `Detector`; sem ele o vídeo passa cru e o badge diz `SEM MODELO` |
| `metrics.json` | não | vira as métricas na tela e linhas em `model_metrics`; ausente, o modelo funciona igual e a tela só não mostra mAP |

`metrics.json` é opcional de propósito: um `best.pt` copiado à mão, de outra
fonte, tem que funcionar. A ausência de métrica não é erro de modelo.

---

## Ligar e desligar a inferência

O botão fica na tela **Voo**, ao lado do painel Pipeline.

- **Desligar não descarrega os pesos.** O modelo continua em memória e religar
  volta a detectar no quadro seguinte, sem os segundos de carga. É o que
  permite comparar o mesmo voo com e sem detecção — o primeiro teste que se faz
  ao receber um modelo novo.
- **Recarregar** (`POST /api/v1/model/reload`) relê o disco. É outra ação, para
  o caso raro de o arquivo ser reescrito com o mesmo `mtime`.
- O estado do toggle é **persistido**. Reiniciar o backend não religa sozinho
  um modelo que alguém desligou de propósito.

---

## Quando o peso não carrega

Um `.pt` corrompido, incompatível ou treinado por uma versão incompatível do
Ultralytics **não derruba a aplicação**. O detector volta ao passthrough, o
vídeo continua passando, o badge fica vermelho com `MODELO NÃO CARREGOU — vídeo
cru` e a mensagem do erro aparece na tela. Um peso ruim não pode tirar a
plataforma do ar.
