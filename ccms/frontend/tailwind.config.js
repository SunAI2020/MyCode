/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eef2ff",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
        },
        surface: {
          50: "#f8fafc",
          100: "#1e293b",
          200: "#0f172a",
          300: "#020617",
        },
      },
    },
  },
  plugins: [],
};
