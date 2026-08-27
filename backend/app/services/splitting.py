"""Divisão temporal de datasets (Time Series Cross Validation).

Por que não `train_test_split` aleatório
---------------------------------------
A coleta grava frames a 30 fps. Frames vizinhos são quase idênticos: o mesmo
poste, a mesma avaria, deslocados por 33 ms. Um split aleatório coloca o frame
N em `train` e o frame N+1 em `valid` — o modelo "acerta" a validação porque já
viu aquela imagem, e a métrica reportada não tem relação com o desempenho em um
voo novo. É vazamento de dados, e ele infla a métrica exatamente no indicador
que o Dashboard exibe.

Estratégia
----------
1. Ordena os frames por `captured_at`.
2. Corta em três blocos **contíguos** na ordem temporal: train, valid, test.
   O passado treina, o futuro valida — o mesmo princípio do rolling-origin de
   uma validação cruzada de séries temporais.
3. Descarta uma faixa de embargo (em segundos) em cada fronteira. Sem ela, os
   frames imediatamente antes e depois do corte continuam sendo quase
   duplicatas atravessando a divisa.

Esta função é pura: recebe timestamps, devolve rótulos. Sem I/O, sem banco —
o que a torna barata de testar (`tests/test_splitting.py`).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import SplitName


@dataclass(frozen=True, slots=True)
class SplitConfig:
    train_ratio: float = 0.70
    valid_ratio: float = 0.15
    test_ratio: float = 0.15
    embargo_seconds: int = 5

    def __post_init__(self) -> None:
        total = self.train_ratio + self.valid_ratio + self.test_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"As proporções devem somar 1.0 (recebido: {total})")


@dataclass(frozen=True, slots=True)
class SplitAssignment:
    index: int
    split: SplitName | None
    embargoed: bool


@dataclass(frozen=True, slots=True)
class SplitResult:
    assignments: list[SplitAssignment]
    train: int
    valid: int
    test: int
    embargoed: int


def assign_temporal_splits(
    timestamps: Sequence[datetime], config: SplitConfig | None = None
) -> SplitResult:
    """Rotula cada frame como train/valid/test respeitando a ordem temporal.

    Os índices devolvidos referem-se à sequência **original** — a ordenação
    interna não reordena os dados de quem chamou.
    """
    config = config or SplitConfig()
    n = len(timestamps)
    if n == 0:
        return SplitResult([], 0, 0, 0, 0)

    order = sorted(range(n), key=lambda i: timestamps[i])
    train_end = int(n * config.train_ratio)
    valid_end = train_end + int(n * config.valid_ratio)

    # Garante ao menos um frame por bloco quando há dados suficientes.
    if n >= 3:
        train_end = max(1, min(train_end, n - 2))
        valid_end = max(train_end + 1, min(valid_end, n - 1))

    embargo = timedelta(seconds=config.embargo_seconds)
    boundaries = [timestamps[order[i]] for i in (train_end, valid_end) if 0 < i < n]

    assignments: list[SplitAssignment] = []
    counts = {SplitName.TRAIN: 0, SplitName.VALID: 0, SplitName.TEST: 0}
    embargoed_total = 0

    for position, original_index in enumerate(order):
        if position < train_end:
            split = SplitName.TRAIN
        elif position < valid_end:
            split = SplitName.VALID
        else:
            split = SplitName.TEST

        at = timestamps[original_index]
        in_embargo = any(abs(at - boundary) < embargo for boundary in boundaries)

        if in_embargo:
            embargoed_total += 1
            assignments.append(SplitAssignment(original_index, None, True))
        else:
            counts[split] += 1
            assignments.append(SplitAssignment(original_index, split, False))

    assignments.sort(key=lambda a: a.index)
    return SplitResult(
        assignments=assignments,
        train=counts[SplitName.TRAIN],
        valid=counts[SplitName.VALID],
        test=counts[SplitName.TEST],
        embargoed=embargoed_total,
    )
