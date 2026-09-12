"""
Component 7: Seed Demo Data Script
Runs the full pipeline synchronously on demo reports, populates DB into target demo state.
Idempotent — running twice produces the same result.

Target state after seeding:
  OIL_SITE_04: 3 × CE.01 reports, Pattern Score ~0.65, State: ELEVATED
  OIL_SITE_07: 1 × CE.01 report (FFH.01 actually), Pattern Score ~0.22, State: WATCH
  OIL_SITE_02: 1 × EF.04 report, Pattern Score ~0.12, State: NOMINAL

Usage:
  cd sih26165
  python scripts/seed_demo_data.py
"""

import sys
import os
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.models.db import (
    init_db, get_session, Report, OntologyMapping, Classification,
    Cluster, SiteRiskState, ValidationFailure
)
from backend.pipeline.validator import gate_2_validate, validate_mapping, get_standards_references
from backend.pipeline.llm_extraction import run_extraction_with_fallback
from backend.pipeline.classifier import classify_mapping
from backend.graph.pattern_score import (
    compute_site_cluster_score, determine_risk_state, T_WATCH, T_ELEVATED
)

DEMO_DIR = Path(__file__).parent.parent / "demo_data" / "reports"

# Demo assignments: (filename, site_id, days_ago)
# days_ago simulates historical submissions for a realistic cluster
DEMO_ASSIGNMENTS = [
    # Site 4 — CE.01 cluster (3 pre-seeded reports)
    ("report_CE01_a.txt",   "OIL_SITE_04", 28),   # oldest
    ("report_CE02_a.txt",   "OIL_SITE_04", 15),   # CE.02 at same site
    ("report_CE01_b.txt",   "OIL_SITE_04", 5),    # most recent CE.01 at Site 4

    # Site 7 — 1 report (FFH.01)
    ("report_FFH01_a.txt",  "OIL_SITE_07", 10),

    # Site 2 — EF cluster (2 reports)
    ("report_EF01_a.txt",   "OIL_SITE_02", 20),
    ("report_EF04_a.txt",   "OIL_SITE_02", 14),

    # Other sites — spread remaining reports
    ("report_FFH02_a.txt",  "OIL_SITE_11", 7),
    ("report_CISB01_a.txt", "OIL_SITE_15", 12),
    ("report_ELEC01_a.txt", "OIL_SITE_11", 3),
    ("report_VT01_a.txt",   "OIL_SITE_07", 18),
]

CATEGORY_WINDOWS = {
    "EXPLOSION_FIRE":      7,
    "CHEMICAL_EXPOSURE":   14,
    "ELECTRICAL":          14,
    "FALL_FROM_HEIGHT":    30,
    "CAUGHT_IN_STRUCK_BY": 30,
    "VEHICLE_TRANSPORT":   30,
}


def load_report(filename: str) -> tuple[str, str, str]:
    """Load report text, strip metadata header, return (text, osha_id, ground_truth)."""
    filepath = DEMO_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Demo report not found: {filepath}")

    raw = filepath.read_text()
    lines = raw.split("\n")

    osha_id = ""
    ground_truth = ""
    content_lines = []

    for line in lines:
        if line.startswith("# OSHA_REPORT_ID:"):
            osha_id = line.split(":", 1)[1].strip()
        elif line.startswith("# GROUND_TRUTH:"):
            ground_truth = line.split(":", 1)[1].strip()
        elif line.startswith("# SITE_ID:"):
            pass  # ignore — we use the assignment table
        else:
            content_lines.append(line)

    return "\n".join(content_lines).strip(), osha_id, ground_truth


