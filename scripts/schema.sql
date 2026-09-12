-- SIH26165 SIF Precursor Detection System — Full Schema
-- Run this before any application code. Creates all tables for v0 and v1.

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 3.1 Reports
CREATE TABLE IF NOT EXISTS reports (
    report_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id           VARCHAR(50) NOT NULL,
    source            VARCHAR(20) NOT NULL CHECK (source IN ('manual_text', 'pdf_upload', 'flutter_upload')),
    raw_text          TEXT NOT NULL,
    submitted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_by      VARCHAR(100),
    processing_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                      CHECK (processing_status IN ('pending', 'processing', 'mapped', 'classified', 'graphed', 'failed', 'abstained')),
    failure_reason    TEXT,
    osha_report_id    VARCHAR(50),
    text_hash         VARCHAR(64),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_site ON reports(site_id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(processing_status);
CREATE INDEX IF NOT EXISTS idx_reports_hash ON reports(text_hash);

-- 3.2 Ontology Mappings
CREATE TABLE IF NOT EXISTS ontology_mappings (
    mapping_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id            UUID NOT NULL REFERENCES reports(report_id),
    subtype_id           VARCHAR(20) NOT NULL,
    sif_category         VARCHAR(30) NOT NULL,
    contributing_factors VARCHAR(50)[] NOT NULL,
    equipment_classes    VARCHAR(50)[] NOT NULL,
    activity_contexts    VARCHAR(50)[] NOT NULL,
    mapping_confidence   FLOAT NOT NULL CHECK (mapping_confidence BETWEEN 0 AND 1),
    evidence_span        TEXT NOT NULL,
    severity_justification TEXT,
    abstained            BOOLEAN NOT NULL DEFAULT FALSE,
    abstain_reason       TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ontology_mappings_report ON ontology_mappings(report_id);
CREATE INDEX IF NOT EXISTS idx_ontology_mappings_subtype ON ontology_mappings(subtype_id);
CREATE INDEX IF NOT EXISTS idx_ontology_mappings_category ON ontology_mappings(sif_category);

-- 3.3 Classifications
CREATE TABLE IF NOT EXISTS classifications (
    classification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id         UUID NOT NULL REFERENCES reports(report_id),
    sif_category      VARCHAR(30) NOT NULL,
    subtype_id        VARCHAR(20) NOT NULL,
    severity          VARCHAR(10) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    classifier_score  FLOAT NOT NULL,
    model_version     VARCHAR(20) NOT NULL,
    classified_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_classifications_report ON classifications(report_id);
CREATE INDEX IF NOT EXISTS idx_classifications_category ON classifications(sif_category);
CREATE INDEX IF NOT EXISTS idx_classifications_severity ON classifications(severity);

-- 3.4 Graph Nodes and Edges (v1 — created now, used in v1)
CREATE TABLE IF NOT EXISTS graph_nodes (
    node_id    UUID PRIMARY KEY,
    site_id    VARCHAR(50) NOT NULL,
    subtype_id VARCHAR(20) NOT NULL,
    severity   VARCHAR(10) NOT NULL,
    timestamp  TIMESTAMPTZ NOT NULL,
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS graph_edges (
    edge_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node    UUID NOT NULL REFERENCES graph_nodes(node_id),
    target_node    UUID NOT NULL REFERENCES graph_nodes(node_id),
    edge_types     VARCHAR(30)[] NOT NULL,
    base_weight    FLOAT NOT NULL,
    site_modifier  FLOAT NOT NULL DEFAULT 0.0,
    current_weight FLOAT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_node);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_node);

-- 3.5 Clusters
CREATE TABLE IF NOT EXISTS clusters (
    cluster_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id       VARCHAR(50),
    sif_category  VARCHAR(30) NOT NULL,
    subtype_id    VARCHAR(20),
    report_ids    UUID[] NOT NULL,
    pattern_score FLOAT NOT NULL,
    risk_state    VARCHAR(10) NOT NULL CHECK (risk_state IN ('NOMINAL', 'WATCH', 'ELEVATED', 'CRITICAL')),
    first_seen    TIMESTAMPTZ NOT NULL,
    last_updated  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_clusters_site ON clusters(site_id);
CREATE INDEX IF NOT EXISTS idx_clusters_state ON clusters(risk_state);
CREATE INDEX IF NOT EXISTS idx_clusters_category ON clusters(sif_category);

-- 3.6 Site Risk States
CREATE TABLE IF NOT EXISTS site_risk_states (
    site_id           VARCHAR(50) PRIMARY KEY,
    current_state     VARCHAR(10) NOT NULL DEFAULT 'NOMINAL'
                      CHECK (current_state IN ('NOMINAL', 'WATCH', 'ELEVATED', 'CRITICAL')),
    dominant_category VARCHAR(30),
    dominant_cluster  UUID REFERENCES clusters(cluster_id),
    state_entered_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    baseline_velocity FLOAT NOT NULL DEFAULT 0.5
);

-- 3.7 Alerts
CREATE TABLE IF NOT EXISTS alerts (
    alert_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id    UUID NOT NULL REFERENCES clusters(cluster_id),
    site_id       VARCHAR(50) NOT NULL,
    alert_type    VARCHAR(20) NOT NULL CHECK (alert_type IN ('STATE_TRANSITION', 'VELOCITY_SPIKE', 'CRITICAL_JOIN')),
    from_state    VARCHAR(10),
    to_state      VARCHAR(10) NOT NULL,
    pattern_score FLOAT NOT NULL,
    message       TEXT NOT NULL,
    delivered     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3.8 Validation Failures
CREATE TABLE IF NOT EXISTS validation_failures (
    failure_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id      UUID REFERENCES reports(report_id),
    gate           VARCHAR(10) NOT NULL CHECK (gate IN ('GATE_1', 'GATE_2', 'GATE_3')),
    failure_reason TEXT NOT NULL,
    raw_input      TEXT,
    site_id        VARCHAR(50),
    submitted_by   VARCHAR(100),
    failed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_validation_failures_gate ON validation_failures(gate);
CREATE INDEX IF NOT EXISTS idx_validation_failures_site ON validation_failures(site_id);

-- Seed site registry (known sites)
INSERT INTO site_risk_states (site_id, current_state, baseline_velocity) VALUES
    ('OIL_SITE_02',  'NOMINAL', 0.5),
    ('OIL_SITE_04',  'NOMINAL', 0.5),
    ('OIL_SITE_07',  'NOMINAL', 0.5),
    ('OIL_SITE_11',  'NOMINAL', 0.5),
    ('OIL_SITE_15',  'NOMINAL', 0.5)
ON CONFLICT (site_id) DO NOTHING;

-- Done
SELECT 'Schema created successfully' AS status;
