/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "jbhifi-primary": "#FFD700",
        "jbhifi-dark": "#1a1a1a",
        "bunnings-primary": "#E8352A",
        "babybunting-primary": "#F472B6",
        "supercheapauto-primary": "#E8352A",
        "supercheapauto-dark": "#1a1a1a",
      },
      animation: {
        blink: "blink 1s step-end infinite",
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
