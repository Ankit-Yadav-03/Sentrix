import { useState } from "react";
import Head from "next/head";
import Link from "next/link";
import Navbar from "../components/Navbar";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SITES = ["OIL_SITE_02","OIL_SITE_04","OIL_SITE_07","OIL_SITE_11","OIL_SITE_15"];

const DEMO_REPORTS = [
  {
    label: "Chemical Exposure — CE.04",
    siteId: "OIL_SITE_04",
    text: `During routine valve maintenance, operator contacted sodium hydroxide solution when relief valve discharged unexpectedly without PPE change-out between tasks. The operator was not wearing the mandatory chemical resistant gloves specified in the chemical handling procedure SOP-CHEM-007. The operator immediately moved to the emergency eyewash and shower station located 8 meters away and flushed the affected area for 15 minutes. No injury was sustained due to prompt first aid, but direct skin contact with acid occurred.

Contributing Factors:
1. PPE non-compliance: Operator failed to wear chemical-resistant nitrile gloves as required by procedure. Gloves were available at the station but not used due to perceived inconvenience.
2. Procedure violation: The chemical handling procedure SOP-CHEM-007 requires full PPE including face shield, gloves, and apron for any valve operations on acid injection lines.
3. Equipment condition: Valve packing on the acid injection line was deteriorated. Maintenance work order MW-4456 had been raised 6 days prior but not actioned.

Equipment involved: Chemical drum manifold, acid injection valve, chemical injection line, emergency eyewash station.`
  },
  {
    label: "Fall from Height — FFH.02",
    siteId: "OIL_SITE_07",
    text: `Worker ascended scaffold without attaching lanyard to the horizontal lifeline. Scaffold was at 4.2 meters elevation during tank inspection. No observer was stationed at ground level.

Contributing Factors:
1. PPE Failure: Worker did not attach fall arrest lanyard to the horizontal lifeline as required by site procedure SAFE-012.
2. Procedure Violation: No safety observer was stationed at ground level during elevated work above 2 meters.
3. Equipment: Scaffold was properly erected and tagged, but fall protection system was not utilized.

Equipment involved: SCAFFOLD, TANK_TOP, HORIZONTAL_LIFELINE
Activity contexts: INSPECTION, MAINTENANCE`
  },
  {
    label: "Explosion / Fire — EF.04",
    siteId: "OIL_SITE_02",
    text: `Hot work permit issued 2 hours prior had expired before job restart after lunch break. Gas test was not repeated before welding resumed on the crude transfer line. Sparks from welding landed near flange connection with residual hydrocarbon vapor.

Contributing Factors:
1. Procedure Violation: Hot work permit expired and was not renewed. Gas testing was not repeated before resuming hot work after break.
2. Equipment: Crude transfer line had residual hydrocarbon vapor in flange area.
3. Environmental: Wind direction shifted during lunch break, potentially carrying vapor toward ignition source.

Equipment involved: PIPELINE, PRESSURE_VESSEL, WELDING_EQUIPMENT
Activity contexts: WELDING, HOT_WORK, MAINTENANCE`
  }
];

const SEV_COLORS = {
  LOW: "bg-low-sev-bg text-low-sev-text border-low-sev-bg",
  MEDIUM: "bg-medium-sev-bg text-medium-sev-text border-medium-sev-bg",
  HIGH: "bg-high-sev-bg text-high-sev-text border-high-sev-bg",
  CRITICAL: "bg-critical-sev-bg text-critical-sev-text border-critical-sev-bg font-bold",
};
const STATE_COLORS = {
  NOMINAL: "bg-nominal-badge-bg text-nominal-green",
  WATCH: "bg-watch-badge-bg text-watch-yellow",
  ELEVATED: "bg-elevated-badge-bg text-elevated-orange",
  CRITICAL: "bg-critical-badge-bg text-critical-red font-bold",
};

function ScoreBar({ label, value }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-36 text-xs text-text-secondary">{label}</span>
      <div className="flex-1 progress-bar">
        <div className="progress-fill bg-accent-orange transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-text-secondary w-8 text-right">{value?.toFixed(3)}</span>
    </div>
  );
}

