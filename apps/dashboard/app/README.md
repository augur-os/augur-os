# apps/dashboard/app/ — GENERATED DIRECTORY

**DO NOT create or edit page files here directly.**

This directory contains Next.js routes that are **auto-generated** by the skill
mount system (`npm run mount-plugins`). Files created here will be overwritten
on the next build.

## Where to create pages

Custom dashboard pages belong under:

```
apps/dashboard/features/pages/{hub}/{pageId}/page.tsx
```

The catch-all registry discovers custom pages from `features/pages/`.
Placing page files under `project-brain/capabilities/skills/{skill}/augur/dashboard/` is legacy and can
create orphan tabs because that path is not part of the current page registry.

## Shell pages (exceptions)

Only framework-level pages live here permanently:

- `page.tsx` (root)
- `artifact/`
- `files/`
- `help/`
- `login/`
- `settings/`
- `setup/`

These are NOT skill pages and are not managed by mount-plugins.

## How to add a new page

1. Create `apps/dashboard/features/pages/{hub}/{pageId}/page.tsx`
2. Declare it in the owning skill frontmatter so the tab registry can mount it
3. Run `npm run mount-plugins` (or let the dev watcher pick it up)
4. The tab appears automatically in the hub's tab bar
