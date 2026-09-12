import { useEffect, useState } from "react";
import Head from "next/head";
import { toIST, relativeIST } from "../lib/datetime";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATE_COLORS = {
  NOMINAL:  { bg: "bg-green-100",  text: "text-green-800",  border: "border-green-300",  dot: "bg-green-500"  },
  WATCH:    { bg: "bg-yellow-100", text: "text-yellow-800", border: "border-yellow-400", dot: "bg-yellow-500" },
  ELEVATED: { bg: "bg-orange-100", text: "text-orange-800", border: "border-orange-400", dot: "bg-orange-500" },
  CRITICAL: { bg: "bg-red-100",    text: "text-red-800",    border: "border-red-400",    dot: "bg-red-600"    },
};

const SEV_COLORS = {
  LOW:      "bg-blue-100 text-blue-700",
  MEDIUM:   "bg-yellow-100 text-yellow-700",
  HIGH:     "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700 font-bold",
};

function StatCard({ label, value, sub, color = "text-gray-900" }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color}`}>{value ?? "—"}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

function StateChip({ state }) {
  const c = STATE_COLORS[state] || STATE_COLORS.NOMINAL;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${c.bg} ${c.text} ${c.border}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {state}
    </span>
  );
}

function SeverityChip({ sev }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${SEV_COLORS[sev] || "bg-gray-100 text-gray-600"}`}>
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <p className="text-gray-500 animate-pulse">Loading dashboard…</p>
    </div>
  );

  if (error) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md text-center">
        <p className="text-red-700 font-medium">{error}</p>
        <button onClick={() => { setError(null); setLoading(true); fetchAll(); }}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded text-sm hover:bg-red-700">
          Retry
        </button>
      </div>
    </div>
  );

  const elevatedSites = sites.filter(s => ["ELEVATED","CRITICAL"].includes(s.current_state));

  return (
    <>
      <Head><title>SIF Precursor Detection — Dashboard</title></Head>
      <div className="min-h-screen bg-gray-50">

        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">SIF Precursor Detection System</h1>
            <p className="text-xs text-gray-500">SIH26165 · Oil &amp; Gas Safety Intelligence</p>
          </div>
          <nav className="flex gap-4 text-sm">
            <Link href="/" className="text-blue-600 font-medium">Dashboard</Link>
            <Link href="/sites" className="text-gray-600 hover:text-gray-900">Sites</Link>
            <Link href="/clusters" className="text-gray-600 hover:text-gray-900">Clusters</Link>
            <Link href="/reports" className="text-gray-600 hover:text-gray-900">Reports</Link>
            <Link href="/submit" className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">
              Submit Report
            </Link>
          </nav>
        </header>

        <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">

          {/* Elevated Alert Banner */}
          {elevatedSites.length > 0 && (
            <div className="bg-orange-50 border border-orange-300 rounded-lg p-4 flex items-start gap-3">
              <span className="text-orange-500 text-xl">⚠</span>
              <div>
                <p className="font-semibold text-orange-800">
                  {elevatedSites.length} site{elevatedSites.length > 1 ? "s" : ""} at ELEVATED or CRITICAL risk state
                </p>
                <p className="text-orange-700 text-sm mt-0.5">
                  {elevatedSites.map(s => `${s.site_id} (${s.current_state})`).join(" · ")}
                </p>
              </div>
            </div>
          )}

          {/* Stats row */}
          <section>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Overview</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <StatCard label="Total Reports"    value={stats?.total_reports} />
              <StatCard label="Classified"       value={stats?.classified_reports} />
              <StatCard label="Active Clusters"  value={stats?.active_clusters} />
              <StatCard label="Elevated Sites"   value={stats?.elevated_sites}
                        color={stats?.elevated_sites > 0 ? "text-orange-600" : "text-gray-900"} />
              <StatCard label="Gate Failures"    value={stats?.gate_failures}
                        color={stats?.gate_failures > 0 ? "text-red-600" : "text-gray-900"} />
            </div>
          </section>

          {/* Category + Severity breakdown */}
          {stats && (
            <section className="grid md:grid-cols-2 gap-6">
              <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Category Breakdown</h3>
                <div className="space-y-2">
                  {Object.entries(stats.category_breakdown || {}).sort((a,b)=>b[1]-a[1]).map(([cat, n]) => (
                    <div key={cat} className="flex items-center gap-2">
                      <span className="text-xs text-gray-600 w-44 truncate">{cat.replace(/_/g," ")}</span>
                      <div className="flex-1 bg-gray-100 rounded h-2">
                        <div className="bg-blue-500 h-2 rounded"
                          style={{width: `${Math.round((n / stats.classified_reports) * 100)}%`}} />
                      </div>
                      <span className="text-xs text-gray-500 w-4">{n}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Severity Breakdown</h3>
                <div className="space-y-2">
                  {["CRITICAL","HIGH","MEDIUM","LOW"].map(sev => {
                    const n = stats.severity_breakdown?.[sev] || 0;
                    const pct = stats.classified_reports > 0
                      ? Math.round((n / stats.classified_reports) * 100) : 0;
                    return (
                      <div key={sev} className="flex items-center gap-2">
                        <SeverityChip sev={sev} />
                        <div className="flex-1 bg-gray-100 rounded h-2 ml-1">
                          <div className={`h-2 rounded ${sev==="CRITICAL"?"bg-red-500":sev==="HIGH"?"bg-orange-400":sev==="MEDIUM"?"bg-yellow-400":"bg-blue-300"}`}
                            style={{width: `${pct}%`}} />
                        </div>
                        <span className="text-xs text-gray-500 w-4">{n}</span>
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
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Site Risk States</h2>
              <Link href="/sites" className="text-xs text-blue-600 hover:underline">View all →</Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {sites.map(site => {
                const c = STATE_COLORS[site.current_state] || STATE_COLORS.NOMINAL;
                return (
                  <Link key={site.site_id} href={`/sites/${site.site_id}`}
                    className={`rounded-lg border p-4 hover:shadow-md transition-shadow ${c.bg} ${c.border}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-gray-800">{site.site_id}</span>
                      <StateChip state={site.current_state} />
                    </div>
                    {site.dominant_category && (
                      <p className="text-xs text-gray-600 mt-1 truncate">
                        {site.dominant_category.replace(/_/g," ")}
                      </p>
                    )}
                    <p className="text-xs text-gray-500 mt-0.5">{site.report_count_30d} reports (30d)</p>
                  </Link>
                );
              })}
            </div>
          </section>

          {/* Top clusters */}
          {clusters.length > 0 && (
            <section>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Active Clusters</h2>
                <Link href="/clusters" className="text-xs text-blue-600 hover:underline">View all →</Link>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      {["Site","Category","Subtype","Pattern Score","Risk State","Reports"].map(h => (
                        <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {clusters.slice(0,8).map(cl => (
                      <tr key={cl.cluster_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2.5 font-medium text-gray-900">{cl.site_id}</td>
                        <td className="px-4 py-2.5 text-gray-600 text-xs">{cl.sif_category?.replace(/_/g," ")}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-blue-600">
                          <Link href={`/clusters/${cl.cluster_id}`} className="hover:underline">{cl.subtype_id}</Link>
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="w-16 bg-gray-100 rounded h-1.5">
                              <div className="bg-blue-500 h-1.5 rounded"
                                style={{width: `${(cl.pattern_score * 100).toFixed(0)}%`}} />
                            </div>
                            <span className="text-xs text-gray-600">{cl.pattern_score.toFixed(3)}</span>
                          </div>
                        </td>
                        <td className="px-4 py-2.5"><StateChip state={cl.risk_state} /></td>
                        <td className="px-4 py-2.5 text-gray-600">{cl.report_count}</td>
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
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Recent Reports</h2>
              <Link href="/reports" className="text-xs text-blue-600 hover:underline">View all →</Link>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    {["Site","Category","Severity","Status","Submitted"].map(h => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {reports.map(r => (
                    <tr key={r.report_id} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5 font-medium text-gray-900">{r.site_id}</td>
                      <td className="px-4 py-2.5 text-xs text-gray-600">{r.sif_category?.replace(/_/g," ") || "—"}</td>
                      <td className="px-4 py-2.5">
                        {r.severity ? <SeverityChip sev={r.severity} /> : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          r.processing_status === "graphed" ? "bg-green-100 text-green-700" :
                          r.processing_status === "failed"  ? "bg-red-100 text-red-700" :
                          "bg-gray-100 text-gray-600"
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
          </section>

        </main>
      </div>
    </>
  );
}
