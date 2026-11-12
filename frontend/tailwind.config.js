export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F7F7F3",
        ink: "#202923",
        muted: "#5C675F",
        line: "#E2E4DC",
        brand: { DEFAULT: "#244A36", dark: "#1A3828", soft: "#E6EEE8", tint: "#F0F5F1" },
        ok: { DEFAULT: "#244A36", soft: "#E6EEE8" },
        warn: { DEFAULT: "#8A5A00", soft: "#FBF1D9" },
        bad: { DEFAULT: "#A63A2B", soft: "#F8E6E2" },
        info: { DEFAULT: "#2F5D7C", soft: "#E4EEF4" },
      },
      fontFamily: { sans: ['"DM Sans"', "system-ui", "sans-serif"], display: ["Manrope", '"DM Sans"', "sans-serif"] },
      borderRadius: { lg: "10px", md: "8px", sm: "6px" },
    },
  },
  plugins: [],
};
