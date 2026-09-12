"""
Component 4: LLM Extraction Pipeline
- build_prompt(report_text) — constructs full extraction prompt
- run_extraction(report_text) — calls Ollama, returns parsed dict

Architecture doc Sections 6.1, 6.2, 6.3, 6.4
"""

import json
import os
import re
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load ontology vocabulary at module import (injected into prompt at runtime)
# ---------------------------------------------------------------------------

_REGISTRY_PATH = Path(__file__).parent.parent / "ontology" / "registry.json"

with open(_REGISTRY_PATH, "r") as _f:
    _REGISTRY = json.load(_f)

_ALL_EQUIPMENT_CLASSES: list[str] = sorted(set(_REGISTRY["all_equipment_classes"]))
_ALL_ACTIVITY_CONTEXTS: list[str] = sorted(set(_REGISTRY["all_activity_contexts"]))

# Build subtype list for prompt
_SUBTYPE_LINES = []
for cat_name, cat_data in _REGISTRY["categories"].items():
    subtypes = list(cat_data["subtypes"].keys())
    _SUBTYPE_LINES.append(f"- {cat_name}: {', '.join(subtypes)}")
_SUBTYPE_BLOCK = "\n".join(_SUBTYPE_LINES)

# ---------------------------------------------------------------------------
# Ollama configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen3:8B")
OLLAMA_TIMEOUT  = 120  # seconds


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(report_text: str) -> str:
    """
    Constructs full extraction prompt. Equipment classes and activity contexts
    are injected at runtime from ontology registry — not hardcoded.
    All rules from Architecture doc Section 6.2 included verbatim.
    """
    equipment_str = ", ".join(_ALL_EQUIPMENT_CLASSES)
    activity_str  = ", ".join(_ALL_ACTIVITY_CONTEXTS)

    prompt = f"""You are a domain expert in industrial safety analysis for oil and gas operations.
Your task is to analyze a near-miss safety report and map it to a predefined safety ontology.

ONTOLOGY VOCABULARY (you may ONLY use labels from these lists):

SIF CATEGORIES: FALL_FROM_HEIGHT, CAUGHT_IN_STRUCK_BY, EXPLOSION_FIRE, CHEMICAL_EXPOSURE, ELECTRICAL, VEHICLE_TRANSPORT

SUBTYPES:
{_SUBTYPE_BLOCK}

CONTRIBUTING FACTORS: PPE_FAILURE, PROCEDURE_VIOLATION, EQUIPMENT_FAULT, ENVIRONMENTAL

EQUIPMENT CLASSES: {equipment_str}

ACTIVITY CONTEXTS: {activity_str}

SEVERITY LEVELS:
- LOW: equipment involvement only, no personnel exposure or proximity
- MEDIUM: multiple contributing factors OR personnel in proximity but not contacted
- HIGH: direct personnel exposure or contact, injury possible but avoided
- CRITICAL: near-fatality, multiple personnel affected, energy release or toxic exposure occurred

RULES:
1. Map ONLY to subtypes, contributing factors, equipment classes, and activity contexts listed above.
2. Do NOT invent new labels. If no existing label fits, either omit that field or abstain entirely.
3. A report may have multiple applicable subtypes. Map all that apply.
4. For each mapping, provide ONLY the exact text span from the report that supports it as evidence_span.
5. mapping_confidence is your certainty that this mapping is correct given the evidence (0.0–1.0).
6. If the report text does not provide sufficient evidence for ANY mapping, return abstain: true with a clear abstain_reason.
7. Partial confidence is acceptable. Do not inflate confidence — 0.6 is better than a false 0.9.
8. severity_justification: one sentence explaining why this severity level was assigned.
   Reference the severity criteria: LOW = equipment only / no personnel, MEDIUM = proximity
   without contact, HIGH = direct exposure/contact, CRITICAL = near-fatality or energy release.

REPORT:
{report_text}

Respond ONLY with valid JSON. No preamble. No explanation outside the JSON. No markdown fences.

JSON SCHEMA:
{{
  "abstain": false,
  "abstain_reason": null,
  "mappings": [
    {{
      "sif_category": "CATEGORY_NAME",
      "subtype_id": "XX.00",
      "contributing_factors": ["FACTOR"],
      "equipment_classes": ["CLASS"],
      "activity_contexts": ["CONTEXT"],
      "mapping_confidence": 0.0,
      "evidence_span": "exact text from report",
      "severity": "LOW|MEDIUM|HIGH|CRITICAL",
      "severity_justification": "one sentence explaining severity assignment"
    }}
  ]
}}"""
    return prompt


