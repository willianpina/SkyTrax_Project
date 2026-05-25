/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        graphite: "#101418",
        panel: "#171d23",
        panelSoft: "#202832",
        signal: "#39c6a3",
        amber: "#d7a942",
        risk: "#e05a47"
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      }
    }
  },
  plugins: []
};
