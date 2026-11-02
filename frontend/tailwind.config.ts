import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#fdf3eb",
          100: "#f9e2d0",
          200: "#f3c3a1",
          500: "#c85a17", // Raw Terracotta / Shendur
          600: "#ab470c",
          700: "#8c3506",
          800: "#6f2905",
          900: "#451701",
        },
        khata: {
          canvas:  "#f8f6f1", // Warm alabaster / rice paper canvas
          surface: "#ffffff",
          raised:  "#f2eee5",
          subtle:  "#e8e3d8", // Delicate ledger rule lines
          border:  "#d9d3c5",
          muted:   "#757064",
          ink:     "#23201a", // Deep warm charcoal ink
        },
        ochre: {
          50:  "#fefce8",
          100: "#fef9c3",
          200: "#fef08a",
          500: "#eab308",
          700: "#a16207",
          900: "#713f12",
        },
        sage: {
          50:  "#f0fdf4",
          100: "#dcfce7",
          200: "#bbf7d0",
          600: "#16a34a",
          700: "#15803d",
          800: "#166534",
          900: "#14532d",
        },
        sindoor: {
          50:  "#fff1f2",
          100: "#ffe4e6",
          200: "#fecdd3",
          600: "#e11d48",
          700: "#be123c",
          800: "#9f1239",
          900: "#881337",
        },
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        devanagari: ["Noto Sans Devanagari", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(35, 32, 26, 0.04), 0 1px 2px -1px rgba(35, 32, 26, 0.03)",
        "card-hover": "0 6px 16px -2px rgba(35, 32, 26, 0.07), 0 2px 6px -2px rgba(35, 32, 26, 0.04)",
        drawer: "-8px 0 24px -4px rgba(35, 32, 26, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
