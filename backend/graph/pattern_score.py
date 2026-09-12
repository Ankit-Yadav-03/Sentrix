"""
Component 6: Pattern Score Engine
All 5 components from Architecture doc Sections 10.1 and 10.2.
For v0: operates on DB query results, no NetworkX dependency.
For v1: NetworkX subgraph is passed in.

Architecture doc Section 9.1:
Pattern Score = w1*Density + w2*EdgeStrength + w3*Velocity + w4*Severity + w5*Concentration
"""

import math
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weights (Architecture doc Section 9.1)
# ---------------------------------------------------------------------------

PATTERN_WEIGHTS = {
    "density":        0.25,
    "edge":           0.20,
    "velocity":       0.20,
    "severity":       0.20,
    "concentration":  0.15,
}

# ---------------------------------------------------------------------------
# Severity mappings (Architecture doc Section 9.2)
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {
    "LOW":      0.1,
    "MEDIUM":   0.3,
    "HIGH":     0.6,
    "CRITICAL": 1.0,   # nonlinear — disproportionate influence (AD-06)
}

# ---------------------------------------------------------------------------
# Temporal decay (Architecture doc Section 8.6)
# ---------------------------------------------------------------------------

DECAY_HALF_LIFE_DAYS: float = 60.0  # configurable per deployment


def decayed_weight(base_weight: float, age_days: float) -> float:
    """Exponential decay. 60-day half-life."""
    lambda_decay = math.log(2) / DECAY_HALF_LIFE_DAYS
    return base_weight * math.exp(-lambda_decay * age_days)


# ---------------------------------------------------------------------------
# Edge weight computation (Architecture doc Section 8.3)
# ---------------------------------------------------------------------------

def compute_edge_weight(node_a: dict, node_b: dict) -> tuple[float, list[str]]:
    """
    Computes composite edge weight between two report nodes.
    SITE_TEMPORAL is a modifier only — never creates standalone edge.
    Returns (weight, edge_types). Weight 0.0 means no edge created.
    """
    edge_types = []
    base_weight = 0.0

    # ONTOLOGY_MATCH — same subtype
    if node_a.get("subtype_id") == node_b.get("subtype_id"):
        edge_types.append("ONTOLOGY_MATCH")
        base_weight += 1.0

    # EQUIPMENT_SHARED — non-empty intersection
    eq_a = set(node_a.get("equipment_classes", []))
    eq_b = set(node_b.get("equipment_classes", []))
    if eq_a & eq_b:
        edge_types.append("EQUIPMENT_SHARED")
        base_weight += 0.7

    # ACTIVITY_SHARED — non-empty intersection
    ac_a = set(node_a.get("activity_contexts", []))
    ac_b = set(node_b.get("activity_contexts", []))
    if ac_a & ac_b:
        edge_types.append("ACTIVITY_SHARED")
        base_weight += 0.6

    # No qualifying edge → no edge created (SITE_TEMPORAL cannot create standalone)
    if base_weight == 0.0:
        return 0.0, []

    # SITE_TEMPORAL modifier — only applied when qualifying edge exists
    site_modifier = 0.0
    if node_a.get("site_id") == node_b.get("site_id"):
        ts_a = node_a.get("timestamp")
        ts_b = node_b.get("timestamp")
        if ts_a and ts_b:
            delta_days = abs((ts_a - ts_b).days)
            if delta_days <= 7:
                edge_types.append("SITE_TEMPORAL_7D")
                site_modifier = 0.5
            elif delta_days <= 30:
                edge_types.append("SITE_TEMPORAL_30D")
                site_modifier = 0.3

    return base_weight + site_modifier, edge_types


# ---------------------------------------------------------------------------
# Component 1: Density
# ---------------------------------------------------------------------------

def compute_density(nodes: list[dict], edges: list[dict]) -> float:
    """
    Graph density = actual_edges / max_possible_edges.
    For v0: edges computed from node pairs directly.
    """
    n = len(nodes)
    if n < 2:
        return 0.0
    actual_edges = len(edges)
    max_edges = n * (n - 1) / 2
    return actual_edges / max_edges if max_edges > 0 else 0.0


# ---------------------------------------------------------------------------
# Component 2: Edge Strength
# ---------------------------------------------------------------------------

