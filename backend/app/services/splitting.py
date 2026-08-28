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
3. Descarta uma faixa de embargo em cada fronteira. Sem ela, os frames
   imediatamente antes e depois do corte continuam sendo quase duplicatas
   atravessando a divisa.

As duas unidades do embargo
---------------------------
O embargo é a **união** de uma janela de tempo (`embargo_seconds`) e uma janela
de quadros (`embargo_frames`). Não é redundância: o M4TD media a margem em
quadros e esta plataforma media em segundos, e cada uma cobre um buraco da
outra.

* Com deduplicação ligada o intervalo entre quadros salvos é irregular — dois
  quadros consecutivos podem estar a 2 s ou a 40 s de distância. Uma margem só
  em quadros deixa de ser margem de tempo justamente aí.
* Com intervalo de amostragem de 5 s, uma margem só de 5 s descartaria um
  quadro de cada lado. É menos separação do que o M4TD aplicava, e a diferença
  aparece na métrica, não no código.

Aplicando as duas, o descarte nunca é menor que o do protótipo.

Encolhimento das margens
------------------------
Coleta curta com margem cheia esvazia uma partição, e uma partição vazia não
mede nada. Em vez de recusar, as duas margens encolhem até caber — primeiro a
de quadros, depois a de segundos — e o resultado diz que encolheu
(`warnings`). Abaixo de `min_frames` não há o que particionar e tudo vai para
train, com aviso de nível `error`: o dataset existe, mas não serve para medir o
modelo, e isso precisa estar escrito em algum lugar que não seja a cabeça de
quem coletou.

