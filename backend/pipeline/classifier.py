"""
Component 5: SIF Classifier
Inference module. Loads distilBERT fine-tuned model if available.
Falls back to rule-based classifier when model not yet trained.

Architecture doc Sections 8.1–8.5.
"""

import logging
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
load_dotenv()

MODEL_PATH = os.getenv("CLASSIFIER_MODEL_PATH", "./models/distilbert-sif-v1.0")
MODEL_VERSION = "distilbert-sif-v1.0"

# ---------------------------------------------------------------------------
# Severity mapping (Architecture doc Section 8.4)
# ---------------------------------------------------------------------------

SEVERITY_CRITERIA = {
    "LOW":      "Equipment involvement only, no personnel exposure or proximity",
    "MEDIUM":   "Multiple contributing factors OR personnel in proximity but not contacted",
    "HIGH":     "Direct personnel exposure or contact, injury possible but avoided",
    "CRITICAL": "Near-fatality, multiple personnel, energy release or toxic exposure occurred",
}

# Category → subtype mapping for classification
CATEGORY_SUBTYPES = {
    "FALL_FROM_HEIGHT":    ["FFH.01", "FFH.02", "FFH.03", "FFH.04"],
    "CAUGHT_IN_STRUCK_BY": ["CISB.01", "CISB.02", "CISB.03", "CISB.04"],
    "EXPLOSION_FIRE":      ["EF.01", "EF.02", "EF.03", "EF.04"],
    "CHEMICAL_EXPOSURE":   ["CE.01", "CE.02", "CE.03", "CE.04"],
    "ELECTRICAL":          ["ELEC.01", "ELEC.02", "ELEC.03", "ELEC.04"],
    "VEHICLE_TRANSPORT":   ["VT.01", "VT.02", "VT.03", "VT.04"],
}

# ---------------------------------------------------------------------------
# Model singleton
# ---------------------------------------------------------------------------

_model = None
_tokenizer = None
_model_loaded = False


def _try_load_model():
    """Attempt to load fine-tuned distilBERT. Returns True if successful."""
    global _model, _tokenizer, _model_loaded

    model_dir = Path(MODEL_PATH)
    if not model_dir.exists():
        logger.info(f"Model not found at {MODEL_PATH} — using rule-based classifier")
        return False

    try:
        from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
        import torch

        _tokenizer = DistilBertTokenizer.from_pretrained(str(model_dir))
        _model = DistilBertForSequenceClassification.from_pretrained(str(model_dir))
        _model.eval()
        _model_loaded = True
        logger.info(f"Loaded classifier model from {MODEL_PATH}")
        return True
    except Exception as e:
        logger.warning(f"Failed to load model: {e} — using rule-based classifier")
        return False


# Try to load model on module import
_try_load_model()


# ---------------------------------------------------------------------------
# Input encoding (Architecture doc Section 8.2)
# ---------------------------------------------------------------------------

def encode_mapping_for_classifier(mapping: dict) -> str:
    """
    Encodes a mapping dict into the structured token sequence expected by the classifier.
    Architecture doc Section 8.2 — exact format specified.
    """
    subtype = mapping.get("subtype_id", "")
    factors  = " ".join(mapping.get("contributing_factors", []))
    equipment = " ".join(mapping.get("equipment_classes", []))
    activity  = " ".join(mapping.get("activity_contexts", []))
    evidence  = mapping.get("evidence_span", "")

    return (
        f"SUBTYPE: {subtype} "
        f"FACTORS: {factors} "
        f"EQUIPMENT: {equipment} "
        f"ACTIVITY: {activity} "
        f"EVIDENCE: {evidence}"
    )


# ---------------------------------------------------------------------------
# Neural inference (used when model is loaded)
# ---------------------------------------------------------------------------

def _infer_with_model(encoded_input: str) -> tuple[str, str, float]:
    """Returns (sif_category, severity, score) from neural model."""
    import torch
    inputs = _tokenizer(
        encoded_input,
        return_tensors="pt",
        truncation=True,
        max_length=256,
        padding=True
    )
    with torch.no_grad():
        outputs = _model(**inputs)

    logits = outputs.logits
    probs  = torch.softmax(logits, dim=-1)
    predicted_class = torch.argmax(probs, dim=-1).item()
    confidence = probs[0][predicted_class].item()

    # Map predicted class index to label (assumes label order from training)
    label_map = _model.config.id2label
    label = label_map.get(predicted_class, "CHEMICAL_EXPOSURE|HIGH")

    parts = label.split("|") if "|" in label else [label, "HIGH"]
    sif_category = parts[0] if len(parts) > 0 else "CHEMICAL_EXPOSURE"
    severity     = parts[1] if len(parts) > 1 else "HIGH"

    return sif_category, severity, confidence


# ---------------------------------------------------------------------------
# Rule-based classifier fallback (v0 — used when model not trained yet)
# ---------------------------------------------------------------------------

def _infer_rule_based(mapping: dict) -> tuple[str, str, float]:
    """
    Deterministic rule-based classifier. Uses LLM output directly.
    Category and severity come from the mapping (LLM already assigned them).
    This is not a separate model — it trusts the LLM's category assignment
    and derives severity from the severity field the LLM returned.
    """
    # Trust LLM's category assignment
    sif_category = mapping.get("sif_category", "CHEMICAL_EXPOSURE")
    subtype_id   = mapping.get("subtype_id", "CE.01")

    # Severity from LLM output (direct field)
    severity = mapping.get("severity", "")

    # If LLM didn't return severity, infer from contributing factors
    if not severity or severity not in SEVERITY_CRITERIA:
        factors   = set(mapping.get("contributing_factors", []))
        confidence = mapping.get("mapping_confidence", 0.5)

        if "PPE_FAILURE" in factors and "PROCEDURE_VIOLATION" in factors:
            severity = "HIGH"
        elif "PPE_FAILURE" in factors or "EQUIPMENT_FAULT" in factors:
            severity = "MEDIUM"
        elif confidence > 0.8:
            severity = "HIGH"
        else:
            severity = "MEDIUM"

    # Confidence: use LLM mapping confidence as proxy
    confidence = mapping.get("mapping_confidence", 0.75)

    return sif_category, severity, min(confidence, 0.99)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def classify_mapping(mapping: dict) -> dict:
    """
    Classify a single ontology mapping.
    Returns dict with sif_category, subtype_id, severity, classifier_score, model_version.

    Architecture doc Section 8.3 output contract.
    """
    if _model_loaded:
        encoded = encode_mapping_for_classifier(mapping)
        sif_category, severity, score = _infer_with_model(encoded)
    else:
        sif_category, severity, score = _infer_rule_based(mapping)

    # Subtype from mapping (classifier refines category, subtype stays from LLM)
    subtype_id = mapping.get("subtype_id", "")
    # If category changed (neural), pick first subtype for that category
    if sif_category != mapping.get("sif_category") and sif_category in CATEGORY_SUBTYPES:
        subtype_id = CATEGORY_SUBTYPES[sif_category][0]

    used_version = MODEL_VERSION if _model_loaded else "rule-based-v0"

    return {
        "sif_category":    sif_category,
        "subtype_id":      subtype_id,
        "severity":        severity,
        "classifier_score": round(score, 4),
        "model_version":   used_version,
    }


def get_model_info() -> dict:
    return {
        "model_path":    MODEL_PATH,
        "model_loaded":  _model_loaded,
        "model_version": MODEL_VERSION if _model_loaded else "rule-based-v0",
    }
