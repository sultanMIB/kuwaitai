from .kwituni_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import Index
import uuid
from pydantic import BaseModel

class DataChunk(SQLAlchemyBase):
    __tablename__ = "chunks"

    chunk_id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    chunk_text = Column(String, nullable=False)
    chunk_metadata = Column(JSONB, nullable=True)
    chunk_order = Column(Integer, nullable=False)
    chunk_project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    project = relationship("Project", back_populates="chunks")
    chunk_asset_id = Column(Integer, ForeignKey("assets.asset_id",ondelete="CASCADE"), nullable=False)
    asset = relationship("Asset", back_populates="chunks")
    is_indexed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index('ix_chunk_asset_id', chunk_asset_id),
        Index('ix_chunk_project_id', chunk_project_id),
    )
class RetrievedDocument(BaseModel):
    text:str
    score:float