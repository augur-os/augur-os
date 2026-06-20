import { redactPaths, stripPayloadPII } from '@/lib/help/stripPII';

describe('stripPII utilities', () => {
  describe('redactPaths', () => {
    it('redacts macOS and Windows home paths and local hostnames', () => {
      const input =
        'Open /Users/jane doe/Projects/Augur/file.ts and C:\\Users\\John Smith\\AppData\\Local\\Temp\\a.log on macbook.local';
      const output = redactPaths(input);

      expect(output).toContain('/[HOME]/Projects/Augur/file.ts');
      expect(output).toContain('C:\\[HOME]\\AppData\\Local\\Temp\\a.log');
      expect(output).toContain('[HOSTNAME].local');
      expect(output).not.toContain('/Users/jane doe/');
      expect(output).not.toContain('C:\\Users\\John Smith\\');
      expect(output).not.toContain('macbook.local');
    });
  });

  describe('stripPayloadPII', () => {
    it('sanitizes description, context page, and browser errors while preserving email opt-in', () => {
      const payload = {
        topic: 'bug' as const,
        description:
          'Contact me at jane@example.com with key sk-abcdefghijklmnopqrstuvwxyz1234567890 from /Users/janedoe/Projects/Augur',
        context: {
          page: '/Users/janedoe/Projects/Augur/apps/dashboard',
          skill: 'daemon',
          mode: 'operation',
          browser: 'chrome',
        },
        logs: {
          browserErrors: [
            'Error from macbook.local user john@example.com at C:\\Users\\John\\logs\\debug.txt',
          ],
        },
        supportToken: 'token-1',
        timestamp: '2026-02-11T00:00:00.000Z',
        email_notification: 'alerts@example.com',
      };

      const result = stripPayloadPII(payload);

      expect(result.cleaned.description).toContain('[REDACTED]');
      expect(result.cleaned.description).toContain('/[HOME]/Projects/Augur');
      expect(result.cleaned.description).not.toContain('sk-abcdefghijklmnopqrstuvwxyz1234567890');
      expect(result.cleaned.description).not.toContain('/Users/janedoe/');

      expect(result.cleaned.context.page).toContain('/[HOME]/Projects/Augur/apps/dashboard');
      expect(result.cleaned.logs?.browserErrors[0]).toContain('[HOSTNAME].local');
      expect(result.cleaned.logs?.browserErrors[0]).toContain('C:\\[HOME]\\logs\\debug.txt');

      expect(result.cleaned.email_notification).toBe('alerts@example.com');
      expect(result.strippedItems.length).toBeGreaterThan(0);
      expect(result.strippedItems.some(item => item.type === 'Email')).toBe(true);
      expect(result.strippedItems.some(item => item.type === 'OpenAI Key')).toBe(true);
    });

    it('handles payloads without logs and without email notification', () => {
      const payload = {
        topic: 'general' as const,
        description: 'No sensitive data here',
        context: {
          page: '/health',
          skill: null,
          mode: 'operation',
          browser: 'chrome',
        },
        supportToken: 'token-2',
        timestamp: '2026-02-11T00:00:00.000Z',
      };

      const result = stripPayloadPII(payload);
      expect(result.cleaned.logs).toBeUndefined();
      expect(result.cleaned.email_notification).toBeUndefined();
      expect(result.cleaned.description).toBe('No sensitive data here');
      expect(result.strippedItems).toHaveLength(0);
    });
  });
});
