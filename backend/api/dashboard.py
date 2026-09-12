"""
Dashboard routes — GET /health, GET /stats, GET /alerts, GET /validation-failures
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.models.db import (
    Report, Cluster, SiteRiskState, Alert, ValidationFailure, Classification
)
from backend.api.dependencies import get_db, SITE_REGISTRY, get_model_info

router = APIRouter()


@router.get("/health")
def health():
    model_info = get_model_info()
    return {
        "status": "ok",
        "version": "0.1.0",
        "model_loaded": model_info["model_loaded"],
        "model_version": model_info["model_version"],
        "site_count": len(SITE_REGISTRY),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_reports = db.query(Report).count()
    classified    = db.query(Report).filter(
        Report.processing_status.in_(["classified", "graphed"])
    ).count()
    active_clusters = db.query(Cluster).filter(Cluster.active == True).count()
    elevated_sites  = db.query(SiteRiskState).filter(
        SiteRiskState.current_state.in_(["ELEVATED", "CRITICAL"])
    ).count()
    gate_failures = db.query(ValidationFailure).count()

    # Severity breakdown
    severity_counts = {}
    for clf in db.query(Classification).all():
        severity_counts[clf.severity] = severity_counts.get(clf.severity, 0) + 1

    # Category breakdown
    category_counts = {}
    for clf in db.query(Classification).all():
        category_counts[clf.sif_category] = category_counts.get(clf.sif_category, 0) + 1

    return {
        "total_reports":      total_reports,
        "classified_reports": classified,
        "active_clusters":    active_clusters,
        "elevated_sites":     elevated_sites,
        "gate_failures":      gate_failures,
        "severity_breakdown": severity_counts,
        "category_breakdown": category_counts,
    }


@router.get("/alerts")
def list_alerts(
    site_id: Optional[str] = None,
    delivered: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(Alert)
    if site_id:
        q = q.filter(Alert.site_id == site_id)
    if not delivered:
        q = q.filter(Alert.delivered == False)
    alerts = q.order_by(Alert.created_at.desc()).limit(100).all()
    return {
        "alerts": [
            {
                "alert_id":     str(a.alert_id),
                "cluster_id":   str(a.cluster_id),
                "site_id":      a.site_id,
                "alert_type":   a.alert_type,
                "from_state":   a.from_state,
                "to_state":     a.to_state,
                "pattern_score": a.pattern_score,
                "message":      a.message,
                "delivered":    a.delivered,
                "created_at":   a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ]
    }


@router.get("/validation-failures")
def list_validation_failures(
    gate: Optional[str] = None,
    site_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(ValidationFailure)
    if gate:
        q = q.filter(ValidationFailure.gate == gate)
    if site_id:
        q = q.filter(ValidationFailure.site_id == site_id)
    total = q.count()
    failures = q.order_by(ValidationFailure.failed_at.desc()).limit(limit).all()
    return {
        "total": total,
        "failures": [
            {
                "failure_id":    str(f.failure_id),
                "report_id":     str(f.report_id) if f.report_id else None,
                "gate":          f.gate,
                "failure_reason": f.failure_reason,
                "site_id":       f.site_id,
                "submitted_by":  f.submitted_by,
                "failed_at":     f.failed_at.isoformat() if f.failed_at else None,
            }
            for f in failures
        ]
    }