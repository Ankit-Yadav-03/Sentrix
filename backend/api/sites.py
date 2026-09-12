"""
Site routes — GET /sites, GET /sites/{site_id}, GET /sites/{site_id}/state
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.models.db import (
    SiteRiskState, Cluster, Report
)
from backend.api.dependencies import get_db, SITE_REGISTRY

router = APIRouter()


@router.get("/sites")
def list_sites(db: Session = Depends(get_db)):
    states = db.query(SiteRiskState).all()
    result = []
    for s in states:
        recent_count = db.query(Report).filter(
            Report.site_id == s.site_id,
            Report.submitted_at >= datetime.now(timezone.utc) - timedelta(days=30),
            Report.processing_status.in_(["classified", "graphed"]),
        ).count()
        result.append({
            "site_id":           s.site_id,
            "current_state":     s.current_state,
            "dominant_category": s.dominant_category,
            "state_entered_at":  s.state_entered_at.isoformat() if s.state_entered_at else None,
            "last_evaluated_at": s.last_evaluated_at.isoformat() if s.last_evaluated_at else None,
            "report_count_30d":  recent_count,
        })
    return {"sites": result}


@router.get("/sites/{site_id}")
def get_site(site_id: str, db: Session = Depends(get_db)):
    if site_id not in SITE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown site: {site_id}")

    state = db.query(SiteRiskState).filter(SiteRiskState.site_id == site_id).first()
    clusters = db.query(Cluster).filter(
        Cluster.site_id == site_id,
        Cluster.active  == True,
    ).order_by(Cluster.pattern_score.desc()).all()

    recent_reports = db.query(Report).filter(
        Report.site_id == site_id,
        Report.submitted_at >= datetime.now(timezone.utc) - timedelta(days=30),
    ).order_by(Report.submitted_at.desc()).limit(10).all()

    return {
        "site_id":       site_id,
        "current_state": state.current_state if state else "NOMINAL",
        "state_entered_at": state.state_entered_at.isoformat() if state and state.state_entered_at else None,
        "baseline_velocity": state.baseline_velocity if state else 0.5,
        "clusters": [
            {
                "cluster_id":    str(c.cluster_id),
                "sif_category":  c.sif_category,
                "subtype_id":    c.subtype_id,
                "pattern_score": c.pattern_score,
                "risk_state":    c.risk_state,
                "report_count":  len(c.report_ids or []),
                "first_seen":    c.first_seen.isoformat() if c.first_seen else None,
                "last_updated":  c.last_updated.isoformat() if c.last_updated else None,
            }
            for c in clusters
        ],
        "recent_reports": [
            {
                "report_id":    str(r.report_id),
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "status":       r.processing_status,
                "osha_id":      r.osha_report_id,
            }
            for r in recent_reports
        ],
    }


@router.get("/sites/{site_id}/state")
def get_site_state(site_id: str, db: Session = Depends(get_db)):
    if site_id not in SITE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown site: {site_id}")

    state = db.query(SiteRiskState).filter(SiteRiskState.site_id == site_id).first()
    if not state:
        return {
            "site_id": site_id,
            "current_state": "NOMINAL",
            "dominant_category": None,
            "dominant_cluster_pattern_score": None,
            "active_clusters": 0,
        }

    # Get dominant cluster pattern_score
    dominant_cluster_score = None
    if state.dominant_cluster:
        dom_cluster = db.query(Cluster).filter(Cluster.cluster_id == state.dominant_cluster).first()
        if dom_cluster:
            dominant_cluster_score = dom_cluster.pattern_score

    # Count active clusters for this site
    active_clusters = db.query(Cluster).filter(
        Cluster.site_id == site_id,
        Cluster.active == True,
    ).count()

    return {
        "site_id": site_id,
        "current_state": state.current_state,
        "dominant_category": state.dominant_category,
        "dominant_cluster_pattern_score": dominant_cluster_score,
        "active_clusters": active_clusters,
        "state_entered_at": state.state_entered_at.isoformat() if state.state_entered_at else None,
        "last_evaluated_at": state.last_evaluated_at.isoformat() if state.last_evaluated_at else None,
    }