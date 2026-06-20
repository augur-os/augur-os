# Release Management

**Module for**: `platform-admin` skill

## Purpose
Manage semantic versioning, git tags, GitHub releases, and changelogs for open source excellence.

## Workflow: Prepare Release

### Pre-Release Checklist
1. [ ] All tests passing (`npm run test`)
2. [ ] Build succeeds (`npm run build`)
3. [ ] CHANGELOG.md updated
4. [ ] Version bumped in package.json / version.yaml
5. [ ] README.md reflects current features

### Versioning Rules (Semantic)
- **MAJOR** (1.0.0): Breaking changes, API incompatibility
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, no new features

### Git Tag Format
```bash
# For monorepo with skills:
git tag skill-name-v1.2.3

# For main project:
git tag v1.2.3
```

### Release Script
```bash
# 1. Ensure clean working directory
git status --porcelain

# 2. Update version
npm version minor  # or major/patch

# 3. Generate release notes
git log $(git describe --tags --abbrev=0)..HEAD --oneline > release_notes.md

# 4. Create tag
git tag -a v$(node -p "require('./package.json').version") -m "Release v$(node -p "require('./package.json').version")"

# 5. Push with tags
git push origin main --tags
```

### GitHub Release Template
```markdown
## What's New
- Feature 1
- Feature 2

## Bug Fixes
- Fix 1
- Fix 2

## Breaking Changes
- None

## Full Changelog
[v1.1.0...v1.2.0](https://github.com/username/repo/compare/v1.1.0...v1.2.0)
```

## Automation
Consider GitHub Actions for automated releases on tag push:
- `.github/workflows/release.yml`
