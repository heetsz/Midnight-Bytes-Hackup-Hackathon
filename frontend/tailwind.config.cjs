/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx,js,jsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Text",
          "sans-serif",
        ],
      },
      colors: {
        background: "#020617",
        foreground: "#f9fafb",
      },
      borderRadius: {
        xl: "1.5rem",
        "2xl": "1.75rem",
      },
      boxShadow: {
        "soft-glow": "0 0 40px rgba(59,130,246,0.35)",
      },
    },
  },
  plugins: [],
};