def compute_edge_strength(edges: list[dict], current_time: datetime) -> float:
    """
    Sum of decayed edge weights, normalized to [0,1].
    Max possible weight per edge = 1.0 + 0.7 + 0.6 + 0.5 = 2.8 (all types + 7D temporal).
    Architecture uses 2.3 as practical maximum.
    """
    if not edges:
        return 0.0

    total = 0.0
    for edge in edges:
        created_at = edge.get("created_at", current_time)
        if isinstance(created_at, str):
            from datetime import datetime, timezone
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        # Ensure both are aware UTC before subtraction
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        age_days = max((current_time - created_at).days, 0)
        weight = edge.get("current_weight", edge.get("base_weight", 1.0))
        total += decayed_weight(weight, age_days)

    max_possible = len(edges) * 2.3
    return min(total / max_possible, 1.0) if max_possible > 0 else 0.0


# ---------------------------------------------------------------------------
# Component 3: Velocity
# ---------------------------------------------------------------------------

def compute_velocity(cluster_reports: list[dict], site_id: str, window_days: int,
                     baseline_velocity: float = 0.5) -> float:
    """
    Recent report rate vs site baseline.
    Architecture doc Section 9.2: Velocity.
    """
    now = datetime.now(timezone.utc)
    recent_count = sum(
        1 for r in cluster_reports
        if (now - _get_ts(r)).days <= 2
    )

    current_rate = recent_count / 2.0  # reports/day over last 48h

    if baseline_velocity > 0:
        velocity_multiplier = current_rate / baseline_velocity
        return min(velocity_multiplier / 5.0, 1.0)  # 5× baseline = 1.0
    else:
        # MVP fallback: 3 in 48h = 1.0
        return min(recent_count / 3.0, 1.0)


# ---------------------------------------------------------------------------
# Component 4: Severity (nonlinear, AD-06)
# ---------------------------------------------------------------------------

def compute_severity(cluster_reports: list[dict]) -> float:
    """
    Nonlinear severity score. CRITICAL has disproportionate influence.
    Uses max + mean combination — CRITICAL pulls score up significantly.
    """
    if not cluster_reports:
        return 0.0

    scores = [SEVERITY_WEIGHTS.get(r.get("severity", "MEDIUM"), 0.3)
              for r in cluster_reports]

    # 60% max + 40% mean — CRITICAL (1.0) dominates
    return 0.6 * max(scores) + 0.4 * (sum(scores) / len(scores))


# ---------------------------------------------------------------------------
# Component 5: Concentration (AD-07)
# ---------------------------------------------------------------------------

def compute_concentration(cluster_reports: list[dict]) -> float:
    """
    How focused the cluster is: 10 reports at same site/activity/equipment → 1.0.
    10 reports across 10 sites → low score.
    Architecture doc Section 9.2: Concentration.
    """
    n = len(cluster_reports)
    if n == 0:
        return 0.0

    sites = [r.get("site_id", "") for r in cluster_reports]
    activities = [a for r in cluster_reports for a in r.get("activity_contexts", [])]
    equipment  = [e for r in cluster_reports for e in r.get("equipment_classes", [])]

    site_concentration = max(Counter(sites).values()) / n if sites else 0.0

    activity_concentration = (
        max(Counter(activities).values()) / len(activities)
        if activities else 0.0
    )
    equipment_concentration = (
        max(Counter(equipment).values()) / len(equipment)
        if equipment else 0.0
    )

    return (
        0.5 * site_concentration
        + 0.3 * activity_concentration
        + 0.2 * equipment_concentration
    )


# ---------------------------------------------------------------------------
# Master: compute_pattern_score
# ---------------------------------------------------------------------------

