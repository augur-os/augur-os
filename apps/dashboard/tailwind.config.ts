const config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  safelist: [
    {
      pattern: /(text|from|to)-(emerald|amber|red|rose)-(400|500|700)/,
    },
  ],
  theme: {
    extend: {
      colors: {
        border: "var(--glass-border)",
        input: "var(--glass-border)",
        ring: "var(--accent-primary)",
        background: "var(--bg-primary)",
        foreground: "var(--text-primary)",
        primary: {
          DEFAULT: "var(--accent-primary)",
          foreground: "var(--accent-foreground)",
        },
        secondary: {
          DEFAULT: "var(--bg-secondary)",
          foreground: "var(--text-primary)",
        },
        destructive: {
          DEFAULT: "var(--accent-danger)",
          foreground: "#ffffff",
        },
        muted: {
          DEFAULT: "var(--bg-secondary)",
          foreground: "var(--text-muted)",
        },
        accent: {
          DEFAULT: "var(--bg-secondary)",
          foreground: "var(--text-primary)",
        },
        popover: {
          DEFAULT: "var(--bg-card)",
          foreground: "var(--text-primary)",
        },
        card: {
          DEFAULT: "var(--bg-card)",
          foreground: "var(--text-primary)",
        },
        success: "var(--accent-success)",
        warning: "var(--accent-warning)",
        info: "var(--accent-info)",
      },
      fontFamily: {
        sans: [
          "var(--font-fira-sans)",
          "Fira Sans",
          "var(--font-inter)",
          "Inter",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "var(--font-fira-code)",
          "Fira Code",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
        heading: [
          "var(--font-fira-code)",
          "Fira Code",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