# ---------------------------------------------------------------------------
# Ollama call + JSON extraction
# ---------------------------------------------------------------------------

def _extract_json_from_response(text: str) -> str:
    """
    Strips preamble from LLM response to isolate JSON object.
    Handles models that prepend explanatory text before JSON.
    """
    # Try to find JSON object directly
    stripped = text.strip()
    if stripped.startswith("{"):
        return stripped

    # Try to extract from markdown fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fence_match:
        return fence_match.group(1)

    # Find first { and last } — take the outermost object
    start = stripped.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response")

    # Balance braces to find the end
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(stripped[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return stripped[start:i + 1]

    raise ValueError("Unbalanced JSON braces in LLM response")


def run_extraction(report_text: str) -> dict:
    """
    Sends report text to Ollama, parses JSON response.
    Returns dict matching LLM output contract (Architecture doc Section 6.4).
    Raises on Ollama connection failure after retries.
    """
    prompt = build_prompt(report_text)

    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,    # Low temperature for deterministic structured output
            "top_p": 0.9,
            "num_predict": 1024,
        }
    }

    try:
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.ConnectError:
        raise RuntimeError(
            f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. "
            "Ensure Ollama is running: ollama serve"
        )
    except httpx.TimeoutException:
        raise RuntimeError(
            f"Ollama request timed out after {OLLAMA_TIMEOUT}s. "
            "The model may be loading — try again in 30 seconds."
        )

    ollama_response = response.json()
    raw_text = ollama_response.get("response", "")

    if not raw_text.strip():
        raise ValueError("Ollama returned empty response")

    # Extract and parse JSON
    try:
        json_str = _extract_json_from_response(raw_text)
        result = json.loads(json_str)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"JSON parse failed. Raw response: {raw_text[:500]}")
        raise ValueError(f"Failed to parse LLM JSON response: {e}")

    # Normalize output structure
    result.setdefault("abstain", False)
    result.setdefault("abstain_reason", None)
    result.setdefault("mappings", [])

    # If abstaining, ensure mappings is empty
    if result.get("abstain"):
        result["mappings"] = []

    return result


def run_extraction_with_fallback(report_text: str) -> dict:
    """
    Wraps run_extraction with a graceful fallback for when Ollama is unavailable.
    Returns a rule-based best-effort result. Used only when Ollama is down.
    """
    try:
        return run_extraction(report_text)
    except RuntimeError as e:
        logger.warning(f"Ollama unavailable, using fallback extraction: {e}")
        return _rule_based_fallback(report_text)


def _rule_based_fallback(report_text: str) -> dict:
    """
    Minimal rule-based fallback when Ollama is unavailable.
    Used only in demos when Ollama is down — not production logic.
    """
    text_lower = report_text.lower()

    # Detect category from keywords
    if any(kw in text_lower for kw in ["fall", "fell", "scaffold", "ladder", "height"]):
        category, subtype = "FALL_FROM_HEIGHT", "FFH.01"
        evidence = "fall-related incident detected"
    elif any(kw in text_lower for kw in ["fire", "explosion", "ignition", "blast"]):
        category, subtype = "EXPLOSION_FIRE", "EF.01"
        evidence = "fire/explosion-related incident detected"
    elif any(kw in text_lower for kw in ["chemical", "h2s", "acid", "toxic", "exposure", "ppe", "gloves"]):
        category, subtype = "CHEMICAL_EXPOSURE", "CE.01"
        evidence = report_text[:200].split(".")[0]
    elif any(kw in text_lower for kw in ["electrical", "electric", "shock", "loto", "arc"]):
        category, subtype = "ELECTRICAL", "ELEC.01"
        evidence = "electrical-related incident detected"
    elif any(kw in text_lower for kw in ["vehicle", "truck", "tanker", "collision"]):
        category, subtype = "VEHICLE_TRANSPORT", "VT.01"
        evidence = "vehicle transport incident detected"
    else:
        category, subtype = "CAUGHT_IN_STRUCK_BY", "CISB.01"
        evidence = "safety incident detected"

    return {
        "abstain": False,
        "abstain_reason": None,
        "mappings": [{
            "sif_category": category,
            "subtype_id": subtype,
            "contributing_factors": ["PROCEDURE_VIOLATION"],
            "equipment_classes": [],
            "activity_contexts": ["MAINTENANCE"],
            "mapping_confidence": 0.45,
            "evidence_span": evidence,
            "severity": "MEDIUM",
            "severity_justification": (
                "Rule-based fallback: medium severity assigned by default. "
                "Ollama unavailable for detailed analysis."
            )
        }]
    }
