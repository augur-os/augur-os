'use client';

import React from 'react';
import { Sparkles, Download, FolderInput, FileText, ArrowUpCircle, ShoppingBag } from 'lucide-react';

export type AddSkillStep =
  | 'cards'
  | 'install-url'
  | 'import-data'
  | 'import-notion'
  | 'promote'
  | 'success';

interface CardDef {
  id: AddSkillStep | 'create' | 'skillstore';
  title: string;
  description: string;
  icon: React.ReactNode;
  badge: 'cli' | 'in-app';
  iconBg: string;
}

const CARDS: CardDef[] = [
  {
    id: 'create',
    title: 'Create from Scratch',
    description: 'Scaffold a new skill with AI assistance in the default CLI.',
    icon: <Sparkles className="size-4 text-indigo-400" />,
    badge: 'cli',
    iconBg: 'bg-indigo-950',
  },
  {
    id: 'install-url',
    title: 'Install from URL',
    description: 'Install a skill from GitHub, a local path, or any URL with a SKILL.md.',
    icon: <Download className="size-4 text-green-400" />,
    badge: 'in-app',
    iconBg: 'bg-green-950',
  },
  {
    id: 'import-data',
    title: 'Import Data Folder',
    description: 'Import a local folder of files (CSV, Excel, PDF, Markdown) as a new skill.',
    icon: <FolderInput className="size-4 text-yellow-400" />,
    badge: 'in-app',
    iconBg: 'bg-yellow-950',
  },
  {
    id: 'import-notion',
    title: 'Import from Notion',
    description: 'Import a Notion workspace export (ZIP or directory) with smart format detection.',
    icon: <FileText className="size-4 text-yellow-400" />,
    badge: 'in-app',
    iconBg: 'bg-yellow-950',
  },
  {
    id: 'promote',
    title: 'Promote Client Skill',
    description: 'Move a skill from .claude/skills/, .codex/prompts/, or .gemini/skills/ into Augur.',
    icon: <ArrowUpCircle className="size-4 text-purple-400" />,
    badge: 'in-app',
    iconBg: 'bg-purple-950',
  },
  {
    id: 'skillstore',
    title: 'Browse Skillstore',
    description: 'Search and install community skills from skills.sh and GitHub.',
    icon: <ShoppingBag className="size-4 text-cyan-400" />,
    badge: 'cli',
    iconBg: 'bg-cyan-950',
  },
];

interface AddSkillCardsProps {
  onSelectStep: (step: AddSkillStep) => void;
  onIdeDispatch: (actionId: string, prompt: string) => void;
}

export function AddSkillCards({ onSelectStep, onIdeDispatch }: AddSkillCardsProps) {
  const handleClick = (card: CardDef) => {
    if (card.id === 'create') {
      onIdeDispatch(
        'new-skills',
        'Create a new skill in the Augur project. Ask me what the skill should do, which hub/bundle it belongs to, and what capabilities it needs.',
      );
    } else if (card.id === 'skillstore') {
      onIdeDispatch(
        'skillstore-browse',
        'Browse the skillstore at skills.sh and help me find and install a community skill.',
      );
    } else {
      onSelectStep(card.id as AddSkillStep);
    }
  };

  return (
    <div>
      <h3 className="mb-1 text-lg font-semibold text-foreground">Add Skill</h3>
      <p className="mb-5 text-sm text-muted-foreground">
        Choose how you want to add a new skill to Augur
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {CARDS.map((card) => (
          <button type="button"
            key={card.id}
            onClick={() => handleClick(card)}
            aria-describedby="skill-dispatch-legend"
            className="flex flex-col items-start rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary"
          >
            <div className="mb-2 flex items-center gap-2.5">
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${card.iconBg}`}>
                {card.icon}
              </div>
              <span className="text-sm font-semibold text-foreground">{card.title}</span>
            </div>
            <p className="mb-2 text-xs leading-relaxed text-muted-foreground">{card.description}</p>
            <span
              className={`text-[10px] rounded px-1.5 py-0.5 font-medium ${
                card.badge === 'cli'
                  ? 'bg-indigo-950 text-indigo-400'
                  : 'bg-green-950 text-green-400'
              }`}
            >
              {card.badge === 'cli' ? 'CLI' : 'In-app'}
            </span>
          </button>
        ))}
      </div>
      <p id="skill-dispatch-legend" className="mt-4 text-[11px] text-muted-foreground/60">
        <span className="text-indigo-400">CLI</span> = runs in the default CLI{' '}
        <span className="mx-1">·</span>{' '}
        <span className="text-green-400">In-app</span> = form and preview in this dialog
      </p>
    </div>
  );
}
