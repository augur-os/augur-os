<\!-- Canonical source: apps/dashboard/docs/references/design-standards.md -->
# Frontend Design Standards

## Reference Implementation

**🎯 Canonical Design Pattern**: http://localhost:3000/sense
**Component**: `apps/dashboard/components/ui/GlassCard.tsx`

**When refactoring or creating pages, use `/sense` as the design reference.** This page demonstrates:
- Glass morphism cards with gradient overlays
- Gradient icons with color schemes
- Hover glow effects with blur
- Proper z-index layering (content over background)
- Color-coded card variants (cyan, purple, emerald, amber, blue, rose, violet, pink)

See the GlassCard component documentation below for detailed patterns.

## Tab Registry System

All hub tabs are defined in a central registry at `apps/dashboard/lib/tabs/registry.ts`. This is the **single source of truth** for tab configurations.

### Key Files

| File | Purpose |
|------|---------|
| `lib/tabs/registry.ts` | Central tab definitions for all 14 hubs |
| `lib/tabs/types.ts` | TypeScript types for TabItem and HubConfig |
| `scripts/validate-tab-registry.ts` | CI validation script |

### Using the Registry in Layouts

All hub layouts should use the tab registry pattern:

```tsx
import UnifiedHubTabs from '@/components/UnifiedHubTabs';
import { tabRegistry } from '@/lib/tabs/registry';
import { Rocket } from 'lucide-react';

const hub = tabRegistry.venture;

export default function VentureLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-6">
      <header className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
            <Rocket className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <h1 className="page-title from-emerald-400 to-teal-400">{hub.title}</h1>
            <p className="page-subtitle mt-1">{hub.subtitle}</p>
          </div>
        </div>
      </header>

      <UnifiedHubTabs tabs={hub.tabs} mode="path" />

      <div>{children}</div>
    </div>
  );
}
```

### Adding New Tabs

1. Add the tab to `lib/tabs/registry.ts`:
   ```typescript
   venture: {
     tabs: [
       // ... existing tabs
       { id: 'new-tab', label: 'New Tab', icon: 'Sparkles', href: '/venture/new-tab' },
     ],
   },
   ```

2. Create the corresponding folder: `app/venture/new-tab/page.tsx`

3. The CI pipeline will validate that all tab hrefs have matching folders.

### Icon Format

Icons in the registry are stored as **string names** (e.g., `'LayoutDashboard'`, `'Users'`) to allow Server Components to pass tabs to Client Components without serialization issues.

## GlassCard Component System

The `GlassCard` component (`apps/dashboard/components/ui/GlassCard.tsx`) is the **standard card component** for all dashboard pages.

### Available Components

| Component | Use Case |
|-----------|----------|
| `GlassCard` | Standard content card with optional header |
| `GlassCardIcon` | Standalone gradient icon |
| `GlassLinkCard` | Clickable navigation card with stats |

### Color Schemes

```typescript
type GlassCardColor = 'cyan' | 'purple' | 'emerald' | 'amber' | 'blue' | 'rose' | 'violet' | 'pink'
```

### Usage Examples

```tsx
import { GlassCard, GlassLinkCard, GlassCardIcon } from '@/components/ui/GlassCard';
import { Inbox, Brain } from 'lucide-react';

// Standard card with header
<GlassCard color="purple" icon={Inbox} title="Inbox" subtitle="5 items pending">
  <div className="space-y-2">
    {items.map(item => <ItemRow key={item.id} {...item} />)}
  </div>
</GlassCard>

// Clickable link card (for domain/capability grids)
<GlassLinkCard
  href="/inbox"
  color="purple"
  icon={Inbox}
  title="Inbox"
  stat={12}
  subtitle="Items to process"
  actionHint="Click to view"
/>

// Standalone gradient icon
<GlassCardIcon icon={Brain} color="cyan" size="lg" />
```

### Core Pattern (Manual Implementation)

If you need to implement the pattern manually without the component:

```tsx
<div className="group relative overflow-hidden rounded-xl border border-white/10 bg-neutral-900/50 p-5 transition-all duration-300 hover:bg-neutral-900/70 hover:scale-[1.02]">
  {/* Background gradient overlay */}
  <div className="absolute inset-0 bg-gradient-to-br from-purple-950/20 via-transparent to-transparent pointer-events-none" />

  {/* Hover glow effect (interactive cards only) */}
  <div className="absolute inset-0 bg-purple-500/20 opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-300" />

  {/* Content - MUST be relative z-10 */}
  <div className="relative z-10">
    {/* Gradient icon */}
    <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500">
      <Icon className="w-5 h-5 text-white" />
    </div>
    {/* ... rest of content */}
  </div>
</div>
```

