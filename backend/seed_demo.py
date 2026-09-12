"""
SIH26165 — Demo Data Seed Script (v0_2)
Replaces the old seed script with deterministic, idempotent seeding for the demo.

Run: python backend/seed_demo.py

Requires DATABASE_URL environment variable (or uses default).
"""

import os
import sys
import uuid
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

from backend.models.db import (
    init_db, get_session, Report, OntologyMapping, Classification,
    Cluster, SiteRiskState, Alert, GraphNode, GraphEdge, ValidationFailure
)

# ============================================================================
# FIXED UUIDs — deterministic for idempotent seeding
# ============================================================================

# Report UUIDs (15 total)
REPORT_UUIDS = {
    "CE-1": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "CE-2": uuid.UUID("11111111-1111-1111-1111-111111111112"),
    "CE-3": uuid.UUID("11111111-1111-1111-1111-111111111113"),
    "CE-4": uuid.UUID("11111111-1111-1111-1111-111111111114"),
    "EF-1": uuid.UUID("22222222-2222-2222-2222-222222222221"),
    "EF-2": uuid.UUID("22222222-2222-2222-2222-222222222222"),
    "EF-3": uuid.UUID("22222222-2222-2222-2222-222222222223"),
    "FFH-1": uuid.UUID("33333333-3333-3333-3333-333333333331"),
    "FFH-2": uuid.UUID("33333333-3333-3333-3333-333333333332"),
    "FFH-3": uuid.UUID("33333333-3333-3333-3333-333333333333"),
    "FFH-4": uuid.UUID("33333333-3333-3333-3333-333333333334"),
    "VT-1":  uuid.UUID("44444444-4444-4444-4444-444444444441"),
    "CISB-1": uuid.UUID("55555555-5555-5555-5555-555555555551"),
    "ELEC-1": uuid.UUID("66666666-6666-6666-6666-666666666661"),
    "CE-5":  uuid.UUID("11111111-1111-1111-1111-111111111115"),  # Additional HIGH severity
}

# Cluster UUIDs (3 total)
CLUSTER_UUIDS = {
    "CE04_SITE04": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),  # ELEVATED
    "EF04_SITE02": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),  # WATCH
    "FFH02_CROSS": uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),  # WATCH (cross-site)
}

# Alert UUIDs (3 total)
ALERT_UUIDS = {
    "ALERT_1": uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),  # NOMINAL -> WATCH (CE.04)
    "ALERT_2": uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),  # WATCH -> ELEVATED (CRITICAL_JOIN)
    "ALERT_3": uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),  # NOMINAL -> WATCH (EF.04)
}

# Mapping UUIDs (one per report for primary mapping)
MAPPING_UUIDS = {
    "CE-1": uuid.UUID("77777777-7777-7777-7777-777777777771"),
    "CE-2": uuid.UUID("77777777-7777-7777-7777-777777777772"),
    "CE-3": uuid.UUID("77777777-7777-7777-7777-777777777773"),
    "CE-4": uuid.UUID("77777777-7777-7777-7777-777777777774"),
    "EF-1": uuid.UUID("88888888-8888-8888-8888-888888888881"),
    "EF-2": uuid.UUID("88888888-8888-8888-8888-888888888882"),
    "EF-3": uuid.UUID("88888888-8888-8888-8888-888888888883"),
    "FFH-1": uuid.UUID("99999999-9999-9999-9999-999999999991"),
    "FFH-2": uuid.UUID("99999999-9999-9999-9999-999999999992"),
    "FFH-3": uuid.UUID("99999999-9999-9999-9999-999999999993"),
    "FFH-4": uuid.UUID("99999999-9999-9999-9999-999999999994"),
    "VT-1":  uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1"),
    "CISB-1": uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2"),
    "ELEC-1": uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee3"),
    "CE-5":  uuid.UUID("77777777-7777-7777-7777-777777777775"),
}

# Classification UUIDs (one per report)
CLASSIFICATION_UUIDS = {
    "CE-1": uuid.UUID("bbbbbbbb-cccc-dddd-eeee-fffffffffff1"),
    "CE-2": uuid.UUID("bbbbbbbb-cccc-dddd-eeee-fffffffffff2"),
    "CE-3": uuid.UUID("bbbbbbbb-cccc-dddd-eeee-fffffffffff3"),
    "CE-4": uuid.UUID("bbbbbbbb-cccc-dddd-eeee-fffffffffff4"),
    "EF-1": uuid.UUID("cccccccc-dddd-eeee-ffff-111111111111"),
    "EF-2": uuid.UUID("cccccccc-dddd-eeee-ffff-111111111112"),
    "EF-3": uuid.UUID("cccccccc-dddd-eeee-ffff-111111111113"),
    "FFH-1": uuid.UUID("dddddddd-eeee-ffff-1111-222222222221"),
    "FFH-2": uuid.UUID("dddddddd-eeee-ffff-1111-222222222222"),
    "FFH-3": uuid.UUID("dddddddd-eeee-ffff-1111-222222222223"),
    "FFH-4": uuid.UUID("dddddddd-eeee-ffff-1111-222222222224"),
    "VT-1":  uuid.UUID("eeeeeeee-ffff-1111-2222-333333333331"),
    "CISB-1": uuid.UUID("eeeeeeee-ffff-1111-2222-333333333332"),
    "ELEC-1": uuid.UUID("eeeeeeee-ffff-1111-2222-333333333333"),
    "CE-5":  uuid.UUID("bbbbbbbb-cccc-dddd-eeee-fffffffffff5"),
}

