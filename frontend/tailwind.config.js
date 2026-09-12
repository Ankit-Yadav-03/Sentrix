/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./pages/**/*.{js,jsx}", "./components/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Background colors
        'bg-primary': '#0f1117',
        'bg-secondary': '#1a1d27',
        'bg-card': '#1e2130',
        // Border color
        border: '#2a2d3e',
        // Text colors
        'text-primary': '#f1f5f9',
        'text-secondary': '#94a3b8',
        // Accent colors
        'accent-orange': '#f97316',
        'accent-orange-hover': '#ea6c0a',
        // State colors
        'nominal-green': '#22c55e',
        'watch-yellow': '#eab308',
        'elevated-orange': '#f97316',
        'critical-red': '#ef4444',
        // State badge backgrounds
        'nominal-badge-bg': '#14532d',
        'watch-badge-bg': '#713f12',
        'elevated-badge-bg': '#7c2d12',
        'critical-badge-bg': '#7f1d1d',
        // Severity badge backgrounds
        'critical-sev-bg': '#7f1d1d',
        'high-sev-bg': '#7c2d12',
        'medium-sev-bg': '#713f12',
        'low-sev-bg': '#1e3a5f',
        // Severity badge text
        'critical-sev-text': '#ef4444',
        'high-sev-text': '#f97316',
        'medium-sev-text': '#eab308',
        'low-sev-text': '#60a5fa',
        // Table row hover
        'table-hover': '#252840',
      },
    },
  },
  plugins: [],
};