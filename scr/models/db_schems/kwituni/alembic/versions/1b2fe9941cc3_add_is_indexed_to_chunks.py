from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '1b2fe9941cc3'
down_revision: Union[str, None] = '66ba7b7abd80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column(
            "is_indexed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false()
        )
    )


def downgrade() -> None:
    op.drop_column("chunks", "is_indexed")
