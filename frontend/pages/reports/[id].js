import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import { toIST } from "../../lib/datetime";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SEV_COLORS = {
  LOW: "bg-blue-50 text-blue-700 border-blue-200",
  MEDIUM: "bg-yellow-50 text-yellow-700 border-yellow-200",
  HIGH: "bg-orange-50 text-orange-700 border-orange-200",
  CRITICAL: "bg-red-50 text-red-700 border-red-300 font-bold",
};

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

  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading…</div>;
  if (!report || report.detail) return <div className="min-h-screen flex items-center justify-center text-red-500">Report not found</div>;

  const clf = report.classification;
  return (
    <>
      <Head><title>Report {report.osha_report_id || report.report_id?.slice(0,8)} — SIF Detection</title></Head>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">Report Detail</h1>
            <p className="text-xs text-gray-500">{report.osha_report_id || report.report_id}</p>
          </div>
          <nav className="flex gap-4 text-sm">
            <Link href="/" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link href="/reports" className="text-gray-600 hover:text-gray-900">← Reports</Link>
          </nav>
        </header>
        <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
          <div className="bg-white rounded-lg border p-5 shadow-sm grid grid-cols-2 md:grid-cols-3 gap-4">
            {[["Site", report.site_id], ["Source", report.source], ["Status", report.processing_status],
              ["Submitted", report.submitted_at ? toIST(report.submitted_at) : "—"],
              ["Submitted By", report.submitted_by || "—"], ["OSHA ID", report.osha_report_id || "—"]
            ].map(([label, val]) => (
              <div key={label}><p className="text-xs text-gray-500">{label}</p>
                <p className="text-sm font-medium text-gray-800 break-all">{val}</p></div>
            ))}
          </div>

          {clf && (
            <div className="bg-white rounded-lg border p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Classification</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><p className="text-xs text-gray-500">Category</p><p className="font-semibold">{clf.sif_category?.replace(/_/g," ")}</p></div>
                <div><p className="text-xs text-gray-500">Subtype</p><p className="font-mono text-blue-600 font-semibold">{clf.subtype_id}</p></div>
                <div><p className="text-xs text-gray-500">Severity</p>
                  <span className={`inline-block px-2 py-0.5 rounded border text-xs font-medium ${SEV_COLORS[clf.severity]}`}>{clf.severity}</span>
                </div>
                <div><p className="text-xs text-gray-500">Score</p><p className="font-semibold">{clf.classifier_score?.toFixed(4)}</p></div>
              </div>
            </div>
          )}

          {report.mappings?.map((m, i) => (
            <div key={m.mapping_id} className="bg-white rounded-lg border p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">Ontology Mapping — {m.subtype_id}</h2>
              <div className="space-y-3 text-sm">
                <div><span className="text-xs text-gray-500 block mb-0.5">Evidence Span</span>
                  <blockquote className="bg-gray-50 border-l-4 border-blue-300 pl-3 py-2 text-gray-700 text-xs italic">{m.evidence_span}</blockquote>
                </div>
                {m.severity_justification && <div><span className="text-xs text-gray-500 block">Severity Justification</span>
                  <p className="text-xs text-gray-600 mt-0.5">{m.severity_justification}</p></div>}
                <div className="grid grid-cols-3 gap-4">
                  {[["Contributing Factors", m.contributing_factors, "bg-purple-100 text-purple-700"],
                    ["Equipment Classes", m.equipment_classes, "bg-gray-100 text-gray-700"],
                    ["Activity Contexts", m.activity_contexts, "bg-green-100 text-green-700"]].map(([label, items, cls]) => (
                    <div key={label}><span className="text-xs text-gray-500 block mb-1">{label}</span>
                      <div className="flex flex-wrap gap-1">
                        {items?.map(x => <span key={x} className={`px-1.5 py-0.5 rounded text-xs font-mono ${cls}`}>{x}</span>)}
                      </div>
                    </div>
                  ))}
                </div>
                {m.standards_references?.length > 0 && (
                  <div><span className="text-xs text-gray-500 block mb-1">Standards References</span>
                    <ul className="space-y-0.5">{m.standards_references.map((ref, ri) => (
                      <li key={ri} className="text-xs text-gray-600">› {ref}</li>
                    ))}</ul>
                  </div>
                )}
              </div>
            </div>
          ))}

          <div className="bg-white rounded-lg border p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">Raw Report Text</h2>
            <pre className="text-xs text-gray-700 bg-gray-50 rounded p-4 overflow-x-auto whitespace-pre-wrap leading-relaxed">{report.raw_text}</pre>
          </div>

          {report.validation_failures?.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-5">
              <h2 className="text-sm font-semibold text-amber-700 mb-2">Validation Failures</h2>
              {report.validation_failures.map((vf, i) => (
                <div key={i} className="text-xs text-amber-700 mb-1"><strong>{vf.gate}</strong>: {vf.reason}</div>
              ))}
            </div>
          )}
        </main>
      </div>
    </>
  );
}