### Anti-Patterns

```tsx
// ❌ WRONG - Icon not using gradient
<div className="p-2 rounded-lg bg-purple-500">
  <Icon className="w-5 h-5 text-white" />
</div>

// ✅ CORRECT - Gradient icon
<div className="p-2 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500">
  <Icon className="w-5 h-5 text-white" />
</div>

// ❌ WRONG - Content not layered above background
<div className="relative overflow-hidden">
  <div className="absolute inset-0 bg-gradient-to-br ..." />
  <div>Content here</div>  {/* Missing z-10! */}
</div>

// ✅ CORRECT - Content with z-10
<div className="relative overflow-hidden">
  <div className="absolute inset-0 bg-gradient-to-br ..." />
  <div className="relative z-10">Content here</div>
</div>
```

## Design System Awareness
Before writing code, review:
- `tailwind.config.ts` for theme tokens and spacing.
- `app/globals.css` for CSS variables and base styles.
- `components/ui` (ShadCN/Radix) for reusable atoms.
- `references/agents-page-design-pattern.md` for design patterns.
- **Component Registry**: Use `get-component-info` MCP tool for component details.
- **Block Templates**: Use `suggest-blocks` MCP tool to find pre-built patterns.

## Aesthetic Standards
- Use whitespace intentionally (e.g., `gap-4`, `p-6`).
- Add hover/focus-visible states and `transition-colors`.
- Use subtle glassmorphism when consistent with the Augur brand.
- Maintain clear typographic hierarchy.

## Apple Liquid Glass Design System

**Introduced**: Apple WWDC 2025 (iOS 26, macOS Tahoe)
**Reference**: Apple's unified design language that combines optical properties of glass with fluidity.

### Overview

Liquid Glass is Apple's 2025 design language that elevates glassmorphism with:
- Physically accurate lensing and refraction
- Dynamic response to light, motion, and environment
- Real-time adaptation to light/dark appearance
- Layered visual hierarchy between content and controls

### Core CSS Classes (Available in globals.css)

| Class | Use Case |
|-------|----------|
| `.liquid-glass` | Primary material for floating UI elements (action bars, tooltips, popovers) |
| `.liquid-glass-card` | Elevated containers and cards |
| `.liquid-glass-subtle` | Subtle backgrounds for secondary elements |

### Implementation

#### Primary Liquid Glass Material
```css
.liquid-glass {
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.1),
    inset 0 -1px 0 rgba(0, 0, 0, 0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

#### Light Mode Variant
```css
[data-mode="light"] .liquid-glass {
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    inset 0 -1px 0 rgba(0, 0, 0, 0.02);
}
```

### Key Properties Explained

| Property | Purpose | Recommended Value |
|----------|---------|-------------------|
| `backdrop-filter: blur()` | Creates the frosted glass effect | 16-24px for primary, 8-12px for subtle |
| `saturate()` | Enhances color vibrancy through glass | 150-200% |
| `background` | Semi-transparent base with alpha | 0.05-0.12 for dark, 0.6-0.8 for light |
| `border` | Subtle edge definition | rgba white/black at 0.08-0.15 |
| `inset box-shadow` | Creates "glass edge" lighting effect | Top highlight + bottom shadow |
| `transition` | Smooth state changes | cubic-bezier(0.4, 0, 0.2, 1) for Apple-like easing |

### Usage Examples

#### Floating Action Bar
```tsx
<div className="liquid-glass border rounded-2xl shadow-2xl p-2">
  {/* Content */}
</div>
```

#### Dropdown Menu
```tsx
<div className="liquid-glass-card border rounded-xl shadow-xl p-2">
  {/* Menu items */}
</div>
```

#### Subtle Background
```tsx
<div className="liquid-glass-subtle rounded-lg p-4">
  {/* Secondary content */}
</div>
```

### Design Principles (from Apple HIG)

1. **Hierarchy**: Use glass materials to showcase hierarchy between content and controls
2. **Context Awareness**: Elements should refract content behind them while reflecting surrounding context
3. **Dynamic Adaptation**: Material adapts to light/dark mode automatically
4. **Depth Through Layers**: Use multiple glass layers with varying blur/opacity for visual depth
5. **Legibility First**: Ensure sufficient contrast for text - Apple adjusted transparency after accessibility feedback

### Anti-Patterns

```tsx
// ❌ WRONG - Static blur without saturation
backdrop-filter: blur(10px);

