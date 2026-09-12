"""
Component 1: SQLAlchemy ORM models — all tables from Architecture Section 3.
v0: actively uses Report, OntologyMapping, Classification, ValidationFailure.
All models defined now to avoid migration debt.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Float, Boolean, DateTime, ForeignKey, ARRAY,
    create_engine, event
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
import os
from dotenv import load_dotenv

load_dotenv()
Base = declarative_base()


class Report(Base):
    __tablename__ = "reports"

    report_id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id           = Column(String(50), nullable=False)
    source            = Column(String(20), nullable=False)
    raw_text          = Column(Text, nullable=False)
    submitted_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    submitted_by      = Column(String(100))
    processing_status = Column(String(20), nullable=False, default="pending")
    failure_reason    = Column(Text)
    osha_report_id    = Column(String(50))
    text_hash         = Column(String(64))
    created_at        = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    ontology_mappings   = relationship("OntologyMapping", back_populates="report",
                                       cascade="all, delete-orphan")
    classifications     = relationship("Classification", back_populates="report",
                                       cascade="all, delete-orphan")
    validation_failures = relationship("ValidationFailure", back_populates="report")


class OntologyMapping(Base):
    __tablename__ = "ontology_mappings"

    mapping_id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id             = Column(UUID(as_uuid=True), ForeignKey("reports.report_id"), nullable=False)
    subtype_id            = Column(String(20), nullable=False)
    sif_category          = Column(String(30), nullable=False)
    contributing_factors  = Column(ARRAY(String(50)), nullable=False)
    equipment_classes     = Column(ARRAY(String(50)), nullable=False)
    activity_contexts     = Column(ARRAY(String(50)), nullable=False)
    mapping_confidence    = Column(Float, nullable=False)
    evidence_span         = Column(Text, nullable=False)
    severity_justification = Column(Text)
    abstained             = Column(Boolean, nullable=False, default=False)
    abstain_reason        = Column(Text)
    created_at            = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    report = relationship("Report", back_populates="ontology_mappings")


class Classification(Base):
    __tablename__ = "classifications"

    classification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id         = Column(UUID(as_uuid=True), ForeignKey("reports.report_id"), nullable=False)
    sif_category      = Column(String(30), nullable=False)
    subtype_id        = Column(String(20), nullable=False)
    severity          = Column(String(10), nullable=False)
    classifier_score  = Column(Float, nullable=False)
    model_version     = Column(String(20), nullable=False)
    classified_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    report = relationship("Report", back_populates="classifications")


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    node_id    = Column(UUID(as_uuid=True), primary_key=True)  # same as report_id
    site_id    = Column(String(50), nullable=False)
    subtype_id = Column(String(20), nullable=False)
    severity   = Column(String(10), nullable=False)
    timestamp  = Column(DateTime(timezone=True), nullable=False)
    active     = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    edge_id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node    = Column(UUID(as_uuid=True), ForeignKey("graph_nodes.node_id"), nullable=False)
    target_node    = Column(UUID(as_uuid=True), ForeignKey("graph_nodes.node_id"), nullable=False)
    edge_types     = Column(ARRAY(String(30)), nullable=False)
    base_weight    = Column(Float, nullable=False)
    site_modifier  = Column(Float, nullable=False, default=0.0)
    current_weight = Column(Float, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_updated   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Cluster(Base):
    __tablename__ = "clusters"

    cluster_id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id           = Column(String(50))  # NULL for cross-site
    sif_category      = Column(String(30), nullable=False)
    subtype_id        = Column(String(20))  # NULL for mixed-subtype
    report_ids        = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    pattern_score     = Column(Float, nullable=False)
    risk_state        = Column(String(10), nullable=False)
    first_seen        = Column(DateTime(timezone=True), nullable=False)
    last_updated      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    active            = Column(Boolean, nullable=False, default=True)
    score_components  = Column(JSONB, nullable=True)


class SiteRiskState(Base):
    __tablename__ = "site_risk_states"

    site_id           = Column(String(50), primary_key=True)
    current_state     = Column(String(10), nullable=False, default="NOMINAL")
    dominant_category = Column(String(30))
    dominant_cluster  = Column(UUID(as_uuid=True), ForeignKey("clusters.cluster_id"))
    state_entered_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_evaluated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    baseline_velocity = Column(Float, nullable=False, default=0.5)


class Alert(Base):
    __tablename__ = "alerts"

    alert_id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id    = Column(UUID(as_uuid=True), ForeignKey("clusters.cluster_id"), nullable=False)
    site_id       = Column(String(50), nullable=False)
    alert_type    = Column(String(20), nullable=False)
    from_state    = Column(String(10))
    to_state      = Column(String(10), nullable=False)
    pattern_score = Column(Float, nullable=False)
    message       = Column(Text, nullable=False)
    delivered     = Column(Boolean, nullable=False, default=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ValidationFailure(Base):
    __tablename__ = "validation_failures"

    failure_id     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id      = Column(UUID(as_uuid=True), ForeignKey("reports.report_id"))
    gate           = Column(String(10), nullable=False)
    failure_reason = Column(Text, nullable=False)
    raw_input      = Column(Text)
    site_id        = Column(String(50))
    submitted_by   = Column(String(100))
    failed_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    report = relationship("Report", back_populates="validation_failures")


# Database connection
def get_engine(database_url: str = None):
    url = database_url or os.getenv("DATABASE_URL")
    return create_engine(url, echo=False, pool_pre_ping=True)


def get_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=True, autocommit=False)


# Singleton engine/session for v0 sync usage
_engine = None
_SessionFactory = None


def init_db(database_url: str = None):
    global _engine, _SessionFactory
    _engine = get_engine(database_url)
    _SessionFactory = get_session_factory(_engine)
    return _engine


def get_db():
    """Dependency-injection style session getter."""
    if _SessionFactory is None:
        raise RuntimeError("DB not initialized. Call init_db() first.")
    session = _SessionFactory()
    try:
        yield session
    finally:
        session.close()


def get_session():
    """Direct session getter for scripts."""
    if _SessionFactory is None:
        raise RuntimeError("DB not initialized. Call init_db() first.")
    return _SessionFactory()
