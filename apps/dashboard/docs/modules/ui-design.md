<!--
Copyright 2026 Augur Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This document incorporates and modifies content from the Company-in-a-Box project,
licensed under the Apache License 2.0.
-->

# UI Design Module

## Overview

UI mockup creation, visual design patterns, and brand consistency guidelines.
**Standard**: Tailwind CSS + ShadCN UI + Lucide React.

## Visual Design Principles

### Hierarchy
```
1. Primary Action    → bg-primary text-primary-foreground (Button)
2. Secondary Action  → bg-secondary text-secondary-foreground (Button variant="secondary")
3. Tertiary Action   → hover:bg-accent hover:text-accent-foreground (Button variant="ghost")
4. Content          → text-foreground (High contrast)
5. Muted            → text-muted-foreground (Low contrast)
```

### Visual Weight Distribution
```
┌─────────────────────────────┐
│  LOGO          [Nav] [Nav] │  ← border-b bg-background/95
├─────────────────────────────┤
│                             │
│    ████████████████        │  ← text-4xl font-bold
│    Primary Headline         │
│                             │
├─────────────────────────────┤
│  Card    Card    Card       │  ← grid grid-cols-3 gap-6
├─────────────────────────────┤
│  Footer links               │  ← bg-muted/50
└─────────────────────────────┘
```

## Layout Patterns

### Grid System
We use Tailwind's CSS Grid utilities. Do NOT use custom column classes.

```tsx
// 12-column grid example
<div className="grid grid-cols-12 gap-4">
  <div className="col-span-1" />   {/* 8.33% */}
  <div className="col-span-3" />   {/* 25% - Sidebar */}
  <div className="col-span-6" />   {/* 50% - Half */}
  <div className="col-span-9" />   {/* 75% - Main content */}
  <div className="col-span-12" />  {/* 100% - Full width */}
</div>
```

### Common Layouts
| Layout | Use Case | Tailwind Structure |
|--------|----------|--------------------|
| Single Column | Mobile, articles | `flex flex-col min-h-screen` |
| Sidebar Left | Dashboards | `grid lg:grid-cols-[280px_1fr]` |
| Sidebar Right | Settings | `grid lg:grid-cols-[1fr_300px]` |
| Split | Auth, comparison | `grid lg:grid-cols-2` |
| Card Grid | Galleries | `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6` |

## Color Application

### Semantic Tokens (ShadCN)
Always use semantic variables over hardcoded colors to support Dark Mode.

| Purpose | Class | Usage |
|---------|-------|-------|
| Background | `bg-background` | Page background |
| Surface | `bg-card` | Cards, modals, dropdowns |
| Primary | `bg-primary` | Main actions |
| Secondary | `bg-secondary` | Alternative actions |
| Muted | `bg-muted` | Subtle backgrounds |
| Accent | `bg-accent` | Hover states |
| Border | `border-border` | Default borders |
| Divider | `border-input` | Form borders |

### Typography

### Type Scale (Tailwind)
```
text-xs    → 12px (Caption)
text-sm    → 14px (Secondary/UI)
text-base  → 16px (Body/Input)
text-lg    → 18px (Lead)
text-xl    → 20px (H4)
text-2xl   → 24px (H3)
text-3xl   → 30px (H2)
text-4xl   → 36px (H1)
```

### Font Weights
- `font-normal` (400): Body text
- `font-medium` (500): UI labels, table headers
- `font-semibold` (600): Headings, emphasized UI
- `font-bold` (700): Page titles

## Spacing System

### Spacing Scale
Use standard Tailwind spacing utilities (`p-*`, `m-*`, `gap-*`).

```
gap-1  (4px)   → Tight grouping (icon + label)
gap-2  (8px)   → Related items (form fields)
gap-3  (12px)  → Card spacing (BugsTab pattern)
gap-4  (16px)  → Component padding (Card p-4)
gap-6  (24px)  → Section separation (space-y-6)
gap-8  (32px)  → Module separation (space-y-8)
gap-12 (48px)  → Page sections
```

