# Dev Build Troubleshooting

## Common Build Issues

### TypeScript Errors
Update the reported types or property access.

### Import Errors
Check the file exists and the import path is still valid.

### Client/Server Boundary Errors
If React client hooks are used in a server component, add the correct client boundary or move the logic.

### Hydration Mismatches
Ensure server and client render the same content. Dynamic-only values need explicit client handling.

## Quick Reload Mode

Use `/dev-build --watch` when you need a cache clear and restart without a full rebuild.

## After Completion

1. Fix any build errors before handoff.
2. Re-check affected pages in the browser.
3. Keep the dashboard running and healthy for the next step in the workflow.
