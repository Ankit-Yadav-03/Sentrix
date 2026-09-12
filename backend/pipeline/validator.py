"""
Component 2: Ontology Validator
- gate_1_validate(payload) — structural checks
- gate_2_validate(raw_text) — safety keyword check (80+ terms)
- validate_mapping(mapping) — vocabulary lock against ontology registry

Architecture doc Sections 5 and 6.3.
"""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Optional

try:
    from langdetect import detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Ontology registry — loaded at module import
# ---------------------------------------------------------------------------

_REGISTRY_PATH = Path(__file__).parent.parent / "ontology" / "registry.json"

with open(_REGISTRY_PATH, "r") as _f:
    _REGISTRY = json.load(_f)

# Build valid label sets from registry
VALID_SUBTYPES: set = set()
for _cat, _cat_data in _REGISTRY["categories"].items():
    for _sid in _cat_data["subtypes"].keys():
        VALID_SUBTYPES.add(_sid)

VALID_CONTRIBUTING_FACTORS: set = set(_REGISTRY["global_contributing_factors"])
VALID_EQUIPMENT_CLASSES: set = set(_REGISTRY["all_equipment_classes"])
VALID_ACTIVITY_CONTEXTS: set = set(_REGISTRY["all_activity_contexts"])

VALID_CATEGORIES: set = set(_REGISTRY["categories"].keys())

# ---------------------------------------------------------------------------
# Site registry — loaded from DB on startup; fallback to hardcoded set for v0
# ---------------------------------------------------------------------------

SITE_REGISTRY: set = {
    "OIL_SITE_02",
    "OIL_SITE_04",
    "OIL_SITE_07",
    "OIL_SITE_11",
    "OIL_SITE_15",
}

ALLOWED_SOURCES: set = {"manual_text", "pdf_upload", "flutter_upload"}
MIN_TEXT_LENGTH: int = 50  # characters


def load_site_registry_from_db(session) -> None:
    """Refresh SITE_REGISTRY from DB on startup. Called by main.py."""
    global SITE_REGISTRY
    try:
        from backend.models.db import SiteRiskState
        rows = session.query(SiteRiskState.site_id).all()
        if rows:
            SITE_REGISTRY = {r.site_id for r in rows}
    except Exception:
        pass  # Fall back to hardcoded set


# ---------------------------------------------------------------------------
# Duplicate hash check (in-memory cache for v0)
# ---------------------------------------------------------------------------

_recent_hashes: dict = {}  # hash -> submitted_at timestamp


def _compute_text_hash(raw_text: str, site_id: str) -> str:
    return hashlib.sha256((raw_text.strip() + site_id).encode()).hexdigest()


def _is_duplicate(text_hash: str, window_minutes: int = 60) -> bool:
    from datetime import datetime, timedelta, timezone
    if text_hash not in _recent_hashes:
        return False
    submitted_at = _recent_hashes[text_hash]
    return (datetime.now(timezone.utc) - submitted_at) < timedelta(minutes=window_minutes)


def _register_hash(text_hash: str) -> None:
    from datetime import datetime, timezone
    _recent_hashes[text_hash] = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Gate 1 — Structural Validation
# ---------------------------------------------------------------------------

def gate_1_validate(payload: dict) -> tuple[bool, str]:
    """
    Deterministic structural checks. Returns (ok, error_message).
    All checks from Architecture doc Section 5.2.
    """
    # Required field presence
    for field in ["site_id", "raw_text", "source"]:
        if not payload.get(field):
            return False, f"Missing required field: {field}"

    raw_text = payload["raw_text"]
    site_id  = payload["site_id"]
    source   = payload["source"]

    # Text length
    if len(raw_text.strip()) < MIN_TEXT_LENGTH:
        return False, (
            f"Report text too short (minimum {MIN_TEXT_LENGTH} characters). "
            "Please provide a detailed description of the incident."
        )

    # Source enum
    if source not in ALLOWED_SOURCES:
        return False, f"Invalid source: '{source}'. Must be one of: {', '.join(ALLOWED_SOURCES)}"

    # Site registry check
    if site_id not in SITE_REGISTRY:
        return False, f"Unknown site_id: '{site_id}'. Please use a registered site identifier."

    # Language detection
    if LANGDETECT_AVAILABLE:
        try:
            lang = detect(raw_text)
            if lang != "en":
                return False, (
                    f"Report language not supported: detected '{lang}'. "
                    "Please submit reports in English."
                )
        except LangDetectException:
            return False, "Could not detect report language. Please submit in English."

    # Duplicate hash check
    text_hash = _compute_text_hash(raw_text, site_id)
    if _is_duplicate(text_hash, window_minutes=60):
        return False, (
            "Duplicate report detected. This report appears identical to a "
            "recent submission from the same site within the last hour."
        )

    # Register hash for future duplicate checks
    _register_hash(text_hash)

    return True, ""


# ---------------------------------------------------------------------------
# Gate 2 — Content Plausibility (domain keyword check)
# Architecture doc Section 5.3 — minimum 80 domain terms
# ---------------------------------------------------------------------------

