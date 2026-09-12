import { useEffect, useState } from "react";
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

export default function Reports() {
  const [reports, setReports] = useState([]);
  const [total, setTotal]     = useState(0);
  const [loading, setLoading] = useState(true);
  const [siteFilter, setSiteFilter] = useState("");
  const [offset, setOffset]   = useState(0);
  const limit = 20;

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit, offset });
    if (siteFilter) params.set("site_id", siteFilter);
    fetch(`${API}/reports?${params}`)
      .then(r => r.json())
      .then(d => { setReports(d.items || []); setTotal(d.total || 0); })
      .finally(() => setLoading(false));
  }, [offset, siteFilter]);

  return (
    <>
      <Head><title>Reports — SIF Detection</title></Head>
      <div className="min-h-screen">

        <Navbar />

        <main className="max-w-6xl mx-auto px-6 py-8">
          <div className="flex gap-3 mb-4">
            <input value={siteFilter} onChange={e => { setSiteFilter(e.target.value); setOffset(0); }}
              placeholder="Filter by site ID…"
              className="input w-48" />
            <span className="text-sm text-text-secondary self-center">{total} total</span>
          </div>
          <div className="card table-container">
            <table className="w-full text-sm">
              <thead className="table-header">
                <tr>{["Site","OSHA ID","Category","Subtype","Severity","Score","Status","Submitted"].map(h => (
                  <th key={h} className="table-header-cell">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr><td colSpan={8} className="table-cell text-center text-text-secondary py-8">Loading…</td></tr>
                ) : reports.map(r => (
                  <tr key={r.report_id} className="table-row">
                    <td className="table-cell font-medium text-text-primary">{r.site_id}</td>
                    <td className="table-cell text-xs font-mono text-text-secondary">{r.osha_report_id || "—"}</td>
                    <td className="table-cell text-xs text-text-secondary">{r.sif_category?.replace(/_/g," ") || "—"}</td>
                    <td className="table-cell font-mono text-xs text-accent-orange">{r.subtype_id || "—"}</td>
                    <td className="table-cell">
                      {r.severity ? <SeverityChip sev={r.severity} /> : <span className="text-text-secondary">—</span>}
                    </td>
                    <td className="table-cell text-xs text-text-secondary">{r.classifier_score?.toFixed(3) || "—"}</td>
                    <td className="table-cell">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        r.processing_status==="graphed" ? "bg-nominal-badge-bg text-nominal-green border-nominal-green" :
                        r.processing_status==="failed"  ? "bg-critical-badge-bg text-critical-red border-critical-red" : "bg-border text-text-secondary"
                      }`}>{r.processing_status}</span>
                    </td>
                    <td className="table-cell text-xs text-text-secondary">
                      <Link href={`/reports/${r.report_id}`} className="link">
                        {r.submitted_at ? toIST(r.submitted_at) : "—"}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-2 mt-4 justify-center">
            <button onClick={() => setOffset(Math.max(0,offset-limit))} disabled={offset===0}
              className="btn-secondary disabled:opacity-40">← Prev</button>
            <span className="text-sm text-text-secondary self-center">{offset+1}–{Math.min(offset+limit,total)} of {total}</span>
            <button onClick={() => setOffset(offset+limit)} disabled={offset+limit>=total}
              className="btn-secondary disabled:opacity-40">Next →</button>
          </div>
        </main>
      </div>
    </>
  );
}