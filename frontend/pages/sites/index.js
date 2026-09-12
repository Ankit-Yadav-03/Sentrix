import { useEffect, useState } from "react";
import Head from "next/head";
import { toISTDate } from "../../lib/datetime";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STATE_COLORS = {
  NOMINAL: { bg:"bg-green-50",  text:"text-green-800",  border:"border-green-200" },
  WATCH:   { bg:"bg-yellow-50", text:"text-yellow-800", border:"border-yellow-300" },
  ELEVATED:{ bg:"bg-orange-50", text:"text-orange-800", border:"border-orange-300" },
  CRITICAL:{ bg:"bg-red-50",    text:"text-red-800",    border:"border-red-300" },
};

export default function Sites() {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/sites`).then(r => r.json())
      .then(d => setSites(d.sites || [])).finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Head><title>Sites — SIF Detection</title></Head>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <h1 className="text-lg font-bold text-gray-900">Sites</h1>
          <nav className="flex gap-4 text-sm">
            <Link href="/" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link href="/submit" className="bg-blue-600 text-white px-3 py-1 rounded">Submit Report</Link>
          </nav>
        </header>
        <main className="max-w-5xl mx-auto px-6 py-8">
          {loading ? <p className="text-gray-400">Loading…</p> : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {sites.map(site => {
                const c = STATE_COLORS[site.current_state] || STATE_COLORS.NOMINAL;
                return (
                  <Link key={site.site_id} href={`/sites/${site.site_id}`}
                    className={`rounded-lg border p-5 hover:shadow-md transition-shadow ${c.bg} ${c.border}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-lg font-bold ${c.text}`}>{site.site_id}</span>
                      <span className={`px-3 py-1 rounded-full text-sm font-semibold ${c.bg} ${c.text} border ${c.border}`}>
                        {site.current_state}
                      </span>
                    </div>
                    {site.dominant_category && (
                      <p className="text-sm text-gray-700">
                        Dominant: <strong>{site.dominant_category.replace(/_/g," ")}</strong>
                      </p>
                    )}
                    <p className="text-xs text-gray-500 mt-1">{site.report_count_30d} reports in last 30 days</p>
                    {site.state_entered_at && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        State since: {toISTDate(site.state_entered_at)}
                      </p>
                    )}
                  </Link>
                );
              })}
            </div>
          )}
        </main>
      </div>
    </>
  );
}
