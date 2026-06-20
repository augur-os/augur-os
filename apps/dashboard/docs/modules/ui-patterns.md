# UI Design Patterns Module

## Purpose
UI mockup creation, visual design patterns, and brand consistency guidelines.

## Layout Patterns

### Page Templates
```
┌─────────────────────────────────────┐
│ Header (nav, logo, actions)         │
├─────────────────────────────────────┤
│                                     │
│  Main Content Area                  │
│  - Hero section                     │
│  - Feature blocks                   │
│  - CTA sections                     │
│                                     │
├─────────────────────────────────────┤
│ Footer (links, legal, social)       │
└─────────────────────────────────────┘

┌─────────┬───────────────────────────┐
│ Sidebar │ Dashboard Layout          │
│ (nav)   │                           │
│         │ ┌─────┐ ┌─────┐ ┌─────┐  │
│         │ │Card │ │Card │ │Card │  │
│         │ └─────┘ └─────┘ └─────┘  │
│         │                           │
│         │ ┌─────────────────────┐  │
│         │ │   Data Table        │  │
│         │ └─────────────────────┘  │
└─────────┴───────────────────────────┘
```

### Grid Systems
```css
/* 12-column grid */
.grid-12 {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--space-4);
}

/* Common spans */
.col-full    { grid-column: span 12; }
.col-half    { grid-column: span 6; }
.col-third   { grid-column: span 4; }
.col-quarter { grid-column: span 3; }
```

### Responsive Breakpoints
```css
/* Mobile first */
--breakpoint-sm: 640px;   /* Tablet portrait */
--breakpoint-md: 768px;   /* Tablet landscape */
--breakpoint-lg: 1024px;  /* Desktop */
--breakpoint-xl: 1280px;  /* Large desktop */
--breakpoint-2xl: 1536px; /* Wide screens */
```

## Component Patterns

### GlassCard (Standard Dashboard Card)

**🎯 Use this for ALL dashboard cards.** Component: `@/components/ui/GlassCard`

```tsx
import { GlassCard } from '@/components/ui/GlassCard';

// Content card with header
<GlassCard
  color="purple"           // cyan | purple | emerald | amber | blue | rose | violet | pink
  icon={Inbox}             // LucideIcon
  title="Inbox"
  subtitle="5 items"
  showHoverGlow={true}     // default: true
  showBgOverlay={true}     // default: true
  headerActions={<Button size="sm">Action</Button>}
>
  {/* Card body content */}
</GlassCard>

```

#### Color Schemes
| Color | Gradient | Use Case |
|-------|----------|----------|
| `cyan` | cyan → blue | Primary features, tools |
| `purple` | purple → pink | Inbox, reviews |
| `emerald` | emerald → teal | Success, health |
| `amber` | amber → orange | Warnings, ideas |
| `blue` | blue → indigo | Reading, info |
| `rose` | rose → pink | Voice, audio |
| `violet` | violet → purple | Vision, visual |
| `pink` | pink → rose | Alternative accent |

#### Core CSS Pattern
```css
/* Container */
.glass-card {
  @apply relative overflow-hidden rounded-xl border border-white/10 bg-neutral-900/50;
}

/* Background overlay (absolute, below content) */
.glass-overlay {
  @apply absolute inset-0 bg-gradient-to-br from-{color}-950/20 via-transparent to-transparent pointer-events-none;
}

/* Hover glow (interactive cards only) */
.glass-glow {
  @apply absolute inset-0 bg-{color}-500/20 opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-300;
}

/* Content layer (MUST be relative z-10) */
.glass-content {
  @apply relative z-10;
}

/* Gradient icon */
.gradient-icon {
  @apply p-2 rounded-lg bg-gradient-to-br from-{color}-500 to-{color2}-500;
}
```

### Legacy Card Pattern (ShadCN)
Use for forms, modals, and non-dashboard contexts only.

```tsx
// Standard Card Pattern
<Card className="p-6 hover:shadow-lg transition-shadow">
  <CardHeader>
    <CardTitle>Title</CardTitle>
    <CardDescription>Subtitle text</CardDescription>
  </CardHeader>
  <CardContent>
    {/* Main content */}
  </CardContent>
  <CardFooter className="flex justify-end gap-2">
    <Button variant="outline">Cancel</Button>
    <Button>Confirm</Button>
  </CardFooter>
</Card>
```

### Forms
```tsx
// Form Layout Pattern
<form className="space-y-6">
  <div className="space-y-2">
    <Label htmlFor="email">Email</Label>
    <Input id="email" type="email" placeholder="you@example.com" />
    <p className="text-sm text-muted-foreground">
      We'll never share your email.
    </p>
  </div>
  
  <div className="space-y-2">
    <Label htmlFor="password">Password</Label>
    <Input id="password" type="password" />
  </div>
  
  <Button type="submit" className="w-full">Sign In</Button>
</form>
```

