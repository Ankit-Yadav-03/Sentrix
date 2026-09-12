import { useEffect, useState } from "react";
import Head from "next/head";
import { toISTDate } from "../../lib/datetime";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STATE_COLORS = {
  NOMINAL: "bg-green-100 text-green-700", WATCH: "bg-yellow-100 text-yellow-700",
  ELEVATED: "bg-orange-100 text-orange-700", CRITICAL: "bg-red-100 text-red-700 font-bold",
};

export default function Clusters() {
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    fetch(`${API}/clusters`)
      .then(r => r.json()).then(d => setClusters(d.clusters || []))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Head><title>Clusters — SIF Detection</title></Head>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <h1 className="text-lg font-bold text-gray-900">Active Clusters</h1>
          <nav className="flex gap-4 text-sm">
            <Link href="/" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link href="/submit" className="bg-blue-600 text-white px-3 py-1 rounded">Submit Report</Link>
          </nav>
        </header>
        <main className="max-w-6xl mx-auto px-6 py-8">
          {loading ? <p className="text-gray-400">Loading…</p> : (
            <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>{["Site","Category","Subtype","Pattern Score","Risk State","Reports","First Seen"].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                  ))}</tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {clusters.map(cl => (
                    <tr key={cl.cluster_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium">
                        <Link href={`/sites/${cl.site_id}`} className="hover:text-blue-600">{cl.site_id}</Link>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-600">{cl.sif_category?.replace(/_/g," ")}</td>
                      <td className="px-4 py-3 font-mono text-xs text-blue-600">
                        <Link href={`/clusters/${cl.cluster_id}`} className="hover:underline">{cl.subtype_id}</Link>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-gray-100 rounded h-2">
                            <div className="bg-blue-500 h-2 rounded" style={{width:`${(cl.pattern_score*100).toFixed(0)}%`}} />
                          </div>
                          <span className="text-xs text-gray-600 font-mono">{cl.pattern_score.toFixed(3)}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATE_COLORS[cl.risk_state]}`}>{cl.risk_state}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{cl.report_count}</td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {cl.first_seen ? toISTDate(cl.first_seen) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {clusters.length === 0 && (
                <div className="px-6 py-12 text-center text-gray-400">
                  No active clusters. Submit reports to create clusters.
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </>
  );
}
