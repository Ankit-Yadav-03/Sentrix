import { useEffect, useState } from "react";
import Head from "next/head";
import { toIST, relativeIST } from "../lib/datetime";
import Link from "next/link";
import Navbar from "../components/Navbar";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATE_COLORS = {
  NOMINAL:  { bg: "bg-nominal-badge-bg",  text: "text-nominal-green",  border: "border-nominal-green",  dot: "bg-nominal-green"  },
  WATCH:    { bg: "bg-watch-badge-bg", text: "text-watch-yellow", border: "border-watch-yellow", dot: "bg-watch-yellow" },
  ELEVATED: { bg: "bg-elevated-badge-bg", text: "text-elevated-orange", border: "border-elevated-orange", dot: "bg-elevated-orange" },
  CRITICAL: { bg: "bg-critical-badge-bg",    text: "text-critical-red",    border: "border-critical-red",    dot: "bg-critical-red"    },
};

const SEV_COLORS = {
  LOW:      "bg-low-sev-bg text-low-sev-text border-low-sev-bg",
  MEDIUM:   "bg-medium-sev-bg text-medium-sev-text border-medium-sev-bg",
  HIGH:     "bg-high-sev-bg text-high-sev-text border-high-sev-bg",
  CRITICAL: "bg-critical-sev-bg text-critical-sev-text border-critical-sev-bg font-bold",
};

