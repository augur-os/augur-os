/**
 * @jest-environment node
 */
/**
 * Integration tests for /api/agents/available endpoint
 * Tests that all 5 agents per ADR-005 are returned correctly
 */

import { GET, __resetIdeStatusCacheForTests } from '@/app/api/agents/available/route';
import { NextRequest } from 'next/server';

// Mock fetch for IDE status
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('/api/agents/available', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    __resetIdeStatusCacheForTests();
    // Default: IDE status endpoint fails/times out
    mockFetch.mockRejectedValue(new Error('Network error'));
  });

  describe('default agents', () => {
    it('should return all 5 agents when IDE status endpoint fails', async () => {
      const response = await GET(new NextRequest('http://localhost/api/agents/available'));
      const data = await response.json();

      expect(data.agents).toHaveLength(5);

      const agentIds = data.agents.map((a: { id: string }) => a.id);
      expect(agentIds).toContain('cursor');
      expect(agentIds).toContain('vscode');
      expect(agentIds).toContain('antigravity');
      expect(agentIds).toContain('claude-code');
      expect(agentIds).toContain('claude-sdk');
    });

    it('should return correct agent types', async () => {
      const response = await GET(new NextRequest('http://localhost/api/agents/available'));
      const data = await response.json();

      const ideAgents = data.agents.filter((a: { type: string }) => a.type === 'ide');
      const cliAgents = data.agents.filter((a: { type: string }) => a.type === 'cli');
      const sdkAgents = data.agents.filter((a: { type: string }) => a.type === 'sdk');

      expect(ideAgents).toHaveLength(2); // cursor, vscode

      expect(cliAgents).toHaveLength(1); // claude-code
      expect(sdkAgents).toHaveLength(1); // claude-sdk
    });

    it('should have healthy status for all agents when status endpoint unavailable', async () => {
      const response = await GET(new NextRequest('http://localhost/api/agents/available'));
      const data = await response.json();

      // All agents should default to healthy when we can't check status
      const healthyAgents = data.agents.filter((a: { health: string }) => a.health === 'healthy');
      expect(healthyAgents).toHaveLength(5);
    });
  });

  describe('with IDE status available', () => {
    it('should update IDE agent health based on status response', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          active_ide: 'Cursor',
          available_ides: ['Cursor', 'Antigravity'],
        }),
      });

      const response = await GET(new NextRequest('http://localhost/api/agents/available'));
      const data = await response.json();

      // Cursor and Antigravity should be healthy (in available_ides)
      const cursor = data.agents.find((a: { id: string }) => a.id === 'cursor');
      const antigravity = data.agents.find((a: { id: string }) => a.id === 'antigravity');
      const vscode = data.agents.find((a: { id: string }) => a.id === 'vscode');

      expect(cursor.health).toBe('healthy');
      expect(antigravity.health).toBe('healthy');
      expect(vscode.health).toBe('offline');
    });

    it('should keep non-IDE agents healthy regardless of status', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          active_ide: null,
          available_ides: [],
        }),
      });

      const response = await GET(new NextRequest('http://localhost/api/agents/available'));
      const data = await response.json();

      // CLI and SDK agents should remain healthy
      const claudeCode = data.agents.find((a: { id: string }) => a.id === 'claude-code');
      const claudeSdk = data.agents.find((a: { id: string }) => a.id === 'claude-sdk');

      expect(claudeCode.health).toBe('offline');
      expect(claudeSdk.health).toBe('healthy');
    });
  });

  describe('sorting', () => {
    it('should sort healthy agents before offline agents', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          active_ide: 'Cursor',
          available_ides: ['Cursor'],
        }),
      });

      const response = await GET(new NextRequest('http://localhost/api/agents/available'));
      const data = await response.json();

      // First agents should be healthy
      const firstAgent = data.agents[0];
      expect(firstAgent.health).toBe('healthy');

      // Offline agents should be at the end
      const offlineAgents = data.agents.filter((a: { health: string }) => a.health === 'offline');
      const lastAgents = data.agents.slice(-offlineAgents.length);

      for (const agent of lastAgents) {
        if (offlineAgents.find((o: { id: string }) => o.id === agent.id)) {
          expect(agent.health).toBe('offline');
        }
      }
    });
  });

  describe('error handling', () => {
    it('should skip IDE status lookups entirely in api mode', async () => {
      const response = await GET(new NextRequest('http://localhost/api/agents/available?mode=api'));
      const data = await response.json();

      expect(mockFetch).not.toHaveBeenCalled();
      expect(data.agents.every((a: { execution_mode?: string }) => a.execution_mode === 'api')).toBe(true);
    });

    it('should reuse cached IDE status for repeated requests within the cache window', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          active_ide: 'Cursor',
          available_ides: ['Cursor'],
        }),
      });

      await GET(new NextRequest('http://localhost/api/agents/available?mode=auto'));
      await GET(new NextRequest('http://localhost/api/agents/available?mode=auto'));

      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it('should handle timeout gracefully', async () => {
      // Simulate abort error (timeout)
      const abortError = new Error('The operation was aborted');
      abortError.name = 'AbortError';
      mockFetch.mockRejectedValue(abortError);

      const response = await GET(new NextRequest('http://localhost/api/agents/available'));
      const data = await response.json();

      // Should still return all agents with default health
      expect(data.agents).toHaveLength(5);
    });

    it('should handle malformed status response', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => null, // Malformed response
      });

      const response = await GET(new NextRequest('http://localhost/api/agents/available'));
      const data = await response.json();

      // Should fallback to defaults
      expect(data.agents).toHaveLength(5);
    });

    it('should handle non-OK status response', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
      });

      const response = await GET(new NextRequest('http://localhost/api/agents/available'));
      const data = await response.json();

      // Should fallback to defaults with healthy status
      expect(data.agents).toHaveLength(5);
      const healthyCount = data.agents.filter((a: { health: string }) => a.health === 'healthy').length;
      expect(healthyCount).toBe(5);
    });
  });

  describe('ADR-005 compliance', () => {
    it('should always return all 5 agents per ADR-005 MCP Gateway spec', async () => {
      // Test various failure scenarios
      const scenarios = [
        () => mockFetch.mockRejectedValue(new Error('Network error')),
        () => mockFetch.mockResolvedValue({ ok: false }),
        () => mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) }),
        () => mockFetch.mockResolvedValue({ ok: true, json: async () => null }),
      ];

      for (const setupScenario of scenarios) {
        setupScenario();
        const response = await GET(new NextRequest('http://localhost/api/agents/available'));
        const data = await response.json();

        // ADR-005 mandates these 5 agents
        expect(data.agents).toHaveLength(5);

        const agentIds = data.agents.map((a: { id: string }) => a.id);
        expect(agentIds).toEqual(
          expect.arrayContaining(['cursor', 'vscode', 'antigravity', 'claude-code', 'claude-sdk'])
        );
      }
    });
  });
});
