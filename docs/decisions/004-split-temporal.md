# ADR 004 — Split temporal com embargo

**Estado:** aceita · **Data:** 2026-08-26

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
3. Descarta os frames dentro de `SPLIT_EMBARGO_SECONDS` de cada corte.

Sem o embargo, os frames imediatamente antes e depois da divisa continuam
sendo quase duplicatas atravessando o corte — o vazamento volta pela porta dos
fundos, em escala menor.

## Implementação

Função pura em `services/splitting.py`: recebe timestamps, devolve rótulos. Sem
I/O, sem banco. O teste verifica a **propriedade** que importa:

```python
assert max(train_timestamps) < min(valid_timestamps)
assert max(valid_timestamps) < min(test_timestamps)
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
