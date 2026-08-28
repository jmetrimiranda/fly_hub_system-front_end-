"""coleta, galeria e credenciais do roboflow

Três mudanças, uma por fase da migração do M4TD:

* **Coleta** — os parâmetros escolhidos no modal (`sample_interval_seconds`,
  `frame_limit`, `dedup_enabled`) e os contadores que explicam a forma do
  dataset (`dedup_skipped`, `io_dropped`). Sem eles, "500 amostras viraram 180
  arquivos" não tem resposta seis meses depois.
* **Split e galeria** — `embargo_frames`, `embargoed_count` e `split_at`, que
  registram a margem realmente aplicada e quando o split rodou pela última vez
  (um resplit atualiza).
* **Roboflow** — `roboflow_credentials` com a chave cifrada, e as marcas de
  envio por imagem (`dataset_images.roboflow_sent_at`) que permitem retomar um
  lote parcial de onde parou.

`flight_connection.stream_path` sai. Ela duplicava `FLYHUB_STREAM_PATH`, que é
o que o leitor de quadros consome: duas fontes do mesmo valor, coincidindo por
acaso. Com a coleta gravando, divergirem significa gravar o voo errado sem
mensagem de erro nenhuma.

Toda coluna `NOT NULL` entra com `server_default`: a tabela `datasets` já tem
linhas em qualquer ambiente que rodou uma coleta, e um `ADD COLUMN NOT NULL`
sem padrão falha na hora do deploy, não aqui.

Revision ID: faa5f29adb0c
Revises: e0229b46c0c0
Create Date: 2026-08-28 15:06:12.379151
"""
from alembic import op
import sqlalchemy as sa


revision = 'faa5f29adb0c'
down_revision = 'e0229b46c0c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'roboflow_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=80), nullable=False),
        sa.Column('workspace', sa.String(length=120), nullable=False),
        sa.Column('project', sa.String(length=120), nullable=False),
        # Token Fernet, nunca a chave. Ver `core/crypto.py`.
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('label'),
    )

    op.add_column('dataset_images', sa.Column('roboflow_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('dataset_images', sa.Column('roboflow_error', sa.Text(), nullable=True))

    op.add_column('datasets', sa.Column('sample_interval_seconds', sa.Float(), nullable=False, server_default='2.0'))
    op.add_column('datasets', sa.Column('frame_limit', sa.Integer(), nullable=True))
    op.add_column('datasets', sa.Column('dedup_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('datasets', sa.Column('dedup_skipped', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('datasets', sa.Column('io_dropped', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('datasets', sa.Column('embargo_frames', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('datasets', sa.Column('embargoed_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('datasets', sa.Column('split_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('datasets', sa.Column('roboflow_batch', sa.String(length=120), nullable=True))
    op.add_column('datasets', sa.Column('roboflow_uploaded', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('datasets', sa.Column('roboflow_failed', sa.Integer(), nullable=False, server_default='0'))

    op.drop_column('flight_connection', 'stream_path')


def downgrade() -> None:
    op.add_column(
        'flight_connection',
        sa.Column('stream_path', sa.VARCHAR(length=120), nullable=False, server_default='live/m4td'),
    )
    for column in (
        'roboflow_failed',
        'roboflow_uploaded',
        'roboflow_batch',
        'split_at',
        'embargoed_count',
        'embargo_frames',
        'io_dropped',
        'dedup_skipped',
        'dedup_enabled',
        'frame_limit',
        'sample_interval_seconds',
    ):
        op.drop_column('datasets', column)
    op.drop_column('dataset_images', 'roboflow_error')
    op.drop_column('dataset_images', 'roboflow_sent_at')
    op.drop_table('roboflow_credentials')
