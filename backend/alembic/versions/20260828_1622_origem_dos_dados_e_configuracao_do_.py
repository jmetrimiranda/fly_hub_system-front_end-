"""origem dos dados e configuracao do operador

Duas coisas que entram juntas porque a mesma tarefa pediu as duas:

* `source` em `datasets`, `inspections`, `model_metrics` e `sap_notes` — a
  marca que separa demonstração de voo de verdade. O padrão é `collected`:
  linha que já existia foi coletada, até prova em contrário.
* `app_settings` — chave-valor do que o operador decide com a aplicação no ar
  e que precisa sobreviver a um reinício. Hoje só o toggle da inferência.

Revision ID: 74a17632dc02
Revises: faa5f29adb0c
Create Date: 2026-08-28 16:22:31.139847
"""
from alembic import op
import sqlalchemy as sa


revision = '74a17632dc02'
down_revision = 'faa5f29adb0c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('key'),
    )

    for table in ('datasets', 'inspections', 'model_metrics', 'sap_notes'):
        op.add_column(
            table,
            sa.Column(
                'source', sa.String(length=16), server_default='collected', nullable=False
            ),
        )
        op.create_index(op.f(f'ix_{table}_source'), table, ['source'], unique=False)

    _mark_legacy_seed()


def _mark_legacy_seed() -> None:
    """Reconciliação única: marca o que o seed criou **antes** desta coluna existir.

    Numa instalação nova nada disto casa e a migration não toca em linha
    nenhuma — o `seed.py` já grava `source="seed"` no INSERT. O trecho existe
    para o banco que rodou o seed antes, onde deixar tudo como `collected`
    faria o `--clear` não achar nada e o selo *demonstração* nunca aparecer.

    Os critérios são assinaturas que só o seed escreve, não heurísticas de
    data ou faixa de id:

    * `dataset_images.relative_path` começando com `images/frame_` — a coleta
      real grava `raw/000001_t0.00.jpg`, com índice e tempo no nome, nunca
      `images/frame_000000.jpg`;
    * `inspections.model_version = 'yolo-v8n-2026.07'` com código `INSP-###` —
      literais do seed; nenhuma outra parte do código insere `Inspection`;
    * as notas SAP penduradas nessas inspeções;
    * a métrica `mape` dessa mesma versão fictícia.

    Coletas reais sem imagem (as tentativas que não gravaram nada) **não**
    casam com o primeiro critério, e é de propósito: elas são resíduo real, e
    quem cuida delas é `python -m app.db.maintenance prune-empty`.
    """
    op.execute(
        """
        UPDATE datasets SET source = 'seed'
         WHERE id IN (
               SELECT DISTINCT dataset_id FROM dataset_images
                WHERE relative_path LIKE 'images/frame_%'
         )
        """
    )
    op.execute(
        """
        UPDATE inspections SET source = 'seed'
         WHERE model_version = 'yolo-v8n-2026.07' AND code LIKE 'INSP-%'
        """
    )
    op.execute(
        """
        UPDATE sap_notes SET source = 'seed'
         WHERE inspection_id IN (SELECT id FROM inspections WHERE source = 'seed')
        """
    )
    op.execute(
        """
        UPDATE model_metrics SET source = 'seed'
         WHERE model_version = 'yolo-v8n-2026.07' AND metric = 'mape'
        """
    )


def downgrade() -> None:
    for table in ('sap_notes', 'model_metrics', 'inspections', 'datasets'):
        op.drop_index(op.f(f'ix_{table}_source'), table_name=table)
        op.drop_column(table, 'source')
    op.drop_table('app_settings')
