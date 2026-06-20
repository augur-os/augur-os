import nextConfig from "../../../apps/dashboard/next.config";

describe("dashboard next config", () => {
  it("allows localhost and 127.0.0.1 as dev origins", () => {
    expect(Array.isArray(nextConfig.allowedDevOrigins)).toBe(true);
    expect(nextConfig.allowedDevOrigins).toEqual(
      expect.arrayContaining(["localhost", "127.0.0.1"]),
    );
  });

  it("excludes build-time Next config files from runtime file traces", () => {
    expect(nextConfig.outputFileTracingExcludes?.["*"]).toEqual(
      expect.arrayContaining(["next.config.*", "**/next.config.*"]),
    );
  });

  it("does not mutate readonly nested webpack config objects", () => {
    const watchOptions = Object.freeze({ aggregateTimeout: 100 });
    const resolve = Object.freeze({ extensions: [".tsx"] });
    const config = { watchOptions, resolve };

    const result = nextConfig.webpack?.(
      config as never,
      {} as never,
    ) as typeof config;

    expect(result.watchOptions).not.toBe(watchOptions);
    expect(result.watchOptions).toMatchObject({
      aggregateTimeout: 100,
      ignored: expect.arrayContaining(["**/.venv/**", "**/*.py"]),
    });
    expect(result.resolve).not.toBe(resolve);
    expect(result.resolve).toMatchObject({
      extensions: [".tsx"],
      symlinks: true,
    });
  });

  it("allows same-origin embedding for artifact raw HTML", async () => {
    const headers = await nextConfig.headers?.();
    const artifactRawHeaders = headers?.find(
      (entry) => entry.source === "/api/artifact/:slug/raw",
    )?.headers;

    expect(artifactRawHeaders).toEqual(
      expect.arrayContaining([
        {
          key: "Content-Security-Policy",
          value: expect.stringContaining("frame-ancestors 'self'"),
        },
        { key: "X-Frame-Options", value: "SAMEORIGIN" },
      ]),
    );
  });

  it("does not upgrade HTTP localhost resources in production CSP", async () => {
    const headers = await nextConfig.headers?.();
    const localhostHeaders = headers?.find(
      (entry) =>
        entry.source === "/:path*" &&
        entry.has?.some(
          (condition) =>
            condition.type === "host" &&
            condition.value?.includes("localhost"),
        ),
    )?.headers;

    expect(localhostHeaders).toEqual(
      expect.arrayContaining([
        {
          key: "Content-Security-Policy",
          value: expect.not.stringContaining("upgrade-insecure-requests"),
        },
      ]),
    );
  });
});
