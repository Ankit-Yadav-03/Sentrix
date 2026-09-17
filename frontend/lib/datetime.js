/**
 * IST datetime utilities for Sentrix frontend.
 *
 * Storage: UTC in PostgreSQL (correct, timezone-safe).
 * Display: IST (UTC+5:30) everywhere in the UI.
 *
 * Never store IST in the DB. Convert at display time only.
 */

const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000; // +05:30 in milliseconds

/**
 * Convert a UTC ISO string (from API) to a human-readable IST string.
 * e.g. "2026-08-20T14:30:00Z" → "20 Aug 2026, 08:00 PM IST"
 */
export function toIST(isoString) {
  if (!isoString) return "—";
  try {
    const utcMs = new Date(isoString).getTime();
    const istMs = utcMs + IST_OFFSET_MS;
    const istDate = new Date(istMs);

    return istDate.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
      timeZone: "Asia/Kolkata",
    }) + " IST";
  } catch {
    return isoString;
  }
}

/**
 * Short date only in IST.
 * e.g. "20 Aug 2026"
 */
export function toISTDate(isoString) {
  if (!isoString) return "—";
  try {
    return new Date(isoString).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "Asia/Kolkata",
    });
  } catch {
    return isoString;
  }
}

/**
 * Relative time in IST context.
 * e.g. "3 days ago", "just now"
 */
export function relativeIST(isoString) {
  if (!isoString) return "—";
  try {
    const diffMs = Date.now() - new Date(isoString).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1)  return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24)  return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    if (diffDays < 30) return `${diffDays}d ago`;
    return toISTDate(isoString);
  } catch {
    return isoString;
  }
}
