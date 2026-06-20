'use client';

// Stable re-export barrel (WS5). The implementation was decomposed into cohesive
// siblings (BrowseDetailPanel.{constants,types,helpers,sections,views,main}); this
// file preserves the public import surface "@/components/shared/BrowseDetailPanel"
// with its two named exports unchanged.
export { BrowseItemDetailPanel } from './BrowseDetailPanel.main';
export { BrowseDetailPanel } from './BrowseDetailPanel.main';
