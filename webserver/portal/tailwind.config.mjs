/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#1f1d1b",
          soft: "#3a3733",
        },
        paper: "#f7f4ee",
        accent: "#c2410c",
      },
      fontFamily: {
        display: ["ui-serif", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
