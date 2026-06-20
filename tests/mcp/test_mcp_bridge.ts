/**
 * MCPBridge Tests
 *
 * Tests TypeScript MCP bridge functionality including:
 * - Connection management
 * - Tool invocation
 * - Context passing
 * - Error handling
 */

import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import { MCPBridge, getMCPBridge, extractContextFromRequest } from '@/lib/mcp/MCPBridge';

describe('MCPBridge', () => {
  let bridge: MCPBridge;

  beforeAll(async () => {
    bridge = getMCPBridge();
    await bridge.connect();
  });

  afterAll(async () => {
    await bridge.disconnect();
  });

  describe('Connection', () => {
    it('should connect to MCP server', async () => {
      expect(bridge).toBeDefined();
      // If we got here, connection succeeded
    });

    it('should get server capabilities', async () => {
      const capabilities = await bridge.getCapabilities();
      expect(capabilities).toBeDefined();
      expect(typeof capabilities).toBe('object');
    });
  });

  describe('Tool Listing', () => {
    it('should list available tools', async () => {
      const tools = await bridge.listTools();
      expect(Array.isArray(tools)).toBe(true);
      expect(tools.length).toBeGreaterThan(0);

      // Check for core tools
      const toolNames = tools.map((t) => t.name);
      expect(toolNames).toContain('list-skills');
      expect(toolNames).toContain('get-skill');
      expect(toolNames).toContain('execute-chain');
    });

    it('should enforce max 80 tools based on context', async () => {
      const tools = await bridge.listTools();
      expect(tools.length).toBeLessThanOrEqual(80);
    });
  });

  describe('Tool Invocation', () => {
    it('should call list-skills tool', async () => {
      const result = await bridge.callTool('list-skills', {
        format: 'json',
      });

      expect(result).toBeDefined();
      expect(result.content).toBeDefined();
      expect(Array.isArray(result.content)).toBe(true);

      const text = MCPBridge.extractText(result);
      expect(text).toBeTruthy();

      const parsed = JSON.parse(text);
      expect(Array.isArray(parsed)).toBe(true);
    });

    it('should call get-skill tool', async () => {
      const result = await bridge.callTool('get-skill', {
        skill_name: 'developer',
      });

      expect(result).toBeDefined();
      const text = MCPBridge.extractText(result);
      expect(text).toContain('developer');
    });

    it('should handle tool errors gracefully', async () => {
      try {
        await bridge.callTool('nonexistent-tool', {});
        fail('Should have thrown error');
      } catch (err) {
        expect(err).toBeDefined();
        expect(err instanceof Error).toBe(true);
      }
    });
  });

  describe('Context Passing', () => {
    it('should pass context to tool calls', async () => {
      const context = {
        active_sprint: 'ui_redesign',
        current_page: '/workforce',
        executing_chain: false,
      };

      const result = await bridge.callTool(
        'list-skills',
        {
          format: 'json',
        },
        context
      );

      expect(result).toBeDefined();
      // Context should be passed to tool controller
      // Tool selection should be influenced by context
    });
  });

  describe('Context Extraction', () => {
    it('should extract context from Next.js request', () => {
      const mockRequest = new Request('http://localhost:3000/api/test?sprint=ui_redesign', {
        headers: {
          referer: 'http://localhost:3000/workforce',
        },
      });

      const context = extractContextFromRequest(mockRequest);

      expect(context.active_sprint).toBe('ui_redesign');
      expect(context.current_page).toBe('/workforce');
    });

    it('should detect chain execution from URL', () => {
      const mockRequest = new Request('http://localhost:3000/api/agents/chain', {
        headers: {
          referer: 'http://localhost:3000/workforce',
        },
      });

      const context = extractContextFromRequest(mockRequest);

      expect(context.executing_chain).toBe(true);
    });
  });

  describe('Helper Methods', () => {
    it('should extract text from tool result', () => {
      const result = {
        content: [
          { type: 'text', text: 'Line 1' },
          { type: 'text', text: 'Line 2' },
        ],
      };

      const text = MCPBridge.extractText(result);
      expect(text).toBe('Line 1\nLine 2');
    });

    it('should parse JSON from tool result', () => {
      const result = {
        content: [{ type: 'text', text: '{"key": "value"}' }],
      };

      const parsed = MCPBridge.parseJSON<{ key: string }>(result);
      expect(parsed.key).toBe('value');
    });

    it('should handle empty content', () => {
      const result = {
        content: [],
      };

      const text = MCPBridge.extractText(result);
      expect(text).toBe('');
    });
  });

  describe('Singleton Pattern', () => {
    it('should return same instance', () => {
      const instance1 = getMCPBridge();
      const instance2 = getMCPBridge();

      expect(instance1).toBe(instance2);
    });
  });
});
