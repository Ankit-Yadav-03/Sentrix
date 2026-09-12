"""
Cluster routes — GET /clusters, GET /clusters/{cluster_id}
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.models.db import (
    Cluster, Report, OntologyMapping, Classification
)
from backend.api.dependencies import (
    get_db, CATEGORY_WINDOWS, compute_site_cluster_score
)

router = APIRouter()


@router.get("/clusters")
def list_clusters(
    site_id: Optional[str] = None,
    min_score: float = 0.0,
    db: Session = Depends(get_db),
):
    q = db.query(Cluster).filter(Cluster.active == True)
    if site_id:
        q = q.filter(Cluster.site_id == site_id)
    if min_score > 0:
        q = q.filter(Cluster.pattern_score >= min_score)
    clusters = q.order_by(Cluster.pattern_score.desc()).all()

    return {
        "clusters": [
            {
                "cluster_id":    str(c.cluster_id),
                "site_id":       c.site_id,
                "sif_category":  c.sif_category,
                "subtype_id":    c.subtype_id,
                "pattern_score": c.pattern_score,
                "risk_state":    c.risk_state,
                "report_count":  len(c.report_ids or []),
                "first_seen":    c.first_seen.isoformat() if c.first_seen else None,
                "last_updated":  c.last_updated.isoformat() if c.last_updated else None,
            }
            for c in clusters
        ]
    }


@router.get("/clusters/{cluster_id}")
def get_cluster(cluster_id: str, db: Session = Depends(get_db)):
    try:
        cid = uuid.UUID(cluster_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cluster_id")

    cluster = db.query(Cluster).filter(Cluster.cluster_id == cid).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Use stored score_components if available, otherwise recompute
    if cluster.score_components:
        score_components = cluster.score_components
        edge_count = 0  # Not stored, could be added later
    else:
        window = CATEGORY_WINDOWS.get(cluster.sif_category, 30)
        score_result = compute_site_cluster_score(
            db, cluster.site_id, cluster.subtype_id, window
        )
        score_components = score_result.get("score_components", {})
        edge_count = score_result.get("edge_count", 0)

    # Fetch individual reports in cluster
    report_ids = cluster.report_ids or []
    reports_detail = []
    for rid in report_ids:
        r = db.query(Report).filter(Report.report_id == rid).first()
        c = db.query(Classification).filter(Classification.report_id == rid).first()
        m = db.query(OntologyMapping).filter(OntologyMapping.report_id == rid).first()
        if r:
            reports_detail.append({
                "report_id":    str(r.report_id),
                "osha_id":      r.osha_report_id,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "site_id":      r.site_id,
                "severity":     c.severity if c else None,
                "sif_category": c.sif_category if c else None,
                "evidence_span": m.evidence_span if m else None,
                "contributing_factors": m.contributing_factors if m else [],
                "equipment_classes": m.equipment_classes if m else [],
            })

    return {
        "cluster_id":       str(cluster.cluster_id),
        "site_id":          cluster.site_id,
        "sif_category":     cluster.sif_category,
        "subtype_id":       cluster.subtype_id,
        "pattern_score":    cluster.pattern_score,
        "risk_state":       cluster.risk_state,
        "first_seen":       cluster.first_seen.isoformat() if cluster.first_seen else None,
        "last_updated":     cluster.last_updated.isoformat() if cluster.last_updated else None,
        "score_components": score_components,
        "edge_count":       edge_count,
        "reports":          reports_detail,
    }