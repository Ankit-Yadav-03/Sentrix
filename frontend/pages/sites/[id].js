import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import { toIST } from "../../lib/datetime";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STATE_COLORS = {
  NOMINAL: "bg-green-100 text-green-800", WATCH: "bg-yellow-100 text-yellow-800",
  ELEVATED: "bg-orange-100 text-orange-800", CRITICAL: "bg-red-100 text-red-800 font-bold",
};

export default function SiteDetail() {
  const router = useRouter();
  const { id } = router.query;
  const [site, setSite] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    fetch(`${API}/sites/${id}`).then(r => r.json()).then(setSite).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading…</div>;
  if (!site || site.detail) return <div className="min-h-screen flex items-center justify-center text-red-500">Site not found</div>;

  return (
    <>
      <Head><title>{site.site_id} — SIF Detection</title></Head>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">{site.site_id}</h1>
            <p className="text-xs text-gray-500">Site Risk Overview</p>
          </div>
          <nav className="flex gap-4 text-sm">
            <Link href="/" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link href="/sites" className="text-gray-600 hover:text-gray-900">← Sites</Link>
            <Link href="/submit" className="bg-blue-600 text-white px-3 py-1 rounded">Submit Report</Link>
          </nav>
        </header>
        <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
          {/* State banner */}
          <div className={`rounded-lg p-5 ${STATE_COLORS[site.current_state] || "bg-gray-100"}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold opacity-70 uppercase tracking-wider">Current Risk State</p>
                <p className="text-3xl font-bold mt-0.5">{site.current_state}</p>
              </div>
              {site.state_entered_at && (
                <p className="text-sm opacity-70">Since {toIST(site.state_entered_at)}</p>
              )}
            </div>
          </div>

          {/* Active clusters */}
          {site.clusters?.length > 0 && (
            <div className="bg-white rounded-lg border p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
                Active Clusters ({site.clusters.length})
              </h2>
              <div className="space-y-3">
                {site.clusters.map(cl => (
                  <Link key={cl.cluster_id} href={`/clusters/${cl.cluster_id}`}
                    className="block border border-gray-100 rounded-lg p-4 hover:bg-gray-50 hover:border-blue-200 transition-colors">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-mono text-blue-600 font-semibold">{cl.subtype_id}</span>
                        <span className="text-gray-400 mx-2">·</span>
                        <span className="text-sm text-gray-600">{cl.sif_category?.replace(/_/g," ")}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATE_COLORS[cl.risk_state]}`}>
                          {cl.risk_state}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <div className="w-20 bg-gray-100 rounded h-2">
                            <div className="bg-blue-500 h-2 rounded" style={{width:`${(cl.pattern_score*100).toFixed(0)}%`}} />
                          </div>
                          <span className="text-xs font-mono text-gray-600">{cl.pattern_score?.toFixed(3)}</span>
                        </div>
                        <span className="text-xs text-gray-500">{cl.report_count} reports</span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Recent reports */}
          {site.recent_reports?.length > 0 && (
            <div className="bg-white rounded-lg border p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Recent Reports</h2>
              <div className="space-y-2">
                {site.recent_reports.map(r => (
                  <div key={r.report_id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                    <div className="flex items-center gap-3">
                      <Link href={`/reports/${r.report_id}`} className="font-mono text-xs text-blue-600 hover:underline">
                        {r.osha_id || r.report_id?.slice(0,12)}…
                      </Link>
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        r.status==="graphed" ? "bg-green-100 text-green-700" :
                        r.status==="failed"  ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"
                      }`}>{r.status}</span>
                    </div>
                    <span className="text-xs text-gray-400">
                      {r.submitted_at ? toIST(r.submitted_at) : "—"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {site.clusters?.length === 0 && site.recent_reports?.length === 0 && (
            <div className="bg-white rounded-lg border p-8 text-center text-gray-400">
              No reports submitted for this site yet.
              <Link href="/submit" className="block mt-2 text-blue-600 hover:underline text-sm">Submit a report →</Link>
            </div>
          )}
        </main>
      </div>
    </>
  );
}