def clear_demo_data(session):
    """Remove all existing demo data before reinserting (idempotency)."""
    print("  Clearing existing demo data...")

    # Delete in FK-safe order
    try:
        # Get all report IDs from demo sites
        demo_sites = {"OIL_SITE_04", "OIL_SITE_07", "OIL_SITE_02", "OIL_SITE_11", "OIL_SITE_15"}
        reports = session.query(Report).filter(Report.site_id.in_(demo_sites)).all()
        report_ids = [r.report_id for r in reports]

        if report_ids:
            session.query(OntologyMapping).filter(
                OntologyMapping.report_id.in_(report_ids)
            ).delete(synchronize_session=False)
            session.query(Classification).filter(
                Classification.report_id.in_(report_ids)
            ).delete(synchronize_session=False)
            session.query(ValidationFailure).filter(
                ValidationFailure.report_id.in_(report_ids)
            ).delete(synchronize_session=False)
            session.query(Report).filter(
                Report.report_id.in_(report_ids)
            ).delete(synchronize_session=False)

        # Clear clusters for demo sites
        session.query(Cluster).filter(
            Cluster.site_id.in_(demo_sites)
        ).delete(synchronize_session=False)

        session.commit()
        print(f"  Cleared {len(report_ids)} existing reports")
    except Exception as e:
        session.rollback()
        print(f"  Warning: Clear failed ({e}), continuing...")


def process_report(session, filename: str, site_id: str, days_ago: int) -> dict | None:
    """Run full pipeline on one report and save to DB."""
    print(f"\n  Processing: {filename} → {site_id} ({days_ago}d ago)")

    text, osha_id, ground_truth = load_report(filename)
    submitted_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    text_hash = hashlib.sha256((text.strip() + site_id).encode()).hexdigest()

    # Gate 2 check
    ok, reason = gate_2_validate(text)
    if not ok:
        print(f"    GATE_2 FAIL: {reason[:60]}")
        return None

    # Save report to DB
    report = Report(
        site_id=site_id,
        source="manual_text",
        raw_text=text,
        submitted_at=submitted_at,
        submitted_by="seed_script",
        processing_status="pending",
        osha_report_id=osha_id,
        text_hash=text_hash,
    )
    session.add(report)
    session.flush()

    # LLM extraction
    print(f"    Running LLM extraction...")
    try:
        llm_output = run_extraction_with_fallback(text)
    except Exception as e:
        print(f"    LLM ERROR: {e}")
        report.processing_status = "failed"
        report.failure_reason = str(e)
        session.commit()
        return None

    # Gate 3: abstain?
    if llm_output.get("abstain"):
        reason = llm_output.get("abstain_reason", "LLM abstained")
        print(f"    GATE_3 ABSTAIN: {reason[:60]}")
        report.processing_status = "abstained"
        vf = ValidationFailure(
            report_id=report.report_id,
            gate="GATE_3",
            failure_reason=reason,
            site_id=site_id,
        )
        session.add(vf)
        session.commit()
        return None

    # Validate + save mappings
    valid_mappings = []
    for m in llm_output.get("mappings", []):
        ok_m, errors = validate_mapping(m)
        if not ok_m:
            print(f"    VOCAB INVALID: {errors}")
            continue
        
        mapping = OntologyMapping(
            report_id=report.report_id,
            subtype_id=m["subtype_id"],
            sif_category=m["sif_category"],
            contributing_factors=m.get("contributing_factors", []),
            equipment_classes=m.get("equipment_classes", []),
            activity_contexts=m.get("activity_contexts", []),
            mapping_confidence=m.get("mapping_confidence", 0.75),
            evidence_span=m.get("evidence_span", ""),
            severity_justification=m.get("severity_justification", ""),
        )
        session.add(mapping)
        valid_mappings.append((mapping, m))

    if not valid_mappings:
        print(f"    No valid mappings — skipping")
        report.processing_status = "failed"
        session.commit()
        return None

    report.processing_status = "mapped"
    session.flush()

    # Classify first mapping
    first_mapping_obj, first_mapping_dict = valid_mappings[0]
    clf_result = classify_mapping(first_mapping_dict)
    classification = Classification(
        report_id=report.report_id,
        sif_category=clf_result["sif_category"],
        subtype_id=clf_result["subtype_id"],
        severity=clf_result["severity"],
        classifier_score=clf_result["classifier_score"],
        model_version=clf_result["model_version"],
    )
    session.add(classification)
    report.processing_status = "classified"
    session.commit()

    gt_match = "✓" if clf_result["sif_category"].startswith(ground_truth.split(".")[0][:2]) else "✗"
    print(f"    → {clf_result['sif_category']} / {clf_result['subtype_id']} / {clf_result['severity']} "
          f"[score={clf_result['classifier_score']:.2f}] GT:{ground_truth} {gt_match}")

    return {
        "report_id": str(report.report_id),
        "site_id": site_id,
        "subtype_id": first_mapping_dict["subtype_id"],
        "sif_category": clf_result["sif_category"],
        "severity": clf_result["severity"],
        "submitted_at": submitted_at,
    }