// ✅ CORRECT - Blur with saturation for vibrant glass
backdrop-filter: blur(20px) saturate(180%);

// ❌ WRONG - Flat background without depth
background: rgba(0, 0, 0, 0.5);

// ✅ CORRECT - Layered shadows for glass depth
box-shadow:
  0 8px 32px rgba(0, 0, 0, 0.3),
  inset 0 1px 0 rgba(255, 255, 255, 0.1);

// ❌ WRONG - Sharp transitions
transition: all 0.2s ease;

// ✅ CORRECT - Apple-style cubic-bezier easing
transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
```

### Browser Support

- `backdrop-filter` requires `-webkit-` prefix for Safari
- Always include both: `backdrop-filter` and `-webkit-backdrop-filter`
- Fallback: solid semi-transparent background for unsupported browsers

### References
- [Apple Liquid Glass Announcement (WWDC 2025)](https://www.apple.com/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Glassmorphism Best Practices - NN/g](https://www.nngroup.com/articles/glassmorphism/)

## Technical Best Practices
- Prefer Server Components; add `use client` only when needed.
- Ensure all interactive elements have labels and proper semantics.
- Build mobile-first layouts with responsive grids.

## Quality Assurance Expectations
- Component testing with React Testing Library.
- Accessibility checks (focus, contrast, labels).
- Visual regression checks for critical views.

## Constraints
- **Test mandate:** Any UI change must have a corresponding test file.
- **Dark mode first:** Avoid hardcoded white backgrounds unless requested.
- **Design system compliance:**
  - Use `text-base` for primary inputs and labels.
  - Ensure `items-center` alignment for flex rows.
  - Validate `bg-card`/`bg-background` usage for theme compatibility.
  - `EditableMasonryGrid.defaultBlocks` supports only `auto` or `full`.
- **Configuration access:** Config UIs must offer an open-file action.
- **Nesting logic:** Avoid Card-in-Card when inside `DashboardWidget`.
- **Icon imports:** Ensure all lucide icons used in JSX are imported.
- **Interactive lists:** When a dropdown/popover is open, apply `relative z-20` to prevent clipping.
- **Icon sizing:** Use `w-5 h-5` for action icons and `w-6 h-6` for category indicators.
- **Server/client boundary:** Never pass non-serializable props to client components. Use string icon names in the tab registry.
- **Rounded containers:** All content must be wrapped in either `glass-panel` (16px radius) or `rounded-xl`/`rounded-2xl` - never leave sharp edges on page content.
- **Page root:** Use `glass-panel p-6` as the root element for pages - do NOT wrap in additional outer containers with min-h-screen or gradients (the layout handles this).
- **Grouped lists:** Collapse by default with inline preview info (item name pills, progress bar, badges) and rounded borders. See "Collapsible Grouped Lists" section.

## Hub Page Rules

Hub pages are top-level navigation items (e.g., `/health`, `/lifestyle`, `/venture`).

### Required Structure

1. **Every hub MUST have an Overview tab** as the landing page (`/[hub]`)
   ```typescript
   // ✅ Correct - defined in lib/tabs/registry.ts
   tabs: [
     { id: 'overview', label: 'Overview', icon: 'LayoutDashboard', href: '/health' },
     { id: 'virtual-doctor', label: 'Virtual Doctor', icon: 'Heart', href: '/health/virtual-doctor' },
   ]
   ```

2. **No duplicate headers** - Layout renders the title; page.tsx should NOT repeat it
   - `layout.tsx` → `<h1>{hub.title}</h1>` (from registry)
   - `page.tsx` → Start with content sections, NOT another `<h1>`

3. **Tabs vs Tool Cards** - Same item should NOT appear in both
   - Tabs = primary navigation (defined in registry)
   - Tool cards = quick links for items NOT in tabs

4. **Icon placement** - Icons belong in layout header, not repeated in page content

5. **Use the tab registry** - All layouts should use `tabRegistry.[hubName]`

### Standard Layout Pattern

```tsx
import UnifiedHubTabs from '@/components/UnifiedHubTabs';
import { tabRegistry } from '@/lib/tabs/registry';
import { IconName } from 'lucide-react';

const hub = tabRegistry.hubName;

