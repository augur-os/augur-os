/**
 * API Test Utilities
 *
 * Shared helpers for API route testing:
 * - MCP mock setup
 * - Request factories
 * - Response assertions
 * - Route discovery utilities
 */

import { jest } from '@jest/globals';

/**
 * Type for MCP tool result structure
 */
export interface MCPToolResult {
  content: Array<{
    type: string;
    text: string;
  }>;
  isError?: boolean;
}

/**
 * Create a successful MCP tool result payload
 */
export function makeToolResult(payload: unknown): MCPToolResult {
  return {
    content: [
      {
        type: 'text',
        text: typeof payload === 'string' ? payload : JSON.stringify(payload),
      },
    ],
  };
}

/**
 * Create an error MCP tool result
 */
export function makeErrorResult(message: string): MCPToolResult {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify({ error: message }),
      },
    ],
    isError: true,
  };
}

/**
 * Create a mock request for GET endpoints
 */
export function createGetRequest(
  path: string,
  queryParams?: Record<string, string>
): Request {
  const url = new URL(path, 'http://localhost');
  if (queryParams) {
    Object.entries(queryParams).forEach(([key, value]) => {
      url.searchParams.set(key, value);
    });
  }
  const req = new Request(url.toString(), { method: 'GET' }) as any;
  req.nextUrl = url;
  return req;
}

/**
 * Create a mock request for POST endpoints
 */
export function createPostRequest(path: string, body: unknown): Request {
  return new Request(`http://localhost${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * Create a mock request for PUT endpoints
 */
export function createPutRequest(path: string, body: unknown): Request {
  return new Request(`http://localhost${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * Create a mock request for DELETE endpoints
 */
export function createDeleteRequest(
  path: string,
  queryParams?: Record<string, string>
): Request {
  const url = new URL(path, 'http://localhost');
  if (queryParams) {
    Object.entries(queryParams).forEach(([key, value]) => {
      url.searchParams.set(key, value);
    });
  }
  return new Request(url.toString(), { method: 'DELETE' });
}

/**
 * Parse and validate a JSON response
 */
export async function parseJsonResponse<T = unknown>(
  response: Response
): Promise<{ status: number; data: T }> {
  const data = await response.json();
  return { status: response.status, data };
}

/**
 * Assert response is a successful JSON response
 */
export async function expectSuccessResponse<T = unknown>(
  response: Response,
  statusCode = 200
): Promise<T> {
  expect(response.status).toBe(statusCode);
  const data = await response.json();
  return data as T;
}

/**
 * Assert response is an error response
 */
export async function expectErrorResponse(
  response: Response,
  expectedStatus: number,
  errorContains?: string
): Promise<{ error: string }> {
  expect(response.status).toBe(expectedStatus);
  const data = await response.json();
  expect(data).toHaveProperty('error');
  if (errorContains) {
    expect(data.error.toLowerCase()).toContain(errorContains.toLowerCase());
  }
  return data;
}

/**
 * HTTP method types for route handlers
 */
export type HTTPMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Route handler type (Next.js App Router)
 */
export type RouteHandler = (
  req: Request,
  context?: { params?: Record<string, string | string[]> | Promise<Record<string, string | string[]>> }
) => Promise<Response>;

/**
 * Route info for discovered routes
 */
export interface RouteInfo {
  path: string;
  filePath: string;
  methods: HTTPMethod[];
  isDynamic: boolean;
  dynamicSegments: string[];
}

/**
 * Setup standard MCP mock implementation
 * Returns the mock function for custom implementations
 */
export function setupMCPMock(): jest.Mock {
  const mockCallMCPTool = jest.fn();

  // Default implementation returns empty success
  mockCallMCPTool.mockResolvedValue(makeToolResult({ success: true }));

  return mockCallMCPTool;
}

/**
 * Create a mock implementation that handles multiple tools
 */
export function createMultiToolMock(
  toolHandlers: Record<string, unknown>
): jest.Mock {
  const mock = jest.fn();

  mock.mockImplementation(async (toolName: string) => {
    if (toolName in toolHandlers) {
      return makeToolResult(toolHandlers[toolName]);
    }
    return makeToolResult({ error: `Unknown tool: ${toolName}` });
  });

  return mock;
}

/**
 * Time assertions for performance testing
 */
export async function measureResponseTime<T>(
  fn: () => Promise<T>
): Promise<{ result: T; durationMs: number }> {
  const start = performance.now();
  const result = await fn();
  const durationMs = performance.now() - start;
  return { result, durationMs };
}

/**
 * Assert response time is within limit
 */
export async function expectFastResponse<T>(
  fn: () => Promise<T>,
  maxMs = 200
): Promise<T> {
  const { result, durationMs } = await measureResponseTime(fn);
  expect(durationMs).toBeLessThan(maxMs);
  return result;
}

/**
 * Extract path parameters from a dynamic route
 * e.g., '/api/users/[id]/posts/[postId]' + '/api/users/123/posts/456'
 * returns { id: '123', postId: '456' }
 */
export function extractPathParams(
  routePattern: string,
  actualPath: string
): Record<string, string> {
  const params: Record<string, string> = {};
  const patternParts = routePattern.split('/');
  const actualParts = actualPath.split('/');

  patternParts.forEach((part, index) => {
    if (part.startsWith('[') && part.endsWith(']')) {
      const paramName = part.slice(1, -1);
      params[paramName] = actualParts[index] || '';
    }
  });

  return params;
}

/**
 * Check if a route pattern matches a path
 */
export function matchesRoute(routePattern: string, path: string): boolean {
  const patternParts = routePattern.split('/');
  const pathParts = path.split('/');

  if (patternParts.length !== pathParts.length) {
    return false;
  }

  return patternParts.every((part, index) => {
    if (part.startsWith('[') && part.endsWith(']')) {
      return true; // Dynamic segment matches anything
    }
    return part === pathParts[index];
  });
}
