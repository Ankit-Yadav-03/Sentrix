"""
Shared dependencies and helpers for API routers.
All imports and helper functions used across multiple routers live here.
"""

import hashlib
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (
    FastAPI, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
)
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