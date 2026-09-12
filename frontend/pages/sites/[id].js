import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import { toIST } from "../../lib/datetime";
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

export default function SiteDetail() {
  const router = useRouter();
  const { id } = router.query;
  const [site, setSite] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    fetch(`${API}/sites/${id}`).then(r => r.json()).then(setSite).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="min-h-screen flex items-center justify-center text-text-secondary">Loading…</div>;
  if (!site || site.detail) return <div className="min-h-screen flex items-center justify-center text-critical-red">Site not found</div>;

  return (
    <>
      <Head><title>{site.site_id} — SIF Detection</title></Head>
      <div className="min-h-screen">

        <Navbar />

        <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
          {/* State banner */}
          <div className={`card p-5 ${STATE_COLORS[site.current_state] || "bg-border"}/30 border-l-4 ${STATE_COLORS[site.current_state]?.replace("bg-", "border-") || "border-border"}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Current Risk State</p>
                <p className="text-3xl font-bold mt-0.5 text-text-primary">{site.current_state}</p>
              </div>
              {site.state_entered_at && (
                <p className="text-sm text-text-secondary">Since {toIST(site.state_entered_at)}</p>
              )}
            </div>
          </div>

          {/* Active clusters */}
          {site.clusters?.length > 0 && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
                Active Clusters ({site.clusters.length})
              </h2>
              <div className="space-y-3">
                {site.clusters.map(cl => (
                  <Link key={cl.cluster_id} href={`/clusters/${cl.cluster_id}`}
                    className="block card-hover border border-border rounded-lg p-4 transition-colors">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-mono text-accent-orange font-semibold">{cl.subtype_id}</span>
                        <span className="text-text-secondary mx-2">·</span>
                        <span className="text-sm text-text-secondary">{cl.sif_category?.replace(/_/g," ")}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <StateChip state={cl.risk_state} />
                        <div className="flex items-center gap-1.5">
                          <div className="w-20 progress-bar">
                            <div className={`progress-fill ${cl.risk_state==="ELEVATED"||cl.risk_state==="CRITICAL"?"bg-elevated-orange":cl.risk_state==="WATCH"?"bg-watch-yellow":"bg-nominal-green"}`}
                              style={{width:`${(cl.pattern_score*100).toFixed(0)}%`}} />
                          </div>
                          <span className="text-xs font-mono text-text-secondary">{cl.pattern_score?.toFixed(3)}</span>
                        </div>
                        <span className="text-xs text-text-secondary">{cl.report_count} reports</span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Recent reports */}
          {site.recent_reports?.length > 0 && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">Recent Reports</h2>
              <div className="space-y-2">
                {site.recent_reports.map(r => (
                  <div key={r.report_id} className="flex items-center justify-between py-2 border-b divide-border last:border-0">
                    <div className="flex items-center gap-3">
                      <Link href={`/reports/${r.report_id}`} className="font-mono text-xs text-accent-orange hover:underline">
                        {r.osha_id || r.report_id?.slice(0,12)}…
                      </Link>
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        r.status==="graphed" ? "bg-nominal-badge-bg text-nominal-green border-nominal-green" :
                        r.status==="failed"  ? "bg-critical-badge-bg text-critical-red border-critical-red" : "bg-border text-text-secondary"
                      }`}>{r.status}</span>
                    </div>
                    <span className="text-xs text-text-secondary">
                      {r.submitted_at ? toIST(r.submitted_at) : "—"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {site.clusters?.length === 0 && site.recent_reports?.length === 0 && (
            <div className="card p-8 text-center text-text-secondary">
              No reports submitted for this site yet.
              <Link href="/submit" className="block mt-2 link text-sm">Submit a report →</Link>
            </div>
          )}
        </main>
      </div>
    </>
  );
}