from .kwituni_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import Index
import uuid

class Asset(SQLAlchemyBase):
    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True, autoincrement=True)
    asset_uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    asset_type = Column(String, nullable=False)
    asset_name = Column(String, nullable=False)
    asset_size = Column(Integer, nullable=False)
    asset_config = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    asset_project_id = Column(Integer, ForeignKey("projects.project_id",ondelete="CASCADE"), nullable=False)
    project = relationship("Project", back_populates="assets")
    chunks = relationship("DataChunk", back_populates="asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_asset_project_id', asset_project_id),
        Index('ix_asset_type', asset_type),

    )