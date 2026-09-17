import Link from "next/link";

export default function Navbar() {
  return (
    <header className="bg-bg-secondary border-b border-border px-6 py-4 flex items-center justify-between sticky top-0 z-50">
      <div>
        <h1 className="text-lg font-bold text-text-primary">SIF Precursor Detection System</h1>
        <p className="text-xs text-text-secondary">Sentrix · Oil & Gas Safety Intelligence</p>
      </div>
      <nav className="flex items-center gap-3 text-sm">
        <Link href="/" className="text-text-secondary hover:text-text-primary transition-colors px-2 py-1 rounded">
          Dashboard
        </Link>
        <Link href="/sites" className="text-text-secondary hover:text-text-primary transition-colors px-2 py-1 rounded">
          Sites
        </Link>
        <Link href="/clusters" className="text-text-secondary hover:text-text-primary transition-colors px-2 py-1 rounded">
          Clusters
        </Link>
        <Link href="/reports" className="text-text-secondary hover:text-text-primary transition-colors px-2 py-1 rounded">
          Reports
        </Link>
        <Link href="/submit" className="bg-accent-orange text-white px-3 py-1.5 rounded hover:bg-accent-orange-hover transition-colors font-medium">
          Submit Report
        </Link>
      </nav>
    </header>
  );
}