import { useEffect, useState } from "react";
import Head from "next/head";
import { toISTDate } from "../../lib/datetime";
import Link from "next/link";
import Navbar from "../../components/Navbar";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATE_COLORS = {
  NOMINAL: "bg-nominal-badge-bg text-nominal-green", WATCH: "bg-watch-badge-bg text-watch-yellow",
  ELEVATED: "bg-elevated-badge-bg text-elevated-orange", CRITICAL: "bg-critical-badge-bg text-critical-red font-bold",
};

function StateChip({ state }) {
  return (
    <span className={`state-badge ${STATE_COLORS[state] || STATE_COLORS.NOMINAL}`}>
      {state}
    </span>
  );
}

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
      <div className="min-h-screen">

        <Navbar />

        <main className="max-w-6xl mx-auto px-6 py-8">
          {loading ? <p className="text-text-secondary">Loading…</p> : (
            <div className="card table-container">
              <table className="w-full text-sm">
                <thead className="table-header">
                  <tr>{["Site","Category","Subtype","Pattern Score","Risk State","Reports","First Seen"].map(h => (
                    <th key={h} className="table-header-cell">{h}</th>
                  ))}</tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {clusters.map(cl => (
                    <tr key={cl.cluster_id} className="table-row">
                      <td className="table-cell font-medium">
                        <Link href={`/sites/${cl.site_id}`} className="link">{cl.site_id}</Link>
                      </td>
                      <td className="table-cell text-xs text-text-secondary">{cl.sif_category?.replace(/_/g," ")}</td>
                      <td className="table-cell font-mono text-xs text-accent-orange">
                        <Link href={`/clusters/${cl.cluster_id}`} className="hover:underline">{cl.subtype_id}</Link>
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center gap-2">
                          <div className="w-20 progress-bar">
                            <div className={`progress-fill ${cl.risk_state==="ELEVATED"||cl.risk_state==="CRITICAL"?"bg-elevated-orange":cl.risk_state==="WATCH"?"bg-watch-yellow":"bg-nominal-green"}`}
                              style={{width:`${(cl.pattern_score*100).toFixed(0)}%`}} />
                          </div>
                          <span className="text-xs font-mono text-text-secondary">{cl.pattern_score.toFixed(3)}</span>
                        </div>
                      </td>
                      <td className="table-cell"><StateChip state={cl.risk_state} /></td>
                      <td className="table-cell text-text-secondary">{cl.report_count}</td>
                      <td className="table-cell text-xs text-text-secondary">
                        {cl.first_seen ? toISTDate(cl.first_seen) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {clusters.length === 0 && (
                <div className="px-6 py-12 text-center text-text-secondary">
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