# Design System Manager Module

## Purpose
Govern design tokens, maintain component library, and ensure visual consistency across products.

## Component Registry Integration

**Primary Resource**: `skills/frontend/`

The frontend skill maintains a comprehensive component registry with 104+ components. Use these MCP tools to query it:

### MCP Tools Available

| Tool | Use When |
|------|----------|
| `list-ui-blocks` | See all available blocks by category |
| `get-component-info` | Get details about a specific component (props, usage) |
| `get-block-template` | Get template code for a page block |
| `suggest-blocks` | Get recommendations based on what you're building |
| `search-components` | Search registry by keyword |

### Component Categories

| Category | Count | Examples |
|----------|-------|----------|
| Foundation | 12 | Card, Button, Badge, Tabs, Dialog |
| Widgets | 8 | GlassCard, StatCard, ToolCard, DashboardWidget |
| Renderers | 4 | DataTableRenderer, MetricsGridRenderer, ChartRenderer |
| Layout | 5 | MasonryGrid, SectionRenderer, HubRenderer |
| Actions | 5 | ActionButton, ActionButtons, ChainTriggerModal |
| Feedback | 5 | EmptyState, Skeleton, RelativeTime |

### Block Templates

Pre-composed page patterns in `frontend/templates/blocks/`:

| Template | Use For |
|----------|---------|
| `overview-page` | Hub landing pages with metrics grid |
| `data-list-page` | Lists with filtering, pagination, actions |
| `analytics-page` | Charts, metrics, breakdowns |
| `settings-page` | Configuration forms with sections |
| `detail-page` | Single item view with tabs and timeline |

### Usage in Design Tasks

```python
# When building a new page, first check available blocks
suggest-blocks(description="dashboard with user metrics and activity feed")

# Get specific component details
get-component-info(component="stat_card")

# Get template code to customize
get-block-template(block="overview_page")
```

## Design Token Structure

### Token Hierarchy
```
Global Tokens (primitive)
    └── Semantic Tokens (contextual)
         └── Component Tokens (specific)
```

### Color Tokens
```css
/* Global - Primitive values */
--color-blue-500: #3b82f6;
--color-gray-900: #111827;

/* Semantic - Contextual meaning */
--color-primary: var(--color-blue-500);
--color-text-primary: var(--color-gray-900);
--color-background: #ffffff;
--color-surface: #f9fafb;

/* Component - Specific usage */
--button-primary-bg: var(--color-primary);
--button-primary-text: #ffffff;
--card-bg: var(--color-surface);
```

### Spacing Scale
```css
--space-1: 0.25rem;  /* 4px */
--space-2: 0.5rem;   /* 8px */
--space-3: 0.75rem;  /* 12px */
--space-4: 1rem;     /* 16px */
--space-6: 1.5rem;   /* 24px */
--space-8: 2rem;     /* 32px */
--space-12: 3rem;    /* 48px */
--space-16: 4rem;    /* 64px */
```

### Typography Scale
```css
--text-xs: 0.75rem;    /* 12px */
--text-sm: 0.875rem;   /* 14px */
--text-base: 1rem;     /* 16px */
--text-lg: 1.125rem;   /* 18px */
--text-xl: 1.25rem;    /* 20px */
--text-2xl: 1.5rem;    /* 24px */
--text-3xl: 1.875rem;  /* 30px */

--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
```

## Component Library Governance

### Component Status Levels
| Status | Badge | Meaning |
|--------|-------|---------|
| Draft | 🔴 | In development, not for use |
| Beta | 🟡 | Ready for testing, may change |
| Stable | 🟢 | Production ready |
| Deprecated | ⚫ | Being phased out, use alternative |

### Component Documentation Template
```markdown
## Button

**Status**: 🟢 Stable
**Version**: 2.1.0

### Usage
Primary action buttons for forms and CTAs.

### Variants
- `default` - Standard button
- `destructive` - Dangerous actions
- `outline` - Secondary emphasis
- `ghost` - Minimal styling
- `link` - Text link style

### Props
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| variant | string | "default" | Visual style |
| size | "sm" | "md" | "lg" | "md" | Size |
| disabled | boolean | false | Disabled state |

### Accessibility
- Uses native `<button>` element
- Supports keyboard navigation
- Has focus-visible styles

### Examples
[Code examples here]
```

## Theme Management

### Multi-Theme Support
```typescript
// themes/index.ts
export const themes = {
  light: {
    background: '#ffffff',
    foreground: '#0a0a0a',
    primary: '#3b82f6',
    // ...
  },
  dark: {
    background: '#0a0a0a',
    foreground: '#fafafa',
    primary: '#60a5fa',
    // ...
  },
  brand: {
    background: '#0f172a',
    foreground: '#f1f5f9',
    primary: '#8b5cf6',
    // ...
  }
};
```

### Theme Switching
```typescript
// Apply theme to :root
function applyTheme(theme: keyof typeof themes) {
  const root = document.documentElement;
  const tokens = themes[theme];
  
  Object.entries(tokens).forEach(([key, value]) => {
    root.style.setProperty(`--${key}`, value);
  });
}
```

## Design System Audit

### Audit Checklist
```markdown
## Design System Health Check

### Token Consistency
- [ ] All colors use design tokens
- [ ] No magic numbers for spacing
- [ ] Typography follows scale
- [ ] Shadows use defined values

### Component Quality
- [ ] All components documented
- [ ] Props have TypeScript types
- [ ] Accessibility requirements met
- [ ] Responsive behavior defined

### Usage Compliance
- [ ] No duplicate components
- [ ] Consistent naming conventions
- [ ] Proper import paths
- [ ] No inline styles override tokens
```

### Drift Detection
```yaml
drift_report:
  date: "2026-01-06"
  
  violations:
    - file: "components/CustomCard.tsx"
      issue: "Hardcoded color #333"
      fix: "Use var(--color-text-primary)"
      
    - file: "pages/dashboard.tsx"
      issue: "Custom spacing (13px)"
      fix: "Use space-3 (12px) or space-4 (16px)"
      
  stats:
    total_components: 45
    compliant: 42
    violations: 3
    compliance_rate: 93%
```

## Version Management

### Breaking Change Policy
```markdown
## Versioning Rules

**Major (X.0.0)**: Breaking changes
- Removed props or components
- Changed default behavior
- Token name changes

**Minor (0.X.0)**: New features
- New components
- New variants/props
- New tokens

**Patch (0.0.X)**: Fixes
- Bug fixes
- Documentation updates
- Performance improvements
```

### Migration Guides
```markdown
## Migrating Button v1 → v2

### Breaking Changes
- `type` prop renamed to `variant`
- `small`/`large` replaced with `size` prop

### Before
<Button type="primary" small>Click</Button>

### After
<Button variant="default" size="sm">Click</Button>

### Codemod
npx design-system-migrate button-v2
```

## Output

Design tokens: `skills/frontend/augur/tokens/`
Audit reports: `skills/frontend/augur/operations/audits/`
