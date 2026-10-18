/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b1020",
        canvas: "#f5f7fb",
        signal: "#5b5cf0",
      },
    },
  },
  plugins: [],
};
