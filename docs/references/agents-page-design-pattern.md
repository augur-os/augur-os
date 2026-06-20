<\!-- Canonical source: apps/dashboard/docs/references/agents-page-design-pattern.md -->
# Dashboard Design Pattern References

## Primary Reference: Agents Page

**Reference Page**: http://localhost:3000/agents
**Component**: `apps/dashboard/app/agents/AgentCommandCenter.tsx`

This page serves as the **primary canonical design pattern** for all dashboard pages. When refactoring or creating new pages, use this as the reference implementation for overall layout and structure.

## Complementary Reference: BugsTab Pattern

**Reference Page**: http://localhost:3000/workshop?tab=bugs
**Component**: `apps/dashboard/app/workshop/tabs/BugsTab.tsx` (475 lines)

For features like pagination, filtering, and data-heavy views, also reference the BugsTab implementation:

### Pagination Pattern (Show More/Show Less)
- **Default**: 5 items visible
- **Show More**: +5 items at a time with exact count
- **Show Less**: Reset to 5 items
- **Pattern** from BugsTab lines 445-462

### Semantic Color Coding
Use consistent priority/status colors:
- **P0/Critical**: `bg-red-500/20 text-red-400 border-red-500/30`
- **P1/High**: `bg-orange-500/20 text-orange-400 border-orange-500/30`
- **P2/Medium**: `bg-yellow-500/20 text-yellow-400 border-yellow-500/30`
- **Success**: `bg-green-500/10 text-green-400`

### Progressive Disclosure Pattern
- Collapsed state shows summary (title, key info, status)
- Click to expand for full details and actions
- Smooth transitions with hover states
- Example: BugCard component (lines 35-175)

### Multi-Dimensional Filtering
- Multiple filter dimensions (status, priority, sort order)
- Interactive stat cards that act as filters
- Real-time filtering without page reload

---

## Design Philosophy (Agents Page)

The `/agents` page demonstrates:
- **Visual Hierarchy**: Clear separation between header, KPIs, content sections, and actions
- **Information Density**: Balanced content without cramping
- **Color Coding**: Semantic color usage (purple=factory, amber=vertical, cyan=horizontal)
- **Interactive States**: Smooth transitions and hover effects
- **Responsive Layout**: Grid-based layouts that adapt to screen size
- **Accessibility**: Proper contrast, focus states, and semantic HTML

## Key Design Patterns

### 1. Page Container & Background

```tsx
<div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-950 via-slate-950 to-black text-white p-6 font-sans selection:bg-cyan-500/30">
```

**Pattern**: Gradient background with proper padding and text color
- Use radial gradient for depth
- Dark theme with proper contrast
- Consistent padding (`p-6`)

### 2. Header Section

```tsx
<header className="flex items-center justify-between mb-8 border-b border-white/10 pb-4">
  <div className="flex items-center gap-3">
    <div className="p-2 bg-blue-500/20 rounded-lg border border-blue-500/50">
      <Icon className="w-6 h-6 text-blue-400" />
    </div>
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-white">Page Title</h1>
      <p className="text-sm text-slate-400">Subtitle or context</p>
    </div>
  </div>
  {/* Status indicators, tabs, etc. */}
</header>
```

**Pattern**: 
- Icon in colored container with border
- Title: `text-2xl font-bold tracking-tight`
- Subtitle: `text-sm text-slate-400`
- Border separator: `border-b border-white/10`
- Spacing: `mb-8` for section separation

### 3. KPI Cards

```tsx
<div className="relative overflow-hidden rounded-xl border border-blue-500/20 bg-blue-950/20 backdrop-blur-sm p-6 group hover:border-blue-500/40 transition-all">
  <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl -translate-y-16 translate-x-16" />
  <div className="relative z-10">
    <div className="flex justify-between items-start mb-4">
      <h3 className="text-sm font-medium text-blue-200">Label</h3>
      <Icon className="w-5 h-5 text-blue-400" />
    </div>
    <div className="flex items-baseline gap-2">
      <span className="text-4xl font-bold text-white">{value}</span>
      <span className="text-sm text-blue-300">Unit</span>
    </div>
  </div>
</div>
```

**Pattern**:
- Colored border: `border-{color}-500/20`
- Colored background: `bg-{color}-950/20`
- Backdrop blur: `backdrop-blur-sm`
- Decorative blur circle for depth
- Hover state: `hover:border-{color}-500/40`
- Large number: `text-4xl font-bold`
- Label: `text-sm font-medium`

### 4. Tab Switcher

```tsx
<div className="flex p-1 bg-white/5 rounded-lg border border-white/10">
  <button
    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-2 ${
      activeTab === 'tab1' 
        ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' 
        : 'text-slate-400 hover:text-white hover:bg-white/5'
    }`}
  >
    <Icon className="w-3.5 h-3.5" />
    Tab Label
  </button>
</div>
```

**Pattern**:
- Container: `bg-white/5 rounded-lg border border-white/10`
- Active: `bg-blue-600 text-white shadow-lg shadow-blue-500/20`
- Inactive: `text-slate-400 hover:text-white hover:bg-white/5`
- Icons: `w-3.5 h-3.5` for tab icons

### 5. Content Grid Layout

```tsx
<div className="grid grid-cols-1 lg:grid-cols-3 gap-8 pb-24">
  {/* Column 1 */}
  <div className="space-y-4">
    <div className="flex items-center gap-2 mb-2 px-1">
      <Icon className="w-4 h-4 text-purple-400" />
      <h2 className="text-sm font-bold uppercase tracking-widest text-purple-200">Section Title</h2>
    </div>
    <div className="space-y-3">
      {/* Cards */}
    </div>
  </div>
