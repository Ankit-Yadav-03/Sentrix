import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import { toIST, toISTDate } from "../../lib/datetime";
import Link from "next/link";
import Navbar from "../../components/Navbar";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATE_COLORS = {
  NOMINAL: "bg-nominal-badge-bg text-nominal-green", WATCH: "bg-watch-badge-bg text-watch-yellow",
  ELEVATED: "bg-elevated-badge-bg text-elevated-orange", CRITICAL: "bg-critical-badge-bg text-critical-red font-bold",
};
const SEV_COLORS = {
  LOW: "bg-low-sev-bg text-low-sev-text", MEDIUM: "bg-medium-sev-bg text-medium-sev-text",
  HIGH: "bg-high-sev-bg text-high-sev-text", CRITICAL: "bg-critical-sev-bg text-critical-sev-text font-bold",
};
const COMPONENT_WEIGHTS = {
  density: 0.25, edge_strength: 0.20, velocity: 0.20, severity: 0.20, concentration: 0.15,
};

function StateChip({ state }) {
  return (
    <span className={`state-badge ${STATE_COLORS[state] || STATE_COLORS.NOMINAL}`}>
      {state}
    </span>
  );
}

function SeverityChip({ sev }) {
  return (
    <span className={`severity-badge ${SEV_COLORS[sev] || "bg-border text-text-secondary"}`}>
      {sev}
    </span>
  );
}

function ScoreRow({ label, value, weight }) {
  const pct = Math.round((value || 0) * 100);
  const contribution = ((value || 0) * weight * 100).toFixed(1);
  const riskColor = "bg-accent-orange"; // default, could be passed in
  return (
    <tr className="border-b divide-border">
      <td className="py-2.5 pr-4 text-sm text-text-secondary font-medium capitalize">{label.replace(/_/g," ")}</td>
      <td className="py-2.5 pr-4 w-32">
        <div className="flex items-center gap-2">
          <div className="flex-1 progress-bar">
            <div className="progress-fill bg-accent-orange" style={{width:`${pct}%`}} />
          </div>
        </div>
      </td>
      <td className="py-2.5 pr-4 text-sm font-mono text-text-primary w-16">{value?.toFixed(4)}</td>
      <td className="py-2.5 pr-4 text-xs text-text-secondary w-12">×{weight}</td>
      <td className="py-2.5 text-sm font-mono text-accent-orange w-16">{contribution}%</td>
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

  if (loading) return <div className="min-h-screen flex items-center justify-center text-text-secondary">Loading…</div>;
  if (!cluster || cluster.detail) return <div className="min-h-screen flex items-center justify-center text-critical-red">Cluster not found</div>;

  return (
    <>
      <Head><title>Cluster {cluster.subtype_id} — SIF Detection</title></Head>
      <div className="min-h-screen">

        <Navbar />

        <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">

          {/* Summary cards */}
          <div className="grid grid-cols-4 gap-4">
            {[
              ["Pattern Score", cluster.pattern_score?.toFixed(4), "text-text-primary"],
              ["Risk State", null, null],
              ["Reports in Cluster", cluster.reports?.length, "text-text-primary"],
              ["Edges", cluster.edge_count, "text-text-primary"],
            ].map(([label, val, cls], i) => (
              <div key={label} className="card p-4">
                <p className="text-xs text-text-secondary">{label}</p>
                {i === 1 ? (
                  <StateChip state={cluster.risk_state} />
                ) : (
                  <p className={`text-2xl font-bold mt-1 ${cls}`}>{val ?? "—"}</p>
                )}
              </div>
            ))}
          </div>

          {/* Pattern Score Breakdown */}
          {cluster.score_components && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">Pattern Score Breakdown</h2>
              <div className="mb-3 text-xs text-text-secondary">
                Score = Σ(component × weight) = <strong className="text-text-primary">{cluster.pattern_score?.toFixed(4)}</strong>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="border-b divide-border">
                    {["Component","Bar","Value","Weight","Contribution"].map(h => (
                      <th key={h} className="pb-2 text-left text-xs font-semibold text-text-secondary">{h}</th>
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
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
                Reports ({cluster.reports.length})
              </h2>
              <div className="space-y-3">
                {cluster.reports.map(r => (
                  <div key={r.report_id} className="card-hover border border-border rounded-lg p-4 transition-colors">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Link href={`/reports/${r.report_id}`}
                            className="text-sm font-mono text-accent-orange hover:underline">
                            {r.osha_id || r.report_id?.slice(0,12)}…
                          </Link>
                          {r.severity && <SeverityChip sev={r.severity} />}
                        </div>
                        <p className="text-xs text-text-secondary">
                          {r.site_id} · {r.submitted_at ? toIST(r.submitted_at) : "—"}
                        </p>
                        {r.evidence_span && (
                          <p className="text-xs text-text-secondary italic mt-1 max-w-xl">"{r.evidence_span?.slice(0,120)}…"</p>
                        )}
                      </div>
                    </div>
                    {r.contributing_factors?.length > 0 && (
                      <div className="flex gap-1 mt-2">
                        {r.contributing_factors.map(f => (
                          <span key={f} className="px-1.5 py-0.5 bg-purple-900/30 text-purple-300 rounded text-xs">{f}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="text-xs text-text-secondary">
            Cluster ID: {cluster.cluster_id} · First seen: {cluster.first_seen ? toIST(cluster.first_seen) : "—"} ·
            Last updated: {cluster.last_updated ? toIST(cluster.last_updated) : "—"}
          </div>
        </main>
      </div>
    </>
  );
}