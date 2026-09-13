"""
Report routes — POST /submit/text, POST /submit/pdf, GET /reports, GET /reports/{report_id}
"""

import hashlib
import uuid
from typing import Optional

from fastapi import (
    APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
)
from sqlalchemy.orm import Session

from backend.models.db import (
    Report, OntologyMapping, Classification, ValidationFailure
)
from backend.api.dependencies import (
    get_db, gate_1_validate, gate_2_validate, SITE_REGISTRY,
    _full_pipeline, extract_text_from_pdf
)

router = APIRouter()


@router.post("/submit/text")
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
        site_id           = payload["site_id"],
        source            = payload["source"],
        raw_text          = payload["raw_text"],
        submitted_by      = payload.get("submitted_by"),
        processing_status = "pending",
        text_hash         = text_hash,
    )
    db.add(report)
    db.flush()

    # Full pipeline (synchronous for v0)
    result = _full_pipeline(db, report.report_id, payload["raw_text"], payload["site_id"])
    return result


@router.post("/submit/pdf")
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


@router.get("/reports")
def list_reports(
    site_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Report)

    if site_id:
        q = q.filter(Report.site_id.ilike(f"%{site_id}%"))

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


@router.get("/reports/{report_id}")
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

    from backend.api.dependencies import get_standards_references

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