Esta função é pura: recebe timestamps, devolve rótulos. Sem I/O, sem banco —
o que a torna barata de testar (`tests/test_splitting.py`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.models.enums import SplitName

STRATEGY = "temporal_contiguous"
STRATEGY_REASON = (
    "blocos contíguos de tempo com faixa de embargo nas fronteiras; split "
    "aleatório vazaria quadros vizinhos entre treino e validação"
)


@dataclass(frozen=True, slots=True)
class SplitConfig:
    train_ratio: float = 0.70
    valid_ratio: float = 0.15
    test_ratio: float = 0.15
    embargo_seconds: int = 5
    embargo_frames: int = 5
    """Margem em quadros. É a `DEFAULT_MARGIN` do M4TD."""
    min_frames: int = 10
    """Abaixo disto não se particiona: `valid` de 1 quadro não mede nada."""

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
class SplitWarning:
    code: str
    level: str
    """`warn` mostra em amarelo; `error` significa dataset que não mede modelo."""
    message: str


@dataclass(frozen=True, slots=True)
class SplitResult:
    assignments: list[SplitAssignment]
    train: int
    valid: int
    test: int
    embargoed: int
    embargo_frames_applied: int = 0
    embargo_seconds_applied: int = 0
    warnings: list[SplitWarning] = field(default_factory=list)


def _cuts(n: int, config: SplitConfig) -> tuple[int, int]:
    """Posições dos dois cortes na sequência ordenada.

    `int(x + 0.5)` em vez de `round()`: `round()` arredonda .5 para o par mais
    próximo, e `round(2.5) == 2` deslocaria o corte de um quadro sem motivo.
    """
    first = int(n * config.train_ratio + 0.5)
    second = first + int(n * config.valid_ratio + 0.5)
    first = max(1, min(first, n - 2))
    second = max(first + 1, min(second, n - 1))
    return first, second


def _fits(n: int, first: int, second: int, margin: int) -> bool:
    """Toda partição precisa de pelo menos um quadro depois do descarte."""
    return (
        (first - margin) >= 1
        and (second - margin) - (first + margin) >= 1
        and (n - (second + margin)) >= 1
    )


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
    warnings: list[SplitWarning] = []

    if n < config.min_frames:
        return SplitResult(
            assignments=[SplitAssignment(index, SplitName.TRAIN, False) for index in range(n)],
            train=n,
            valid=0,
            test=0,
            embargoed=0,
            warnings=[
                SplitWarning(
                    code="dataset_curto",
                    level="error",
                    message=(
                        f"Apenas {n} quadro(s) — menos que o mínimo de {config.min_frames} "
                        "para particionar. Tudo foi para train: este dataset não tem valid "
                        "nem test e não serve para medir o modelo."
                    ),
                )
            ],
        )

    train_end, valid_end = _cuts(n, config)

    margin = config.embargo_frames
    while margin > 0 and not _fits(n, train_end, valid_end, margin):
        margin -= 1
    if margin != config.embargo_frames:
        warnings.append(
            SplitWarning(
                code="margem_reduzida",
                level="warn",
                message=(
                    f"A margem de descarte caiu de {config.embargo_frames} para {margin} "
                    f"quadro(s): com {n} quadros, a margem pedida esvaziaria uma das "
                    "partições."
                    + (
                        " Com margem 0, o último quadro de treino e o primeiro de validação "
                        "são vizinhos temporais — colete mais tempo antes de treinar."
                        if margin == 0
                        else ""
                    )
                ),
            )
        )

    # A janela de tempo encolhe pelo mesmo motivo que a de quadros, e o motivo
    # aparece na primeira coleta curta: 12 quadros gravados em 6 s ficam todos
    # a menos de 5 s de alguma fronteira, e um embargo fixo de 5 s esvaziaria
    # as três partições de uma vez. Fica o maior valor que ainda deixa as três
    # com pelo menos um quadro.
    seconds_applied = config.embargo_seconds
    while True:
        assignments, counts, embargoed_total = _label(
            timestamps, order, train_end, valid_end, margin, seconds_applied
        )
        if seconds_applied == 0 or all(counts[name] > 0 for name in counts):
            break
        seconds_applied -= 1

    if seconds_applied != config.embargo_seconds:
        warnings.append(
            SplitWarning(
                code="embargo_reduzido",
                level="warn",
                message=(
                    f"A faixa de embargo caiu de {config.embargo_seconds} s para "
                    f"{seconds_applied} s: com {n} quadros em "
                    f"{(timestamps[order[-1]] - timestamps[order[0]]).total_seconds():.0f} s, "
                    "a faixa pedida esvaziaria uma das partições. Colete por mais tempo "
                    "antes de treinar."
                ),
            )
        )

    for name in (SplitName.TRAIN, SplitName.VALID, SplitName.TEST):
        if counts[name] == 0:
            warnings.append(
                SplitWarning(
                    code=f"particao_vazia_{name}",
                    level="error",
                    message=(
                        f"A partição {name} ficou vazia. Com {n} quadros não há como "
                        "separar treino, validação e teste — este dataset não mede modelo."
                    ),
                )
            )

    assignments.sort(key=lambda a: a.index)
    return SplitResult(
        assignments=assignments,
        train=counts[SplitName.TRAIN],
        valid=counts[SplitName.VALID],
        test=counts[SplitName.TEST],
        embargoed=embargoed_total,
        embargo_frames_applied=margin,
        embargo_seconds_applied=seconds_applied,
        warnings=warnings,
    )


def _label(
    timestamps: Sequence[datetime],
    order: list[int],
    train_end: int,
    valid_end: int,
    margin: int,
    embargo_seconds: int,
) -> tuple[list[SplitAssignment], dict[SplitName, int], int]:
    """Rotula uma vez, com um par de margens já escolhido."""
    embargo = timedelta(seconds=embargo_seconds)
    cuts = (train_end, valid_end)
    boundaries = [timestamps[order[cut]] for cut in cuts]

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
        in_time_window = embargo > timedelta(0) and any(
            abs(at - boundary) < embargo for boundary in boundaries
        )
        # `-margin <= posição - corte < margin`, a mesma faixa do M4TD.
        in_frame_window = any(-margin <= position - cut < margin for cut in cuts)

        if in_time_window or in_frame_window:
            embargoed_total += 1
            assignments.append(SplitAssignment(original_index, None, True))
        else:
            counts[split] += 1
            assignments.append(SplitAssignment(original_index, split, False))

    return assignments, counts, embargoed_total
