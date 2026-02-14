"""add is_indexed to chunks

Revision ID: d3a8d38d5854
Revises: 1b2fe9941cc3
Create Date: 2025-12-18 12:34:49.308341

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3a8d38d5854'
down_revision: Union[str, None] = '1b2fe9941cc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
