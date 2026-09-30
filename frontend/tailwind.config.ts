import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        slate: {
          850: "#172033",
          900: "#0F172A",
          950: "#080D1A",
        },
        primary: {
          DEFAULT: "#38BDF8", // Sky Blue (Data Primary)
          dark: "#0284C7",
        },
        warning: {
          DEFAULT: "#F59E0B", // Amber (Data Warning)
          dark: "#D97706",
        },
        critical: {
          DEFAULT: "#E11D48", // Rose (Data Critical)
          dark: "#BE123C",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