def compute_and_save_cluster(session, site_id: str, subtype_id: str, sif_category: str,
                              window_days: int) -> dict:
    """Compute Pattern Score for a site+subtype cluster and save to DB."""
    result = compute_site_cluster_score(session, site_id, subtype_id, window_days)
    
    reports = result["cluster_reports"]
    if not reports:
        return {"pattern_score": 0.0, "risk_state": "NOMINAL", "cluster_size": 0}

    score = result["pattern_score"]
    has_critical = any(r["severity"] == "CRITICAL" for r in reports)

    # Determine state
    cluster_size = len(reports)
    risk_state = "NOMINAL"
    if score >= T_WATCH and cluster_size >= 3:
        risk_state = "WATCH"
    if score >= T_ELEVATED or (has_critical and risk_state == "WATCH"):
        risk_state = "ELEVATED"
    if cluster_size < 3 and score < T_WATCH:
        risk_state = "NOMINAL" if cluster_size < 2 else "WATCH"

    # Save/update cluster record
    existing = session.query(Cluster).filter(
        Cluster.site_id == site_id,
        Cluster.subtype_id == subtype_id,
        Cluster.active == True,
    ).first()

    report_ids = [r["report_id"] for r in reports]

    if existing:
        existing.report_ids = report_ids
        existing.pattern_score = score
        existing.risk_state = risk_state
        existing.last_updated = datetime.now(timezone.utc)
        cluster = existing
    else:
        cluster = Cluster(
            site_id=site_id,
            sif_category=sif_category,
            subtype_id=subtype_id,
            report_ids=report_ids,
            pattern_score=score,
            risk_state=risk_state,
            first_seen=datetime.now(timezone.utc) - timedelta(days=30),
            active=True,
        )
        session.add(cluster)
        session.flush()

    # Update site risk state
    site_state = session.query(SiteRiskState).filter(
        SiteRiskState.site_id == site_id
    ).first()
    if not site_state:
        site_state = SiteRiskState(site_id=site_id)
        session.add(site_state)
        session.flush()

    # Only upgrade site state, never downgrade here
    state_order = ["NOMINAL", "WATCH", "ELEVATED", "CRITICAL"]
    current_idx = state_order.index(site_state.current_state)
    new_idx = state_order.index(risk_state)
    if new_idx > current_idx:
        site_state.current_state = risk_state
        site_state.dominant_category = sif_category
        site_state.dominant_cluster = cluster.cluster_id
        site_state.last_evaluated_at = datetime.now(timezone.utc)

    session.commit()

    return {
        "pattern_score": score,
        "score_components": result["score_components"],
        "risk_state": risk_state,
        "cluster_size": cluster_size,
    }


