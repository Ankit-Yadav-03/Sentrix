import { useEffect, useState } from "react";
import Head from "next/head";
import { toIST } from "../../lib/datetime";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SEV_COLORS = {
  LOW: "bg-blue-100 text-blue-700", MEDIUM: "bg-yellow-100 text-yellow-700",
  HIGH: "bg-orange-100 text-orange-700", CRITICAL: "bg-red-100 text-red-700 font-bold",
};

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
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <h1 className="text-lg font-bold text-gray-900">Reports</h1>
          <nav className="flex gap-4 text-sm">
            <Link href="/" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link href="/submit" className="bg-blue-600 text-white px-3 py-1 rounded">Submit Report</Link>
          </nav>
        </header>
        <main className="max-w-6xl mx-auto px-6 py-8">
          <div className="flex gap-3 mb-4">
            <input value={siteFilter} onChange={e => { setSiteFilter(e.target.value); setOffset(0); }}
              placeholder="Filter by site ID…"
              className="border border-gray-300 rounded px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-300" />
            <span className="text-sm text-gray-500 self-center">{total} total</span>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>{["Site","OSHA ID","Category","Subtype","Severity","Score","Status","Submitted"].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>
                ) : reports.map(r => (
                  <tr key={r.report_id} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5 font-medium">{r.site_id}</td>
                    <td className="px-4 py-2.5 text-xs font-mono text-gray-500">{r.osha_report_id || "—"}</td>
                    <td className="px-4 py-2.5 text-xs text-gray-600">{r.sif_category?.replace(/_/g," ") || "—"}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-blue-600">{r.subtype_id || "—"}</td>
                    <td className="px-4 py-2.5">
                      {r.severity ? <span className={`px-2 py-0.5 rounded text-xs ${SEV_COLORS[r.severity]}`}>{r.severity}</span> : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-600">{r.classifier_score?.toFixed(3) || "—"}</td>
                    <td className="px-4 py-2.5">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        r.processing_status==="graphed" ? "bg-green-100 text-green-700" :
                        r.processing_status==="failed"  ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"
                      }`}>{r.processing_status}</span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-500">
                      <Link href={`/reports/${r.report_id}`} className="hover:text-blue-600 hover:underline">
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
              className="px-3 py-1 text-sm border rounded disabled:opacity-40">← Prev</button>
            <span className="text-sm text-gray-500 self-center">{offset+1}–{Math.min(offset+limit,total)} of {total}</span>
            <button onClick={() => setOffset(offset+limit)} disabled={offset+limit>=total}
              className="px-3 py-1 text-sm border rounded disabled:opacity-40">Next →</button>
          </div>
        </main>
      </div>
    </>
  );
}
