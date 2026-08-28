# Treino do modelo de visão

Esta pasta é o **começo** do ciclo; `models/` é o fim dele.

```
voa → coleta → split temporal → Roboflow → anota → TREINA → best.pt → inferência ao vivo
                                                    ^^^^^^                ^^^^^^^^^^^^^^
                                                  notebooks/                 models/
```

Nada aqui roda dentro da aplicação, e é de propósito: a plataforma **consome**
o resultado do modelo, não o produz. O notebook grava dois arquivos e a
aplicação os lê.

---

## Instalação

Separada do resto do projeto, também de propósito:

```bash
pip install -r notebooks/requirements.txt
```

`ultralytics` arrasta torch e torchvision, cerca de 2,5 GB. O backend não
precisa de nada disso: sem pesos ele roda em passthrough, e com pesos o
`Detector` importa `ultralytics` preguiçosamente, dentro da função de carga.
Quem só opera o painel não instala 2,5 GB à toa.

Sem GPU o treino roda, mas é lento a ponto de não valer para 100 épocas. Um
`EPOCHS=5, IMGSZ=320` serve para verificar o encanamento de ponta a ponta antes
de mandar o treino real numa máquina com GPU.

---

## O notebook

`treino-yolo.ipynb`, em ordem:

1. **Parâmetros** — uma célula só, no topo. É o único lugar que se edita.
2. **Baixa** a versão anotada do Roboflow.
3. **Confere a partição** contra o `split_manifest.json` da coleta.
4. **Treina** e **valida**.
5. **Escreve** `models/best.pt` e `models/metrics.json`.

Depois disso não há passo nenhum na aplicação: ela confere o arquivo sozinha e
recarrega quando o `mtime` muda. Ver [`models/README.md`](../models/README.md).

---

## Preserve a partição ao gerar a versão no Roboflow

**Este é o ponto em que todo o cuidado da coleta pode ser perdido em um clique.**

A plataforma particiona o dataset por **blocos contíguos de tempo**, com uma
faixa de embargo nas fronteiras, e sobe cada imagem ao Roboflow com `split=`
explícito. A razão está no [ADR 004](../docs/decisions/004-split-temporal.md):
quadros consecutivos de vídeo a 30 fps são quase idênticos, e um split
aleatório põe o quadro *N* em treino e o *N+1* em validação. O modelo memoriza
em vez de generalizar, a métrica de validação sobe para um valor que não se
sustenta em voo novo, e **nada no treino indica que aconteceu**.

Ao **gerar uma versão**, o Roboflow oferece rebalancear a partição no passo
*Train/Test Split*, sugerindo por padrão algo como 70/20/10. Aceitando:

- o `data.yaml` baixado vem com a partição **do Roboflow**, não a temporal;
- quadros vizinhos no tempo voltam a ficar em partições diferentes;
- o treino roda normalmente e reporta métricas melhores que a realidade.

**O que fazer:** em *Generate* → *Train/Test Split*, escolha manter a divisão
existente (*Keep existing split* / *Use existing split*). Não use *Rebalance*.

Pré-processamento e aumento de dados podem ser usados normalmente: eles
multiplicam imagens **dentro** de cada partição, não movem imagens entre
partições. A contagem de train sobe e a proporção muda — isso é esperado. O que
não pode acontecer é uma imagem mudar de partição.

O notebook **confere isso sozinho** antes de treinar, comparando as proporções
baixadas com o `split_manifest.json` da coleta, e imprime uma tabela lado a
lado. O resultado da conferência vai para o `metrics.json`, em
`dataset.split_check_ok` — meses depois ainda dá para saber se aquelas métricas
vieram de um dataset com a partição preservada. A tela Voo mostra um aviso
quando ele é `false`.

---

## O ciclo de novo

Com o modelo em produção, a coleta seguinte já mostra as detecções sobre o
vídeo do voo — e os quadros em que o modelo erra são exatamente os que valem a
pena coletar para a próxima versão do dataset.