function ResultPanel({ result }) {
  if (!result) return null;
  const { abstained, abstain_reason, sif_category, subtype_id, severity,
          classifier_score, model_version, mappings, cluster, site_risk_state } = result;

  return (
    <div className="space-y-4 mt-6">
      {abstained ? (
        <div className="card border-amber-500/30 bg-amber-900/10 p-4">
          <p className="font-semibold text-amber-400">LLM Abstained</p>
          <p className="text-amber-300 text-sm mt-1">{abstain_reason}</p>
          <p className="text-amber-300/80 text-xs mt-2">
            The model could not find sufficient evidence to classify this report.
            Please provide more specific details about the incident.
          </p>
        </div>
      ) : (
        <>
          {/* Primary classification */}
          <div className="card p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">Classification Result</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-text-secondary">SIF Category</p>
                <p className="font-semibold text-text-primary">{sif_category?.replace(/_/g," ")}</p>
              </div>
              <div>
                <p className="text-xs text-text-secondary">Subtype</p>
                <p className="font-mono text-accent-orange font-semibold">{subtype_id}</p>
              </div>
              <div>
                <p className="text-xs text-text-secondary">Severity</p>
                <span className={`inline-block px-2 py-0.5 rounded border text-xs font-medium ${SEV_COLORS[severity]}`}>
                  {severity}
                </span>
              </div>
              <div>
                <p className="text-xs text-text-secondary">Classifier Score</p>
                <p className="font-semibold text-text-primary">{classifier_score?.toFixed(4)}</p>
              </div>
              <div className="col-span-2">
                <p className="text-xs text-text-secondary">Model Version</p>
                <p className="text-xs text-text-secondary font-mono">{model_version}</p>
              </div>
            </div>
          </div>

          {/* Mappings */}
          {mappings?.map((m, i) => (
            <div key={i} className="card p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">
                Ontology Mapping {mappings.length > 1 ? `#${i+1}` : ""} — {m.subtype_id}
              </h3>
              <div className="space-y-2.5 text-sm">
                <div>
                  <span className="text-xs text-text-secondary block mb-0.5">Evidence Span</span>
                  <blockquote className="card border-l-4 border-accent-orange pl-3 py-1.5 text-text-primary text-xs italic rounded-r">
                    {m.evidence_span}
                  </blockquote>
                </div>
                <div>
                  <span className="text-xs text-text-secondary block mb-1">Contributing Factors</span>
                  <div className="flex flex-wrap gap-1">
                    {m.contributing_factors?.map(f => (
                      <span key={f} className="px-2 py-0.5 bg-purple-900/30 text-purple-300 rounded text-xs">{f}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-xs text-text-secondary block mb-1">Equipment Classes</span>
                  <div className="flex flex-wrap gap-1">
                    {m.equipment_classes?.map(e => (
                      <span key={e} className="px-2 py-0.5 bg-border text-text-secondary rounded text-xs font-mono">{e}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-xs text-text-secondary block mb-1">Activity Contexts</span>
                  <div className="flex flex-wrap gap-1">
                    {m.activity_contexts?.map(a => (
                      <span key={a} className="px-2 py-0.5 bg-green-900/30 text-green-300 rounded text-xs">{a}</span>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-xs text-text-secondary">Confidence</span>
                    <div className="flex items-center gap-2 mt-0.5">
                      <div className="flex-1 progress-bar">
                        <div className="progress-fill bg-accent-orange"
                          style={{width: `${(m.mapping_confidence * 100).toFixed(0)}%`}} />
                      </div>
                      <span className="text-xs text-text-secondary">{m.mapping_confidence?.toFixed(2)}</span>
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-text-secondary">Severity</span>
                    <span className={`inline-block mt-0.5 px-2 py-0.5 rounded border text-xs font-medium ${SEV_COLORS[m.severity]}`}>
                      {m.severity}
                    </span>
                  </div>
                </div>
                {m.severity_justification && (
                  <div>
                    <span className="text-xs text-text-secondary block mb-0.5">Severity Justification</span>
                    <p className="text-xs text-text-secondary">{m.severity_justification}</p>
                  </div>
                )}
                {m.standards_references?.length > 0 && (
                  <div>
                    <span className="text-xs text-text-secondary block mb-1">Standards References</span>
                    <ul className="space-y-0.5">
                      {m.standards_references.map((ref, ri) => (
                        <li key={ri} className="text-xs text-text-secondary flex gap-1.5">
                          <span className="text-accent-orange">›</span>{ref}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Cluster & Pattern Score */}
          {cluster && (
            <div className="card p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">Cluster Update</h3>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div>
                  <p className="text-xs text-text-secondary">Pattern Score</p>
                  <p className="text-2xl font-bold text-text-primary">{cluster.pattern_score?.toFixed(3)}</p>
                </div>
                <div>
                  <p className="text-xs text-text-secondary">Risk State</p>
                  <span className={`inline-block mt-0.5 px-3 py-1 rounded font-semibold text-sm ${STATE_COLORS[cluster.risk_state]}`}>
                    {cluster.risk_state}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-text-secondary">Cluster Size</p>
                  <p className="text-2xl font-bold text-text-primary">{cluster.cluster_size}</p>
                </div>
              </div>
              {cluster.score_components && (
                <div className="space-y-1.5">
                  <p className="text-xs text-text-secondary mb-2 font-medium">Score Components</p>
                  <ScoreBar label="Density"       value={cluster.score_components.density} />
                  <ScoreBar label="Edge Strength" value={cluster.score_components.edge_strength} />
                  <ScoreBar label="Velocity"      value={cluster.score_components.velocity} />
                  <ScoreBar label="Severity"      value={cluster.score_components.severity} />
                  <ScoreBar label="Concentration" value={cluster.score_components.concentration} />
                </div>
              )}
              {cluster.new_cluster && (
                <p className="text-xs text-accent-orange mt-3 font-medium">✦ New cluster created</p>
              )}
              {cluster.risk_state !== "NOMINAL" && (
                <p className={`text-xs mt-2 font-semibold ${cluster.risk_state === "ELEVATED" ? "text-elevated-orange" : "text-critical-red"}`}>
                  ⚠ Site risk state: {site_risk_state}
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function Submit() {
  const [tab, setTab]           = useState("text");
  const [siteId, setSiteId]     = useState(SITES[0]);
  const [text, setText]         = useState("");
  const [submitter, setSubmitter] = useState("");
  const [file, setFile]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState(null);
  const [error, setError]       = useState(null);

  async function handleTextSubmit(e) {
    e.preventDefault();
    setLoading(true); setResult(null); setError(null);
    try {
      const res = await fetch(`${API}/submit/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site_id: siteId, raw_text: text, source: "manual_text", submitted_by: submitter }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Submission failed");
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handlePdfSubmit(e) {
    e.preventDefault();
    if (!file) return;
    setLoading(true); setResult(null); setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("site_id", siteId);
      if (submitter) fd.append("submitted_by", submitter);
      const res = await fetch(`${API}/submit/pdf`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "PDF submission failed");
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function loadDemo(demo) {
    setText(demo.text);
    setSiteId(demo.siteId);
    setResult(null);
    setError(null);
  }

  return (
    <>
      <Head><title>Submit Report — SIF Detection</title></Head>
      <div className="min-h-screen">

        <Navbar />

        <main className="max-w-3xl mx-auto px-6 py-8">
          <div className="card shadow-lg">
            {/* Tabs */}
            <div className="flex border-b divide-border">
              {["text","pdf"].map(t => (
                <button key={t} onClick={() => { setTab(t); setResult(null); setError(null); }}
                  className={`px-6 py-3 text-sm font-medium ${tab===t
                    ? "border-b-2 border-accent-orange text-accent-orange"
                    : "text-text-secondary hover:text-text-primary"}`}>
                  {t === "text" ? "📝 Text Report" : "📄 PDF Upload"}
                </button>
              ))}
            </div>

            <div className="p-6">
              {/* Demo preload buttons */}
              <div className="mb-5">
                <p className="text-xs text-text-secondary mb-2 font-medium">Quick Load Demo Reports:</p>
                <div className="flex flex-wrap gap-2">
                  {DEMO_REPORTS.map((demo, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => loadDemo(demo)}
                      className="px-3 py-1.5 text-xs font-medium bg-bg-primary border border-border rounded hover:bg-bg-secondary hover:border-accent-orange/50 transition-colors"
                    >
                      {demo.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Common: site select + submitter */}
              <div className="grid grid-cols-2 gap-4 mb-5">
                <div>
                  <label className="label">Site ID *</label>
                  <select value={siteId} onChange={e => setSiteId(e.target.value)}
                    className="input">
                    {SITES.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Submitted By</label>
                  <input value={submitter} onChange={e => setSubmitter(e.target.value)}
                    placeholder="Name or employee ID"
                    className="input" />
                </div>
              </div>

              {tab === "text" ? (
                <form onSubmit={handleTextSubmit}>
                  <label className="label">
                    Incident Description * <span className="font-normal text-text-secondary">(min. 50 chars)</span>
                  </label>
                  <textarea
                    value={text} onChange={e => setText(e.target.value)}
                    rows={10} required
                    placeholder="Describe the near-miss or unsafe condition in detail. Include: what happened, equipment involved, activity being performed, contributing factors, and personnel involved..."
                    className="input font-mono resize-none"
                  />
                  <p className="text-xs text-text-secondary mt-1">{text.length} characters</p>
                  <button type="submit" disabled={loading || text.length < 50}
                    className="btn-primary mt-4">
                    {loading ? "⏳ Analysing…" : "Submit Report →"}
                  </button>
                </form>
              ) : (
                <form onSubmit={handlePdfSubmit}>
                  <label className="label">PDF File *</label>
                  <div className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-accent-orange/50 transition-colors">
                    <input type="file" accept=".pdf" onChange={e => setFile(e.target.files[0])}
                      className="hidden" id="pdf-input" required />
                    <label htmlFor="pdf-input" className="cursor-pointer">
                      <p className="text-4xl mb-2">📄</p>
                      <p className="text-sm text-text-secondary">
                        {file ? file.name : "Click to choose PDF or drag & drop"}
                      </p>
                      <p className="text-xs text-text-secondary mt-1">Max 10MB · PDF only</p>
                    </label>
                  </div>
                  <button type="submit" disabled={loading || !file}
                    className="btn-primary mt-4">
                    {loading ? "⏳ Extracting & Analysing…" : "Upload & Analyse →"}
                  </button>
                </form>
              )}

              {/* Error */}
              {error && (
                <div className="mt-4 card border-critical-red/30 bg-critical-badge-bg/10 p-4">
                  <p className="text-critical-red text-sm font-medium">Submission failed</p>
                  <p className="text-critical-red/80 text-xs mt-1">{error}</p>
                </div>
              )}

              {/* Result */}
              <ResultPanel result={result} />
            </div>
          </div>
        </main>
      </div>
    </>
  );
}