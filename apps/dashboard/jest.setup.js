import "@testing-library/jest-dom";
import { TextEncoder, TextDecoder } from "util";

global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

// Mock child_process to prevent absolute paths/python spawning in tests
jest.mock("child_process", () => ({
  exec: jest.fn((cmd, options, cb) => {
    const callback = typeof options === "function" ? options : cb;
    if (callback) callback(null, { stdout: "", stderr: "" });
  }),
  execFile: jest.fn((cmd, args, options, cb) => {
    const callback = typeof options === "function" ? options : cb;
    if (callback) callback(null, { stdout: "", stderr: "" });
  }),
  spawn: jest.fn(() => ({
    on: jest.fn(),
    stdout: { on: jest.fn() },
    stderr: { on: jest.fn() },
  })),
}));

// Mock MCP Bridge globally — routes use callMCPTool which requires a live MCP server.
// Individual tests can override via jest.spyOn or per-test jest.mock.
jest.mock("./lib/mcp/MCPBridge", () => ({
  callMCPTool: jest.fn().mockResolvedValue({
    content: [{ type: "text", text: "{}" }],
  }),
  MCPBridge: {
    parseJSON: jest.fn((result) => {
      try {
        const text =
          result?.content?.[0]?.text ?? result?.text ?? JSON.stringify(result);
        return typeof text === "string" ? JSON.parse(text) : text;
      } catch {
        return {};
      }
    }),
    extractText: jest.fn((result) => {
      return result?.content?.[0]?.text ?? "";
    }),
  },
  extractContextFromRequest: jest.fn(() => ({})),
}));

// Mock ResizeObserver (not available in JSDOM, used by UnifiedHubTabs)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Polyfill globals for Next.js App Router components using fetch/Request
if (typeof global.Request === "undefined") {
  global.Request = class Request {
    constructor(input, init) {
      this.url = input;
      this.method = init?.method || "GET";
      this.headers = new Headers(init?.headers);
    }
  };
}
if (typeof global.Response === "undefined" || typeof global.Response.json !== "function") {
  global.Response = class Response {
    constructor(body, init) {
      this._body = body ?? "";
      this.body = this._body;
      this.status = init?.status || 200;
      this.statusText = init?.statusText || "";
      this.ok = this.status >= 200 && this.status < 300;
      this.headers = new Headers(init?.headers);
    }

    async json() {
      if (typeof this._body === "string") {
        return JSON.parse(this._body || "{}");
      }
      return this._body;
    }

    async text() {
      return typeof this._body === "string"
        ? this._body
        : JSON.stringify(this._body ?? {});
    }

    clone() {
      return new global.Response(this._body, {
        status: this.status,
        statusText: this.statusText,
        headers: this.headers,
      });
    }

    static json(data, init) {
      return new global.Response(JSON.stringify(data), {
        ...init,
        headers: {
          "content-type": "application/json",
          ...(init?.headers || {}),
        },
      });
    }
  };
}
if (typeof global.Headers === "undefined") {
  global.Headers = class Headers {
    constructor(init) {
      this.map = new Map(Object.entries(init || {}));
    }
    get(name) {
      return this.map.get(name);
    }
    set(name, value) {
      this.map.set(name, value);
    }
  };
}
if (typeof global.ReadableStream === "undefined") {
  const { ReadableStream } = require("stream/web");
  global.ReadableStream = ReadableStream;
}

// Global fetch mock for environments that lack it (like JSDOM)
if (typeof global.fetch === "undefined") {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve(""),
    }),
  );

  // Also mock Request/Response if not present (handled above, but fetch needs them mostly)
}

/**
 * Jest Test Setup
 *
 * Runs before all tests to configure test environment
 */

// Set test environment variables
process.env.NODE_ENV = "test";
process.env.API_URL = process.env.API_URL || "http://localhost:3000";

// Mock next/cache for unstable_cache
// In Jest (JSDOM), the Next.js Server Runtime is not available.
// We use an identity mock (fn => fn) to execute the inner logic directly,
// allowing tests to verify data fetching without needing the actual cache infrastructure.
jest.mock("next/cache", () => ({
  unstable_cache: (fn) => fn,
  revalidatePath: jest.fn(),
  revalidateTag: jest.fn(),
}));

// Increase timeout for slow CI environments
jest.setTimeout(30000);

// Global test utilities
global.beforeAll(() => {
  console.log("Starting E2E test suite...");
  console.log(`Testing API at: ${process.env.API_URL}`);
});

global.afterAll(() => {
  console.log("E2E test suite completed");
});

// Suppress console.error in tests unless explicitly testing errors
const originalError = console.error;
beforeAll(() => {
  console.error = (...args) => {
    if (
      typeof args[0] === "string" &&
      (args[0].includes("Warning:") || args[0].includes("Error:"))
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});
