---
title: hostinger-hcdn-image-cache
name: hostinger-hcdn-image-cache
description: Hostinger CDN (hcdn) serves stale optimized images and ignores query-string
  cache-busts — rename the asset file to force a refresh.
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: hostinger-hcdn-image-cache.md
source_hash: de00c16fc945292e
---


augur.run / guriqo.com are hosted on Hostinger behind its CDN (`server: hcdn`). The CDN
does **on-the-fly image optimization** (resizes/recompresses, e.g. 1690×931 → 1600×881)
and caches the optimized variant **keyed by URL path**.

Gotcha: after redeploying a changed image, the live URL keeps serving the OLD optimized
copy even though the origin file on disk is correct (verified via `ssh hostinger md5sum`).
A `?v=N` query string does **not** bust it — hcdn ignores query strings for image opt.

Fix: **rename the asset file** (a path hcdn has never optimized) and update the HTML refs.
Done this for the homepage diagram: `architecture-second-brain.png` → `architecture-knowledge-brain.png`.
Verify the fix **visually** in a browser (md5 won't match — the CDN re-optimizes the bytes).

Deploy flow itself: `website-working/release.sh` → `scp`/`ssh hostinger` unzip into
`domains/<domain>/public_html` (see [[public-presence]] skill + venture-augur/websites/DEPLOYMENT.md).