SAFETY_KEYWORDS: frozenset = frozenset({
    # Incident types
    "leak", "leaking", "leaked", "spill", "spilled", "spillage",
    "fire", "fires", "burning", "ignition", "ignited",
    "explosion", "exploded", "explosive", "blast", "blowout",
    "fall", "fell", "fallen", "falling",
    "collapse", "collapsed", "collapsing",
    "struck", "strike", "hitting", "hit",
    "caught", "entangled", "entanglement", "pinned",
    "contact", "contacted", "touching",
    "exposure", "exposed", "inhaled", "inhalation",
    "release", "released", "released",
    "rupture", "ruptured", "burst", "bursting",
    "near miss", "near-miss", "nearmiss", "near incident",
    "incident", "accident", "injury", "injured",
    "hazard", "hazardous", "dangerous", "unsafe", "risk",
    "emergency", "evacuation", "evacuated",
    # Equipment
    "valve", "valves",
    "pipe", "pipes", "pipeline", "piping",
    "equipment", "machinery", "machine",
    "scaffold", "scaffolding",
    "ladder", "ladders",
    "crane", "cranes", "hoist",
    "vehicle", "vehicles", "truck", "tanker",
    "pump", "pumps", "compressor",
    "vessel", "vessels", "tank", "tanks",
    "electrical", "electric", "cable", "wiring",
    "panel", "switchgear", "generator",
    "pressure", "pressurized", "pressurised",
    "hose", "fitting", "flange", "gasket",
    "drum", "cylinder", "container",
    # Substances
    "gas", "gases", "vapour", "vapor", "fumes", "smoke",
    "chemical", "chemicals", "substance", "acid",
    "h2s", "hydrogen sulphide", "hydrogen sulfide",
    "hydrocarbon", "crude", "oil", "fuel", "petrol", "petroleum",
    "flammable", "combustible", "toxic", "corrosive",
    "oxygen", "nitrogen", "chlorine", "ammonia",
    # Safety gear / PPE
    "ppe", "gloves", "glove",
    "harness", "safety harness", "lanyard",
    "helmet", "hard hat", "head protection",
    "mask", "respirator", "scba", "breathing apparatus",
    "goggles", "face shield", "eye protection",
    "safety boots", "safety shoes",
    # Procedures
    "loto", "lockout", "tagout", "lock-out", "tag-out",
    "permit", "work permit", "hot work",
    "isolation", "isolate", "isolated",
    "grounding", "bonding", "earthing",
    "confined space",
    # Personnel
    "operator", "worker", "technician", "driver",
    "maintenance", "contractor", "employee",
    # Severity
    "critical", "severe", "serious", "fatal", "fatality", "injury",
    "burn", "burns", "burned", "fracture", "laceration",
})


def gate_2_validate(raw_text: str) -> tuple[bool, str]:
    """
    Domain keyword check. Returns (ok, error_message).
    Zero safety keyword matches → reject.
    """
    text_lower = raw_text.lower()
    # Check multi-word keywords first, then single words
    matched = [kw for kw in SAFETY_KEYWORDS if kw in text_lower]
    if not matched:
        return False, (
            "Report does not appear to describe a safety-relevant event. "
            "Please describe the incident, equipment involved, contributing factors, "
            "and the personnel involved in detail."
        )
    return True, ""


# ---------------------------------------------------------------------------
# Vocabulary Lock — validate LLM mapping against ontology registry
# Architecture doc Section 6.3
# ---------------------------------------------------------------------------

def validate_mapping(mapping: dict) -> tuple[bool, list[str]]:
    """
    Checks that every label in the mapping exists in the ontology registry.
    Returns (all_valid, list_of_errors).
    Invalid mappings are logged and excluded from graph construction.
    """
    errors = []

    # Subtype ID
    subtype_id = mapping.get("subtype_id", "")
    if subtype_id not in VALID_SUBTYPES:
        errors.append(f"Invalid subtype_id: {subtype_id}")

    # SIF category
    sif_cat = mapping.get("sif_category", "")
    if sif_cat and sif_cat not in VALID_CATEGORIES:
        errors.append(f"Invalid sif_category: {sif_cat}")

    # Contributing factors
    for cf in mapping.get("contributing_factors", []):
        if cf not in VALID_CONTRIBUTING_FACTORS:
            errors.append(f"Invalid contributing_factor: {cf}")

    # Equipment classes
    for ec in mapping.get("equipment_classes", []):
        if ec not in VALID_EQUIPMENT_CLASSES:
            errors.append(f"Invalid equipment_class: {ec}")

    # Activity contexts
    for ac in mapping.get("activity_contexts", []):
        if ac not in VALID_ACTIVITY_CONTEXTS:
            errors.append(f"Invalid activity_context: {ac}")

    # Evidence span must be present and non-empty
    if not mapping.get("evidence_span", "").strip():
        errors.append("Missing or empty evidence_span")

    # Confidence range
    confidence = mapping.get("mapping_confidence", -1)
    if not (0.0 <= confidence <= 1.0):
        errors.append(f"mapping_confidence out of range: {confidence}")

    return len(errors) == 0, errors


def get_standards_references(subtype_id: str) -> list[str]:
    """
    Fetch standards_references for a subtype from the registry.
    Called at response-construction time — not stored in DB.
    """
    for cat_data in _REGISTRY["categories"].values():
        subtype = cat_data["subtypes"].get(subtype_id)
        if subtype:
            return subtype.get("standards_references", [])
    return []