### Data Tables
```tsx
// Table with sorting, filtering
<div className="rounded-md border">
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead className="w-[100px]">ID</TableHead>
        <TableHead>Name</TableHead>
        <TableHead>Status</TableHead>
        <TableHead className="text-right">Actions</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {items.map(item => (
        <TableRow key={item.id}>
          <TableCell className="font-mono">{item.id}</TableCell>
          <TableCell>{item.name}</TableCell>
          <TableCell>
            <Badge variant={item.status}>{item.status}</Badge>
          </TableCell>
          <TableCell className="text-right">
            <DropdownMenu>...</DropdownMenu>
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
</div>
```

## Visual Design Guidelines

### Color Usage
```yaml
color_guidelines:
  primary:
    use_for: "CTAs, links, key actions"
    avoid: "Large background areas"
    
  destructive:
    use_for: "Delete, errors, warnings"
    avoid: "Styling non-dangerous actions"
    
  muted:
    use_for: "Secondary text, borders, backgrounds"
    avoid: "Important information"
```

### Elevation (Shadows)
```css
--shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
--shadow-md: 0 4px 6px rgba(0,0,0,0.1);
--shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
--shadow-xl: 0 20px 25px rgba(0,0,0,0.15);

/* Usage: Higher = more prominent */
/* Cards: shadow-sm */
/* Dropdowns: shadow-md */
/* Modals: shadow-xl */
```

### Animation Guidelines
```css
/* Timing functions */
--ease-default: cubic-bezier(0.4, 0, 0.2, 1);
--ease-in: cubic-bezier(0.4, 0, 1, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);

/* Duration scale */
--duration-fast: 150ms;    /* Hovers, small changes */
--duration-normal: 200ms;  /* Most transitions */
--duration-slow: 300ms;    /* Page transitions */
--duration-slower: 500ms;  /* Complex animations */
```

## Interaction States

### Button States
```
┌──────────────┐
│   Default    │  Normal appearance
└──────────────┘
       ↓ hover
┌──────────────┐
│   Hover      │  Slightly lighter/darker
└──────────────┘
       ↓ mousedown
┌──────────────┐
│   Active     │  Pressed appearance
└──────────────┘
       ↓ focus (keyboard)
┌──────────────┐
│   Focus      │  Ring outline
└──────────────┘
       ↓ disabled
┌──────────────┐
│   Disabled   │  50% opacity, no pointer
└──────────────┘
```

### Loading States
```tsx
// Skeleton loading
<div className="space-y-4">
  <Skeleton className="h-4 w-3/4" />
  <Skeleton className="h-4 w-1/2" />
  <Skeleton className="h-32 w-full" />
</div>

// Spinner in button
<Button disabled>
  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
  Loading...
</Button>
```

## Empty States

### Pattern
```tsx
<div className="flex flex-col items-center justify-center py-12 text-center">
  <InboxIcon className="h-12 w-12 text-muted-foreground mb-4" />
  <h3 className="text-lg font-medium">No items yet</h3>
  <p className="text-muted-foreground mt-1 mb-4">
    Get started by creating your first item.
  </p>
  <Button>
    <PlusIcon className="mr-2 h-4 w-4" />
    Create Item
  </Button>
</div>
```

## Output

UI mockups: `skills/frontend/augur/mockups/`
Pattern library: `skills/frontend/augur/patterns/`

## User Experience Standards

Focus on perceived performance and predictability.

### 1. Optimistic UI Updates
Don't make users wait for server responses. Update the UI *immediately* when an action is taken, then revert if it fails.

- **Why**: Makes the app feel zero-latency.
- **Pattern**:
```tsx
// 1. Update local state immediately
setItems(prev => prev.filter(i => i.id !== id));

// 2. Perform API call
try {
  await deleteItem(id);
} catch (err) {
  // 3. Revert on failure
  setItems(prev => [...prev, item]);
  toast.error("Failed to delete item");
}
```

### 2. Loading Strategy ("Skeleton First")
Prevent layout shift and perceived sluggishness.

- **Initial Load**: Use **Skeletons** (`<Skeleton />`) that match the final layout structure.
- **Subsequent Actions**: Use **Spinners** inside buttons or subtle indicators for background updates.
- **Avoid**: Full-page loading overlays (unless blocking interaction is absolutely critical).

### 3. Keyboard Navigation (Power User Efficiency)
Enable efficient navigation without a mouse.

- **Global Shortcuts**:
  - `Cmd + K`: Open Command Palette (Navigation/Actions)
  - `?`: Show keyboard shortcuts help
  - `/`: Focus search bar
- **Focus Management**: Ensure modals trap focus and return it when closed.
- **Visual Feedback**: Visible `:focus-visible` ring on all interactive elements.
