import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.db.models import Base

class Synapse(Base):
    __tablename__ = "memory_synapses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    from_memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    to_memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    
    relation_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    
    evidence_ids: Mapped[List[uuid.UUID]] = mapped_column(JSONB, default=[])
    created_by: Mapped[str] = mapped_column(String, nullable=False) # condenser|retrieval|consolidation
    decay_rate: Mapped[float] = mapped_column(Float, nullable=False)
    
    last_activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    activations: Mapped[List["SynapseActivation"]] = relationship(back_populates="synapse", cascade="all, delete-orphan")

class SynapseActivation(Base):
    __tablename__ = "synapse_activations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    synapse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memory_synapses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    context_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    synapse: Mapped["Synapse"] = relationship(back_populates="activations")

class ConsolidatedMemory(Base):
    __tablename__ = "consolidated_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[List[uuid.UUID]] = mapped_column(JSONB, default=[])
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
