# Dev Build Execution Steps

> **Canonical engine:** the build/restart logic now lives in `src/lib/dev_build.py`
> (`aug dev build`, the shared engine in `command_surfaces.yaml`). Humans run `/dev build`;
> agents run `aug dev build`. The steps below describe what that engine does; both paths
> share it (no drift). The engine performs a **scoped** restart via
> `project-brain/capabilities/skills/daemon/scripts/scoped_restart.py` (only the target
> instance's port + its `dashboard-`-scoped MCP children; never a broad `pgrep`, never a
> launchd unload).

## Step 1: Cleanup Processes and Non-Build Caches

> **Lifecycle gate**: `cleanup_processes.py` and `build-lock.sh` now call the dashboard lifecycle gate automatically. No manual gate call is needed when using `/dev-build`. The gate prevents concurrent actors from fighting over the dashboard and detects crash loops.

```bash
python3 project-brain/capabilities/skills/daemon/scripts/cleanup_processes.py

cd apps/dashboard
rm -rf node_modules/.cache
rm -f tsconfig.tsbuildinfo
rm -rf .turbo
```

## Step 2: Install Dependencies If Needed

```bash
cd apps/dashboard
npm install
```

## Step 3: Run Production Build

```bash
cd apps/dashboard
npm run build:safe
```

## Step 4: Determine Pages To Check

Use recent git changes in smart mode, or pass `--all`/`--pages` explicitly.

## Step 5: Start Dev Server and Validate Pages

```bash
cd apps/dashboard
npm run dev
```

## Step 6: Check Each Page

Use browser verification, not just HTTP responses:

- page loads successfully
- no console errors
- no hydration mismatches
- real data renders
- interactive elements still work

## Step 7: Cleanup

Leave the dashboard in a healthy running state when validation completes.
