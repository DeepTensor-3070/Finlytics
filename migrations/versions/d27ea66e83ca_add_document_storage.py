"""Add document storage.

Revision ID: d27ea66e83ca
Revises: e0897f0c8a32
"""

from alembic import op
import sqlalchemy as sa

revision = "d27ea66e83ca"
down_revision = "e0897f0c8a32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=100), nullable=False),
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint(
            "stored_filename",
            name="uq_documents_stored_filename",
        ),
    )

    op.create_index(
        "ix_documents_case_id",
        "documents",
        ["case_id"],
    )
    op.create_index(
        "ix_documents_sha256",
        "documents",
        ["sha256"],
    )
    op.create_index(
        "ix_documents_status",
        "documents",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_sha256", table_name="documents")
    op.drop_index("ix_documents_case_id", table_name="documents")
    op.drop_table("documents")