/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0E1220",
          900: "#141A2E",
          800: "#1D2440",
          700: "#2A3358",
        },
        paper: {
          DEFAULT: "#F7F6F2",
          dim: "#EFEDE6",
        },
        verdigris: {
          600: "#2F6F62",
          500: "#3A8676",
          100: "#E1EDE9",
        },
        amber: {
          600: "#C77D2E",
          100: "#F7EADA",
        },
        brick: {
          600: "#B23A2E",
          100: "#F7E1DE",
        },
        slate: {
          500: "#6B7280",
          300: "#D3D6DC",
        },
      },
      fontFamily: {
        serif: ["Source Serif 4", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        sm: "3px",
        DEFAULT: "5px",
        lg: "8px",
      },
    },
  },
  plugins: [],
};
