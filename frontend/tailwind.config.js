/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Brand palette — "Pitch" teal-cyan as primary, "Strike" amber-orange as accent
        brand: {
          50:  "#eefcfb",
          100: "#d3f8f5",
          200: "#aaeeea",
          300: "#71dedb",
          400: "#3ec3c5",
          500: "#1aa6ab",
          600: "#0d8488",
          700: "#0a696d",
          800: "#0a5457",
          900: "#0a4448",
          950: "#04282b",
        },
        strike: {
          50:  "#fff8eb",
          100: "#ffeac6",
          200: "#ffd28a",
          300: "#ffb44e",
          400: "#ff9425",
          500: "#f6720c",
          600: "#db5306",
          700: "#b53908",
          800: "#922d0e",
          900: "#78260f",
          950: "#451104",
        },
        success: { 500: "#10b981", 600: "#059669", 700: "#047857" },
        danger:  { 500: "#ef4444", 600: "#dc2626", 700: "#b91c1c" },
        warning: { 500: "#f59e0b", 600: "#d97706", 700: "#b45309" },
        info:    { 500: "#0ea5e9", 600: "#0284c7", 700: "#0369a1" },
        ink: {
          50:  "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
          950: "#020617",
        },
      },
      fontFamily: {
        sans: ['"Inter"', '"PingFang SC"', '"Microsoft YaHei"', "system-ui", "sans-serif"],
        display: ['"Inter Display"', '"Inter"', '"PingFang SC"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"SF Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "0.9rem" }],
        "display-xs": ["1.5rem", { lineHeight: "2rem", letterSpacing: "-0.01em", fontWeight: "700" }],
        "display-sm": ["1.875rem", { lineHeight: "2.25rem", letterSpacing: "-0.015em", fontWeight: "700" }],
        "display-md": ["2.25rem", { lineHeight: "2.5rem", letterSpacing: "-0.02em", fontWeight: "700" }],
        "display-lg": ["3rem", { lineHeight: "3.5rem", letterSpacing: "-0.02em", fontWeight: "800" }],
      },
      animation: {
        "fade-in": "fadeIn 0.4s ease-out",
        "slide-up": "slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1)",
        "pulse-glow": "pulseGlow 2.5s ease-in-out infinite",
        "shimmer": "shimmer 2.5s linear infinite",
        "tick": "tick 1s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseGlow: {
          "0%, 100%": { opacity: "1", boxShadow: "0 0 0 0 rgba(26, 166, 171, 0.4)" },
          "50%": { opacity: "0.85", boxShadow: "0 0 0 8px rgba(26, 166, 171, 0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        tick: {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.15)" },
        },
      },
      boxShadow: {
        "glow-brand": "0 0 24px -4px rgba(26, 166, 171, 0.5)",
        "glow-strike": "0 0 24px -4px rgba(246, 114, 12, 0.4)",
        "elevated": "0 1px 3px 0 rgba(0,0,0,0.04), 0 4px 16px -4px rgba(0,0,0,0.06)",
      },
    },
  },
  plugins: [],
};
