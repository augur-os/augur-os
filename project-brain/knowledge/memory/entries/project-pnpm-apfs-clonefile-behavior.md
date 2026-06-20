---
title: project-pnpm-apfs-clonefile-behavior
name: project-pnpm-apfs-clonefile-behavior
description: pnpm 10 on APFS uses clonefile() block-level CoW (not literal hardlinks)
  regardless of package-import-method setting; `find -links +1` will show 0% even
  when bytes are 95% shared
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_pnpm_apfs_clonefile_behavior.md
source_hash: a484ab454e898ea2
---


On APFS, pnpm 10 uses `clonefile()` (block-level copy-on-write) to materialize files from its content-addressable store into `node_modules`, **regardless of the `.npmrc` `package-import-method=hardlink` setting**. The pnpm config reports `hardlink` honestly; pnpm just doesn't actually emit literal hardlinks on APFS.

**Why:** measured this during ADR-759 (2026-05-16). The Layer 3 verification of CoW sharing initially showed "0% hardlinks" via `find -type f -links +1 | wc -l` which read like a defect. Investigation: store files have `nlink=1`, `node_modules` files have `nlink=1` with different inodes — but block-level disk usage shows the bytes ARE shared. A 672 MB apparent `node_modules` actually consumed only 16-31 MB on disk; deleting it reclaimed exactly 16 MB via volume free-space delta.

**How to apply:**
1. **Never use `find -type f -links +1`** as a sharing-rate metric on macOS — it's a false negative.
2. The right metric is **`(apparent_size - volume_free_space_delta) / apparent_size`** measured before/after the install or worktree spawn. Use `du -A -k -s` for apparent, `df -k` before/after for actual.
3. The `package-import-method=hardlink` directive is still essential for **non-APFS** filesystems (ext4, NTFS) — there it produces literal hardlinks since clonefile isn't available. Don't remove it just because APFS doesn't need it.
4. Before claiming "broken hardlinking" in an investigation, check if APFS clones are silently doing the work via volume-delta — pnpm 10's default is already `clone-or-copy` on APFS even without an `.npmrc` override.

Related: [[project-pnpm-store-prune-safe-mid-session]] explains why deleting the store doesn't break existing clones (APFS block refs persist).
