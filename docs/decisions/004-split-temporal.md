# ADR 004 — Split temporal com embargo

**Estado:** aceita · **Data:** 2026-08-26 · **Revisada:** 2026-08-28 (unidade do embargo)

## Problema

Ao salvar uma coleta, é preciso dividi-la em `train`, `valid` e `test`. O
requisito era explícito: nada de split aleatório.

## Por que o aleatório está errado aqui

A coleta grava a 30 fps. O frame N e o frame N+1 são a mesma cena deslocada por
33 ms — o mesmo poste, a mesma avaria, o mesmo ângulo.

Um split aleatório coloca um em `train` e o outro em `valid`. O modelo acerta a
validação porque **já viu aquela imagem**. Isso não é generalização, é memória.
E a métrica inflada é justamente o número que o card MAPE do Dashboard exibe
para quem toma decisão de manutenção.

## Decisão

Blocos **contíguos** na ordem cronológica, com faixa de embargo nas fronteiras.

1. Ordena por `captured_at`.
2. Corta em três blocos: train (70%), valid (15%), test (15%). O passado treina,
   o futuro valida — o princípio do *rolling origin* da validação cruzada de
   séries temporais.
3. Descarta os frames dentro da faixa de embargo de cada corte.

Sem o embargo, os frames imediatamente antes e depois da divisa continuam
sendo quase duplicatas atravessando o corte — o vazamento volta pela porta dos
fundos, em escala menor.

### A faixa tem duas unidades

`SPLIT_EMBARGO_SECONDS` e `SPLIT_EMBARGO_FRAMES`, aplicadas em **união**. Não é
redundância: o M4TD media a margem em quadros (`DEFAULT_MARGIN = 5`) e esta
plataforma media em segundos, e cada uma cobre um buraco da outra.

- Com deduplicação ligada, o intervalo entre quadros salvos é irregular — dois
  vizinhos podem estar a 2 s ou a 40 s de distância. Uma margem só em quadros
  deixa de ser margem de tempo justamente aí.
- Com intervalo de amostragem de 5 s, uma margem só de 5 s descarta um quadro de
  cada lado. É menos separação do que o protótipo aplicava, e a diferença
  aparece na métrica, não no código.

As proporções **não** mudaram: as duas bases sempre usaram 70/15/15.

### As margens encolhem em vez de esvaziar uma partição

Coleta curta com as margens cheias zera `valid`, e partição vazia não mede nada.
Em vez de recusar, as margens encolhem até caber — primeiro a de quadros, depois
a de segundos — e o resultado diz que encolheu, em `warnings`, que o manifesto
grava e a tela exibe.

O caso não é hipotético: 40 quadros gravados em 20 s ficam **todos** a menos de
5 s de alguma fronteira, e as três partições sairiam vazias de uma vez.

Abaixo de 10 quadros não há o que particionar: tudo vai para `train`, com aviso
de nível `error`. O dataset existe e não serve para medir o modelo — e isso
precisa estar escrito em algum lugar que não seja a cabeça de quem coletou.

## Implementação

A **decisão** é uma função pura em `services/splitting.py`: recebe timestamps,
devolve rótulos. Sem I/O, sem banco. A **execução** em disco — ler `raw/`,
copiar para `train|valid|test/images/`, escrever `split_manifest.json` — fica em
`services/split_runner.py`.

A separação é o que permite testar a regra sem tocar arquivo, e reprocessar um
dataset antigo (o botão *Refazer split*) sem tocar o banco. O tempo de cada
quadro vem do nome do arquivo, não de uma linha: um dataset copiado para outra
máquina continua particionável.

O teste verifica a **propriedade** que importa:

```python
assert max(train_timestamps) < min(valid_timestamps)
assert max(valid_timestamps) < min(test_timestamps)

# e, com o embargo ligado, a que ele existe para garantir:
for antes, depois in zip(rotulos, rotulos[1:]):
    assert antes == depois or antes is None or depois is None
```

Um teste de valor fixo quebraria em toda mudança de proporção sem detectar o
bug que interessa.

## Descartadas

- **`train_test_split` aleatório** — vazamento, pelo motivo acima.
- **Agrupar por sessão de voo** — correto, mas exige várias coletas antes de
  gerar o primeiro dataset. Fica como evolução natural quando houver volume:
  a interface da função não muda, só o critério de bloco.
- **Amostrar 1 frame a cada N** — reduz a redundância mas descarta dados úteis
  e não resolve o vazamento, só o dilui.

## Consequências

A soma `train + valid + test` é **menor** que o total de imagens. Isso é
esperado, não um bug — por isso a barra de distribuição na página Datasets
mostra os frames em embargo explicitamente. Esconder esse número faria alguém
perder uma tarde procurando onde as imagens sumiram.

O `split_manifest.json` registra a faixa **pedida** e a **aplicada**. Quando
elas divergem, foi o encolhimento acima, e o dataset traz o aviso junto — sem
isso, uma coleta curta produziria proporções que ninguém consegue explicar.
