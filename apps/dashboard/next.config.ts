import type { NextConfig } from "next";

function contentSecurityPolicy(
  isDev: boolean,
  frameAncestors: "'none'" | "'self'" = "'none'",
  options: { upgradeInsecureRequests?: boolean } = {},
): string {
  const upgradeInsecureRequests =
    options.upgradeInsecureRequests ?? !isDev;

  return [
    "default-src 'self'",
    isDev
      ? "script-src 'self' 'unsafe-eval' 'unsafe-inline'"
      : // Next.js App Router emits inline bootstrap scripts for streamed RSC payloads.
        // Keep this aligned with runtime behavior to avoid blank pages under strict CSP.
        "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https:",
    "font-src 'self' data:",
    isDev ? "connect-src 'self' ws: wss:" : "connect-src 'self'",
    "worker-src 'self' blob:",
    `frame-ancestors ${frameAncestors}`,
    "base-uri 'self'",
    "form-action 'self'",
    ...(upgradeInsecureRequests ? ["upgrade-insecure-requests"] : []),
  ].join("; ");
}

const nextConfig: NextConfig = {
  // Allow local browser verification against either localhost or 127.0.0.1.
  allowedDevOrigins: ["localhost", "127.0.0.1"],

  // Keep Next's devtools launcher out of the dashboard viewport during local UI review.
  devIndicators: false,

  // Native modules that must not be bundled (loaded at runtime on server)
  serverExternalPackages: ["node-pty"],

  // Disable type checking during build for speed (run separately)
  typescript: {
    ignoreBuildErrors: process.env.SKIP_TYPE_CHECK === "true",
  },

  // Exclude non-web directories from output file tracing
  outputFileTracingExcludes: {
    "*": [
      "**/.venv/**",
      "docs/**",
      "**/__pycache__/**",
      "**/*.pyc",
      "**/.git/**",
      "next.config.*",
      "**/next.config.*",
    ],
  },

  // Turbopack config
  turbopack: {
    // Pin the workspace root to this dashboard dir. Without this, Turbopack
    // infers the root from the nearest lockfile and can wrongly select the
    // home directory when a stray ~/package-lock.json exists — which then
    // resolves `@import "tailwindcss"` against ~/node_modules and fails to
    // start the server. The pnpm workspace file lives here, so this is root.
    root: __dirname,
    resolveExtensions: [".tsx", ".ts", ".jsx", ".js", ".json"],
  },

  // Prevent 308 redirects on trailing-slash API requests (halves request count)
  skipTrailingSlashRedirect: true,

  // Experimental features
  experimental: {
    // Tree-shake barrel exports for heavy dependencies
    optimizePackageImports: [
      "lucide-react",
      "framer-motion",
      "recharts",
      "react-markdown",
      "monaco-editor",
      "@monaco-editor/react",
    ],
    // Cache server component HMR results between navigations (Next.js 15.1+)
    // Prevents full recompilation of unchanged server components on page nav.
    serverComponentsHmrCache: true,
    // parallelServerCompiles requires build workers — disabled for now
    // (Next.js 16.1 rejects it without NEXT_PRIVATE_WORKER=1).
  },

  // Webpack config for non-Turbopack builds
  webpack: (config) => {
    config.resolve = {
      ...(config.resolve || {}),
      symlinks: true,
    };

    // Ignore non-web files from webpack watcher (fallback for non-Turbopack builds)
    config.watchOptions = {
      ...(config.watchOptions || {}),
      ignored: [
        "**/.venv/**",
        "**/__pycache__/**",
        "**/*.py",
        "**/*.pyc",
        "**/node_modules/.cache/**",
      ],
    };

    return config;
  },

  // Security: Disable X-Powered-By header
  poweredByHeader: false,

  // Security: Add security headers
  async headers() {
    const isDev = process.env.NODE_ENV === "development";

    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: contentSecurityPolicy(isDev),
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value:
              "camera=(), microphone=(), geolocation=(), interest-cohort=()",
          },
          {
            key: "Cross-Origin-Opener-Policy",
            value: "same-origin",
          },
          {
            key: "Cross-Origin-Resource-Policy",
            value: "same-origin",
          },
        ],
      },
      // HSTS for production (HTTPS only)
      ...(isDev
        ? []
        : [
            {
              source: "/:path*",
              headers: [
                {
                  key: "Strict-Transport-Security",
                  value: "max-age=31536000; includeSubDomains; preload",
                },
              ],
            },
          ]),
      {
        source: "/:path*",
        has: [
          {
            type: "host",
            value: "(?:localhost|127\\.0\\.0\\.1)(?::\\d+)?",
          },
        ],
        headers: [
          {
            key: "Content-Security-Policy",
            value: contentSecurityPolicy(isDev, "'none'", {
              upgradeInsecureRequests: false,
            }),
          },
        ],
      },
      {
        source: "/api/artifact/:slug/raw",
        headers: [
          {
            key: "Content-Security-Policy",
            value: contentSecurityPolicy(isDev, "'self'"),
          },
          {
            key: "X-Frame-Options",
            value: "SAMEORIGIN",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
