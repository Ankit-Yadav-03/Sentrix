import { useEffect, useState } from "react";
import Head from "next/head";
import { toISTDate } from "../../lib/datetime";
import Link from "next/link";
import Navbar from "../../components/Navbar";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATE_COLORS = {
  NOMINAL: { bg:"bg-nominal-badge-bg",  text:"text-nominal-green",  border:"border-nominal-green",  dot:"bg-nominal-green"  },
  WATCH:   { bg:"bg-watch-badge-bg", text:"text-watch-yellow", border:"border-watch-yellow", dot:"bg-watch-yellow" },
  ELEVATED:{ bg:"bg-elevated-badge-bg", text:"text-elevated-orange", border:"border-elevated-orange", dot:"bg-elevated-orange" },
  CRITICAL:{ bg:"bg-critical-badge-bg",    text:"text-critical-red",    border:"border-critical-red",    dot:"bg-critical-red"    },
};

function StateChip({ state }) {
  const c = STATE_COLORS[state] || STATE_COLORS.NOMINAL;
  return (
    <span className={`state-badge ${c.bg} ${c.text} ${c.border}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {state}
    </span>
  );
}

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
      <div className="min-h-screen">

        <Navbar />

        <main className="max-w-5xl mx-auto px-6 py-8">
          {loading ? <p className="text-text-secondary">Loading…</p> : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {sites.map(site => {
                const c = STATE_COLORS[site.current_state] || STATE_COLORS.NOMINAL;
                return (
                  <Link key={site.site_id} href={`/sites/${site.site_id}`}
                    className={`card card-hover p-5 border-l-4 ${c.border} ${c.bg}/30`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-lg font-bold ${c.text}`}>{site.site_id}</span>
                      <StateChip state={site.current_state} />
                    </div>
                    {site.dominant_category && (
                      <p className="text-sm text-text-secondary">
                        Dominant: <strong className="text-text-primary">{site.dominant_category.replace(/_/g," ")}</strong>
                      </p>
                    )}
                    <p className="text-xs text-text-secondary mt-1">{site.report_count_30d} reports in last 30 days</p>
                    {site.state_entered_at && (
                      <p className="text-xs text-text-secondary mt-0.5">
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