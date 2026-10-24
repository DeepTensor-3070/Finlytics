
"""Add external evidence.

Revision ID: 240067e1ccce
Revises: d27ea66e83ca
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "240067e1ccce"
down_revision: Union[str, Sequence[str], None] = "d27ea66e83ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("entity_name", sa.String(length=255), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("credibility_score", sa.Float(), nullable=True),
        sa.Column("validation_status", sa.String(length=30), nullable=False),
        sa.Column("validation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_external_evidence_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_evidence")),
    )

    op.create_index(
        op.f("ix_external_evidence_case_id"),
        "external_evidence",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_external_evidence_case_status",
        "external_evidence",
        ["case_id", "validation_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_evidence_validation_status"),
        "external_evidence",
        ["validation_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_external_evidence_validation_status"),
        table_name="external_evidence",
    )
    op.drop_index(
        "ix_external_evidence_case_status",
        table_name="external_evidence",
    )
    op.drop_index(
        op.f("ix_external_evidence_case_id"),
        table_name="external_evidence",
    )
    op.drop_table("external_evidence")