export default function HubLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-6">
      <header className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[color]-500/20 flex items-center justify-center">
            <IconName className="w-6 h-6 text-[color]-400" />
          </div>
          <div>
            <h1 className="page-title from-[color]-400 to-[color2]-400">{hub.title}</h1>
            <p className="page-subtitle mt-1">{hub.subtitle}</p>
          </div>
        </div>
      </header>

      <UnifiedHubTabs tabs={hub.tabs} mode="path" />

      <div>{children}</div>
    </div>
  );
}
```

### File Structure Pattern

```
app/[hub]/
├── layout.tsx      # Uses tabRegistry, renders title/tabs
├── page.tsx        # Overview content (stats, tool cards)
└── [sub-page]/
    └── page.tsx    # Sub-page content
```

## Route Organization

### Current Hub Structure

| Hub | Path | Purpose |
|-----|------|---------|
| Sense | `/sense` | Sensory inputs (voice, vision, wearables) |
| Brain | `/brain` | Cognitive infrastructure |
| Hands | `/hands` | System tooling |
| Inbox | `/inbox` | Unified inbox |
| Career | `/career` | Job search & interviews |
| Health | `/health` | Health tracking |
| Lifestyle | `/lifestyle` | Recreation & learning |
| Venture | `/venture` | Primary venture operations |
| Projects | `/projects` | Active workspace |
| Organizations | `/organizations` | Enterprise management |
| Operations | `/operations` | Agent workforce & task execution |
| Settings | `/settings` | Configuration & preferences |
| SMB Design Office | `/smb-client-template` | SMB design agency |

### Route Rules

1. **No standalone pages in root** - All pages belong under a hub
2. **Skills pages** → `/settings/skills/[skill]`
3. **Dev tools** → `/settings/dev-routes`, `/settings/mcp-tools`
4. **Preview pages** → Under their parent hub (e.g., `/operations/wizard/preview`)

## Component Patterns
See `patterns/` for reusable snippets (Badge, Hover, Select).

## Collapsible Grouped Lists

When rendering grouped lists (e.g., hub categories, skill collections, settings sections), follow this pattern:

### Rules

1. **Collapsed by default** — All groups start collapsed. Users click to expand.
2. **Inline preview when collapsed** — Fill the row with useful info so it's not empty space:
   - Item name pills (first 5 items as compact tags)
   - Mini progress bar (enabled/total ratio)
   - Badge counts (dependencies, disabled items, warnings)
3. **Rounded border on collapsed rows** — Use `rounded-xl border border-[var(--border-color)]` to give each row card-like structure. On hover: `hover:border-[var(--text-muted)]/30 hover:bg-[var(--bg-secondary)]/50`.
4. **Expanded state border accent** — When expanded, use `border-[var(--accent-primary)]/30 bg-[var(--bg-secondary)]/50` to visually distinguish the active group.
5. **Chevron indicator** — Use `ChevronRight` from lucide-react with `rotate-90` transition on expand.

### Code Pattern

```tsx
const [expanded, setExpanded] = useState<Set<string>>(new Set());

// Collapsed row
<button
  onClick={() => toggleGroup(groupId)}
  className={`w-full flex items-center gap-2 py-2.5 px-3 rounded-xl border transition-colors ${
    isExpanded
      ? 'border-[var(--accent-primary)]/30 bg-[var(--bg-secondary)]/50'
      : 'border-[var(--border-color)] hover:border-[var(--text-muted)]/30'
  }`}
>
  <ChevronRight className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
  <Icon className="w-5 h-5" />
  <span className="font-semibold">{group.label}</span>
  <span className="text-xs text-muted">{enabledCount}/{totalCount}</span>

  {!isExpanded && (
    <div className="flex items-center gap-2 ml-2 flex-1 min-w-0 overflow-hidden">
      {/* Progress bar */}
      <div className="w-16 h-1.5 rounded-full bg-tertiary overflow-hidden">
        <div className="h-full rounded-full bg-success" style={{ width: `${pct}%` }} />
      </div>
      {/* Item name pills */}
      {previewNames.map(n => (
        <span key={n} className="text-[10px] px-1.5 py-0.5 rounded bg-secondary border">{n}</span>
      ))}
      {remaining > 0 && <span className="text-[10px] text-muted">+{remaining} more</span>}
      {/* Right-aligned badges */}
      <div className="ml-auto flex gap-1.5">
        {hasDeps && <span className="text-[10px] badge-primary">N with deps</span>}
        {hasDisabled && <span className="text-[10px] badge-danger">N disabled</span>}
      </div>
    </div>
  )}
