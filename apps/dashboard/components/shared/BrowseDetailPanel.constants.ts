import { File, Image, Link2, MessageSquare, Mic, Users } from 'lucide-react';
import type { SkillOwnership } from '@/lib/browse/types';

export const EMPTY_CAPTIONS_TRACK = 'data:text/vtt,WEBVTT%0A';

export const HEALTH_STYLES: Record<string, string> = {
  healthy: 'bg-[var(--accent-success)]/20 text-[var(--accent-success)]',
  degraded: 'bg-[var(--accent-warning)]/20 text-[var(--accent-warning)]',
  critical: 'bg-[var(--accent-danger)]/20 text-[var(--accent-danger)]',
  unknown: 'bg-[var(--text-muted)]/20 text-[var(--text-muted)]',
};

export const OWNERSHIP_STYLES: Record<SkillOwnership, string> = {
  augur: 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]',
  external: 'bg-[var(--text-muted)]/15 text-[var(--text-secondary)]',
  adopted: 'bg-[var(--accent-success)]/15 text-[var(--accent-success)]',
  user: 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]',
};

export const OWNERSHIP_LABELS: Record<SkillOwnership, string> = {
  augur: 'Augur',
  external: 'External',
  adopted: 'Adopted',
  user: 'User',
};

export const NOTE_TYPE_LABELS: Record<string, string> = {
  url: 'URL',
  file: 'File',
  thought: 'Thought',
  'voice-memo': 'Voice Memo',
  meeting: 'Meeting',
  image: 'Image',
  prompt: 'Prompt',
};

export const NOTE_TYPE_ICONS = {
  url: Link2,
  file: File,
  thought: MessageSquare,
  'voice-memo': Mic,
  meeting: Users,
  image: Image,
  prompt: MessageSquare,
} as const;

/** Categories whose items are genuine notes and keep the note-centric panel. */
export const NOTE_PANEL_CATEGORY_IDS = new Set(['notes', 'archive']);
export const NOTE_CLASSIFICATION_CATEGORY_IDS = new Set(['notes', 'archive']);

export const TEXT_FILE_EXTENSIONS = new Set([
  'md', 'mdx', 'markdown', 'txt', 'rst',
  'py', 'ts', 'tsx', 'js', 'jsx', 'mjs', 'cjs',
  'json', 'yaml', 'yml', 'toml', 'ini', 'cfg',
  'sh', 'bash', 'zsh', 'css', 'scss', 'sql', 'env', 'log',
]);
export const MARKDOWN_EXTENSIONS = new Set(['md', 'mdx', 'markdown']);
export const AUDIO_EXTENSIONS = new Set(['aac', 'flac', 'm4a', 'mp3', 'ogg', 'wav', 'webm']);
export const VIDEO_EXTENSIONS = new Set(['m4v', 'mov', 'mp4', 'webm']);

/** primaryAction types that executeBrowseAction can run with only a router. */
export const PRIMARY_SAFE_TYPES = new Set(['navigate', 'configure', 'extract-and-open-adr', 'copy', 'mcp-tool']);

export const SOURCE_LABELS: Record<string, string> = {
  'claude-local': 'Claude (local)',
  'claude-global': 'Claude (global)',
  'codex-local': 'Codex (local)',
  'codex-global': 'Codex (global)',
  'gemini-local': 'Gemini (local)',
  'gemini-global': 'Gemini (global)',
  'cursor-local': 'Cursor (local)',
  'cursor-global': 'Cursor (global)',
  'copilot-local': 'Copilot (local)',
  'copilot-global': 'Copilot (global)',
  'opencode-local': 'OpenCode (local)',
  'opencode-global': 'OpenCode (global)',
};
