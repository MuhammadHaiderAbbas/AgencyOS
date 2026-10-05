/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        jarvis: {
          bg: "#060a12",
          panel: "rgba(255,255,255,0.06)",
          border: "rgba(255,255,255,0.08)",
          accent: "#3ee0ff",
          accent2: "#6c7bff",
          muted: "#9aa4b2"
        }
      },
      fontFamily: {
        sans: ["Inter","system-ui","sans-serif"],
        mono: ["JetBrains Mono","monospace"]
      }
    },
  },
  plugins: [],
}
