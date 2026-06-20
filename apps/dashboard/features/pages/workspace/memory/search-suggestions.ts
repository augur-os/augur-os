'use client';

import type { MemoryStats } from './types';
import type { MemorySearchSuggestion } from './components/MemorySearchWidget';

const SUGGESTION_STOPWORDS = new Set([
  'and',
  'what',
  'was',
  'were',
  'where',
  'should',
  'for',
  'the',
  'on',
  'store',
  'from',
  'this',
  'that',
  'about',
  'into',
  'with',
  'after',
  'before',
  'implemented',
  'clarified',
  'split',
  'conversation',
  'april',
  'brainstorming',
]);

function topicToSuggestion(topic: string) {
  const tokens = topic
    .toLowerCase()
    .replace(/[^a-z0-9\s/-]+/g, ' ')
    .split(/\s+/)
    .filter((token) => token.length > 2 && !SUGGESTION_STOPWORDS.has(token) && !/^\d+$/.test(token));
  return tokens.slice(0, 5).join(' ').trim();
}

export function buildSuggestedQueries(stats: MemoryStats | null) {
  const suggestions: MemorySearchSuggestion[] = [];
  for (const decision of stats?.recentDecisions ?? []) {
    const topicSuggestion = decision.topic ? topicToSuggestion(decision.topic) : '';
    if (topicSuggestion) {
      suggestions.push({
        label: topicSuggestion,
        query: decision.topic,
        category: 'decision',
        source: 'curated',
      });
    }
  }
  const topCategory = Object.entries(stats?.categoryCounts ?? {}).reduce<
    [string, number] | null
  >((top, entry) => (top === null || entry[1] > top[1] ? entry : top), null)?.[0];
  if (topCategory) {
    suggestions.push({
      label: `${topCategory} decisions`,
      query: topCategory,
      category: 'decision',
      source: 'curated',
    });
  }
  if ((stats?.totalPreferences ?? 0) > 0) {
    suggestions.push({
      label: 'communication preferences',
      query: 'communication preferences',
      category: 'preference',
      source: 'curated',
    });
  }
  if ((stats?.totalPatterns ?? 0) > 0) {
    suggestions.push({
      label: 'recurring patterns',
      query: 'recurring patterns',
      category: 'pattern',
      source: 'curated',
    });
  }
  suggestions.push({
    label: 'recent decisions',
    query: 'recent decisions',
    category: 'decision',
    source: 'curated',
  });

  const deduped = new Map<string, MemorySearchSuggestion>();
  for (const suggestion of suggestions) {
    deduped.set(suggestion.label.toLowerCase(), suggestion);
  }
  return Array.from(deduped.values()).slice(0, 4);
}
