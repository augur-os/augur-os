---
name: accessibility-audit
trigger: accessibility check, a11y audit, wcag check
---

# Accessibility Audit Module

## Overview

Systematic WCAG 2.1 AA compliance verification for all UI changes.

## Why Accessibility First

| Business Impact | Technical Impact |
|-----------------|------------------|
| Legal compliance | Better SEO |
| Larger user base | Cleaner semantics |
| Better UX for all | Easier testing |

## WCAG 2.1 AA Checklist

### Perceivable

| Check | Criterion | Test |
|-------|-----------|------|
| **Color Contrast** | 1.4.3 | Text ≥ 4.5:1, large text ≥ 3:1 |
| **Images** | 1.1.1 | All `<img>` have meaningful `alt` |
| **Video** | 1.2.2 | Captions available |
| **Responsive** | 1.4.10 | Reflow at 320px width |

### Operable

| Check | Criterion | Test |
|-------|-----------|------|
| **Keyboard** | 2.1.1 | All interactive elements focusable |
| **Focus Visible** | 2.4.7 | Clear focus indicator |
| **No Traps** | 2.1.2 | Can navigate away from all elements |
| **Skip Links** | 2.4.1 | Skip to main content available |

### Understandable

| Check | Criterion | Test |
|-------|-----------|------|
| **Language** | 3.1.1 | `lang` attribute on `<html>` |
| **Labels** | 3.3.2 | Form inputs have labels |
| **Errors** | 3.3.1 | Error identification clear |
| **Consistent** | 3.2.4 | Same UI elements behave same way |

### Robust

| Check | Criterion | Test |
|-------|-----------|------|
| **Valid HTML** | 4.1.1 | No duplicate IDs, proper nesting |
| **Name/Role** | 4.1.2 | ARIA roles correct |
| **Status** | 4.1.3 | Status messages announced |

## Automated Testing

```bash
# Run axe-core via Playwright
npx playwright test --grep @a11y

# Run pa11y for quick checks
npx pa11y http://localhost:3000/dashboard

# Lighthouse accessibility audit
npx lighthouse http://localhost:3000 --only-categories=accessibility
```

## Manual Testing Checklist

Before completing any UI change:

- [ ] Tab through entire page - logical order?
- [ ] Use screen reader - content makes sense?
- [ ] Zoom to 200% - layout still works?
- [ ] Turn off CSS - content readable?
- [ ] High contrast mode - elements visible?

## Accessibility Report Format

```markdown
## Accessibility Audit: [Component/Page]

**Date**: 2026-01-26
**Standard**: WCAG 2.1 AA
**Result**: ⚠️ 2 issues

### Issues Found

| Severity | Rule | Element | Issue |
|----------|------|---------|-------|
| CRITICAL | 1.4.3 | `.btn-subtle` | Contrast 2.8:1 (need 4.5:1) |
| MODERATE | 2.4.7 | `input.search` | No visible focus state |

### Remediation

1. **btn-subtle**: Change text color from `text-gray-400` to `text-gray-200`
2. **input.search**: Add `focus:ring-2 focus:ring-blue-500`

### Passing Checks
- ✅ Keyboard navigation
- ✅ Alt text on images
- ✅ Form labels
- ✅ Heading hierarchy
```

## React/Next.js Patterns

### Focus Management

```tsx
// Auto-focus on modal open
useEffect(() => {
  if (isOpen) {
    modalRef.current?.focus();
  }
}, [isOpen]);

// Trap focus in modal
<FocusTrap active={isOpen}>
  <div role="dialog" aria-modal="true">
    {/* content */}
  </div>
</FocusTrap>
```

### ARIA Labels

```tsx
// Button with icon only
<button aria-label="Close dialog">
  <XIcon aria-hidden="true" />
</button>

// Loading state
<button aria-busy={isLoading} aria-live="polite">
  {isLoading ? 'Saving...' : 'Save'}
</button>
```

### Skip Links

```tsx
// In layout.tsx
<a href="#main-content" className="sr-only focus:not-sr-only">
  Skip to main content
</a>

// Main content
<main id="main-content" tabIndex={-1}>
  {/* page content */}
</main>
```

## Integration with CI

```yaml
# In .github/workflows/a11y.yml
- name: Accessibility Check
  run: |
    npm run build
    npm run start &
    sleep 5
    npx pa11y-ci --sitemap http://localhost:3000/sitemap.xml
```

## Severity Levels

| Level | Action | Examples |
|-------|--------|----------|
| **CRITICAL** | 🛑 BLOCK | No keyboard access, missing alt text |
| **SERIOUS** | 🛑 BLOCK | Low contrast, no focus indicator |
| **MODERATE** | ⚠️ FIX | Missing labels, poor heading order |
| **MINOR** | ✅ NOTE | Redundant ARIA, minor improvements |