</button>

{isExpanded && (
  <div className="grid gap-3 sm:grid-cols-2 mt-2 ml-9">
    {items.map(item => <ItemCard key={item.id} {...item} />)}
  </div>
)}
```

### Anti-Patterns

```tsx
// ❌ WRONG - All groups expanded by default (forces scrolling through dozens of cards)
{groups.map(g => (
  <div>
    <h3>{g.label}</h3>
    <div className="grid">{g.items.map(...)}</div>
  </div>
))}

// ✅ CORRECT - Collapsed by default with preview info
{groups.map(g => (
  <CollapsibleGroup key={g.id} defaultOpen={false} preview={g.items.slice(0,5)} />
))}

// ❌ WRONG - Collapsed row with no border (floating text, empty space)
<button className="w-full flex items-center gap-2 py-2.5 px-3">
  <span>{label}</span> <span>(5/5 enabled)</span>
</button>

// ✅ CORRECT - Rounded border + inline preview fills the row
<button className="w-full flex items-center gap-2 py-2.5 px-3 rounded-xl border border-[var(--border-color)]">
  <ChevronRight /> <Icon /> <span>{label}</span> <span>5/5</span>
  <ProgressBar /> <NamePills /> <Badges />
</button>
```

## Performance Patterns

### 1. Standardized List Pagination
**Issue**: Uncapped lists causing UI clutter and performance issues.
**Standard**: Implement the "Show More / Show Less" pattern.
- **Default Visibility**: **5 items**.
- **Pagination**: Client-side `.slice(0, visibleCount)` for < 100 items. server-side for larger.
- **Interaction**:
  - "Show More (+5)" button when more items exist.
  - "Show Less" button to reset to default.

**Code Pattern**:
```tsx
const [visibleCount, setVisibleCount] = useState(5);
const visibleItems = items.slice(0, visibleCount);

return (
  <>
    {visibleItems.map(item => <Item key={item.id} {...item} />)}

    {(items.length > visibleCount || visibleCount > 5) && (
      <div className="flex gap-2 justify-center">
        {items.length > visibleCount && (
          <Button onClick={() => setVisibleCount(p => p + 5)}>Show More (+5)</Button>
        )}
        {visibleCount > 5 && (
          <Button onClick={() => setVisibleCount(5)}>Show Less</Button>
        )}
      </div>
    )}
  </>
);
```

### 2. Error Boundaries
**Issue**: "Failed to fetch" crashing entire pages.
**Solution**: Wrap async calls in try/catch and distinct components in ErrorBoundaries.

### 3. Hub Overview Data Source Mismatch
**Issue**: Hub overview page showed "0 posts tracked" despite posts existing in the content pipeline.
**Root Cause**: The overview card called `getSocialStats()` which reads from a different skill's data directory (`venture-augur/index.yaml`), not the actual content pipeline posts.
**Solution**: Hub overview pages must read from their own skill's data source. Use the skill's own data library (e.g., `listPostGroups()` from `skills/smb-client-template/augur/lib/posts`) instead of generic cross-skill services.

**Anti-Pattern**:
```tsx
// Wrong — reads from venture-augur skill, not the consulting content pipeline
const stats = await getSocialStats();
return <Card>{stats.posts} posts tracked</Card>;
```

**Correct**:
```tsx
// Right — reads from the skill's own data source
const posts = await listPostGroups();
return <Card>{posts.length} posts tracked</Card>;
```


### SSE Routes Must Use GET and Named Event Listeners

**Issue**: Rebuild dialog showed "Connection to build server lost" immediately on open.
**Root Cause**: Two mismatches — API route exported `POST` but `EventSource` only sends `GET` (returns 405); client used `onmessage` but server sent named events (`event: stage`) which `onmessage` ignores.
**Solution**: SSE routes must export `GET`. Clients must use `addEventListener('eventName', ...)` for each named event type.

**Anti-Pattern**:
```ts
// API route — wrong method
export async function POST() { /* SSE stream */ }
// Client — wrong listener
eventSource.onmessage = (e) => { /* never fires for named events */ };
```

**Correct**:
```ts
// API route — EventSource requires GET
export async function GET() { /* SSE stream */ }
// Client — one listener per named event
eventSource.addEventListener('stage', (e) => { /* ... */ });
eventSource.addEventListener('done', (e) => { /* ... */ });
```