## Pagination Patterns

### Show More/Show Less Pattern
Standard pagination for lists < 100 items (from BugsTab.tsx):

```tsx
const [visibleCount, setVisibleCount] = useState(5);
const visibleItems = items.slice(0, visibleCount);

return (
  <>
    {visibleItems.map(item => <Item key={item.id} {...item} />)}

    {visibleCount < items.length && (
      <Button onClick={() => setVisibleCount(p => p + 5)}>
        Show More (+{Math.min(5, items.length - visibleCount)})
      </Button>
    )}
    {visibleCount > 5 && (
      <Button onClick={() => setVisibleCount(5)}>Show Less</Button>
    )}
  </>
);
```

**Guidelines**:
- Default: 5 items visible
- Increment: +5 items per click
- Show exact remaining count in button text
- Always provide "Show Less" option when > 5 items visible

## Semantic Color Coding

### Priority/Status Colors
Use consistent semantic colors across the application (from BugsTab.tsx):

| Priority | Background | Text | Border |
|----------|-----------|------|--------|
| P0/Critical | `bg-red-500/20` | `text-red-400` | `border-red-500/30` |
| P1/High | `bg-orange-500/20` | `text-orange-400` | `border-orange-500/30` |
| P2/Medium | `bg-yellow-500/20` | `text-yellow-400` | `border-yellow-500/30` |
| Success | `bg-green-500/10` | `text-green-400` | `border-green-500/30` |
| Info | `bg-cyan-500/10` | `text-cyan-400` | `border-cyan-500/30` |
| Neutral | `bg-neutral-800` | `text-neutral-100` | `border-neutral-700` |

**Pattern**:
```tsx
const priorityColors: Record<string, string> = {
  P0: 'bg-red-500/20 text-red-400 border-red-500/30',
  P1: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  P2: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
};
```

### Progressive Disclosure
Expandable cards for complex data:

```tsx
const [expanded, setExpanded] = useState(false);

return (
  <div className="bg-neutral-800/50 rounded-lg border border-neutral-700/50">
    <div
      className="p-4 cursor-pointer hover:bg-neutral-700/30 transition-colors"
      onClick={() => setExpanded(!expanded)}
    >
      {/* Summary view */}
    </div>
    {expanded && (
      <div className="border-t border-neutral-700/50 p-4 bg-neutral-900/30">
        {/* Detailed view with actions */}
      </div>
    )}
  </div>
);
```

## UI Patterns

### Form Design
Use `shadcn/ui` Form components.

```tsx
<FormField
  control={form.control}
  name="username"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Username</FormLabel>
      <FormControl>
        <Input placeholder="shadcn" {...field} />
      </FormControl>
      <FormDescription>This is your public display name.</FormDescription>
      <FormMessage />
    </FormItem>
  )}
/>
```

### Card Pattern
Use `shadcn/ui` Card components.

```tsx
<Card>
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
    <CardDescription>Card Description</CardDescription>
  </CardHeader>
  <CardContent>
    <p>Card Content</p>
  </CardContent>
  <CardFooter>
    <Button>Action</Button>
  </CardFooter>
</Card>
```

## Brand Consistency

### Checklist
- [ ] No hardcoded hex colors (use semantic vars)
- [ ] Dark mode tested (toggle theme)
- [ ] Interactive states present (`hover:`, `focus-visible:`)
- [ ] Mobile responsive (`md:`, `lg:` breakpoints)
- [ ] Fonts use `Inter` (via `font-sans`)
- [ ] Icons are Lucide React

## Commands

| Command | Action |
|---------|--------|
| `mockup: [page]` | Generate UI mockup code |
| `theme check` | Verify semantic variable usage |
| `layout: [type]` | Get Tailwind layout template |
| `brand check: [url]` | Audit styling consistency |