def compute_pattern_score(
    cluster_reports: list[dict],
    site_id: str,
    window_days: int,
    baseline_velocity: float = 0.5,
    current_time: Optional[datetime] = None,
) -> dict:
    """
    Compute full Pattern Score and all 5 components.

    cluster_reports: list of dicts with keys:
        report_id, site_id, severity, equipment_classes, activity_contexts,
        subtype_id, timestamp

    Returns dict with pattern_score and score_components.
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    # Build edge list from all pairs of cluster reports
    edges = _build_edges(cluster_reports, current_time)

    # Compute all components
    density       = compute_density(cluster_reports, edges)
    edge_strength = compute_edge_strength(edges, current_time)
    velocity      = compute_velocity(cluster_reports, site_id, window_days, baseline_velocity)
    severity      = compute_severity(cluster_reports)
    concentration = compute_concentration(cluster_reports)

    # Weighted sum
    score = (
        PATTERN_WEIGHTS["density"]       * density
        + PATTERN_WEIGHTS["edge"]        * edge_strength
        + PATTERN_WEIGHTS["velocity"]    * velocity
        + PATTERN_WEIGHTS["severity"]    * severity
        + PATTERN_WEIGHTS["concentration"] * concentration
    )
    score = min(max(score, 0.0), 1.0)

    return {
        "pattern_score": round(score, 4),
        "score_components": {
            "density":       round(density, 4),
            "edge_strength": round(edge_strength, 4),
            "velocity":      round(velocity, 4),
            "severity":      round(severity, 4),
            "concentration": round(concentration, 4),
        },
        "edge_count": len(edges),
        "report_count": len(cluster_reports),
    }


# ---------------------------------------------------------------------------
# DB-backed computation for v0
# ---------------------------------------------------------------------------

def compute_site_cluster_score(
    session,
    site_id: str,
    subtype_id: str,
    window_days: int,
    baseline_velocity: float = 0.5,
) -> dict:
    """
    Load cluster reports from DB and compute Pattern Score.
    Used in v0 where NetworkX graph is not wired.
    """
    from backend.models.db import Report, OntologyMapping, Classification

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    # Join reports + mappings + classifications for this site+subtype+window
    rows = (
        session.query(Report, OntologyMapping, Classification)
        .join(OntologyMapping, OntologyMapping.report_id == Report.report_id)
        .join(Classification, Classification.report_id == Report.report_id)
        .filter(
            Report.site_id == site_id,
            OntologyMapping.subtype_id == subtype_id,
            Report.submitted_at >= cutoff,
            Report.processing_status.in_(["classified", "graphed"]),
        )
        .all()
    )

    cluster_reports = []
    for report, mapping, classification in rows:
        cluster_reports.append({
            "report_id":         str(report.report_id),
            "osha_report_id":    report.osha_report_id,
            "site_id":           report.site_id,
            "severity":          classification.severity,
            "equipment_classes": mapping.equipment_classes or [],
            "activity_contexts": mapping.activity_contexts or [],
            "subtype_id":        mapping.subtype_id,
            "sif_category":      mapping.sif_category,
            "timestamp":         report.submitted_at,
            "evidence_span":     mapping.evidence_span,
            "submitted_at":      report.submitted_at.isoformat() if report.submitted_at else None,
        })

    # Deduplicate by report_id
    seen = set()
    unique_reports = []
    for r in cluster_reports:
        if r["report_id"] not in seen:
            seen.add(r["report_id"])
            unique_reports.append(r)

    result = compute_pattern_score(
        cluster_reports=unique_reports,
        site_id=site_id,
        window_days=window_days,
        baseline_velocity=baseline_velocity,
        current_time=now,
    )
    result["cluster_reports"] = unique_reports
    return result


# ---------------------------------------------------------------------------
# State determination
# ---------------------------------------------------------------------------

T_WATCH    = 0.35
T_ELEVATED = 0.60

def determine_risk_state(pattern_score: float, cluster_size: int,
                          has_critical: bool, current_state: str = "NOMINAL") -> str:
    """
    Apply state machine rules from Architecture doc Section 9.3.
    Returns new state string.
    """
    score = pattern_score

    if current_state == "NOMINAL":
        if score >= T_WATCH and cluster_size >= 3:
            return "WATCH"
        return "NOMINAL"

    elif current_state == "WATCH":
        if score >= T_ELEVATED or has_critical:
            return "ELEVATED"
        elif score < T_WATCH * 0.9:  # decay below threshold
            return "NOMINAL"
        return "WATCH"

    elif current_state == "ELEVATED":
        if score < T_ELEVATED * 0.9:
            return "WATCH"
        return "ELEVATED"

    elif current_state == "CRITICAL":
        if score < T_ELEVATED * 0.9:
            return "ELEVATED"
        return "CRITICAL"

    return "NOMINAL"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ts(report: dict) -> datetime:
    """Extract timestamp from report dict, always returns timezone-aware UTC datetime."""
    ts = report.get("timestamp") or report.get("submitted_at")
    if ts is None:
        return datetime.now(timezone.utc)
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if isinstance(ts, str):
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _build_edges(cluster_reports: list[dict], current_time: datetime) -> list[dict]:
    """
    Build edge list from all qualifying report pairs.
    Minimum edge threshold: 0.7 (Architecture doc Section 8.4).
    """
    edges = []
    n = len(cluster_reports)
    for i in range(n):
        for j in range(i + 1, n):
            a = cluster_reports[i]
            b = cluster_reports[j]
            weight, edge_types = compute_edge_weight(a, b)
            if weight >= 0.7:
                edges.append({
                    "source": a["report_id"],
                    "target": b["report_id"],
                    "current_weight": weight,
                    "base_weight": weight,
                    "edge_types": edge_types,
                    "created_at": min(_get_ts(a), _get_ts(b)),
                })
    return edges
