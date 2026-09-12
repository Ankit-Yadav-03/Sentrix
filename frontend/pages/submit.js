import { useState } from "react";
import Head from "next/head";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SITES = ["OIL_SITE_02","OIL_SITE_04","OIL_SITE_07","OIL_SITE_11","OIL_SITE_15"];

const SEV_COLORS = {
  LOW: "bg-blue-50 text-blue-700 border-blue-200",
  MEDIUM: "bg-yellow-50 text-yellow-700 border-yellow-200",
  HIGH: "bg-orange-50 text-orange-700 border-orange-200",
  CRITICAL: "bg-red-50 text-red-700 border-red-300 font-bold",
};
const STATE_COLORS = {
  NOMINAL: "bg-green-50 text-green-700",
  WATCH: "bg-yellow-50 text-yellow-700",
  ELEVATED: "bg-orange-50 text-orange-700",
  CRITICAL: "bg-red-50 text-red-700 font-bold",
};

function ScoreBar({ label, value }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-36 text-xs text-gray-600">{label}</span>
      <div className="flex-1 bg-gray-100 rounded h-2">
        <div className="bg-blue-500 h-2 rounded transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{value?.toFixed(3)}</span>
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
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4">
          <p className="font-semibold text-amber-800">LLM Abstained</p>
          <p className="text-amber-700 text-sm mt-1">{abstain_reason}</p>
          <p className="text-amber-600 text-xs mt-2">
            The model could not find sufficient evidence to classify this report.
            Please provide more specific details about the incident.
          </p>
        </div>
      ) : (
        <>
          {/* Primary classification */}
          <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Classification Result</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-gray-500">SIF Category</p>
                <p className="font-semibold text-gray-800">{sif_category?.replace(/_/g," ")}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Subtype</p>
                <p className="font-mono text-blue-600 font-semibold">{subtype_id}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Severity</p>
                <span className={`inline-block px-2 py-0.5 rounded border text-xs font-medium ${SEV_COLORS[severity]}`}>
                  {severity}
                </span>
              </div>
              <div>
                <p className="text-xs text-gray-500">Classifier Score</p>
                <p className="font-semibold text-gray-800">{classifier_score?.toFixed(4)}</p>
              </div>
              <div className="col-span-2">
                <p className="text-xs text-gray-500">Model Version</p>
                <p className="text-xs text-gray-600 font-mono">{model_version}</p>
              </div>
            </div>
          </div>

          {/* Mappings */}
          {mappings?.map((m, i) => (
            <div key={i} className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Ontology Mapping {mappings.length > 1 ? `#${i+1}` : ""} — {m.subtype_id}
              </h3>
              <div className="space-y-2.5 text-sm">
                <div>
                  <span className="text-xs text-gray-500 block mb-0.5">Evidence Span</span>
                  <blockquote className="bg-gray-50 border-l-4 border-blue-300 pl-3 py-1.5 text-gray-700 text-xs italic rounded-r">
                    {m.evidence_span}
                  </blockquote>
                </div>
                <div>
                  <span className="text-xs text-gray-500 block mb-1">Contributing Factors</span>
                  <div className="flex flex-wrap gap-1">
                    {m.contributing_factors?.map(f => (
                      <span key={f} className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">{f}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-xs text-gray-500 block mb-1">Equipment Classes</span>
                  <div className="flex flex-wrap gap-1">
                    {m.equipment_classes?.map(e => (
                      <span key={e} className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-mono">{e}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-xs text-gray-500 block mb-1">Activity Contexts</span>
                  <div className="flex flex-wrap gap-1">
                    {m.activity_contexts?.map(a => (
                      <span key={a} className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">{a}</span>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-xs text-gray-500">Confidence</span>
                    <div className="flex items-center gap-2 mt-0.5">
                      <div className="flex-1 bg-gray-100 rounded h-1.5">
                        <div className="bg-blue-400 h-1.5 rounded"
                          style={{width: `${(m.mapping_confidence * 100).toFixed(0)}%`}} />
                      </div>
                      <span className="text-xs text-gray-600">{m.mapping_confidence?.toFixed(2)}</span>
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-gray-500">Severity</span>
                    <span className={`inline-block mt-0.5 px-2 py-0.5 rounded border text-xs font-medium ${SEV_COLORS[m.severity]}`}>
                      {m.severity}
                    </span>
                  </div>
                </div>
                {m.severity_justification && (
                  <div>
                    <span className="text-xs text-gray-500 block mb-0.5">Severity Justification</span>
                    <p className="text-xs text-gray-600">{m.severity_justification}</p>
                  </div>
                )}
                {m.standards_references?.length > 0 && (
                  <div>
                    <span className="text-xs text-gray-500 block mb-1">Standards References</span>
                    <ul className="space-y-0.5">
                      {m.standards_references.map((ref, ri) => (
                        <li key={ri} className="text-xs text-gray-600 flex gap-1.5">
                          <span className="text-blue-400">›</span>{ref}
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
            <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Cluster Update</h3>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div>
                  <p className="text-xs text-gray-500">Pattern Score</p>
                  <p className="text-2xl font-bold text-gray-900">{cluster.pattern_score?.toFixed(3)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Risk State</p>
                  <span className={`inline-block mt-0.5 px-3 py-1 rounded font-semibold text-sm ${STATE_COLORS[cluster.risk_state]}`}>
                    {cluster.risk_state}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Cluster Size</p>
                  <p className="text-2xl font-bold text-gray-900">{cluster.cluster_size}</p>
                </div>
              </div>
              {cluster.score_components && (
                <div className="space-y-1.5">
                  <p className="text-xs text-gray-500 mb-2 font-medium">Score Components</p>
                  <ScoreBar label="Density"       value={cluster.score_components.density} />
                  <ScoreBar label="Edge Strength" value={cluster.score_components.edge_strength} />
                  <ScoreBar label="Velocity"      value={cluster.score_components.velocity} />
                  <ScoreBar label="Severity"      value={cluster.score_components.severity} />
                  <ScoreBar label="Concentration" value={cluster.score_components.concentration} />
                </div>
              )}
              {cluster.new_cluster && (
                <p className="text-xs text-blue-600 mt-3 font-medium">✦ New cluster created</p>
              )}
              {cluster.risk_state !== "NOMINAL" && (
                <p className={`text-xs mt-2 font-semibold ${cluster.risk_state === "ELEVATED" ? "text-orange-600" : "text-red-600"}`}>
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

  return (
    <>
      <Head><title>Submit Report — SIF Detection</title></Head>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">Submit Near-Miss Report</h1>
            <p className="text-xs text-gray-500">SIH26165 · SIF Precursor Detection</p>
          </div>
          <nav className="flex gap-4 text-sm">
            <Link href="/" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link href="/reports" className="text-gray-600 hover:text-gray-900">Reports</Link>
          </nav>
        </header>

        <main className="max-w-3xl mx-auto px-6 py-8">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
            {/* Tabs */}
            <div className="flex border-b border-gray-200">
              {["text","pdf"].map(t => (
                <button key={t} onClick={() => { setTab(t); setResult(null); setError(null); }}
                  className={`px-6 py-3 text-sm font-medium ${tab===t
                    ? "border-b-2 border-blue-600 text-blue-600"
                    : "text-gray-500 hover:text-gray-700"}`}>
                  {t === "text" ? "📝 Text Report" : "📄 PDF Upload"}
                </button>
              ))}
            </div>

            <div className="p-6">
              {/* Common: site select + submitter */}
              <div className="grid grid-cols-2 gap-4 mb-5">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Site ID *</label>
                  <select value={siteId} onChange={e => setSiteId(e.target.value)}
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-blue-300 focus:outline-none">
                    {SITES.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Submitted By</label>
                  <input value={submitter} onChange={e => setSubmitter(e.target.value)}
                    placeholder="Name or employee ID"
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-blue-300 focus:outline-none" />
                </div>
              </div>

              {tab === "text" ? (
                <form onSubmit={handleTextSubmit}>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">
                    Incident Description * <span className="font-normal text-gray-400">(min. 50 chars)</span>
                  </label>
                  <textarea
                    value={text} onChange={e => setText(e.target.value)}
                    rows={10} required
                    placeholder="Describe the near-miss or unsafe condition in detail. Include: what happened, equipment involved, activity being performed, contributing factors, and personnel involved..."
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-300 focus:outline-none resize-none"
                  />
                  <p className="text-xs text-gray-400 mt-1">{text.length} characters</p>
                  <button type="submit" disabled={loading || text.length < 50}
                    className="mt-4 w-full bg-blue-600 text-white py-2.5 rounded font-medium text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                    {loading ? "⏳ Analysing…" : "Submit Report →"}
                  </button>
                </form>
              ) : (
                <form onSubmit={handlePdfSubmit}>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">PDF File *</label>
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors">
                    <input type="file" accept=".pdf" onChange={e => setFile(e.target.files[0])}
                      className="hidden" id="pdf-input" required />
                    <label htmlFor="pdf-input" className="cursor-pointer">
                      <p className="text-4xl mb-2">📄</p>
                      <p className="text-sm text-gray-600">
                        {file ? file.name : "Click to choose PDF or drag & drop"}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">Max 10MB · PDF only</p>
                    </label>
                  </div>
                  <button type="submit" disabled={loading || !file}
                    className="mt-4 w-full bg-blue-600 text-white py-2.5 rounded font-medium text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                    {loading ? "⏳ Extracting & Analysing…" : "Upload & Analyse →"}
                  </button>
                </form>
              )}

              {/* Error */}
              {error && (
                <div className="mt-4 bg-red-50 border border-red-200 rounded p-4">
                  <p className="text-red-700 text-sm font-medium">Submission failed</p>
                  <p className="text-red-600 text-xs mt-1">{error}</p>
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