# Graph edge UUIDs (for CE.04: 6 edges, EF.04: 3 edges)
EDGE_UUIDS = [
    uuid.UUID("ff000000-0000-0000-0000-000000000001"),
    uuid.UUID("ff000000-0000-0000-0000-000000000002"),
    uuid.UUID("ff000000-0000-0000-0000-000000000003"),
    uuid.UUID("ff000000-0000-0000-0000-000000000004"),
    uuid.UUID("ff000000-0000-0000-0000-000000000005"),
    uuid.UUID("ff000000-0000-0000-0000-000000000006"),
    uuid.UUID("ff000000-0000-0000-0000-000000000007"),
    uuid.UUID("ff000000-0000-0000-0000-000000000008"),
    uuid.UUID("ff000000-0000-0000-0000-000000000009"),
]

# ============================================================================
# REPORT DATA SPECIFICATION
# ============================================================================

REPORTS_DATA = [
    # Chemical Exposure cluster at OIL_SITE_04 (4 reports, subtype CE.04)
    {
        "key": "CE-1",
        "site_id": "OIL_SITE_04",
        "osha_id": "202-0456-32",
        "submitted_at": datetime(2026, 8, 15, 8, 20, tzinfo=timezone(timedelta(hours=5, minutes=30))),  # IST
        "submitted_by": "HSE_OFFICER_04",
        "sif_category": "CHEMICAL_EXPOSURE",
        "subtype_id": "CE.04",
        "severity": "HIGH",
        "classifier_score": 0.94,
        "mapping_confidence": 0.91,
        "evidence_span": "During routine valve maintenance, operator contacted sodium hydroxide solution when relief valve discharged unexpectedly without PPE change-out between tasks.",
        "contributing_factors": ["PPE_FAILURE", "PROCEDURE_VIOLATION"],
        "equipment_classes": ["RELIEF_VALVE", "CHEMICAL_DRUM"],
        "activity_contexts": ["VALVE_MAINTENANCE", "CHEMICAL_HANDLING"],
    },
    {
        "key": "CE-2",
        "site_id": "OIL_SITE_04",
        "osha_id": "202-0441-09",
        "submitted_at": datetime(2026, 8, 28, 10, 15, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "FIELD_TECH_07",
        "sif_category": "CHEMICAL_EXPOSURE",
        "subtype_id": "CE.04",
        "severity": "HIGH",
        "classifier_score": 0.91,
        "mapping_confidence": 0.88,
        "evidence_span": "During sampling activities at the chemical storage area, a laboratory technician collected a sample from a reagent tank containing sodium hydroxide caustic soda 30 percent solution without wearing the required chemical resistant gloves.",
        "contributing_factors": ["PPE_FAILURE"],
        "equipment_classes": ["REAGENT_TANK"],
        "activity_contexts": ["CHEMICAL_HANDLING"],
    },
    {
        "key": "CE-3",
        "site_id": "OIL_SITE_04",
        "osha_id": "202-0471-18",
        "submitted_at": datetime(2026, 9, 7, 6, 21, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "HSE_OFFICER_04",
        "sif_category": "CHEMICAL_EXPOSURE",
        "subtype_id": "CE.04",
        "severity": "CRITICAL",
        "classifier_score": 0.97,
        "mapping_confidence": 0.95,
        "evidence_span": "Maintenance technician sustained chemical burns to both forearms when a flanged connection on a caustic transfer line failed during tightening. Technician was not wearing chemical-resistant sleeves as required by site LOTO procedure SOP-CH-04.",
        "contributing_factors": ["PPE_FAILURE", "PROCEDURE_VIOLATION", "EQUIPMENT_FAULT"],
        "equipment_classes": ["PIPELINE", "CHEMICAL_DRUM"],
        "activity_contexts": ["CHEMICAL_HANDLING", "MAINTENANCE"],
    },
    {
        "key": "CE-4",
        "site_id": "OIL_SITE_04",
        "osha_id": "202-0488-51",
        "submitted_at": datetime(2026, 9, 11, 9, 45, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "SHIFT_SUP_02",
        "sif_category": "CHEMICAL_EXPOSURE",
        "subtype_id": "CE.04",
        "severity": "HIGH",
        "classifier_score": 0.89,
        "mapping_confidence": 0.86,
        "evidence_span": "Worker reported eye irritation after chemical splash during tank drain operation. Face shield was available at the workstation but not donned prior to task commencement.",
        "contributing_factors": ["PPE_FAILURE", "PROCEDURE_VIOLATION"],
        "equipment_classes": ["STORAGE_TANK", "CHEMICAL_DRUM"],
        "activity_contexts": ["CHEMICAL_HANDLING"],
    },

    # Explosion/Fire cluster at OIL_SITE_02 (3 reports, subtype EF.04)
    {
        "key": "EF-1",
        "site_id": "OIL_SITE_02",
        "osha_id": "202-0388-44",
        "submitted_at": datetime(2026, 8, 23, 14, 5, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "HSE_OFFICER_01",
        "sif_category": "EXPLOSION_FIRE",
        "subtype_id": "EF.04",
        "severity": "HIGH",
        "classifier_score": 0.88,
        "mapping_confidence": 0.84,
        "evidence_span": "Hot work permit issued 2 hours prior had expired before job restart after lunch break. Gas test was not repeated before welding resumed on the crude transfer line.",
        "contributing_factors": ["PROCEDURE_VIOLATION"],
        "equipment_classes": ["PIPELINE", "PRESSURE_VESSEL"],
        "activity_contexts": ["WELDING", "HOT_WORK"],
    },
    {
        "key": "EF-2",
        "site_id": "OIL_SITE_02",
        "osha_id": "202-0399-17",
        "submitted_at": datetime(2026, 8, 29, 11, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "FIELD_TECH_07",
        "sif_category": "EXPLOSION_FIRE",
        "subtype_id": "EF.04",
        "severity": "HIGH",
        "classifier_score": 0.86,
        "mapping_confidence": 0.82,
        "evidence_span": "Sparks from angle grinder fell into drain channel containing residual hydrocarbon liquid not cleaned prior to work commencement as required by the hot work permit pre-conditions.",
        "contributing_factors": ["PROCEDURE_VIOLATION", "EQUIPMENT_FAULT"],
        "equipment_classes": ["PIPELINE", "PRESSURE_VESSEL"],
        "activity_contexts": ["WELDING", "HOT_WORK"],
    },
    {
        "key": "EF-3",
        "site_id": "OIL_SITE_02",
        "osha_id": "202-0415-63",
        "submitted_at": datetime(2026, 9, 5, 15, 40, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "SAFETY_INSP_11",
        "sif_category": "EXPLOSION_FIRE",
        "subtype_id": "EF.04",
        "severity": "MEDIUM",
        "classifier_score": 0.78,
        "mapping_confidence": 0.76,
        "evidence_span": "Isolation of adjacent crude line was not verified before hot work commenced in the vicinity. Contractor team assumed isolation was complete based on verbal confirmation rather than physical lock verification.",
        "contributing_factors": ["PROCEDURE_VIOLATION"],
        "equipment_classes": ["PIPELINE"],
        "activity_contexts": ["HOT_WORK", "MAINTENANCE"],
    },

    # Fall From Height at OIL_SITE_07 and OIL_SITE_11 (4 reports, subtype FFH.02)
    {
        "key": "FFH-1",
        "site_id": "OIL_SITE_07",
        "osha_id": "202-0412-55",
        "submitted_at": datetime(2026, 9, 2, 7, 15, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "FIELD_TECH_07",
        "sif_category": "FALL_FROM_HEIGHT",
        "subtype_id": "FFH.02",
        "severity": "HIGH",
        "classifier_score": 0.87,
        "mapping_confidence": 0.83,
        "evidence_span": "Worker ascended scaffold without attaching lanyard to the horizontal lifeline. Scaffold was at 4.2 meters elevation during tank inspection. No observer was stationed at ground level.",
        "contributing_factors": ["PPE_FAILURE", "PROCEDURE_VIOLATION"],
        "equipment_classes": ["SCAFFOLD", "TANK_TOP"],
        "activity_contexts": ["INSPECTION", "MAINTENANCE"],
    },
    {
        "key": "FFH-2",
        "site_id": "OIL_SITE_11",
        "osha_id": "202-0427-33",
        "submitted_at": datetime(2026, 9, 5, 8, 50, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "HSE_OFFICER_04",
        "sif_category": "FALL_FROM_HEIGHT",
        "subtype_id": "FFH.02",
        "severity": "HIGH",
        "classifier_score": 0.85,
        "mapping_confidence": 0.81,
        "evidence_span": "Maintenance technician working at 3.8 meters on scaffold platform was observed without fall arrest harness during pump inspection. Harness was signed out but left at ground level.",
        "contributing_factors": ["PPE_FAILURE"],
        "equipment_classes": ["SCAFFOLD", "ELEVATED_PLATFORM"],
        "activity_contexts": ["MAINTENANCE", "INSPECTION"],
    },
    {
        "key": "FFH-3",
        "site_id": "OIL_SITE_07",
        "osha_id": "202-0433-19",
        "submitted_at": datetime(2026, 9, 8, 9, 10, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "SHIFT_SUP_02",
        "sif_category": "FALL_FROM_HEIGHT",
        "subtype_id": "FFH.02",
        "severity": "MEDIUM",
        "classifier_score": 0.76,
        "mapping_confidence": 0.74,
        "evidence_span": "Portable ladder used to access valve manifold at 2.5m was not footed or tied off. A second worker attempted to stabilize the base manually during the task.",
        "contributing_factors": ["EQUIPMENT_FAULT", "PROCEDURE_VIOLATION"],
        "equipment_classes": ["LADDER"],
        "activity_contexts": ["MAINTENANCE"],
    },
    {
        "key": "FFH-4",
        "site_id": "OIL_SITE_11",
        "osha_id": "202-0362-91",
        "submitted_at": datetime(2026, 9, 9, 6, 23, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "SAFETY_INSP_11",
        "sif_category": "FALL_FROM_HEIGHT",
        "subtype_id": "FFH.02",
        "severity": "HIGH",
        "classifier_score": 0.92,
        "mapping_confidence": 0.89,
        "evidence_span": "Worker slipped on wet scaffold plank during morning shift. No non-slip surface treatment had been applied and no weather-related work suspension had been called despite overnight rainfall.",
        "contributing_factors": ["ENVIRONMENTAL", "PROCEDURE_VIOLATION"],
        "equipment_classes": ["SCAFFOLD"],
        "activity_contexts": ["INSPECTION"],
    },

    # Remaining single-incident reports
    {
        "key": "VT-1",
        "site_id": "OIL_SITE_07",
        "osha_id": "202-0375-28",
        "submitted_at": datetime(2026, 8, 25, 13, 20, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "WORKER_15",
        "sif_category": "VEHICLE_TRANSPORT",
        "subtype_id": "VT.02",
        "severity": "MEDIUM",
        "classifier_score": 0.81,
        "mapping_confidence": 0.79,
        "evidence_span": "Tanker reversing into loading bay did not have a banksman assigned. Site CCTV confirmed the vehicle reversed without ground observation for 15 meters.",
        "contributing_factors": ["PROCEDURE_VIOLATION"],
        "equipment_classes": ["TANKER", "VEHICLE"],
        "activity_contexts": ["TRANSPORT"],
    },
    {
        "key": "CISB-1",
        "site_id": "OIL_SITE_15",
        "osha_id": "202-0348-77",
        "submitted_at": datetime(2026, 8, 31, 11, 10, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "HSE_OFFICER_01",
        "sif_category": "CAUGHT_IN_STRUCK_BY",
        "subtype_id": "CISB.04",
        "severity": "LOW",
        "classifier_score": 0.73,
        "mapping_confidence": 0.71,
        "evidence_span": "Rotating pump coupling guard was found removed during routine inspection. Maintenance work order had been closed without reinstating the guard after bearing replacement.",
        "contributing_factors": ["EQUIPMENT_FAULT", "PROCEDURE_VIOLATION"],
        "equipment_classes": ["PUMP", "COMPRESSOR"],
        "activity_contexts": ["MAINTENANCE", "INSPECTION"],
    },
    {
        "key": "ELEC-1",
        "site_id": "OIL_SITE_11",
        "osha_id": "202-0390-44",
        "submitted_at": datetime(2026, 9, 3, 10, 5, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "FIELD_TECH_07",
        "sif_category": "ELECTRICAL",
        "subtype_id": "ELEC.04",
        "severity": "HIGH",
        "classifier_score": 0.90,
        "mapping_confidence": 0.87,
        "evidence_span": "Electrician received shock from exposed terminal block in MCC panel while tracing a fault. LOTO had been applied to the upstream breaker but the downstream terminal remained energized due to an undocumented backfeed from an adjacent circuit.",
        "contributing_factors": ["EQUIPMENT_FAULT", "PROCEDURE_VIOLATION"],
        "equipment_classes": ["ELECTRICAL_PANEL", "CABLE"],
        "activity_contexts": ["MAINTENANCE", "INSPECTION"],
    },
    {
        "key": "CE-5",
        "site_id": "OIL_SITE_01",
        "osha_id": "202-0499-12",
        "submitted_at": datetime(2026, 9, 10, 14, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "submitted_by": "HSE_OFFICER_01",
        "sif_category": "CHEMICAL_EXPOSURE",
        "subtype_id": "CE.01",
        "severity": "HIGH",
        "classifier_score": 0.88,
        "mapping_confidence": 0.85,
        "evidence_span": "Operator transferring sulfuric acid between totes failed to don chemical-resistant apron as required by SOP-CHEM-012. Minor splash contacted forearm causing first-degree burns. Emergency shower activated within 30 seconds.",
        "contributing_factors": ["PPE_FAILURE", "PROCEDURE_VIOLATION"],
        "equipment_classes": ["CHEMICAL_DRUM", "TOTE"],
        "activity_contexts": ["CHEMICAL_HANDLING", "TRANSFER"],
    },
]

# ============================================================================
# SITE RISK STATES SPECIFICATION
# ============================================================================

SITES_DATA = [
    {"site_id": "OIL_SITE_01", "baseline_velocity": 0.6},
    {"site_id": "OIL_SITE_02", "baseline_velocity": 0.4},
    {"site_id": "OIL_SITE_04", "baseline_velocity": 0.5},
    {"site_id": "OIL_SITE_07", "baseline_velocity": 0.5},
    {"site_id": "OIL_SITE_11", "baseline_velocity": 0.4},
    {"site_id": "OIL_SITE_15", "baseline_velocity": 0.3},
]

# ============================================================================
# CLUSTER SPECIFICATION
# ============================================================================

CLUSTERS_DATA = [
    {
        "key": "CE04_SITE04",
        "cluster_id": CLUSTER_UUIDS["CE04_SITE04"],
        "site_id": "OIL_SITE_04",
        "sif_category": "CHEMICAL_EXPOSURE",
        "subtype_id": "CE.04",
        "report_keys": ["CE-1", "CE-2", "CE-3", "CE-4"],
        "pattern_score": 0.71,
        "risk_state": "ELEVATED",
        "first_seen": datetime(2026, 8, 15, 8, 20, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "score_components": {
            "density": 0.83,
            "edge_strength": 0.79,
            "velocity": 0.62,
            "severity": 0.76,
            "concentration": 0.88,
        },
    },
    {
        "key": "EF04_SITE02",
        "cluster_id": CLUSTER_UUIDS["EF04_SITE02"],
        "site_id": "OIL_SITE_02",
        "sif_category": "EXPLOSION_FIRE",
        "subtype_id": "EF.04",
        "report_keys": ["EF-1", "EF-2", "EF-3"],
        "pattern_score": 0.48,
        "risk_state": "WATCH",
        "first_seen": datetime(2026, 8, 23, 14, 5, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "score_components": {
            "density": 0.67,
            "edge_strength": 0.58,
            "velocity": 0.31,
            "severity": 0.46,
            "concentration": 0.72,
        },
    },
    {
        "key": "FFH02_CROSS",
        "cluster_id": CLUSTER_UUIDS["FFH02_CROSS"],
        "site_id": None,  # cross-site
        "sif_category": "FALL_FROM_HEIGHT",
        "subtype_id": "FFH.02",
        "report_keys": ["FFH-1", "FFH-2", "FFH-3", "FFH-4"],
        "pattern_score": 0.41,
        "risk_state": "WATCH",
        "first_seen": datetime(2026, 9, 2, 7, 15, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        "score_components": {
            "density": 0.50,
            "edge_strength": 0.44,
            "velocity": 0.38,
            "severity": 0.52,
            "concentration": 0.41,
        },
    },
]

# ============================================================================
# ALERTS SPECIFICATION
# ============================================================================

ALERTS_DATA = [
    {
        "alert_id": ALERT_UUIDS["ALERT_1"],
        "cluster_id": CLUSTER_UUIDS["CE04_SITE04"],
        "site_id": "OIL_SITE_04",
        "alert_type": "STATE_TRANSITION",
        "from_state": "NOMINAL",
        "to_state": "WATCH",
        "pattern_score": 0.38,
        "message": "OIL_SITE_04 \u2014 Chemical Exposure (CE.04): 3 HIGH severity precursor reports detected within 30 days. Pattern Score: 0.38. Site elevated to WATCH state. HSE review recommended.",
        "created_at": datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
    },
    {
        "alert_id": ALERT_UUIDS["ALERT_2"],
        "cluster_id": CLUSTER_UUIDS["CE04_SITE04"],
        "site_id": "OIL_SITE_04",
        "alert_type": "CRITICAL_JOIN",
        "from_state": "WATCH",
        "to_state": "ELEVATED",
        "pattern_score": 0.71,
        "message": "OIL_SITE_04 \u2014 Chemical Exposure (CE.04): CRITICAL severity report joined active WATCH cluster. Pattern Score: 0.71. Site elevated to ELEVATED state. Immediate inspection required.",
        "created_at": datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
    },
    {
        "alert_id": ALERT_UUIDS["ALERT_3"],
        "cluster_id": CLUSTER_UUIDS["EF04_SITE02"],
        "site_id": "OIL_SITE_02",
        "alert_type": "STATE_TRANSITION",
        "from_state": "NOMINAL",
        "to_state": "WATCH",
        "pattern_score": 0.48,
        "message": "OIL_SITE_02 \u2014 Explosion/Fire (EF.04): 3 related hot work precursor reports detected within 14 days. Pattern Score: 0.48. Site elevated to WATCH state. Hot work permit audit recommended.",
        "created_at": datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
    },
]

# ============================================================================
# SITE RISK STATE UPDATES (after clusters)
# ============================================================================

SITE_STATE_UPDATES = [
    {
        "site_id": "OIL_SITE_04",
        "current_state": "ELEVATED",
        "dominant_category": "CHEMICAL_EXPOSURE",
        "dominant_cluster": CLUSTER_UUIDS["CE04_SITE04"],
        "state_entered_at": datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
    },
    {
        "site_id": "OIL_SITE_02",
        "current_state": "WATCH",
        "dominant_category": "EXPLOSION_FIRE",
        "dominant_cluster": CLUSTER_UUIDS["EF04_SITE02"],
        "state_entered_at": datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
    },
    {
        "site_id": "OIL_SITE_07",
        "current_state": "WATCH",
        "dominant_category": "FALL_FROM_HEIGHT",
        "dominant_cluster": CLUSTER_UUIDS["FFH02_CROSS"],
        "state_entered_at": datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
    },
    {
        "site_id": "OIL_SITE_11",
        "current_state": "WATCH",
        "dominant_category": "FALL_FROM_HEIGHT",
        "dominant_cluster": CLUSTER_UUIDS["FFH02_CROSS"],
        "state_entered_at": datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
    },
    {
        "site_id": "OIL_SITE_01",
        "current_state": "NOMINAL",
        "dominant_category": None,
        "dominant_cluster": None,
        "state_entered_at": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
    },
    {
        "site_id": "OIL_SITE_15",
        "current_state": "NOMINAL",
        "dominant_category": None,
        "dominant_cluster": None,
        "state_entered_at": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
    },
]

# ============================================================================
# GRAPH EDGES COMPUTATION
# ============================================================================

def compute_graph_edges(report_nodes):
    """
    Compute edges between report nodes following the architecture rules.
    Returns list of (source_key, target_key, edge_types, base_weight, site_modifier, current_weight)
    """
    from backend.graph.pattern_score import compute_edge_weight
    
    # Build node dicts for compute_edge_weight
    nodes_dict = {}
    for r in report_nodes:
        nodes_dict[r["key"]] = {
            "subtype_id": r["subtype_id"],
            "equipment_classes": r["equipment_classes"],
            "activity_contexts": r["activity_contexts"],
            "site_id": r["site_id"],
            "timestamp": r["submitted_at"],
        }
    
    edges = []
    keys = list(nodes_dict.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a_key = keys[i]
            b_key = keys[j]
            a = nodes_dict[a_key]
            b = nodes_dict[b_key]
            
            weight, edge_types = compute_edge_weight(a, b)
            if weight >= 0.7:
                # Compute base_weight and site_modifier separately
                base_weight = 0.0
                if a["subtype_id"] == b["subtype_id"]:
                    base_weight += 1.0
                if set(a["equipment_classes"]) & set(b["equipment_classes"]):
                    base_weight += 0.7
                if set(a["activity_contexts"]) & set(b["activity_contexts"]):
                    base_weight += 0.6
                
                site_modifier = 0.0
                if a["site_id"] == b["site_id"]:
                    delta_days = abs((a["timestamp"] - b["timestamp"]).days)
                    if delta_days <= 7:
                        site_modifier = 0.5
                    elif delta_days <= 30:
                        site_modifier = 0.3
                
                edges.append({
                    "source_key": a_key,
                    "target_key": b_key,
                    "edge_types": edge_types,
                    "base_weight": base_weight,
                    "site_modifier": site_modifier,
                    "current_weight": weight,
                })
    return edges


# ============================================================================
# MAIN SEED FUNCTION
# ============================================================================

def clear_existing_data(session):
    """Clear existing demo data for idempotency."""
    print("  Clearing existing demo data...")
    
    # Delete in FK-safe order
    try:
        demo_sites = {"OIL_SITE_01", "OIL_SITE_02", "OIL_SITE_04", "OIL_SITE_07", "OIL_SITE_11", "OIL_SITE_15"}
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
            
            # Delete graph edges first (FK references graph_nodes)
            session.query(GraphEdge).filter(
                GraphEdge.source_node.in_(report_ids)
            ).delete(synchronize_session=False)
            session.query(GraphEdge).filter(
                GraphEdge.target_node.in_(report_ids)
            ).delete(synchronize_session=False)
            
            # Then delete graph nodes
            session.query(GraphNode).filter(
                GraphNode.node_id.in_(report_ids)
            ).delete(synchronize_session=False)
            
            session.query(Report).filter(
                Report.report_id.in_(report_ids)
            ).delete(synchronize_session=False)
        
        # Clear alerts first (FK references clusters)
        session.query(Alert).filter(
            Alert.site_id.in_(demo_sites)
        ).delete(synchronize_session=False)
        
        # Clear site risk states (FK references clusters)
        session.query(SiteRiskState).filter(
            SiteRiskState.site_id.in_(demo_sites)
        ).delete(synchronize_session=False)
        
        # Clear clusters for demo sites (including cross-site clusters that reference these reports)
        session.query(Cluster).filter(
            (Cluster.site_id.in_(demo_sites)) | (Cluster.site_id.is_(None))
        ).delete(synchronize_session=False)
        
        session.commit()
        print(f"  Cleared {len(report_ids)} existing reports")
    except Exception as e:
        session.rollback()
        print(f"  Warning: Clear failed ({e}), continuing...")


def seed_sites(session):
    """Seed site_risk_states with baseline_velocity."""
    print("  Seeding site_risk_states...")
    for site_data in SITES_DATA:
        existing = session.query(SiteRiskState).filter(
            SiteRiskState.site_id == site_data["site_id"]
        ).first()
        if not existing:
            site_state = SiteRiskState(
                site_id=site_data["site_id"],
                current_state="NOMINAL",
                baseline_velocity=site_data["baseline_velocity"],
            )
            session.add(site_state)
    session.commit()
    print(f"  Seeded {len(SITES_DATA)} sites")


def seed_reports(session):
    """Seed all 15 reports with ontology mappings and classifications."""
    print("  Seeding 15 reports with mappings and classifications...")
    
    for rdata in REPORTS_DATA:
        key = rdata["key"]
        report_id = REPORT_UUIDS[key]
        
        # Check if already exists
        existing = session.query(Report).filter(Report.report_id == report_id).first()
        if existing:
            print(f"    {key} already exists, skipping")
            continue
        
        # Convert IST to UTC for storage
        submitted_at_utc = rdata["submitted_at"].astimezone(timezone.utc)
        
        # Create report
        report = Report(
            report_id=report_id,
            site_id=rdata["site_id"],
            source="manual_text",
            raw_text=rdata["evidence_span"],  # Use evidence_span as raw_text for demo
            submitted_at=submitted_at_utc,
            submitted_by=rdata["submitted_by"],
            processing_status="classified",
            osha_report_id=rdata["osha_id"],
            text_hash=uuid.uuid4().hex,  # dummy hash for demo
        )
        session.add(report)
        
        # Create ontology mapping
        mapping = OntologyMapping(
            mapping_id=MAPPING_UUIDS[key],
            report_id=report_id,
            subtype_id=rdata["subtype_id"],
            sif_category=rdata["sif_category"],
            contributing_factors=rdata["contributing_factors"],
            equipment_classes=rdata["equipment_classes"],
            activity_contexts=rdata["activity_contexts"],
            mapping_confidence=rdata["mapping_confidence"],
            evidence_span=rdata["evidence_span"],
            severity_justification=f"Auto-seeded for demo: {rdata['severity']} severity based on incident description",
        )
        session.add(mapping)
        
        # Create classification
        classification = Classification(
            classification_id=CLASSIFICATION_UUIDS[key],
            report_id=report_id,
            sif_category=rdata["sif_category"],
            subtype_id=rdata["subtype_id"],
            severity=rdata["severity"],
            classifier_score=rdata["classifier_score"],
            model_version="demo-v0.2",
        )
        session.add(classification)
    
    session.commit()
    print(f"  Seeded {len(REPORTS_DATA)} reports")


def seed_graph_nodes_and_edges(session):
    """Seed graph_nodes and graph_edges for CE.04 and EF.04 clusters."""
    print("  Seeding graph_nodes and graph_edges...")
    
    # Collect nodes for CE.04 (OIL_SITE_04) and EF.04 (OIL_SITE_02)
    ce04_nodes = [r for r in REPORTS_DATA if r["subtype_id"] == "CE.04"]
    ef04_nodes = [r for r in REPORTS_DATA if r["subtype_id"] == "EF.04"]
    
    all_cluster_nodes = ce04_nodes + ef04_nodes
    
    # Seed graph nodes
    for rdata in all_cluster_nodes:
        key = rdata["key"]
        report_id = REPORT_UUIDS[key]
        
        existing = session.query(GraphNode).filter(GraphNode.node_id == report_id).first()
        if not existing:
            node = GraphNode(
                node_id=report_id,
                site_id=rdata["site_id"],
                subtype_id=rdata["subtype_id"],
                severity=rdata["severity"],
                timestamp=rdata["submitted_at"].astimezone(timezone.utc),
                active=True,
            )
            session.add(node)
    
    session.flush()
    
    # Compute and seed edges for CE.04
    ce04_edges = compute_graph_edges(ce04_nodes)
    print(f"    CE.04 edges: {len(ce04_edges)}")
    
    # Compute and seed edges for EF.04
    ef04_edges = compute_graph_edges(ef04_nodes)
    print(f"    EF.04 edges: {len(ef04_edges)}")
    
    all_edges = ce04_edges + ef04_edges
    
    for idx, edge_data in enumerate(all_edges):
        edge_id = EDGE_UUIDS[idx]
        source_id = REPORT_UUIDS[edge_data["source_key"]]
        target_id = REPORT_UUIDS[edge_data["target_key"]]
        
        existing = session.query(GraphEdge).filter(GraphEdge.edge_id == edge_id).first()
        if not existing:
            edge = GraphEdge(
                edge_id=edge_id,
                source_node=source_id,
                target_node=target_id,
                edge_types=edge_data["edge_types"],
                base_weight=edge_data["base_weight"],
                site_modifier=edge_data["site_modifier"],
                current_weight=edge_data["current_weight"],
            )
            session.add(edge)
    
    session.commit()
    print(f"  Seeded {len(all_cluster_nodes)} graph nodes and {len(all_edges)} graph edges")


def seed_clusters(session):
    """Seed the 3 clusters with fixed UUIDs and score_components."""
    print("  Seeding clusters...")
    
    for cdata in CLUSTERS_DATA:
        existing = session.query(Cluster).filter(Cluster.cluster_id == cdata["cluster_id"]).first()
        if existing:
            print(f"    Cluster {cdata['key']} already exists, skipping")
            continue
        
        report_ids = [REPORT_UUIDS[key] for key in cdata["report_keys"]]
        
        cluster = Cluster(
            cluster_id=cdata["cluster_id"],
            site_id=cdata["site_id"],
            sif_category=cdata["sif_category"],
            subtype_id=cdata["subtype_id"],
            report_ids=report_ids,
            pattern_score=cdata["pattern_score"],
            risk_state=cdata["risk_state"],
            first_seen=cdata["first_seen"].astimezone(timezone.utc),
            active=True,
            score_components=cdata.get("score_components"),
        )
        session.add(cluster)
    
    session.commit()
    print(f"  Seeded {len(CLUSTERS_DATA)} clusters")


def seed_alerts(session):
    """Seed alerts table with state transition history."""
    print("  Seeding alerts...")
    
    for adata in ALERTS_DATA:
        existing = session.query(Alert).filter(Alert.alert_id == adata["alert_id"]).first()
        if existing:
            print(f"    Alert {adata['alert_id']} already exists, skipping")
            continue
        
        alert = Alert(
            alert_id=adata["alert_id"],
            cluster_id=adata["cluster_id"],
            site_id=adata["site_id"],
            alert_type=adata["alert_type"],
            from_state=adata["from_state"],
            to_state=adata["to_state"],
            pattern_score=adata["pattern_score"],
            message=adata["message"],
            delivered=False,
            created_at=adata["created_at"],
        )
        session.add(alert)
    
    session.commit()
    print(f"  Seeded {len(ALERTS_DATA)} alerts")


def update_site_risk_states(session):
    """Update site_risk_states to reflect clusters."""
    print("  Updating site_risk_states...")
    
    for sdata in SITE_STATE_UPDATES:
        site_state = session.query(SiteRiskState).filter(
            SiteRiskState.site_id == sdata["site_id"]
        ).first()
        
        if not site_state:
            site_state = SiteRiskState(site_id=sdata["site_id"])
            session.add(site_state)
        
        site_state.current_state = sdata["current_state"]
        site_state.dominant_category = sdata["dominant_category"]
        site_state.dominant_cluster = sdata["dominant_cluster"]
        site_state.state_entered_at = sdata["state_entered_at"]
        site_state.last_evaluated_at = datetime.now(timezone.utc)
    
    session.commit()
    print(f"  Updated {len(SITE_STATE_UPDATES)} site risk states")


def verify_seeding(session):
    """Run verification queries to confirm seeding worked."""
    print("\n" + "=" * 60)
    print("VERIFICATION QUERIES")
    print("=" * 60)
    
    # 1. Total classified reports
    count = session.query(Report).filter(
        Report.processing_status == "classified"
    ).count()
    print(f"1. Classified reports: {count} (expected 15)")
    
    # 2. No hardcoded 0.950 scores
    count = session.query(Classification).filter(
        Classification.classifier_score == 0.950
    ).count()
    print(f"2. Classifications with score 0.950: {count} (expected 0)")
    
    # 3. Active clusters
    clusters = session.query(Cluster).filter(Cluster.active == True).all()
    print(f"3. Active clusters: {len(clusters)} (expected 3)")
    for c in clusters:
        print(f"   - {c.site_id or 'CROSS-SITE'} | {c.sif_category} | {c.risk_state} | score={c.pattern_score:.2f}")
    
    # 4. Site risk states
    states = session.query(SiteRiskState).order_by(SiteRiskState.site_id).all()
    print(f"4. Site risk states:")
    for s in states:
        print(f"   - {s.site_id}: {s.current_state} (dominant: {s.dominant_category})")
    
    # 5. Alerts
    alerts = session.query(Alert).all()
    print(f"5. Alerts: {len(alerts)} (expected 3)")
    for a in alerts:
        print(f"   - {a.site_id} | {a.alert_type} | {a.from_state} -> {a.to_state}")
    
    # 6. No seed_script submitted_by
    count = session.query(Report).filter(Report.submitted_by == "seed_script").count()
    print(f"6. Reports with submitted_by='seed_script': {count} (expected 0)")
    
    # 7. Severity distribution
    from sqlalchemy import func
    severity_counts = session.query(
        Classification.severity, func.count(Classification.classification_id)
    ).group_by(Classification.severity).all()
    print(f"7. Severity breakdown:")
    for sev, cnt in severity_counts:
        print(f"   - {sev}: {cnt}")
    
    # 8. Classifier scores variety
    scores = session.query(Classification.classifier_score).all()
    unique_scores = set(round(s[0], 2) for s in scores)
    print(f"8. Unique classifier scores: {sorted(unique_scores)} (expected variety, not all 0.95)")
    
    # 9. Graph nodes and edges
    node_count = session.query(GraphNode).filter(GraphNode.active == True).count()
    edge_count = session.query(GraphEdge).count()
    print(f"9. Graph nodes: {node_count}, Graph edges: {edge_count}")
    
    print("=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)


def main():
    print("=" * 60)
    print("SIH26165 v0_2 — Demo Data Seed Script")
    print("=" * 60)
    
    # Init DB
    db_url = os.getenv("DATABASE_URL")
    
    try:
        engine = init_db(db_url)
        session = get_session()
        session.execute(__import__('sqlalchemy').text("SELECT 1"))
        print("DB connection: OK")
    except Exception as e:
        print(f"\nDB connection FAILED: {e}")
        print("Ensure PostgreSQL is running and schema has been applied.")
        sys.exit(1)
    
    try:
        # Clear existing data
        clear_existing_data(session)
        
        # Seed in dependency order
        seed_sites(session)
        seed_reports(session)
        seed_graph_nodes_and_edges(session)
        seed_clusters(session)
        seed_alerts(session)
        update_site_risk_states(session)
        
        # Verify
        verify_seeding(session)
        
        print("\n[OK] Seed complete. Demo data ready.")
        
    except Exception as e:
        session.rollback()
        print(f"\n[FAILED] Seed failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()