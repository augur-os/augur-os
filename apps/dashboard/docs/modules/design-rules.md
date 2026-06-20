# Design Rules & Standards

## Core Principles

1. **Inherit Global Layout**: Pages inherit global background, font, and layout from root layout (`app/layout.tsx`) and section layouts.
2. **Avoid Page-Level Overrides**: Do NOT apply global styles at the page component level.
3. **Rounded Design**: Maintain the "rounded" aesthetic with containers that respect global padding and border radius.

## Anti-Patterns (Forbidden)

- **Hardcoded Backgrounds**: Do NOT use `bg-[radial-gradient(...)]` or `bg-slate-950` on page root elements. Breaks visual consistency.
- **`min-h-screen` on Pages**: Root layout handles full height. Adding it causes unnecessary scrolling.
- **Static blur without saturation**: Always pair `blur()` with `saturate()` for vibrant glass effects.
- **Flat backgrounds on glass elements**: Use layered `box-shadow` with inset highlights for depth.

## Component Guidelines

### Page Structure

```tsx
export default function MyPage() {
  return (
    <div className="space-y-6">
       {/* Content */}
    </div>
  );
}
```

### Cards and Panels

Use `Card` or `glass-panel` classes for content sections:

```tsx
<div className="p-6 rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm">
  {/* Card Content */}
</div>
```

### Apple Liquid Glass (Floating Elements)

For floating UI elements (action bars, tooltips, popovers):

```tsx
// Floating action bar
<div className="liquid-glass border rounded-2xl shadow-2xl p-2">
  {/* Content */}
</div>

// Dropdown/popover
<div className="liquid-glass-card border rounded-xl shadow-xl p-2">
  {/* Menu items */}
</div>
```

See `references/design-standards.md` for full Apple Liquid Glass documentation.

## Hub Page Rules

Hub pages (`/health`, `/lifestyle`, `/venture`, etc.) MUST follow:

1. **Overview tab required** - First tab must be "Overview" pointing to `/[hub]`
2. **No duplicate headers** - `layout.tsx` renders title; `page.tsx` should NOT repeat it
3. **Tabs != Tool Cards** - Items in tabs should NOT also appear as tool cards below
4. **No duplicate destination surfaces** - Do not point to the same page from hero CTAs, summary cards, activity lists, and section maps in the same viewport
5. **Icons in layout only** - Don't repeat the page icon in page.tsx content

## Canonical References

1. **Primary**: `/agents` page (AgentCommandCenter.tsx) - layout, color coding, KPI cards, floating actions
2. **Secondary**: `/workshop?tab=bugs` (BugsTab.tsx) - pagination, filtering, semantic colors, progressive disclosure

See `references/design-standards.md` and `references/agents-page-design-pattern.md` for details.
