"""
Tests for Sentrix v0 Prototype
Covers: Gate 1, Gate 2, vocabulary lock, pattern score engine, classifier, edge weights.
Run: pytest tests/ -v
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ===========================================================================
# Gate 1 — Structural Validation
# ===========================================================================

class TestGate1:
    def setup_method(self):
        from backend.pipeline.validator import gate_1_validate, SITE_REGISTRY
        SITE_REGISTRY.add("OIL_SITE_04")
        SITE_REGISTRY.add("OIL_SITE_07")
        self.validate = gate_1_validate

    def test_valid_payload_passes(self):
        ok, reason = self.validate({
            "site_id": "OIL_SITE_04",
            "raw_text": "Worker observed without PPE gloves during chemical drum sampling at transfer station. "
                        "Acid spray contacted forearm. Valve packing leak on injection line caused spill.",
            "source": "manual_text",
        })
        assert ok is True
        assert reason == ""

    def test_missing_site_id_fails(self):
        ok, reason = self.validate({
            "raw_text": "Some incident description that is long enough to pass.",
            "source": "manual_text",
        })
        assert ok is False
        assert "site_id" in reason.lower()

    def test_missing_raw_text_fails(self):
        ok, reason = self.validate({
            "site_id": "OIL_SITE_04",
            "source": "manual_text",
        })
        assert ok is False
        assert "raw_text" in reason.lower() or "required" in reason.lower()

    def test_text_too_short_fails(self):
        ok, reason = self.validate({
            "site_id": "OIL_SITE_04",
            "raw_text": "Short.",
            "source": "manual_text",
        })
        assert ok is False
        assert "short" in reason.lower() or "minimum" in reason.lower() or "50" in reason

    def test_invalid_source_fails(self):
        ok, reason = self.validate({
            "site_id": "OIL_SITE_04",
            "raw_text": "Worker observed without PPE gloves during chemical drum sampling. "
                        "Acid spray contacted forearm during valve packing maintenance.",
            "source": "telegram_bot",
        })
        assert ok is False
        assert "source" in reason.lower() or "invalid" in reason.lower()

    def test_unknown_site_fails(self):
        ok, reason = self.validate({
            "site_id": "UNKNOWN_SITE_99",
            "raw_text": "Worker observed without PPE gloves during chemical drum sampling. "
                        "Acid spray contacted forearm during valve packing maintenance.",
            "source": "manual_text",
        })
        assert ok is False
        assert "site" in reason.lower() or "unknown" in reason.lower()

    def test_all_valid_sources_pass(self):
        import backend.pipeline.validator as v
        v._recent_hashes.clear()  # isolate from duplicate-hash state
        texts = {
            "manual_text":    "Worker observed without PPE gloves during chemical drum sampling. Acid spray contacted forearm during valve packing maintenance.",
            "pdf_upload":     "Operator exposed to caustic soda without gloves at reagent tank. Skin contact with chemical occurred during sampling activity.",
            "flutter_upload": "Safety incident: pressure relief valve opened unexpectedly. Gas release near ignition source. Evacuation initiated by operator.",
        }
        for src, text in texts.items():
            ok, reason = self.validate({"site_id": "OIL_SITE_04", "raw_text": text, "source": src})
            assert ok is True, f"Source '{src}' should pass Gate 1, got: {reason}"


# ===========================================================================
# Gate 2 — Domain Keyword Check
# ===========================================================================

class TestGate2:
    def setup_method(self):
        from backend.pipeline.validator import gate_2_validate
        self.validate = gate_2_validate

    def test_ppe_report_passes(self):
        ok, _ = self.validate(
            "Operator not wearing gloves during chemical handling at the reagent tank. "
            "Acid contacted forearm. Emergency eyewash station used immediately."
        )
        assert ok is True

    def test_fall_report_passes(self):
        ok, _ = self.validate(
            "Worker fell from scaffold at 4 metre elevation without harness. "
            "Near miss — caught themselves on the ladder rail."
        )
        assert ok is True

    def test_explosion_report_passes(self):
        ok, _ = self.validate(
            "Hydrocarbon vapour cloud formed near pump after pipeline flange leak. "
            "Ignition risk from nearby grinder. Fire emergency response activated."
        )
        assert ok is True

    def test_h2s_report_passes(self):
        ok, _ = self.validate(
            "H2S monitor alarmed at 8 ppm near well head. Operator exposed without SCBA. "
            "Toxic gas release from separator valve."
        )
        assert ok is True

    def test_electrical_report_passes(self):
        ok, _ = self.validate(
            "Electrician received electric shock from live bus bar on MCC panel. "
            "LOTO not applied before electrical work began."
        )
        assert ok is True

    def test_vehicle_report_passes(self):
        ok, _ = self.validate(
            "Tanker near-rollover on site road. Vehicle exceeded speed limit at intersection. "
            "Two workers on foot in proximity during the incident."
        )
        assert ok is True

    def test_nonsense_text_fails(self):
        ok, reason = self.validate(
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris."
        )
        assert ok is False
        assert "safety" in reason.lower() or "domain" in reason.lower() or "describe" in reason.lower()

    def test_empty_text_fails(self):
        ok, _ = self.validate("")
        assert ok is False

    def test_administrative_text_fails(self):
        ok, _ = self.validate(
            "Please submit your annual performance review by Friday. "
            "HR has updated the leave application form. Meeting rescheduled to next week. "
            "Remember to update your timesheet by end of month for payroll processing."
        )
        assert ok is False

    def test_minimum_keyword_match(self):
        # Single keyword should be enough
        ok, _ = self.validate(
            "There was a leak at the facility today that required immediate attention "
            "from the maintenance team who were on site inspecting equipment."
        )
        assert ok is True


# ===========================================================================
# Vocabulary Lock
# ===========================================================================

class TestVocabularyLock:
    def setup_method(self):
        from backend.pipeline.validator import validate_mapping
        self.validate = validate_mapping

    def _valid_mapping(self, **overrides):
        base = {
            "subtype_id":           "CE.01",
            "sif_category":         "CHEMICAL_EXPOSURE",
            "contributing_factors": ["PPE_FAILURE"],
            "equipment_classes":    ["CHEMICAL_DRUM"],
            "activity_contexts":    ["CHEMICAL_HANDLING"],
            "mapping_confidence":   0.85,
            "evidence_span":        "operator not wearing gloves during acid transfer",
        }
        base.update(overrides)
        return base

    def test_valid_mapping_passes(self):
        ok, errors = self.validate(self._valid_mapping())
        assert ok is True
        assert errors == []

    def test_all_24_subtypes_valid(self):
        subtypes = [
            "FFH.01","FFH.02","FFH.03","FFH.04",
            "CISB.01","CISB.02","CISB.03","CISB.04",
            "EF.01","EF.02","EF.03","EF.04",
            "CE.01","CE.02","CE.03","CE.04",
            "ELEC.01","ELEC.02","ELEC.03","ELEC.04",
            "VT.01","VT.02","VT.03","VT.04",
        ]
        for sid in subtypes:
            ok, errs = self.validate(self._valid_mapping(subtype_id=sid))
            assert ok is True, f"Subtype {sid} should be valid, got: {errs}"

    def test_invalid_subtype_fails(self):
        ok, errors = self.validate(self._valid_mapping(subtype_id="MADE_UP.99"))
        assert ok is False
        assert any("subtype_id" in e for e in errors)

    def test_invalid_contributing_factor_fails(self):
        ok, errors = self.validate(self._valid_mapping(contributing_factors=["MANAGEMENT_FAILURE"]))
        assert ok is False
        assert any("contributing_factor" in e for e in errors)

    def test_invalid_equipment_class_fails(self):
        ok, errors = self.validate(self._valid_mapping(equipment_classes=["MAGIC_MACHINE"]))
        assert ok is False
        assert any("equipment_class" in e for e in errors)

    def test_invalid_activity_context_fails(self):
        ok, errors = self.validate(self._valid_mapping(activity_contexts=["DANCING"]))
        assert ok is False
        assert any("activity_context" in e for e in errors)

    def test_empty_evidence_span_fails(self):
        ok, errors = self.validate(self._valid_mapping(evidence_span=""))
        assert ok is False
        assert any("evidence_span" in e for e in errors)

    def test_confidence_out_of_range_fails(self):
        ok, errors = self.validate(self._valid_mapping(mapping_confidence=1.5))
        assert ok is False
        assert any("confidence" in e for e in errors)

    def test_confidence_negative_fails(self):
        ok, errors = self.validate(self._valid_mapping(mapping_confidence=-0.1))
        assert ok is False

    def test_all_contributing_factors_valid(self):
        for cf in ["PPE_FAILURE", "PROCEDURE_VIOLATION", "EQUIPMENT_FAULT", "ENVIRONMENTAL"]:
            ok, errs = self.validate(self._valid_mapping(contributing_factors=[cf]))
            assert ok is True, f"Contributing factor {cf} should be valid, got: {errs}"

    def test_multiple_valid_factors(self):
        ok, errors = self.validate(self._valid_mapping(
            contributing_factors=["PPE_FAILURE", "PROCEDURE_VIOLATION", "EQUIPMENT_FAULT"]
        ))
        assert ok is True
        assert errors == []


# ===========================================================================
# Pattern Score Engine
# ===========================================================================

class TestPatternScore:
    def _make_report(self, report_id, site_id, subtype_id, severity,
                     equipment_classes=None, activity_contexts=None, days_ago=0):
        return {
            "report_id":         report_id,
            "site_id":           site_id,
            "subtype_id":        subtype_id,
            "sif_category":      "CHEMICAL_EXPOSURE",
            "severity":          severity,
            "equipment_classes": equipment_classes or ["CHEMICAL_DRUM"],
            "activity_contexts": activity_contexts or ["CHEMICAL_HANDLING"],
            "timestamp":         datetime.now(timezone.utc) - timedelta(days=days_ago),
        }

    def test_empty_cluster_returns_zero(self):
        from backend.graph.pattern_score import compute_pattern_score
        result = compute_pattern_score([], "OIL_SITE_04", 30)
        assert result["pattern_score"] == 0.0

    def test_single_report_returns_nonzero(self):
        from backend.graph.pattern_score import compute_pattern_score
        reports = [self._make_report("r1", "OIL_SITE_04", "CE.01", "HIGH")]
        result = compute_pattern_score(reports, "OIL_SITE_04", 30)
        # Severity component should be nonzero for HIGH
        assert result["pattern_score"] >= 0.0
        assert result["score_components"]["severity"] > 0.0

    def test_score_increases_with_more_reports(self):
        from backend.graph.pattern_score import compute_pattern_score
        r1 = [self._make_report("r1", "OIL_SITE_04", "CE.01", "HIGH", days_ago=5)]
        r3 = [
            self._make_report("r1", "OIL_SITE_04", "CE.01", "HIGH", days_ago=10),
            self._make_report("r2", "OIL_SITE_04", "CE.01", "HIGH", days_ago=5),
            self._make_report("r3", "OIL_SITE_04", "CE.01", "HIGH", days_ago=1),
        ]
        score1 = compute_pattern_score(r1, "OIL_SITE_04", 30)["pattern_score"]
        score3 = compute_pattern_score(r3, "OIL_SITE_04", 30)["pattern_score"]
        assert score3 > score1

    def test_critical_severity_raises_score(self):
        from backend.graph.pattern_score import compute_pattern_score
        medium_reports = [self._make_report(f"r{i}", "OIL_SITE_04", "CE.01", "MEDIUM", days_ago=i)
                          for i in range(3)]
        critical_reports = [self._make_report(f"r{i}", "OIL_SITE_04", "CE.01", "CRITICAL", days_ago=i)
                            for i in range(3)]
        score_medium   = compute_pattern_score(medium_reports, "OIL_SITE_04", 30)["score_components"]["severity"]
        score_critical = compute_pattern_score(critical_reports, "OIL_SITE_04", 30)["score_components"]["severity"]
        assert score_critical > score_medium

    def test_score_bounded_0_to_1(self):
        from backend.graph.pattern_score import compute_pattern_score
        # Stress test: many CRITICAL reports
        reports = [
            self._make_report(f"r{i}", "OIL_SITE_04", "CE.01", "CRITICAL",
                              equipment_classes=["CHEMICAL_DRUM"], activity_contexts=["CHEMICAL_HANDLING"],
                              days_ago=i % 3)
            for i in range(20)
        ]
        result = compute_pattern_score(reports, "OIL_SITE_04", 30)
        assert 0.0 <= result["pattern_score"] <= 1.0

    def test_five_components_returned(self):
        from backend.graph.pattern_score import compute_pattern_score
        reports = [self._make_report("r1", "OIL_SITE_04", "CE.01", "HIGH")]
        result = compute_pattern_score(reports, "OIL_SITE_04", 30)
        components = result["score_components"]
        assert set(components.keys()) == {"density", "edge_strength", "velocity", "severity", "concentration"}

    def test_high_concentration_same_equipment(self):
        from backend.graph.pattern_score import compute_pattern_score
        # All reports with same equipment → high concentration
        reports = [
            self._make_report(f"r{i}", "OIL_SITE_04", "CE.01", "HIGH",
                              equipment_classes=["CHEMICAL_DRUM"], activity_contexts=["CHEMICAL_HANDLING"],
                              days_ago=i*2)
            for i in range(5)
        ]
        result = compute_pattern_score(reports, "OIL_SITE_04", 30)
        assert result["score_components"]["concentration"] > 0.3


# ===========================================================================
# Edge Weight Computation
# ===========================================================================

class TestEdgeWeights:
    def _node(self, subtype_id, site_id, equipment=None, activity=None, days_ago=0):
        return {
            "report_id":         f"r_{subtype_id}_{days_ago}",
            "site_id":           site_id,
            "subtype_id":        subtype_id,
            "equipment_classes": equipment or [],
            "activity_contexts": activity or [],
            "timestamp":         datetime.now(timezone.utc) - timedelta(days=days_ago),
        }

    def test_same_subtype_creates_edge(self):
        from backend.graph.pattern_score import compute_edge_weight
        a = self._node("CE.01", "OIL_SITE_04", equipment=["CHEMICAL_DRUM"])
        b = self._node("CE.01", "OIL_SITE_04", equipment=["REAGENT_TANK"])
        weight, edge_types = compute_edge_weight(a, b)
        assert weight > 0
        assert "ONTOLOGY_MATCH" in edge_types

    def test_different_subtype_no_shared_attrs_no_edge(self):
        from backend.graph.pattern_score import compute_edge_weight
        a = self._node("CE.01", "OIL_SITE_04", equipment=["CHEMICAL_DRUM"], activity=["CHEMICAL_HANDLING"])
        b = self._node("FFH.01", "OIL_SITE_07", equipment=["SCAFFOLD"],     activity=["CONSTRUCTION"])
        weight, edge_types = compute_edge_weight(a, b)
        assert weight == 0.0
        assert edge_types == []

    def test_shared_equipment_creates_edge(self):
        from backend.graph.pattern_score import compute_edge_weight
        a = self._node("CE.01", "OIL_SITE_04", equipment=["CHEMICAL_DRUM", "PUMP"])
        b = self._node("CE.02", "OIL_SITE_07", equipment=["CHEMICAL_DRUM", "VALVE"])
        weight, edge_types = compute_edge_weight(a, b)
        assert weight > 0
        assert "EQUIPMENT_SHARED" in edge_types

    def test_site_temporal_modifier_applied_within_7d(self):
        from backend.graph.pattern_score import compute_edge_weight
        a = self._node("CE.01", "OIL_SITE_04", equipment=["CHEMICAL_DRUM"], days_ago=1)
        b = self._node("CE.01", "OIL_SITE_04", equipment=["CHEMICAL_DRUM"], days_ago=3)
        weight, edge_types = compute_edge_weight(a, b)
        assert "SITE_TEMPORAL_7D" in edge_types
        # Weight should include ontology match + site temporal boost
        assert weight >= 1.5

    def test_site_temporal_not_applied_across_sites(self):
        from backend.graph.pattern_score import compute_edge_weight
        a = self._node("CE.01", "OIL_SITE_04", equipment=["CHEMICAL_DRUM"], days_ago=1)
        b = self._node("CE.01", "OIL_SITE_07", equipment=["CHEMICAL_DRUM"], days_ago=2)
        weight, edge_types = compute_edge_weight(a, b)
        # Has ontology match, but no temporal modifier (different sites)
        assert "SITE_TEMPORAL_7D" not in edge_types
        assert "ONTOLOGY_MATCH" in edge_types

    def test_site_temporal_standalone_cannot_create_edge(self):
        """SITE_TEMPORAL is a modifier only — cannot create an edge by itself."""
        from backend.graph.pattern_score import compute_edge_weight
        a = self._node("CE.01", "OIL_SITE_04", equipment=[], activity=[], days_ago=1)
        b = self._node("FFH.01", "OIL_SITE_04", equipment=[], activity=[], days_ago=2)
        weight, edge_types = compute_edge_weight(a, b)
        # Different subtypes, no shared equipment/activity → no edge at all
        assert weight == 0.0


# ===========================================================================
# State Machine
# ===========================================================================

class TestStateMachine:
    def setup_method(self):
        from backend.graph.pattern_score import determine_risk_state
        self.determine = determine_risk_state

    def test_nominal_stays_nominal_below_threshold(self):
        state = self.determine(pattern_score=0.20, cluster_size=2,
                               has_critical=False, current_state="NOMINAL")
        assert state == "NOMINAL"

    def test_nominal_transitions_to_watch(self):
        state = self.determine(pattern_score=0.40, cluster_size=3,
                               has_critical=False, current_state="NOMINAL")
        assert state == "WATCH"

    def test_watch_transitions_to_elevated(self):
        state = self.determine(pattern_score=0.65, cluster_size=4,
                               has_critical=False, current_state="WATCH")
        assert state == "ELEVATED"

    def test_watch_stays_watch_mid_range(self):
        state = self.determine(pattern_score=0.45, cluster_size=3,
                               has_critical=False, current_state="WATCH")
        assert state == "WATCH"

    def test_elevated_stays_elevated(self):
        state = self.determine(pattern_score=0.70, cluster_size=5,
                               has_critical=False, current_state="ELEVATED")
        assert state == "ELEVATED"

    def test_elevated_decays_to_watch(self):
        state = self.determine(pattern_score=0.40, cluster_size=2,
                               has_critical=False, current_state="ELEVATED")
        assert state == "WATCH"


# ===========================================================================
# Classifier (rule-based fallback)
# ===========================================================================

class TestClassifier:
    def _mapping(self, subtype_id, sif_category, severity, confidence=0.85):
        return {
            "subtype_id":           subtype_id,
            "sif_category":         sif_category,
            "contributing_factors": ["PPE_FAILURE"],
            "equipment_classes":    ["CHEMICAL_DRUM"],
            "activity_contexts":    ["CHEMICAL_HANDLING"],
            "mapping_confidence":   confidence,
            "evidence_span":        "test evidence",
            "severity":             severity,
        }

    def test_returns_required_fields(self):
        from backend.pipeline.classifier import classify_mapping
        result = classify_mapping(self._mapping("CE.01", "CHEMICAL_EXPOSURE", "HIGH"))
        assert "sif_category" in result
        assert "subtype_id" in result
        assert "severity" in result
        assert "classifier_score" in result
        assert "model_version" in result

    def test_severity_valid_value(self):
        from backend.pipeline.classifier import classify_mapping
        for sev in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            result = classify_mapping(self._mapping("CE.01", "CHEMICAL_EXPOSURE", sev))
            assert result["severity"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_score_in_range(self):
        from backend.pipeline.classifier import classify_mapping
        result = classify_mapping(self._mapping("CE.01", "CHEMICAL_EXPOSURE", "HIGH"))
        assert 0.0 <= result["classifier_score"] <= 1.0

    def test_category_preserved_in_fallback(self):
        from backend.pipeline.classifier import classify_mapping, _model_loaded
        if not _model_loaded:
            result = classify_mapping(self._mapping("EF.01", "EXPLOSION_FIRE", "CRITICAL"))
            assert result["sif_category"] == "EXPLOSION_FIRE"

    def test_all_subtypes_classifiable(self):
        from backend.pipeline.classifier import classify_mapping
        subtypes = [
            ("FFH.01","FALL_FROM_HEIGHT"),("CISB.01","CAUGHT_IN_STRUCK_BY"),
            ("EF.01","EXPLOSION_FIRE"),   ("CE.01","CHEMICAL_EXPOSURE"),
            ("ELEC.01","ELECTRICAL"),     ("VT.01","VEHICLE_TRANSPORT"),
        ]
        for sid, cat in subtypes:
            result = classify_mapping(self._mapping(sid, cat, "HIGH"))
            assert result["severity"] in ["LOW","MEDIUM","HIGH","CRITICAL"]


# ===========================================================================
# Ontology Registry
# ===========================================================================

class TestOntologyRegistry:
    def test_registry_loads(self):
        from backend.pipeline.validator import VALID_SUBTYPES, VALID_CATEGORIES
        assert len(VALID_SUBTYPES) == 24
        assert len(VALID_CATEGORIES) == 6

    def test_all_expected_categories_present(self):
        from backend.pipeline.validator import VALID_CATEGORIES
        expected = {
            "FALL_FROM_HEIGHT","CAUGHT_IN_STRUCK_BY","EXPLOSION_FIRE",
            "CHEMICAL_EXPOSURE","ELECTRICAL","VEHICLE_TRANSPORT"
        }
        assert expected == VALID_CATEGORIES

    def test_contributing_factors_complete(self):
        from backend.pipeline.validator import VALID_CONTRIBUTING_FACTORS
        assert {"PPE_FAILURE","PROCEDURE_VIOLATION","EQUIPMENT_FAULT","ENVIRONMENTAL"} == VALID_CONTRIBUTING_FACTORS

    def test_standards_references_returned(self):
        from backend.pipeline.validator import get_standards_references
        refs = get_standards_references("CE.01")
        assert len(refs) == 3
        assert any("ILO" in r for r in refs)
        assert any("OISD" in r for r in refs)
        assert any("OSHA" in r for r in refs)

    def test_standards_references_all_subtypes(self):
        from backend.pipeline.validator import get_standards_references, VALID_SUBTYPES
        for sid in VALID_SUBTYPES:
            refs = get_standards_references(sid)
            assert len(refs) == 3, f"Subtype {sid} should have exactly 3 standards references"

    def test_unknown_subtype_returns_empty(self):
        from backend.pipeline.validator import get_standards_references
        refs = get_standards_references("MADE_UP.99")
        assert refs == []


# ===========================================================================
# PDF Parser
# ===========================================================================

class TestPDFParser:
    def test_invalid_bytes_raises(self):
        from backend.pipeline.pdf_parser import extract_text_from_pdf
        with pytest.raises((ValueError, Exception)):
            extract_text_from_pdf(b"this is not a pdf file at all")

    def test_empty_bytes_raises(self):
        from backend.pipeline.pdf_parser import extract_text_from_pdf
        with pytest.raises(Exception):
            extract_text_from_pdf(b"")


# ===========================================================================
# LLM Extraction — Prompt Builder
# ===========================================================================

class TestLLMPrompt:
    def test_prompt_contains_all_categories(self):
        from backend.pipeline.llm_extraction import build_prompt
        prompt = build_prompt("test incident report text here")
        for cat in ["FALL_FROM_HEIGHT","CAUGHT_IN_STRUCK_BY","EXPLOSION_FIRE",
                    "CHEMICAL_EXPOSURE","ELECTRICAL","VEHICLE_TRANSPORT"]:
            assert cat in prompt

    def test_prompt_contains_all_subtypes(self):
        from backend.pipeline.llm_extraction import build_prompt
        prompt = build_prompt("test incident report text here")
        for sid in ["CE.01","CE.02","CE.03","CE.04","FFH.01","EF.01","ELEC.01","VT.01","CISB.01"]:
            assert sid in prompt

    def test_prompt_contains_contributing_factors(self):
        from backend.pipeline.llm_extraction import build_prompt
        prompt = build_prompt("test")
        for cf in ["PPE_FAILURE","PROCEDURE_VIOLATION","EQUIPMENT_FAULT","ENVIRONMENTAL"]:
            assert cf in prompt

    def test_prompt_contains_severity_criteria(self):
        from backend.pipeline.llm_extraction import build_prompt
        prompt = build_prompt("test")
        for sev in ["LOW","MEDIUM","HIGH","CRITICAL"]:
            assert sev in prompt

    def test_report_text_injected(self):
        from backend.pipeline.llm_extraction import build_prompt
        report = "Worker slipped on wet surface near chemical drum without gloves."
        prompt = build_prompt(report)
        assert report in prompt

    def test_json_extraction_from_raw_response(self):
        from backend.pipeline.llm_extraction import _extract_json_from_response
        # Clean JSON
        raw = '{"abstain": false, "mappings": []}'
        result = _extract_json_from_response(raw)
        assert result == raw

    def test_json_extraction_from_preamble(self):
        from backend.pipeline.llm_extraction import _extract_json_from_response
        raw = 'Here is the JSON response:\n\n{"abstain": false, "mappings": []}'
        result = _extract_json_from_response(raw)
        assert result == '{"abstain": false, "mappings": []}'

    def test_json_extraction_from_markdown(self):
        from backend.pipeline.llm_extraction import _extract_json_from_response
        raw = '```json\n{"abstain": false, "mappings": []}\n```'
        result = _extract_json_from_response(raw)
        assert result == '{"abstain": false, "mappings": []}'

    def test_fallback_returns_valid_structure(self):
        from backend.pipeline.llm_extraction import _rule_based_fallback
        result = _rule_based_fallback(
            "Worker fell from scaffold without harness at 6m elevation."
        )
        assert "abstain" in result
        assert "mappings" in result
        assert len(result["mappings"]) > 0
        m = result["mappings"][0]
        assert "sif_category" in m
        assert "subtype_id" in m
        assert "severity" in m

    def test_fallback_detects_chemical(self):
        from backend.pipeline.llm_extraction import _rule_based_fallback
        result = _rule_based_fallback("PPE failure during chemical handling, ppe gloves not worn.")
        assert result["mappings"][0]["sif_category"] == "CHEMICAL_EXPOSURE"

    def test_fallback_detects_fire(self):
        from backend.pipeline.llm_extraction import _rule_based_fallback
        result = _rule_based_fallback("Fire and explosion risk from hydrocarbon ignition near pump.")
        assert result["mappings"][0]["sif_category"] == "EXPLOSION_FIRE"

    def test_fallback_detects_fall(self):
        from backend.pipeline.llm_extraction import _rule_based_fallback
        result = _rule_based_fallback("Worker fell from ladder at elevated platform.")
        assert result["mappings"][0]["sif_category"] == "FALL_FROM_HEIGHT"


# ===========================================================================
# Temporal Decay
# ===========================================================================

class TestTemporalDecay:
    def test_zero_age_no_decay(self):
        from backend.graph.pattern_score import decayed_weight
        w = decayed_weight(1.0, 0)
        assert abs(w - 1.0) < 1e-6

    def test_60_day_half_life(self):
        from backend.graph.pattern_score import decayed_weight
        w = decayed_weight(1.0, 60)
        assert abs(w - 0.5) < 0.01  # ~0.5 at 60 days

    def test_120_day_quarter_life(self):
        from backend.graph.pattern_score import decayed_weight
        w = decayed_weight(1.0, 120)
        assert abs(w - 0.25) < 0.02  # ~0.25 at 120 days

    def test_decay_monotonically_decreasing(self):
        from backend.graph.pattern_score import decayed_weight
        weights = [decayed_weight(1.0, d) for d in range(0, 181, 30)]
        for i in range(len(weights) - 1):
            assert weights[i] > weights[i+1]