def main():
    print("=" * 60)
    print("SIH26165 — Demo Data Seed Script")
    print("=" * 60)

    # Init DB
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:oilsif357@localhost:5432/sif_db")

    try:
        engine = init_db(db_url)
        session = get_session()
        session.execute(__import__('sqlalchemy').text("SELECT 1"))
        print("DB connection: OK")
    except Exception as e:
        print(f"\nDB connection FAILED: {e}")
        print("Ensure PostgreSQL is running and schema has been applied:")
        print("  psql -U postgres -d sif_db -f scripts/schema.sql")
        sys.exit(1)

    # Clear existing demo data
    clear_demo_data(session)

    # Reset site states
    for site_id in ["OIL_SITE_04", "OIL_SITE_07", "OIL_SITE_02", "OIL_SITE_11", "OIL_SITE_15"]:
        state = session.query(SiteRiskState).filter(
            SiteRiskState.site_id == site_id
        ).first()
        if state:
            state.current_state = "NOMINAL"
            state.dominant_category = None
            state.last_evaluated_at = datetime.now(timezone.utc)
        else:
            session.add(SiteRiskState(site_id=site_id, current_state="NOMINAL"))
    session.commit()

    # Process all demo reports
    print("\n--- Processing Demo Reports ---")
    processed = []
    for filename, site_id, days_ago in DEMO_ASSIGNMENTS:
        result = process_report(session, filename, site_id, days_ago)
        if result:
            processed.append(result)

    print(f"\nProcessed: {len(processed)}/{len(DEMO_ASSIGNMENTS)} reports")

    # Compute Pattern Scores for key clusters
    print("\n--- Computing Pattern Scores ---")

    # Site 4: CE.01 cluster
    site4_ce01 = compute_and_save_cluster(
        session, "OIL_SITE_04", "CE.01", "CHEMICAL_EXPOSURE",
        CATEGORY_WINDOWS["CHEMICAL_EXPOSURE"]
    )
    print(f"  Site 4 CE.01: score={site4_ce01['pattern_score']:.3f}, "
          f"state={site4_ce01['risk_state']}, n={site4_ce01['cluster_size']}")

    # Site 4: CE.02 (separate subtype, should be smaller cluster)
    site4_ce02 = compute_and_save_cluster(
        session, "OIL_SITE_04", "CE.02", "CHEMICAL_EXPOSURE",
        CATEGORY_WINDOWS["CHEMICAL_EXPOSURE"]
    )
    print(f"  Site 4 CE.02: score={site4_ce02['pattern_score']:.3f}, "
          f"state={site4_ce02['risk_state']}, n={site4_ce02['cluster_size']}")

    # Site 7: FFH.01
    site7_ffh = compute_and_save_cluster(
        session, "OIL_SITE_07", "FFH.01", "FALL_FROM_HEIGHT",
        CATEGORY_WINDOWS["FALL_FROM_HEIGHT"]
    )
    print(f"  Site 7 FFH.01: score={site7_ffh['pattern_score']:.3f}, "
          f"state={site7_ffh['risk_state']}, n={site7_ffh['cluster_size']}")

    # Site 2: EF clusters
    site2_ef01 = compute_and_save_cluster(
        session, "OIL_SITE_02", "EF.01", "EXPLOSION_FIRE",
        CATEGORY_WINDOWS["EXPLOSION_FIRE"]
    )
    site2_ef04 = compute_and_save_cluster(
        session, "OIL_SITE_02", "EF.04", "EXPLOSION_FIRE",
        CATEGORY_WINDOWS["EXPLOSION_FIRE"]
    )
    best_ef_score = max(site2_ef01["pattern_score"], site2_ef04["pattern_score"])
    best_ef_state = site2_ef01["risk_state"] if site2_ef01["pattern_score"] >= site2_ef04["pattern_score"] else site2_ef04["risk_state"]
    print(f"  Site 2 EF:    score={best_ef_score:.3f}, state={best_ef_state}")

    session.commit()

    # Verification table
    print("\n" + "=" * 50)
    print("SEED VERIFICATION")
    print("=" * 50)

    def get_site_state(sid):
        s = session.query(SiteRiskState).filter(SiteRiskState.site_id == sid).first()
        return s.current_state if s else "UNKNOWN"

    s4_state = get_site_state("OIL_SITE_04")
    s7_state = get_site_state("OIL_SITE_07")
    s2_state = get_site_state("OIL_SITE_02")

    print(f"Site 4:  {site4_ce01['cluster_size']} CE.01 reports | "
          f"Pattern Score: {site4_ce01['pattern_score']:.2f} | State: {s4_state}")
    print(f"Site 7:  {site7_ffh['cluster_size']} FFH.01 report(s) | "
          f"Pattern Score: {site7_ffh['pattern_score']:.2f} | State: {s7_state}")
    print(f"Site 2:  EF cluster | "
          f"Pattern Score: {best_ef_score:.2f} | State: {s2_state}")
    print("=" * 50)

    # Assertion: Site 4 must have ELEVATED or at least WATCH state
    if s4_state not in ("ELEVATED", "WATCH"):
        print(f"\n⚠  WARNING: Site 4 state is {s4_state} — expected ELEVATED or WATCH")
        print("   Demo state not fully achieved. Check LLM output quality.")
        print("   The live demo submission (report_CE01_b.txt to Site 4) should push it to ELEVATED.")
    else:
        print(f"\n✓ Demo state ready. Site 4 at {s4_state}.")
        print("  Submit report_CE01_b.txt to OIL_SITE_04 via UI to demonstrate cluster join.")

    print("\nSeed complete.")
    session.close()


if __name__ == "__main__":
    main()