</div>
```

**Pattern**:
- Grid: `grid grid-cols-1 lg:grid-cols-3 gap-8`
- Section headers: `text-sm font-bold uppercase tracking-widest`
- Column spacing: `space-y-4` for sections, `space-y-3` for cards
- Bottom padding: `pb-24` to account for floating action bar

### 6. Card Components

```tsx
<div className={`relative p-4 rounded-lg border ${c.border} ${c.bg} backdrop-blur-sm flex flex-col gap-3 group hover:bg-white/5 transition-all`}>
  {/* Content */}
</div>
```

**Pattern**:
- Border: Colored border with opacity (`border-{color}-500/20`)
- Background: Colored background with opacity (`bg-{color}-950/10`)
- Backdrop blur: `backdrop-blur-sm`
- Hover: `hover:bg-white/5`
- Transitions: `transition-all`
- Padding: `p-4`
- Spacing: `gap-3` for internal spacing

### 7. Floating Action Bar

```tsx
<div className="fixed bottom-6 left-1/2 -translate-x-1/2 w-full max-w-2xl px-6">
  <div className="bg-slate-900/90 backdrop-blur-xl border border-white/10 rounded-2xl p-2 shadow-2xl flex items-center justify-between gap-4">
    {/* Actions */}
  </div>
</div>
```

**Pattern**:
- Fixed positioning: `fixed bottom-6 left-1/2 -translate-x-1/2`
- Container: `bg-slate-900/90 backdrop-blur-xl`
- Border: `border border-white/10`
- Rounded: `rounded-2xl`
- Shadow: `shadow-2xl`

### 8. Color Coding System

- **Purple** (`purple-500`, `purple-950`): Factory/Infrastructure
- **Amber** (`amber-500`, `amber-950`): Vertical Domains
- **Cyan** (`cyan-500`, `cyan-950`): Horizontal Services
- **Blue** (`blue-500`, `blue-950`): Primary actions, KPIs
- **Red** (`red-500`, `red-950`): Critical/Errors
- **Emerald** (`emerald-500`, `emerald-950`): Success/Active

### 9. Typography Hierarchy

- **Page Title**: `text-2xl font-bold tracking-tight`
- **Section Headers**: `text-sm font-bold uppercase tracking-widest`
- **Card Titles**: `text-sm font-semibold` or `text-sm font-medium`
- **Body Text**: `text-sm` or `text-base`
- **Labels**: `text-xs` or `text-[10px]`
- **Large Numbers**: `text-4xl font-bold`

### 10. Spacing System

- **Page padding**: `p-6`
- **Section separation**: `mb-8` or `gap-8`
- **Card spacing**: `gap-3` or `space-y-3`
- **Internal padding**: `p-4` or `p-6`
- **Grid gaps**: `gap-8` for large grids, `gap-4` for smaller

## Implementation Checklist

When refactoring a page to match this pattern:

- [ ] Use gradient background (`bg-[radial-gradient(...)]`)
- [ ] Add header with icon, title, and subtitle
- [ ] Implement KPI cards with colored borders and blur effects
- [ ] Use tab switcher if multiple views
- [ ] Apply color coding (purple/amber/cyan) for sections
- [ ] Use grid layouts with proper spacing (`gap-8`)
- [ ] Add hover states to all interactive elements
- [ ] Implement floating action bar if needed
- [ ] Use proper typography hierarchy
- [ ] Add backdrop blur effects for depth
- [ ] Ensure proper contrast for accessibility
- [ ] Add transitions for smooth interactions

## Common Mistakes to Avoid

❌ **Don't**: Use flat backgrounds without gradients
❌ **Don't**: Skip hover states on cards
❌ **Don't**: Use inconsistent spacing
❌ **Don't**: Mix color coding systems
❌ **Don't**: Forget backdrop blur on cards
❌ **Don't**: Use generic font weights (always use `font-bold`, `font-semibold`, etc.)
❌ **Don't**: Cramp content - use proper spacing

✅ **Do**: Reference this page when building new pages
✅ **Do**: Use the same color system
✅ **Do**: Match spacing patterns
✅ **Do**: Include proper hover states
✅ **Do**: Use backdrop blur for depth
✅ **Do**: Follow typography hierarchy

## Example: Converting a Simple Page

**Before** (Generic):
```tsx
export default function MyPage() {
  return (
    <DashboardWidget title="My Page">
      <Content />
    </DashboardWidget>
  );
}
```

**After** (Following /agents pattern):
```tsx
export default function MyPage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-950 via-slate-950 to-black text-white p-6">
      <header className="flex items-center justify-between mb-8 border-b border-white/10 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg border border-blue-500/50">
            <Icon className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">My Page</h1>
            <p className="text-sm text-slate-400">Page description</p>
          </div>
        </div>
      </header>
      
      <div className="space-y-6">
        {/* Content with proper spacing */}
      </div>
    </div>
  );
}
```

