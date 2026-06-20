import { createElement, type ComponentType } from 'react';
import dynamic from 'next/dynamic';
import { notFound } from 'next/navigation';
import { PAGES } from './registry';
import { BrainOverviewHome } from '@/features/pages/workspace/overview/BrainOverviewHome';

const DYNAMIC_PAGES: Record<string, ComponentType> = Object.fromEntries(
  Object.entries(PAGES).map(([path, loader]) => [
    path,
    dynamic(loader, {
      loading: () => (
        <div className="space-y-4 animate-pulse min-h-[200px] p-4">
          <div className="h-6 w-48 rounded-lg bg-[var(--bg-secondary)]" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="h-32 rounded-xl bg-[var(--bg-secondary)]" />
            <div className="h-32 rounded-xl bg-[var(--bg-secondary)]" />
          </div>
          <div className="h-24 rounded-xl bg-[var(--bg-secondary)]" />
        </div>
      ),
    }),
  ]),
);

function renderDynamicPage(path: string) {
  const page = DYNAMIC_PAGES[path];
  return page ? createElement(page) : null;
}

interface HubPageProps {
  params: Promise<{
    slug?: string[];
  }>;
}

export default async function HubPage(props: HubPageProps) {
  const { slug } = await props.params;
  const path = slug?.join('/') ?? '';

  if (!path) {
    return <BrainOverviewHome />;
  }

  const page = renderDynamicPage(path);
  if (!page) {
    notFound();
  }

  return page;
}
