"""
FastAPI Application — SIH26165 SIF Precursor Detection System
All routes from Architecture doc Section 4 (API contracts).
"""

import hashlib
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.models.db import (
    init_db, get_db, Report, OntologyMapping, Classification,
    Cluster, SiteRiskState, Alert, ValidationFailure
)
from backend.pipeline.validator import (
    gate_1_validate, gate_2_validate, validate_mapping,
    get_standards_references, load_site_registry_from_db, SITE_REGISTRY
)
from backend.pipeline.pdf_parser import extract_text_from_pdf
from backend.pipeline.llm_extraction import run_extraction_with_fallback
from backend.pipeline.classifier import classify_mapping, get_model_info
from backend.graph.pattern_score import (
    compute_site_cluster_score, determine_risk_state, T_WATCH, T_ELEVATED
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CATEGORY_WINDOWS = {
    "EXPLOSION_FIRE":      7,
    "CHEMICAL_EXPOSURE":   14,
    "ELECTRICAL":          14,
    "FALL_FROM_HEIGHT":    30,
    "CAUGHT_IN_STRUCK_BY": 30,
    "VEHICLE_TRANSPORT":   30,
}


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:oilsif357@localhost:5432/sif_db")
    engine = init_db(db_url)
    logger.info("DB initialized")
    # Load site registry from DB
    from backend.models.db import get_session
    try:
        s = get_session()
        load_site_registry_from_db(s)
        s.close()
    except Exception as e:
        logger.warning(f"Site registry load from DB failed: {e} — using defaults")
    yield
    logger.info("Shutdown")


app = FastAPI(
    title="SIF Precursor Detection System — v0",
    description="SIH26165: AI-powered near-miss report analysis for oil & gas safety",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_site_state(session: Session, site_id: str) -> str:
    s = session.query(SiteRiskState).filter(SiteRiskState.site_id == site_id).first()
    return s.current_state if s else "NOMINAL"


def _update_site_state(session: Session, site_id: str, new_state: str,
                        sif_category: str, cluster_id=None):
    state_order = ["NOMINAL", "WATCH", "ELEVATED", "CRITICAL"]
    site_state = session.query(SiteRiskState).filter(
        SiteRiskState.site_id == site_id
    ).first()
    if not site_state:
        site_state = SiteRiskState(site_id=site_id)
        session.add(site_state)
        session.flush()
    curr_idx = state_order.index(site_state.current_state)
    new_idx  = state_order.index(new_state)
    if new_idx > curr_idx:
        site_state.current_state     = new_state
        site_state.dominant_category = sif_category
        site_state.dominant_cluster  = cluster_id
        site_state.state_entered_at  = datetime.now(timezone.utc)
    site_state.last_evaluated_at = datetime.now(timezone.utc)


def _run_cluster_update(session: Session, site_id: str, subtype_id: str,
                         sif_category: str) -> dict:
    """Recompute cluster for site+subtype and update DB."""
    window = CATEGORY_WINDOWS.get(sif_category, 30)
    result = compute_site_cluster_score(session, site_id, subtype_id, window)
    reports = result["cluster_reports"]
    score   = result["pattern_score"]

    if not reports:
        return {"pattern_score": 0.0, "risk_state": "NOMINAL", "new_cluster": False}

    has_critical = any(r["severity"] == "CRITICAL" for r in reports)
    cluster_size = len(reports)

    # State transition logic
    risk_state = "NOMINAL"
    if score >= T_WATCH and cluster_size >= 2:
        risk_state = "WATCH"
    if score >= T_ELEVATED:
        risk_state = "ELEVATED"
    if has_critical and risk_state in ("WATCH", "ELEVATED"):
        risk_state = "ELEVATED"

    # Upsert cluster
    existing = session.query(Cluster).filter(
        Cluster.site_id   == site_id,
        Cluster.subtype_id == subtype_id,
        Cluster.active    == True,
    ).first()

    report_ids = [r["report_id"] for r in reports]
    if existing:
        existing.report_ids   = report_ids
        existing.pattern_score = score
        existing.risk_state   = risk_state
        existing.last_updated = datetime.now(timezone.utc)
        cluster_id = existing.cluster_id
        new_cluster = False
    else:
        cluster = Cluster(
            site_id       = site_id,
            sif_category  = sif_category,
            subtype_id    = subtype_id,
            report_ids    = report_ids,
            pattern_score = score,
            risk_state    = risk_state,
            first_seen    = datetime.now(timezone.utc),
            active        = True,
        )
        session.add(cluster)
        session.flush()
        cluster_id  = cluster.cluster_id
        new_cluster = True

    # Update site risk state
    _update_site_state(session, site_id, risk_state, sif_category, cluster_id)

    return {
        "pattern_score":     score,
        "score_components":  result["score_components"],
        "risk_state":        risk_state,
        "cluster_id":        str(cluster_id),
        "cluster_size":      cluster_size,
        "new_cluster":       new_cluster,
        "has_critical":      has_critical,
    }


def _full_pipeline(session: Session, report_id, raw_text: str,
                   site_id: str, background_tasks: BackgroundTasks = None) -> dict:
    """
    Run LLM extraction → vocabulary lock → classifier → cluster update.
    Called from both text and PDF submission endpoints.
    Returns pipeline result dict.
    """
    report = session.query(Report).filter(Report.report_id == report_id).first()
    report.processing_status = "processing"
    session.commit()

    # LLM extraction
    try:
        llm_output = run_extraction_with_fallback(raw_text)
    except Exception as e:
        report.processing_status = "failed"
        report.failure_reason    = str(e)
        session.commit()
        raise HTTPException(status_code=502, detail=f"LLM extraction failed: {e}")

    # Gate 3: abstain
    if llm_output.get("abstain"):
        reason = llm_output.get("abstain_reason", "LLM abstained — insufficient evidence")
        report.processing_status = "abstained"
        vf = ValidationFailure(
            report_id=report.report_id, gate="GATE_3",
            failure_reason=reason, site_id=site_id,
        )
        session.add(vf)
        session.commit()
        return {
            "report_id":  str(report_id),
            "abstained":  True,
            "abstain_reason": reason,
        }

    # Vocabulary lock — save valid mappings only
    valid_mappings = []
    for m in llm_output.get("mappings", []):
        ok_m, errors = validate_mapping(m)
        if not ok_m:
            logger.warning(f"Vocab invalid for report {report_id}: {errors}")
            vf = ValidationFailure(
                report_id=report.report_id, gate="GATE_3",
                failure_reason=f"Vocab lock: {errors}",
                site_id=site_id,
            )
            session.add(vf)
            continue

        refs = get_standards_references(m["subtype_id"])
        mapping = OntologyMapping(
            report_id            = report.report_id,
            subtype_id           = m["subtype_id"],
            sif_category         = m["sif_category"],
            contributing_factors = m.get("contributing_factors", []),
            equipment_classes    = m.get("equipment_classes", []),
            activity_contexts    = m.get("activity_contexts", []),
            mapping_confidence   = m.get("mapping_confidence", 0.75),
            evidence_span        = m.get("evidence_span", ""),
            severity_justification = m.get("severity_justification", ""),
        )
        session.add(mapping)
        valid_mappings.append((mapping, m, refs))

    if not valid_mappings:
        report.processing_status = "failed"
        report.failure_reason    = "No valid ontology mappings after vocabulary lock"
        session.commit()
        raise HTTPException(
            status_code=422,
            detail="Report could not be mapped to the safety ontology. "
                   "Please provide more specific incident details."
        )

    report.processing_status = "mapped"
    session.flush()

    # Classify primary mapping (highest confidence)
    best_mapping_obj, best_mapping_dict, best_refs = max(
        valid_mappings, key=lambda x: x[1].get("mapping_confidence", 0)
    )
    clf_result = classify_mapping(best_mapping_dict)
    classification = Classification(
        report_id        = report.report_id,
        sif_category     = clf_result["sif_category"],
        subtype_id       = clf_result["subtype_id"],
        severity         = clf_result["severity"],
        classifier_score = clf_result["classifier_score"],
        model_version    = clf_result["model_version"],
    )
    session.add(classification)
    report.processing_status = "classified"
    session.commit()

    # Cluster update
    cluster_result = _run_cluster_update(
        session, site_id,
        clf_result["subtype_id"],
        clf_result["sif_category"],
    )
    report.processing_status = "graphed"
    session.commit()

    return {
        "report_id":           str(report_id),
        "abstained":           False,
        "sif_category":        clf_result["sif_category"],
        "subtype_id":          clf_result["subtype_id"],
        "severity":            clf_result["severity"],
        "classifier_score":    clf_result["classifier_score"],
        "model_version":       clf_result["model_version"],
        "mappings":            [
            {
                "subtype_id":            m["subtype_id"],
                "sif_category":          m["sif_category"],
                "contributing_factors":  m.get("contributing_factors", []),
                "equipment_classes":     m.get("equipment_classes", []),
                "activity_contexts":     m.get("activity_contexts", []),
                "mapping_confidence":    m.get("mapping_confidence"),
                "evidence_span":         m.get("evidence_span"),
                "severity":              m.get("severity"),
                "severity_justification": m.get("severity_justification"),
                "standards_references":  refs,
            }
            for _, m, refs in valid_mappings
        ],
        "cluster":             cluster_result,
        "site_risk_state":     cluster_result["risk_state"],
        "state_transition":    cluster_result["risk_state"] != "NOMINAL",
    }


# ===========================================================================
# ROUTES
# ===========================================================================

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
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


# ---------------------------------------------------------------------------
# POST /submit/text — Architecture doc Section 4.1
# ---------------------------------------------------------------------------

@app.post("/submit/text")
def submit_text(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submit a near-miss report as plain text.
    Expected payload: { site_id, raw_text, source?, submitted_by? }
    """
    # Normalize
    if "source" not in payload:
        payload["source"] = "manual_text"

    # Gate 1
    ok, reason = gate_1_validate(payload)
    if not ok:
        vf = ValidationFailure(
            gate="GATE_1", failure_reason=reason,
            raw_input=payload.get("raw_text", "")[:500],
            site_id=payload.get("site_id"),
            submitted_by=payload.get("submitted_by"),
        )
        db.add(vf)
        db.commit()
        raise HTTPException(status_code=400, detail=reason)

    # Gate 2
    ok2, reason2 = gate_2_validate(payload["raw_text"])
    if not ok2:
        vf = ValidationFailure(
            gate="GATE_2", failure_reason=reason2,
            raw_input=payload["raw_text"][:500],
            site_id=payload["site_id"],
            submitted_by=payload.get("submitted_by"),
        )
        db.add(vf)
        db.commit()
        raise HTTPException(status_code=400, detail=reason2)

    # Save report
    text_hash = hashlib.sha256(
        (payload["raw_text"].strip() + payload["site_id"]).encode()
    ).hexdigest()
    report = Report(
        site_id          = payload["site_id"],
        source           = payload["source"],
        raw_text         = payload["raw_text"],
        submitted_by     = payload.get("submitted_by"),
        processing_status = "pending",
        text_hash        = text_hash,
    )
    db.add(report)
    db.flush()

    # Full pipeline (synchronous for v0)
    result = _full_pipeline(db, report.report_id, payload["raw_text"], payload["site_id"])
    return result


# ---------------------------------------------------------------------------
# POST /submit/pdf — Architecture doc Section 4.2
# ---------------------------------------------------------------------------

@app.post("/submit/pdf")
async def submit_pdf(
    file: UploadFile = File(...),
    site_id: str = Form(...),
    submitted_by: str = Form(None),
    db: Session = Depends(get_db),
):
    """Upload a PDF incident report. Text extracted, then same pipeline as /submit/text."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=413, detail="PDF file too large (max 10MB).")

    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF extraction failed: {e}")

    payload = {
        "site_id": site_id,
        "raw_text": raw_text,
        "source": "pdf_upload",
        "submitted_by": submitted_by,
    }

    ok, reason = gate_1_validate(payload)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    ok2, reason2 = gate_2_validate(raw_text)
    if not ok2:
        raise HTTPException(status_code=400, detail=reason2)

    text_hash = hashlib.sha256((raw_text.strip() + site_id).encode()).hexdigest()
    report = Report(
        site_id=site_id, source="pdf_upload",
        raw_text=raw_text, submitted_by=submitted_by,
        processing_status="pending", text_hash=text_hash,
    )
    db.add(report)
    db.flush()

    result = _full_pipeline(db, report.report_id, raw_text, site_id)
    return result


# ---------------------------------------------------------------------------
# GET /reports — list all reports (paginated)
# ---------------------------------------------------------------------------

@app.get("/reports")
def list_reports(
    site_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Report)
    if site_id:
        q = q.filter(Report.site_id == site_id)
    if status:
        q = q.filter(Report.processing_status == status)
    total = q.count()
    reports = q.order_by(Report.submitted_at.desc()).offset(offset).limit(limit).all()

    items = []
    for r in reports:
        clf = db.query(Classification).filter(
            Classification.report_id == r.report_id
        ).first()
        items.append({
            "report_id":         str(r.report_id),
            "site_id":           r.site_id,
            "source":            r.source,
            "submitted_at":      r.submitted_at.isoformat() if r.submitted_at else None,
            "submitted_by":      r.submitted_by,
            "processing_status": r.processing_status,
            "osha_report_id":    r.osha_report_id,
            "sif_category":      clf.sif_category if clf else None,
            "subtype_id":        clf.subtype_id if clf else None,
            "severity":          clf.severity if clf else None,
            "classifier_score":  clf.classifier_score if clf else None,
        })
    return {"total": total, "items": items, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# GET /reports/{report_id} — full report detail
# ---------------------------------------------------------------------------

@app.get("/reports/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    try:
        rid = uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid report_id format")

    report = db.query(Report).filter(Report.report_id == rid).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    mappings = db.query(OntologyMapping).filter(
        OntologyMapping.report_id == rid
    ).all()
    clf = db.query(Classification).filter(
        Classification.report_id == rid
    ).first()
    vfs = db.query(ValidationFailure).filter(
        ValidationFailure.report_id == rid
    ).all()

    return {
        "report_id":         str(report.report_id),
        "site_id":           report.site_id,
        "source":            report.source,
        "raw_text":          report.raw_text,
        "submitted_at":      report.submitted_at.isoformat() if report.submitted_at else None,
        "submitted_by":      report.submitted_by,
        "processing_status": report.processing_status,
        "osha_report_id":    report.osha_report_id,
        "failure_reason":    report.failure_reason,
        "mappings": [
            {
                "mapping_id":            str(m.mapping_id),
                "subtype_id":            m.subtype_id,
                "sif_category":          m.sif_category,
                "contributing_factors":  m.contributing_factors,
                "equipment_classes":     m.equipment_classes,
                "activity_contexts":     m.activity_contexts,
                "mapping_confidence":    m.mapping_confidence,
                "evidence_span":         m.evidence_span,
                "severity_justification": m.severity_justification,
                "abstained":             m.abstained,
                "standards_references":  get_standards_references(m.subtype_id),
            }
            for m in mappings
        ],
        "classification": {
            "sif_category":    clf.sif_category,
            "subtype_id":      clf.subtype_id,
            "severity":        clf.severity,
            "classifier_score": clf.classifier_score,
            "model_version":   clf.model_version,
            "classified_at":   clf.classified_at.isoformat() if clf.classified_at else None,
        } if clf else None,
        "validation_failures": [
            {"gate": v.gate, "reason": v.failure_reason, "failed_at": v.failed_at.isoformat()}
            for v in vfs
        ],
    }


# ---------------------------------------------------------------------------
# GET /sites — all sites with current state
# ---------------------------------------------------------------------------

@app.get("/sites")
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


# ---------------------------------------------------------------------------
# GET /sites/{site_id} — site detail with clusters
# ---------------------------------------------------------------------------

@app.get("/sites/{site_id}")
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


# ---------------------------------------------------------------------------
# GET /clusters — all active clusters
# ---------------------------------------------------------------------------

@app.get("/clusters")
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


# ---------------------------------------------------------------------------
# GET /clusters/{cluster_id} — cluster detail with Pattern Score breakdown
# ---------------------------------------------------------------------------

@app.get("/clusters/{cluster_id}")
def get_cluster(cluster_id: str, db: Session = Depends(get_db)):
    try:
        cid = uuid.UUID(cluster_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cluster_id")

    cluster = db.query(Cluster).filter(Cluster.cluster_id == cid).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Recompute score breakdown live
    window = CATEGORY_WINDOWS.get(cluster.sif_category, 30)
    score_result = compute_site_cluster_score(
        db, cluster.site_id, cluster.subtype_id, window
    )

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
        "score_components": score_result.get("score_components", {}),
        "edge_count":       score_result.get("edge_count", 0),
        "reports":          reports_detail,
    }


# ---------------------------------------------------------------------------
# GET /alerts — all undelivered alerts
# ---------------------------------------------------------------------------

@app.get("/alerts")
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


# ---------------------------------------------------------------------------
# GET /validation-failures — Gate failure log
# ---------------------------------------------------------------------------

@app.get("/validation-failures")
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


# ---------------------------------------------------------------------------
# GET /stats — aggregate stats for dashboard
# ---------------------------------------------------------------------------

@app.get("/stats")
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
