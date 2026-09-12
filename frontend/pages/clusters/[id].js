import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import { toIST, toISTDate } from "../../lib/datetime";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STATE_COLORS = {
  NOMINAL: "bg-green-100 text-green-800", WATCH: "bg-yellow-100 text-yellow-800",
  ELEVATED: "bg-orange-100 text-orange-800", CRITICAL: "bg-red-100 text-red-800 font-bold",
};
const SEV_COLORS = {
  LOW: "bg-blue-100 text-blue-700", MEDIUM: "bg-yellow-100 text-yellow-700",
  HIGH: "bg-orange-100 text-orange-700", CRITICAL: "bg-red-100 text-red-700 font-bold",
};
const COMPONENT_WEIGHTS = {
  density: 0.25, edge_strength: 0.20, velocity: 0.20, severity: 0.20, concentration: 0.15,
};

function ScoreRow({ label, value, weight }) {
  const pct = Math.round((value || 0) * 100);
  const contribution = ((value || 0) * weight * 100).toFixed(1);
  return (
    <tr className="border-b border-gray-100">
      <td className="py-2.5 pr-4 text-sm text-gray-700 font-medium capitalize">{label.replace(/_/g," ")}</td>
      <td className="py-2.5 pr-4 w-32">
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-gray-100 rounded h-2">
            <div className="bg-blue-500 h-2 rounded" style={{width:`${pct}%`}} />
          </div>
        </div>
      </td>
      <td className="py-2.5 pr-4 text-sm font-mono text-gray-700 w-16">{value?.toFixed(4)}</td>
      <td className="py-2.5 pr-4 text-xs text-gray-500 w-12">×{weight}</td>
      <td className="py-2.5 text-sm font-mono text-blue-600 w-16">{contribution}%</td>
    </tr>
  );
}

export default function ClusterDetail() {
  const router = useRouter();
  const { id } = router.query;
  const [cluster, setCluster] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    fetch(`${API}/clusters/${id}`)
      .then(r => r.json()).then(setCluster).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading…</div>;
  if (!cluster || cluster.detail) return <div className="min-h-screen flex items-center justify-center text-red-500">Cluster not found</div>;

  return (
    <>
      <Head><title>Cluster {cluster.subtype_id} — SIF Detection</title></Head>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">Cluster Detail</h1>
            <p className="text-xs text-gray-500">{cluster.site_id} · {cluster.sif_category?.replace(/_/g," ")} · {cluster.subtype_id}</p>
          </div>
          <nav className="flex gap-4 text-sm">
            <Link href="/" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link href="/clusters" className="text-gray-600 hover:text-gray-900">← Clusters</Link>
          </nav>
        </header>
        <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">

          {/* Summary cards */}
          <div className="grid grid-cols-4 gap-4">
            {[
              ["Pattern Score", cluster.pattern_score?.toFixed(4), "text-gray-900"],
              ["Risk State", null, null],
              ["Reports in Cluster", cluster.reports?.length, "text-gray-900"],
              ["Edges", cluster.edge_count, "text-gray-900"],
            ].map(([label, val, cls], i) => (
              <div key={label} className="bg-white rounded-lg border p-4 shadow-sm">
                <p className="text-xs text-gray-500">{label}</p>
                {i === 1 ? (
                  <span className={`inline-block mt-1 px-3 py-1 rounded font-semibold text-sm ${STATE_COLORS[cluster.risk_state]}`}>
                    {cluster.risk_state}
                  </span>
                ) : (
                  <p className={`text-2xl font-bold mt-1 ${cls}`}>{val ?? "—"}</p>
                )}
              </div>
            ))}
          </div>

          {/* Pattern Score Breakdown */}
          {cluster.score_components && (
            <div className="bg-white rounded-lg border p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Pattern Score Breakdown</h2>
              <div className="mb-3 text-xs text-gray-500">
                Score = Σ(component × weight) = <strong className="text-gray-800">{cluster.pattern_score?.toFixed(4)}</strong>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    {["Component","Bar","Value","Weight","Contribution"].map(h => (
                      <th key={h} className="pb-2 text-left text-xs font-semibold text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(cluster.score_components).map(([key, val]) => (
                    <ScoreRow key={key} label={key} value={val} weight={COMPONENT_WEIGHTS[key] || 0} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Reports in cluster */}
          {cluster.reports?.length > 0 && (
            <div className="bg-white rounded-lg border p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
                Reports ({cluster.reports.length})
              </h2>
              <div className="space-y-3">
                {cluster.reports.map(r => (
                  <div key={r.report_id} className="border border-gray-100 rounded-lg p-4 hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Link href={`/reports/${r.report_id}`}
                            className="text-sm font-mono text-blue-600 hover:underline">
                            {r.osha_id || r.report_id?.slice(0,12)}…
                          </Link>
                          {r.severity && (
                            <span className={`px-2 py-0.5 rounded text-xs ${SEV_COLORS[r.severity]}`}>{r.severity}</span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500">
                          {r.site_id} · {r.submitted_at ? toIST(r.submitted_at) : "—"}
                        </p>
                        {r.evidence_span && (
                          <p className="text-xs text-gray-600 italic mt-1 max-w-xl">"{r.evidence_span?.slice(0,120)}…"</p>
                        )}
                      </div>
                    </div>
                    {r.contributing_factors?.length > 0 && (
                      <div className="flex gap-1 mt-2">
                        {r.contributing_factors.map(f => (
                          <span key={f} className="px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">{f}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="text-xs text-gray-400">
            Cluster ID: {cluster.cluster_id} · First seen: {cluster.first_seen ? toIST(cluster.first_seen) : "—"} ·
            Last updated: {cluster.last_updated ? toIST(cluster.last_updated) : "—"}
          </div>
        </main>
      </div>
    </>
  );
}
