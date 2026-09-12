import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import { toIST } from "../../lib/datetime";
import Link from "next/link";
import Navbar from "../../components/Navbar";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SEV_COLORS = {
  LOW: "bg-low-sev-bg text-low-sev-text border-low-sev-bg",
  MEDIUM: "bg-medium-sev-bg text-medium-sev-text border-medium-sev-bg",
  HIGH: "bg-high-sev-bg text-high-sev-text border-high-sev-bg",
  CRITICAL: "bg-critical-sev-bg text-critical-sev-text border-critical-sev-bg font-bold",
};

function SeverityChip({ sev }) {
  return (
    <span className={`severity-badge ${SEV_COLORS[sev] || "bg-border text-text-secondary"}`}>
      {sev}
    </span>
  );
}

export default function ReportDetail() {
  const router = useRouter();
  const { id } = router.query;
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    fetch(`${API}/reports/${id}`)
      .then(r => r.json()).then(setReport).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="min-h-screen flex items-center justify-center text-text-secondary">Loading…</div>;
  if (!report || report.detail) return <div className="min-h-screen flex items-center justify-center text-critical-red">Report not found</div>;

  const clf = report.classification;
  const submittedBy = report.submitted_by && report.submitted_by !== "seed_script" ? report.submitted_by : "—";

  return (
    <>
      <Head><title>Report {report.osha_report_id || report.report_id?.slice(0,8)} — SIF Detection</title></Head>
      <div className="min-h-screen">

        <Navbar />

        <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
          <div className="card p-5 grid grid-cols-2 md:grid-cols-3 gap-4">
            {[["Site", report.site_id], ["Source", report.source], ["Status", report.processing_status],
              ["Submitted", report.submitted_at ? toIST(report.submitted_at) : "—"],
              ["Submitted By", submittedBy], ["OSHA ID", report.osha_report_id || "—"]
            ].map(([label, val]) => (
              <div key={label}><p className="text-xs text-text-secondary">{label}</p>
                <p className="text-sm font-medium text-text-primary break-all">{val}</p></div>
            ))}
          </div>

          {clf && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">Classification</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><p className="text-xs text-text-secondary">Category</p><p className="font-semibold text-text-primary">{clf.sif_category?.replace(/_/g," ")}</p></div>
                <div><p className="text-xs text-text-secondary">Subtype</p><p className="font-mono text-accent-orange font-semibold">{clf.subtype_id}</p></div>
                <div><p className="text-xs text-text-secondary">Severity</p>
                  <SeverityChip sev={clf.severity} />
                </div>
                <div><p className="text-xs text-text-secondary">Score</p><p className="font-semibold text-text-primary">{clf.classifier_score?.toFixed(4)}</p></div>
              </div>
            </div>
          )}

          {report.mappings?.map((m, i) => (
            <div key={m.mapping_id} className="card p-5">
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">Ontology Mapping — {m.subtype_id}</h2>
              <div className="space-y-3 text-sm">
                <div><span className="text-xs text-text-secondary block mb-0.5">Evidence Span</span>
                  <blockquote className="card p-3 border-l-4 border-accent-orange text-text-primary text-xs italic">{m.evidence_span}</blockquote>
                </div>
                {m.severity_justification && <div><span className="text-xs text-text-secondary block">Severity Justification</span>
                  <p className="text-xs text-text-secondary mt-0.5">{m.severity_justification}</p></div>}
                <div className="grid grid-cols-3 gap-4">
                  {[["Contributing Factors", m.contributing_factors, "bg-purple-900/30 text-purple-300"],
                    ["Equipment Classes", m.equipment_classes, "bg-border text-text-secondary"],
                    ["Activity Contexts", m.activity_contexts, "bg-green-900/30 text-green-300"]].map(([label, items, cls]) => (
                    <div key={label}><span className="text-xs text-text-secondary block mb-1">{label}</span>
                      <div className="flex flex-wrap gap-1">
                        {items?.map(x => <span key={x} className={`px-1.5 py-0.5 rounded text-xs font-mono ${cls}`}>{x}</span>)}
                      </div>
                    </div>
                  ))}
                </div>
                {m.standards_references?.length > 0 && (
                  <div><span className="text-xs text-text-secondary block mb-1">Standards References</span>
                    <ul className="space-y-0.5">{m.standards_references.map((ref, ri) => (
                      <li key={ri} className="text-xs text-text-secondary flex gap-1.5">
                        <span className="text-accent-orange">›</span>{ref}
                      </li>
                    ))}</ul>
                  </div>
                )}
              </div>
            </div>
          ))}

          <div className="card p-5">
            <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">Raw Report Text</h2>
            <pre className="text-xs text-text-secondary bg-bg-primary rounded p-4 overflow-x-auto whitespace-pre-wrap leading-relaxed">{report.raw_text}</pre>
          </div>

          {report.validation_failures?.length > 0 && (
            <div className="card p-5 border-amber-500/30 bg-amber-900/10">
              <h2 className="text-sm font-semibold text-amber-400 mb-2">Validation Failures</h2>
              {report.validation_failures.map((vf, i) => (
                <div key={i} className="text-xs text-amber-300 mb-1"><strong className="text-amber-400">{vf.gate}</strong>: {vf.reason}</div>
              ))}
            </div>
          )}
        </main>
      </div>
    </>
  );
}