function StatCard({ label, value, sub, color = "text-text-primary" }) {
  return (
    <div className="card p-5">
      <p className="text-xs text-text-secondary uppercase tracking-wider">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color}`}>{value ?? "—"}</p>
      {sub && <p className="text-xs text-text-secondary mt-1">{sub}</p>}
    </div>
  );
}

function StateChip({ state }) {
  const c = STATE_COLORS[state] || STATE_COLORS.NOMINAL;
  return (
    <span className={`state-badge ${c.bg} ${c.text} ${c.border}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
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

export default function Dashboard() {
  const [stats,    setStats]    = useState(null);
  const [sites,    setSites]    = useState([]);
  const [clusters, setClusters] = useState([]);
  const [reports,  setReports]  = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);

  async function fetchAll() {
    try {
      const [s, si, cl, r] = await Promise.all([
        fetch(`${API}/stats`).then(r => r.json()),
        fetch(`${API}/sites`).then(r => r.json()),
        fetch(`${API}/clusters`).then(r => r.json()),
        fetch(`${API}/reports?limit=10`).then(r => r.json()),
      ]);
      setStats(s);
      setSites(si.sites || []);
      setClusters(cl.clusters || []);
      setReports(r.items || []);
    } catch (e) {
      setError("Cannot reach backend at " + API + ". Is the server running?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchAll(); }, []);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-text-secondary animate-pulse">Loading dashboard…</p>
    </div>
  );

  if (error) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="card border-critical-red/30 p-6 max-w-md text-center">
        <p className="text-critical-red font-medium">{error}</p>
        <button onClick={() => { setError(null); setLoading(true); fetchAll(); }}
          className="mt-4 px-4 py-2 bg-critical-red text-white rounded text-sm hover:bg-critical-red/90">
          Retry
        </button>
      </div>
    </div>
  );

  const elevatedSites = sites.filter(s => ["ELEVATED","CRITICAL"].includes(s.current_state));

  return (
    <>
      <Head><title>SIF Precursor Detection — Dashboard</title></Head>
      <div className="min-h-screen">

        {/* Header - using shared Navbar */}
        <Navbar />

        <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">

          {/* Elevated Alert Banner */}
          {elevatedSites.length > 0 && (
            <div className="card border-elevated-orange/30 bg-elevated-badge-bg/30 p-4 flex items-start gap-3">
              <span className="text-elevated-orange text-xl">⚠</span>
              <div>
                <p className="font-semibold text-elevated-orange">
                  {elevatedSites.length} site{elevatedSites.length > 1 ? "s" : ""} at ELEVATED or CRITICAL risk state
                </p>
                <p className="text-text-secondary text-sm mt-0.5">
                  {elevatedSites.map(s => `${s.site_id} (${s.current_state})`).join(" · ")}
                </p>
              </div>
            </div>
          )}

          {/* Stats row */}
          <section>
            <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">Overview</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <StatCard label="Total Reports"    value={stats?.total_reports} />
              <StatCard label="Classified"       value={stats?.classified_reports} />
              <StatCard label="Active Clusters"  value={stats?.active_clusters} />
              <StatCard label="Elevated Sites"   value={stats?.elevated_sites}
                        color={stats?.elevated_sites > 0 ? "text-elevated-orange" : "text-text-primary"} />
              <StatCard label="Gate Failures"    value={stats?.gate_failures}
                        color={stats?.gate_failures > 0 ? "text-critical-red" : "text-text-primary"} />
            </div>
          </section>

          {/* Category + Severity breakdown */}
          {stats && (
            <section className="grid md:grid-cols-2 gap-6">
              <div className="card p-5">
                <h3 className="text-sm font-semibold text-text-secondary mb-3">Category Breakdown</h3>
                <div className="space-y-2">
                  {Object.entries(stats.category_breakdown || {}).sort((a,b)=>b[1]-a[1]).map(([cat, n]) => (
                    <div key={cat} className="flex items-center gap-2">
                      <span className="text-xs text-text-secondary w-44 truncate">{cat.replace(/_/g," ")}</span>
                      <div className="flex-1 progress-bar">
                        <div className="progress-fill bg-accent-orange"
                          style={{width: `${Math.round((n / stats.classified_reports) * 100)}%`}} />
                      </div>
                      <span className="text-xs text-text-secondary w-4">{n}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="card p-5">
                <h3 className="text-sm font-semibold text-text-secondary mb-3">Severity Breakdown</h3>
                <div className="space-y-2">
                  {["CRITICAL","HIGH","MEDIUM","LOW"].map(sev => {
                    const n = stats.severity_breakdown?.[sev] || 0;
                    const pct = stats.classified_reports > 0
                      ? Math.round((n / stats.classified_reports) * 100) : 0;
                    return (
                      <div key={sev} className="flex items-center gap-2">
                        <SeverityChip sev={sev} />
                        <div className="flex-1 progress-bar ml-1">
                          <div className={`progress-fill ${sev==="CRITICAL"?"bg-critical-red":sev==="HIGH"?"bg-high-sev-text":sev==="MEDIUM"?"bg-medium-sev-text":"bg-low-sev-text"}`}
                            style={{width: `${pct}%`}} />
                        </div>
                        <span className="text-xs text-text-secondary w-4">{n}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>
          )}

          {/* Site risk states */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Site Risk States</h2>
              <Link href="/sites" className="link text-xs">View all →</Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {sites.map(site => {
                const c = STATE_COLORS[site.current_state] || STATE_COLORS.NOMINAL;
                return (
                  <Link key={site.site_id} href={`/sites/${site.site_id}`}
                    className={`card card-hover p-4 border-l-4 ${c.border} ${c.bg}/30`}>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-text-primary">{site.site_id}</span>
                      <StateChip state={site.current_state} />
                    </div>
                    {site.dominant_category && (
                      <p className="text-xs text-text-secondary mt-1 truncate">
                        {site.dominant_category.replace(/_/g," ")}
                      </p>
                    )}
                    <p className="text-xs text-text-secondary mt-0.5">{site.report_count_30d} reports (30d)</p>
                  </Link>
                );
              })}
            </div>
          </section>

          {/* Top clusters */}
          {clusters.length > 0 && (
            <section>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Active Clusters</h2>
                <Link href="/clusters" className="link text-xs">View all →</Link>
              </div>
              <div className="card table-container">
                <table className="w-full text-sm">
                  <thead className="table-header">
                    <tr>
                      {["Site","Category","Subtype","Pattern Score","Risk State","Reports"].map(h => (
                        <th key={h} className="table-header-cell">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {clusters.slice(0,8).map(cl => (
                      <tr key={cl.cluster_id} className="table-row">
                        <td className="table-cell font-medium text-text-primary">
                           {cl.site_id ? cl.site_id : <span className="italic text-text-secondary">Cross-site</span>}
                         </td>
                        <td className="table-cell text-xs text-text-secondary">{cl.sif_category?.replace(/_/g," ")}</td>
                        <td className="table-cell font-mono text-xs text-accent-orange">
                          <Link href={`/clusters/${cl.cluster_id}`} className="hover:underline">{cl.subtype_id}</Link>
                        </td>
                        <td className="table-cell">
                          <div className="flex items-center gap-2">
                            <div className="w-16 progress-bar">
                              <div className={`progress-fill ${cl.risk_state==="ELEVATED"||cl.risk_state==="CRITICAL"?"bg-elevated-orange":cl.risk_state==="WATCH"?"bg-watch-yellow":"bg-nominal-green"}`}
                                style={{width: `${(cl.pattern_score * 100).toFixed(0)}%`}} />
                            </div>
                            <span className="text-xs text-text-secondary">{cl.pattern_score.toFixed(3)}</span>
                          </div>
                        </td>
                        <td className="table-cell"><StateChip state={cl.risk_state} /></td>
                        <td className="table-cell text-text-secondary">{cl.report_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Recent reports */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Recent Reports</h2>
              <Link href="/reports" className="link text-xs">View all →</Link>
            </div>
            <div className="card table-container">
              <table className="w-full text-sm">
                <thead className="table-header">
                  <tr>
                    {["Site","Category","Severity","Status","Submitted"].map(h => (
                      <th key={h} className="table-header-cell">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {reports.map(r => (
                    <tr key={r.report_id} className="table-row">
                      <td className="table-cell font-medium text-text-primary">{r.site_id}</td>
                      <td className="table-cell text-xs text-text-secondary">{r.sif_category?.replace(/_/g," ") || "—"}</td>
                      <td className="table-cell">
                        {r.severity ? <SeverityChip sev={r.severity} /> : <span className="text-text-secondary">—</span>}
                      </td>
                      <td className="table-cell">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          r.processing_status === "graphed" ? "bg-nominal-badge-bg text-nominal-green border-nominal-green" :
                          r.processing_status === "failed"  ? "bg-critical-badge-bg text-critical-red border-critical-red" :
                          "bg-border text-text-secondary"
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
          </section>

        </main>
      </div>
    </>
  );
}