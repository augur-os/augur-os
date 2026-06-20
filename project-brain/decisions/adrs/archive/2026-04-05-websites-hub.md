# Websites Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new "Websites" dashboard hub with 4 pages (Overview, Hosting, SEO, Reports) for managing augur.run, guriqo.com, and danit-design.com — all hosted on Hostinger.

**Architecture:** New `skills/websites/` skill owns the hub. Python MCP tools handle status checks (HTTP + SSL via stdlib), deploy pipeline (SSH via subprocess), and vault-backed SEO/report data. Dashboard pages in `apps/dashboard/features/pages/websites/` use `useMcpQuery` for data and `useActionRunner` for IDE-dispatched mutations (deploy, audit).

**Tech Stack:** Python 3.11+ (MCP tools), TypeScript/React (dashboard), shadcn/ui + GlassCard (UI), SSH key auth (deploys), vault frontmatter markdown (data storage).

**Spec:** `docs/superpowers/specs/2026-04-05-websites-hub-design.md`

---

## File Structure

```
skills/websites/
├── SKILL.md
├── config.yaml
├── scripts/
│   ├── mcp/
│   │   ├── __init__.py          # register_tools entry point
│   │   ├── tools_status.py      # get-websites-status, get-websites-overview, get-websites-activity
│   │   ├── tools_hosting.py     # get-website-hosting, list-website-versions
│   │   └── tools_seo.py         # get-website-seo, list-website-audits, list-website-reports
│   └── deploy.py                # deploy pipeline (package + SCP + extract)
├── augur/
│   └── data/
│       └── sites.yaml           # site config
└── assets/
    └── seeds/
        └── sites.yaml           # seed config

apps/dashboard/features/pages/websites/
├── overview/page.tsx
├── hosting/page.tsx
├── seo/page.tsx
└── reports/page.tsx

vault/websites/                  # created at runtime
├── activity.json
├── augur.run/audits/
├── guriqo.com/audits/
└── danit-design.com/audits/
```

---

### Task 1: Skill Scaffold — SKILL.md, config.yaml, sites.yaml

**Files:**
- Create: `skills/websites/SKILL.md`
- Create: `skills/websites/config.yaml`
- Create: `skills/websites/augur/data/sites.yaml`
- Create: `skills/websites/assets/seeds/sites.yaml`

- [ ] **Step 1: Create SKILL.md**

```yaml
---
name: websites
x-augur-type: domain
x-augur-tags: [hosting, deploy, seo, monitoring, websites]
description: >-
  Manage websites hosted on Hostinger — deploy, monitor uptime and SSL,
  run SEO audits, and generate reports. Covers augur.run, guriqo.com,
  and danit-design.com.
x-augur-hub: websites
x-augur-tab: overview
x-augur-dependencies:
  required: []
  optional:
    - venture-augur
x-augur-license: MIT
x-augur-metadata:
  version: 1.0.0
  author: Augur
  mcp-server: augur
x-augur-mcp-tools:
  - get-websites-status
  - get-websites-overview
  - get-websites-activity
  - get-website-hosting
  - list-website-versions
  - get-website-seo
  - list-website-audits
  - list-website-reports
x-augur-dashboard-pages:
  - /websites/overview
  - /websites/hosting
  - /websites/seo
  - /websites/reports
x-augur-data-dir: websites
x-augur-portable: false
x-augur-config:
  hub:
    id: websites
    owner: true
    title: Websites
    nav_order: 35
    subtitle: Deploy, monitor, and optimize your sites
    icon: Globe
    category: web
    iconBg: bg-blue-500/20
    iconColor: text-blue-400
    overview:
      search: false
      layout: masonry
  contributions:
    pages:
      - id: overview
        title: Overview
        icon: LayoutDashboard
        order: 10
        purpose: All sites at a glance — status, version, SEO scores, quick actions
        keywords: [overview, status, websites]
        state: seed
        page_type: custom
      - id: hosting
        title: Hosting
        icon: Server
        order: 20
        purpose: Deploy pipeline, version history, SSL, uptime per site
        keywords: [hosting, deploy, ssl, versions]
        state: seed
        page_type: custom
      - id: seo
        title: SEO
        icon: Search
        order: 30
        purpose: SEO audit scores, findings, trends per site
        keywords: [seo, audit, geo, content]
        state: seed
        page_type: custom
      - id: reports
        title: Reports
        icon: FileText
        order: 40
        purpose: Generate and download PDF reports
        keywords: [reports, pdf, export]
        state: seed
        page_type: custom
---

# Websites

Website management hub for Hostinger-hosted sites. Deploy, monitor uptime/SSL, run SEO audits, and generate reports.
```

- [ ] **Step 2: Create config.yaml**

```yaml
hub:
  id: websites
  owner: true
contributions:
  pages:
    - id: overview
      order: 10
      title: Overview
      icon: LayoutDashboard
      purpose: All sites at a glance
      page_type: custom
    - id: hosting
      order: 20
      title: Hosting
      icon: Server
      purpose: Deploy, versions, SSL, uptime
      page_type: custom
    - id: seo
      order: 30
      title: SEO
      icon: Search
      purpose: Audit scores, findings, trends
      page_type: custom
    - id: reports
      order: 40
      title: Reports
      icon: FileText
      purpose: Generate PDF reports
      page_type: custom
```

- [ ] **Step 3: Create sites.yaml (augur/data/ and assets/seeds/)**

Write the same content to both `skills/websites/augur/data/sites.yaml` and `skills/websites/assets/seeds/sites.yaml`:

```yaml
sites:
  - domain: augur.run
    label: Augur
    deploy_method: scp
    site_key: augur
    local_source: ~/Projects/Au-docs/venture-augur/website-working
    versions_dir: ~/Projects/Au-docs/venture-augur/websites
    zip_prefix: augur-run
    remote_dir: domains/augur.run/public_html
    metrics:
      waitlist: true
      waitlist_path: data/waitlist.csv
  - domain: guriqo.com
    label: Guriqo
    deploy_method: scp
    site_key: guriqo
    local_source: ~/Projects/Au-docs/venture-augur/website-working
    versions_dir: ~/Projects/Au-docs/venture-augur/websites
    zip_prefix: guriqo-com
    remote_dir: domains/guriqo.com/public_html
    metrics:
      inquiries: true
  - domain: danit-design.com
    label: Danit Design
    deploy_method: builder
    builder_url: https://hpanel.hostinger.com
    remote_dir: domains/danit-design.com/public_html
    metrics: {}

ssh:
  alias: hostinger
  host: 82.29.199.38
  port: 65002
  user: u215419198
```

- [ ] **Step 4: Commit**

```bash
git add skills/websites/SKILL.md skills/websites/config.yaml skills/websites/augur/data/sites.yaml skills/websites/assets/seeds/sites.yaml
git commit -m "feat(websites): scaffold skill with SKILL.md, config, and sites data"
```

---

### Task 2: MCP Tools — Status & Overview

**Files:**
- Create: `skills/websites/scripts/mcp/__init__.py`
- Create: `skills/websites/scripts/mcp/tools_status.py`

- [ ] **Step 1: Create tools_status.py**

```python
"""Website status, overview, and activity MCP tools."""

from __future__ import annotations

import json
import logging
import socket
import ssl
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from urllib.request import urlopen, Request
from urllib.error import URLError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from augur_mcp.annotations import tool_annotations

logger = logging.getLogger(__name__)

# ── Site config ──────────────────────────────────────────────────────────────

SITES = [
    {"domain": "augur.run", "label": "Augur"},
    {"domain": "guriqo.com", "label": "Guriqo"},
    {"domain": "danit-design.com", "label": "Danit Design"},
]


def _check_http(domain: str, timeout: int = 10) -> dict:
    """Check HTTP status for a domain."""
    try:
        req = Request(f"https://{domain}/", method="HEAD")
        req.add_header("User-Agent", "Augur-Monitor/1.0")
        with urlopen(req, timeout=timeout) as resp:
            return {"status": resp.status, "ok": resp.status == 200}
    except URLError as e:
        return {"status": 0, "ok": False, "error": str(e)}
    except Exception as e:
        return {"status": 0, "ok": False, "error": str(e)}


def _check_ssl(domain: str) -> dict:
    """Check SSL certificate expiry for a domain."""
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(10)
            s.connect((domain, 443))
            cert = s.getpeercert()
        expiry_str = cert.get("notAfter", "")
        if expiry_str:
            expiry = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z").replace(
                tzinfo=timezone.utc
            )
            days_left = (expiry - datetime.now(timezone.utc)).days
            return {
                "expiry": expiry.isoformat(),
                "days_left": days_left,
                "ok": days_left > 30,
            }
        return {"expiry": None, "days_left": 0, "ok": False}
    except Exception as e:
        return {"expiry": None, "days_left": 0, "ok": False, "error": str(e)}


def _get_vault_websites_dir() -> Path:
    """Get the vault websites directory."""
    try:
        from src.config.paths import get_vault_dir
        return get_vault_dir() / "websites"
    except ImportError:
        return Path.home() / "augur-vault" / "websites"


def _read_activity(limit: int = 10) -> list[dict]:
    """Read recent activity from the activity log."""
    activity_file = _get_vault_websites_dir() / "activity.json"
    if not activity_file.exists():
        return []
    try:
        data = json.loads(activity_file.read_text())
        events = data if isinstance(data, list) else data.get("events", [])
        return sorted(events, key=lambda e: e.get("timestamp", ""), reverse=True)[:limit]
    except Exception:
        return []


def _get_versions_info(site_key: str, zip_prefix: str, versions_dir: str) -> dict:
    """Get version info for a site."""
    vdir = Path(versions_dir).expanduser()
    if not vdir.exists():
        return {"current": None, "count": 0}
    zips = sorted(vdir.glob(f"{zip_prefix}*.zip"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not zips:
        return {"current": None, "count": 0}
    latest = zips[0]
    # Extract version from filename like "augur-run-V38.zip"
    version = latest.stem.split("-")[-1]
    return {
        "current": version,
        "count": len(zips),
        "last_modified": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(),
    }


def register_status_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register website status tools."""

    @mcp.tool(
        name="get-websites-status",
        annotations=tool_annotations(
            {"title": "Get Websites Status", "readOnlyHint": True, "idempotentHint": True}
        ),
    )
    @mcp_tool_interceptor
    async def get_websites_status_tool() -> str:
        """Check HTTP status and SSL expiry for all managed websites.

        Returns:
            JSON with {success, data} where data is array of site status objects.
        """
        metrics.track_tool("get_websites_status", skill="websites")
        results = []
        for site in SITES:
            domain = site["domain"]
            http = _check_http(domain)
            ssl_info = _check_ssl(domain)
            results.append({
                "domain": domain,
                "label": site["label"],
                "http": http,
                "ssl": ssl_info,
            })
        return json.dumps({"success": True, "data": results}, indent=2)

    @mcp.tool(
        name="get-websites-overview",
        annotations=tool_annotations(
            {"title": "Get Websites Overview", "readOnlyHint": True, "idempotentHint": True}
        ),
    )
    @mcp_tool_interceptor
    async def get_websites_overview_tool() -> str:
        """Get overview data for all sites: versions, last deploy, SEO scores.

        Returns:
            JSON with {success, data} where data is array of site overview objects.
        """
        metrics.track_tool("get_websites_overview", skill="websites")
        import yaml

        # Load sites config
        config_path = Path(__file__).parent.parent.parent / "augur" / "data" / "sites.yaml"
        sites_config = {}
        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text()) or {}
            for s in raw.get("sites", []):
                sites_config[s["domain"]] = s

        results = []
        vault_dir = _get_vault_websites_dir()

        for site in SITES:
            domain = site["domain"]
            cfg = sites_config.get(domain, {})
            entry: dict[str, Any] = {"domain": domain, "label": site["label"]}

            # Version info
            if cfg.get("deploy_method") == "scp":
                entry["version"] = _get_versions_info(
                    cfg.get("site_key", ""),
                    cfg.get("zip_prefix", ""),
                    cfg.get("versions_dir", ""),
                )
            else:
                entry["version"] = {"current": None, "count": 0, "deploy_method": "builder"}

            # Latest SEO score (from most recent audit file)
            audit_dir = vault_dir / domain / "audits"
            if audit_dir.exists():
                audits = sorted(audit_dir.glob("*.md"), reverse=True)
                if audits:
                    entry["seo_score"] = _extract_seo_score(audits[0])
                else:
                    entry["seo_score"] = None
            else:
                entry["seo_score"] = None

            results.append(entry)

        return json.dumps({"success": True, "data": results}, indent=2, default=str)

    @mcp.tool(
        name="get-websites-activity",
        annotations=tool_annotations(
            {"title": "Get Websites Activity", "readOnlyHint": True, "idempotentHint": True}
        ),
    )
    @mcp_tool_interceptor
    async def get_websites_activity_tool() -> str:
        """Get recent website activity (deploys, audits, etc.).

        Returns:
            JSON with {success, data} where data is array of activity events.
        """
        metrics.track_tool("get_websites_activity", skill="websites")
        events = _read_activity(limit=10)
        return json.dumps({"success": True, "data": events}, indent=2)


def _extract_seo_score(audit_file: Path) -> dict | None:
    """Extract overall SEO score from an audit frontmatter file."""
    try:
        import yaml

        text = audit_file.read_text()
        if not text.startswith("---"):
            return None
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        fm = yaml.safe_load(parts[1]) or {}
        return {
            "overall": fm.get("overall_score"),
            "technical": fm.get("technical_score"),
            "content": fm.get("content_score"),
            "schema": fm.get("schema_score"),
            "ai_visibility": fm.get("ai_visibility_score"),
            "platform_readiness": fm.get("platform_readiness"),
            "brand_authority": fm.get("brand_authority_score"),
            "date": fm.get("date"),
        }
    except Exception:
        return None


def log_activity(event_type: str, domain: str, details: dict | None = None) -> None:
    """Append an event to the activity log."""
    vault_dir = _get_vault_websites_dir()
    vault_dir.mkdir(parents=True, exist_ok=True)
    activity_file = vault_dir / "activity.json"

    events = []
    if activity_file.exists():
        try:
            raw = json.loads(activity_file.read_text())
            events = raw if isinstance(raw, list) else raw.get("events", [])
        except Exception:
            events = []

    events.append({
        "type": event_type,
        "domain": domain,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **(details or {}),
    })

    # Keep last 100 events
    events = events[-100:]
    activity_file.write_text(json.dumps(events, indent=2, default=str))
```

- [ ] **Step 2: Create __init__.py**

```python
"""Websites MCP Tool Implementations.

Loaded dynamically by the Augur MCP server via the plugin tool loading system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from .tools_status import register_status_tools
from .tools_hosting import register_hosting_tools
from .tools_seo import register_seo_tools


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register all Websites tools with the MCP server."""
    register_status_tools(mcp, mcp_tool_interceptor, metrics)
    register_hosting_tools(mcp, mcp_tool_interceptor, metrics)
    register_seo_tools(mcp, mcp_tool_interceptor, metrics)


__all__ = ["register_tools"]
```

- [ ] **Step 3: Verify tool registration**

Run: `python -c "from skills.websites.scripts.mcp import register_tools; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add skills/websites/scripts/mcp/__init__.py skills/websites/scripts/mcp/tools_status.py
git commit -m "feat(websites): add status, overview, and activity MCP tools"
```

---

### Task 3: MCP Tools — Hosting & Versions

**Files:**
- Create: `skills/websites/scripts/mcp/tools_hosting.py`
- Create: `skills/websites/scripts/deploy.py`

- [ ] **Step 1: Create deploy.py**

This is a library module (not a CLI script) that wraps the deploy pipeline for use by MCP tools.

```python
"""Website deploy pipeline — package, upload, extract.

Wraps the SCP + SSH deploy workflow for use by MCP tools and CLI.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SSH_ALIAS = "hostinger"


def _load_sites_config() -> dict:
    """Load sites.yaml config."""
    import yaml

    config_path = Path(__file__).parent.parent / "augur" / "data" / "sites.yaml"
    if not config_path.exists():
        return {}
    return yaml.safe_load(config_path.read_text()) or {}


def _get_site_config(domain: str) -> dict | None:
    """Get config for a specific site."""
    config = _load_sites_config()
    for site in config.get("sites", []):
        if site["domain"] == domain:
            return site
    return None


def list_versions(domain: str) -> list[dict]:
    """List packaged versions for a site."""
    cfg = _get_site_config(domain)
    if not cfg or cfg.get("deploy_method") != "scp":
        return []

    versions_dir = Path(cfg["versions_dir"]).expanduser()
    prefix = cfg.get("zip_prefix", "")
    if not versions_dir.exists():
        return []

    zips = sorted(versions_dir.glob(f"{prefix}*.zip"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for z in zips:
        stat = z.stat()
        # Extract version from e.g. "augur-run-V38.zip"
        version = z.stem.split("-")[-1]
        result.append({
            "version": version,
            "filename": z.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 1),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "path": str(z),
        })
    return result


def package_site(domain: str) -> dict:
    """Package local files into a new versioned zip."""
    cfg = _get_site_config(domain)
    if not cfg or cfg.get("deploy_method") != "scp":
        return {"success": False, "error": f"Site {domain} does not support SCP deploy"}

    site_key = cfg["site_key"]
    prefix = cfg["zip_prefix"]
    versions_dir = Path(cfg["versions_dir"]).expanduser()
    source_dir = Path(cfg["local_source"]).expanduser()

    if not source_dir.exists() or not any(source_dir.iterdir()):
        return {"success": False, "error": f"Source directory empty: {source_dir}"}

    versions_dir.mkdir(parents=True, exist_ok=True)

    # Auto-increment version
    existing = list(versions_dir.glob(f"{prefix}*.zip"))
    max_v = 0
    for f in existing:
        for part in f.stem.split("-"):
            clean = part.lstrip("Vv")
            if clean.isdigit():
                max_v = max(max_v, int(clean))
    next_v = max_v + 1
    filename = f"{prefix}-V{next_v}.zip"
    output_path = versions_dir / filename

    # Special handling for guriqo: enterprise.html -> index.html
    if site_key == "guriqo":
        enterprise = source_dir / "enterprise.html"
        if not enterprise.exists():
            return {"success": False, "error": f"enterprise.html not found in {source_dir}"}
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(enterprise, "index.html")
            zf.write(source_dir / "styles.css", "styles.css")
            for asset in ["gur-profile.jpg", "favicon.ico", "favicon.png"]:
                asset_path = source_dir / "assets" / asset
                if asset_path.exists():
                    zf.write(asset_path, f"assets/{asset}")
            api_dir = source_dir / "api"
            if api_dir.exists():
                for f in api_dir.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(source_dir))
    else:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    zf.write(file_path, file_path.relative_to(source_dir))

    size_mb = round(output_path.stat().st_size / (1024 * 1024), 1)

    # Prune old versions (keep 2)
    versions = sorted(versions_dir.glob(f"{prefix}*.zip"), key=lambda x: x.stat().st_mtime)
    for old in versions[:-2]:
        old.unlink()

    return {
        "success": True,
        "version": f"V{next_v}",
        "filename": filename,
        "size_mb": size_mb,
        "path": str(output_path),
    }


def deploy_to_server(domain: str, zip_path: str) -> dict:
    """Upload and extract a zip to the server via SSH."""
    cfg = _get_site_config(domain)
    if not cfg:
        return {"success": False, "error": f"No config for {domain}"}

    remote_dir = cfg["remote_dir"]
    zip_file = Path(zip_path)
    if not zip_file.exists():
        return {"success": False, "error": f"Zip not found: {zip_path}"}

    try:
        # SCP upload
        scp_result = subprocess.run(
            ["scp", str(zip_file), f"{SSH_ALIAS}:~/{remote_dir}/"],
            capture_output=True, text=True, timeout=120,
        )
        if scp_result.returncode != 0:
            return {"success": False, "error": f"SCP failed: {scp_result.stderr}"}

        # SSH extract + chmod + cleanup
        ssh_cmd = (
            f"cd {remote_dir} && "
            f"unzip -o {zip_file.name} && "
            f"rm {zip_file.name} && "
            f"find . -type f -exec chmod 644 {{}} \\; && "
            f"find . -type d -exec chmod 755 {{}} \\;"
        )
        ssh_result = subprocess.run(
            ["ssh", SSH_ALIAS, ssh_cmd],
            capture_output=True, text=True, timeout=120,
        )
        if ssh_result.returncode != 0:
            return {"success": False, "error": f"SSH extract failed: {ssh_result.stderr}"}

        return {
            "success": True,
            "domain": domain,
            "version": zip_file.stem.split("-")[-1],
            "message": f"Deployed {zip_file.name} to {domain}",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Deploy timed out (120s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

- [ ] **Step 2: Create tools_hosting.py**

```python
"""Website hosting, versions, and deploy MCP tools."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from augur_mcp.annotations import tool_annotations
from .tools_status import _check_http, _check_ssl, SITES, log_activity
from ..deploy import list_versions, package_site, deploy_to_server

logger = logging.getLogger(__name__)

SSH_ALIAS = "hostinger"


def _get_disk_usage(remote_dir: str) -> dict:
    """Get disk usage for a remote directory via SSH."""
    try:
        result = subprocess.run(
            ["ssh", SSH_ALIAS, f"du -sh {remote_dir} 2>/dev/null"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            size = result.stdout.strip().split("\t")[0]
            return {"size": size, "ok": True}
    except Exception:
        pass
    return {"size": "unknown", "ok": False}


def _get_waitlist_count(remote_dir: str) -> int | None:
    """Get waitlist signup count from server CSV."""
    try:
        result = subprocess.run(
            ["ssh", SSH_ALIAS, f"wc -l < {remote_dir}/data/waitlist.csv 2>/dev/null"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            count = int(result.stdout.strip())
            return max(0, count - 1)  # subtract header row
    except Exception:
        pass
    return None


def register_hosting_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register website hosting tools."""

    @mcp.tool(
        name="get-website-hosting",
        annotations=tool_annotations(
            {"title": "Get Website Hosting", "readOnlyHint": True, "idempotentHint": True}
        ),
    )
    @mcp_tool_interceptor
    async def get_website_hosting_tool(domain: str) -> str:
        """Get hosting details for a specific website.

        Args:
            domain: Site domain (e.g. augur.run, guriqo.com, danit-design.com)

        Returns:
            JSON with {success, data} containing status, SSL, versions, disk usage.
        """
        metrics.track_tool("get_website_hosting", skill="websites")

        import yaml

        config_path = __file__
        # Load site config
        sites_yaml = (
            __import__("pathlib").Path(__file__).parent.parent.parent
            / "augur" / "data" / "sites.yaml"
        )
        cfg = {}
        if sites_yaml.exists():
            raw = yaml.safe_load(sites_yaml.read_text()) or {}
            for s in raw.get("sites", []):
                if s["domain"] == domain:
                    cfg = s
                    break

        http = _check_http(domain)
        ssl_info = _check_ssl(domain)
        remote_dir = cfg.get("remote_dir", f"domains/{domain}/public_html")

        result: dict[str, Any] = {
            "domain": domain,
            "label": cfg.get("label", domain),
            "deploy_method": cfg.get("deploy_method", "unknown"),
            "http": http,
            "ssl": ssl_info,
            "disk": _get_disk_usage(remote_dir),
        }

        if cfg.get("deploy_method") == "scp":
            result["versions"] = list_versions(domain)
            if cfg.get("metrics", {}).get("waitlist"):
                result["waitlist_count"] = _get_waitlist_count(remote_dir)
        else:
            result["builder_url"] = cfg.get("builder_url", "https://hpanel.hostinger.com")

        return json.dumps({"success": True, "data": result}, indent=2, default=str)

    @mcp.tool(
        name="list-website-versions",
        annotations=tool_annotations(
            {"title": "List Website Versions", "readOnlyHint": True, "idempotentHint": True}
        ),
    )
    @mcp_tool_interceptor
    async def list_website_versions_tool(domain: str) -> str:
        """List packaged versions for a website.

        Args:
            domain: Site domain (e.g. augur.run)

        Returns:
            JSON with {success, data} where data is array of version objects.
        """
        metrics.track_tool("list_website_versions", skill="websites")
        versions = list_versions(domain)
        return json.dumps({"success": True, "data": versions}, indent=2, default=str)
```

- [ ] **Step 3: Commit**

```bash
git add skills/websites/scripts/deploy.py skills/websites/scripts/mcp/tools_hosting.py
git commit -m "feat(websites): add hosting, versions, and deploy MCP tools"
```

---

### Task 4: MCP Tools — SEO & Reports

**Files:**
- Create: `skills/websites/scripts/mcp/tools_seo.py`

- [ ] **Step 1: Create tools_seo.py**

```python
"""Website SEO audit and reports MCP tools."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from augur_mcp.annotations import tool_annotations
from .tools_status import _get_vault_websites_dir, _extract_seo_score

logger = logging.getLogger(__name__)


def register_seo_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register website SEO tools."""

    @mcp.tool(
        name="get-website-seo",
        annotations=tool_annotations(
            {"title": "Get Website SEO", "readOnlyHint": True, "idempotentHint": True}
        ),
    )
    @mcp_tool_interceptor
    async def get_website_seo_tool(domain: str) -> str:
        """Get latest SEO audit scores and findings for a website.

        Args:
            domain: Site domain (e.g. augur.run)

        Returns:
            JSON with {success, data} containing scores, findings, and audit date.
        """
        metrics.track_tool("get_website_seo", skill="websites")

        vault_dir = _get_vault_websites_dir()
        audit_dir = vault_dir / domain / "audits"

        if not audit_dir.exists():
            return json.dumps({
                "success": True,
                "data": {"domain": domain, "scores": None, "findings": [], "message": "No audits yet"},
            })

        audits = sorted(audit_dir.glob("*.md"), reverse=True)
        if not audits:
            return json.dumps({
                "success": True,
                "data": {"domain": domain, "scores": None, "findings": [], "message": "No audits yet"},
            })

        latest = audits[0]
        scores = _extract_seo_score(latest)
        findings = _extract_findings(latest)

        return json.dumps({
            "success": True,
            "data": {
                "domain": domain,
                "scores": scores,
                "findings": findings,
                "audit_file": latest.name,
            },
        }, indent=2, default=str)

    @mcp.tool(
        name="list-website-audits",
        annotations=tool_annotations(
            {"title": "List Website Audits", "readOnlyHint": True, "idempotentHint": True}
        ),
    )
    @mcp_tool_interceptor
    async def list_website_audits_tool(domain: str) -> str:
        """List historical SEO audits for a website.

        Args:
            domain: Site domain (e.g. augur.run)

        Returns:
            JSON with {success, data} where data is array of audit summaries.
        """
        metrics.track_tool("list_website_audits", skill="websites")

        vault_dir = _get_vault_websites_dir()
        audit_dir = vault_dir / domain / "audits"

        if not audit_dir.exists():
            return json.dumps({"success": True, "data": []})

        audits = sorted(audit_dir.glob("*.md"), reverse=True)
        results = []
        for audit_file in audits[:20]:
            scores = _extract_seo_score(audit_file)
            results.append({
                "filename": audit_file.name,
                "date": scores.get("date") if scores else None,
                "overall_score": scores.get("overall") if scores else None,
                "size_kb": round(audit_file.stat().st_size / 1024, 1),
            })

        return json.dumps({"success": True, "data": results}, indent=2, default=str)

    @mcp.tool(
        name="list-website-reports",
        annotations=tool_annotations(
            {"title": "List Website Reports", "readOnlyHint": True, "idempotentHint": True}
        ),
    )
    @mcp_tool_interceptor
    async def list_website_reports_tool(domain: str = "") -> str:
        """List generated PDF reports. If domain is empty, list all.

        Args:
            domain: Optional site domain filter

        Returns:
            JSON with {success, data} where data is array of report objects.
        """
        metrics.track_tool("list_website_reports", skill="websites")

        vault_dir = _get_vault_websites_dir()
        results = []

        domains = [domain] if domain else ["augur.run", "guriqo.com", "danit-design.com"]
        for d in domains:
            reports_dir = vault_dir / d / "reports"
            if not reports_dir.exists():
                continue
            for report in sorted(reports_dir.glob("*.pdf"), reverse=True):
                stat = report.stat()
                results.append({
                    "domain": d,
                    "filename": report.name,
                    "path": str(report),
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        return json.dumps({"success": True, "data": results}, indent=2, default=str)


def _extract_findings(audit_file: Path) -> list[dict]:
    """Extract findings list from audit file body."""
    try:
        text = audit_file.read_text()
        if "---" not in text:
            return []
        parts = text.split("---", 2)
        if len(parts) < 3:
            return []
        body = parts[2]

        findings = []
        current: dict[str, str] | None = None
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith("- **") and ":**" in line:
                if current:
                    findings.append(current)
                # Parse "- **Critical:** Description here"
                priority_end = line.index(":**")
                priority = line[4:priority_end]
                desc = line[priority_end + 3:].strip()
                current = {"priority": priority, "description": desc, "category": "general"}
            elif current and line.startswith("- "):
                # Sub-item becomes a separate finding
                findings.append({
                    "priority": current.get("priority", "medium"),
                    "description": line[2:].strip(),
                    "category": "general",
                })
        if current:
            findings.append(current)

        return findings[:50]
    except Exception:
        return []
```

- [ ] **Step 2: Commit**

```bash
git add skills/websites/scripts/mcp/tools_seo.py
git commit -m "feat(websites): add SEO audit and reports MCP tools"
```

---

### Task 5: Dashboard Page — Overview

**Files:**
- Create: `apps/dashboard/features/pages/websites/overview/page.tsx`

- [ ] **Step 1: Create overview page**

```tsx
'use client';

import { useMemo } from 'react';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { useActionRunner } from '@/hooks/useActionRunner';
import type { ActionDef } from '@/lib/actions/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Globe,
  Server,
  Shield,
  Search,
  Rocket,
  Activity,
  Clock,
  FileText,
} from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────────────

interface SiteStatus {
  domain: string;
  label: string;
  http: { status: number; ok: boolean };
  ssl: { expiry: string; days_left: number; ok: boolean };
}

interface SiteOverview {
  domain: string;
  label: string;
  version: { current: string | null; count: number; last_modified?: string };
  seo_score: { overall: number; date: string } | null;
}

interface ActivityEvent {
  type: string;
  domain: string;
  timestamp: string;
  version?: string;
  message?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function unwrap<T>(raw: unknown): T[] {
  if (!raw || typeof raw !== 'object') return [];
  const obj = raw as Record<string, unknown>;
  if (obj.success && Array.isArray(obj.data)) return obj.data as T[];
  return [];
}

function scoreColor(score: number | null | undefined): string {
  if (score == null) return 'text-zinc-500';
  if (score >= 75) return 'text-emerald-400';
  if (score >= 50) return 'text-amber-400';
  return 'text-red-400';
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ── Component ────────────────────────────────────────────────────────────────

export default function WebsitesOverviewPage() {
  const { runAction } = useActionRunner();

  const { data: statuses, loading: statusLoading } = useMcpQuery<SiteStatus[]>(
    'websites-status',
    'get-websites-status',
    'realtime',
    { select: (raw) => unwrap<SiteStatus>(raw) },
  );

  const { data: overviews, loading: overviewLoading } = useMcpQuery<SiteOverview[]>(
    'websites-overview',
    'get-websites-overview',
    'user-data',
    { select: (raw) => unwrap<SiteOverview>(raw) },
  );

  const { data: activity } = useMcpQuery<ActivityEvent[]>(
    'websites-activity',
    'get-websites-activity',
    'user-data',
    { select: (raw) => unwrap<ActivityEvent>(raw) },
  );

  const sites = useMemo(() => {
    if (!statuses || !overviews) return [];
    return statuses.map((status) => {
      const overview = overviews.find((o) => o.domain === status.domain);
      return { ...status, ...overview };
    });
  }, [statuses, overviews]);

  const loading = statusLoading || overviewLoading;

  const handleDeploy = (domain: string) => {
    runAction({
      id: `deploy-${domain}`,
      label: `Deploy ${domain}`,
      description: `Package and deploy ${domain} to Hostinger`,
      dispatch: 'ide',
      page: '/websites/hosting',
      args: { domain },
    } as ActionDef);
  };

  const handleAuditAll = () => {
    runAction({
      id: 'seo-audit-all',
      label: 'Run SEO Audit (All Sites)',
      description: 'Run /geo-audit for augur.run, guriqo.com, and danit-design.com',
      dispatch: 'ide',
      page: '/websites/seo',
    } as ActionDef);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Websites</h1>
        <p className="text-sm text-muted-foreground">All sites at a glance</p>
      </div>

      {/* Site Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {loading
          ? Array.from({ length: 3 }).map((_, i) => (
              <GlassCard key={i} color="blue">
                <div className="h-32 animate-pulse bg-white/5 rounded" />
              </GlassCard>
            ))
          : sites.map((site) => (
              <GlassCard key={site.domain} color="blue">
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        site.http?.ok ? 'bg-emerald-400' : 'bg-red-400'
                      }`}
                    />
                    <span className="font-semibold">{site.domain}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-xs text-muted-foreground uppercase">Version</div>
                      <div className="font-mono font-semibold">
                        {site.version?.current || '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground uppercase">SEO</div>
                      <div className={`font-mono font-semibold ${scoreColor(site.seo_score?.overall)}`}>
                        {site.seo_score?.overall ?? '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground uppercase">SSL</div>
                      <div className="text-sm">
                        {site.ssl?.days_left ? `${site.ssl.days_left}d` : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground uppercase">Status</div>
                      <Badge variant={site.http?.ok ? 'default' : 'destructive'} className="text-xs">
                        {site.http?.ok ? 'Online' : 'Down'}
                      </Badge>
                    </div>
                  </div>
                </div>
              </GlassCard>
            ))}
      </div>

      {/* Quick Actions */}
      <GlassCard color="purple" title="Quick Actions" icon={Rocket}>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => handleDeploy('augur.run')}>
            <Server className="w-3.5 h-3.5 mr-1.5" />
            Deploy augur.run
          </Button>
          <Button size="sm" variant="outline" onClick={handleAuditAll}>
            <Search className="w-3.5 h-3.5 mr-1.5" />
            Run SEO Audit (all)
          </Button>
          <Button size="sm" variant="outline" asChild>
            <a href="/websites/reports">
              <FileText className="w-3.5 h-3.5 mr-1.5" />
              Generate Report
            </a>
          </Button>
        </div>
      </GlassCard>

      {/* Recent Activity */}
      <GlassCard color="cyan" title="Recent Activity" icon={Activity}>
        {!activity || activity.length === 0 ? (
          <p className="text-sm text-muted-foreground">No activity yet</p>
        ) : (
          <div className="space-y-2">
            {activity.slice(0, 5).map((event, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                  <span>{event.type}</span>
                  <span className="text-muted-foreground">— {event.domain}</span>
                  {event.version && (
                    <Badge variant="outline" className="text-xs">{event.version}</Badge>
                  )}
                </div>
                <span className="text-muted-foreground text-xs">
                  {relativeTime(event.timestamp)}
                </span>
              </div>
            ))}
          </div>
        )}
      </GlassCard>
    </div>
  );
}
```

- [ ] **Step 2: Verify the file is valid TSX**

Run: `npx tsc --noEmit apps/dashboard/features/pages/websites/overview/page.tsx 2>&1 | head -5`

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/features/pages/websites/overview/page.tsx
git commit -m "feat(websites): add Overview dashboard page"
```

---

### Task 6: Dashboard Page — Hosting

**Files:**
- Create: `apps/dashboard/features/pages/websites/hosting/page.tsx`

- [ ] **Step 1: Create hosting page**

```tsx
'use client';

import { useState } from 'react';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { useActionRunner } from '@/hooks/useActionRunner';
import type { ActionDef } from '@/lib/actions/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  ExternalLink,
  Globe,
  HardDrive,
  Server,
  Shield,
  Upload,
  History,
} from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────────────

interface HostingData {
  domain: string;
  label: string;
  deploy_method: string;
  http: { status: number; ok: boolean };
  ssl: { expiry: string; days_left: number; ok: boolean };
  disk: { size: string; ok: boolean };
  versions?: VersionEntry[];
  waitlist_count?: number;
  builder_url?: string;
}

interface VersionEntry {
  version: string;
  filename: string;
  size_mb: number;
  modified: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function unwrap(raw: unknown): HostingData | null {
  if (!raw || typeof raw !== 'object') return null;
  const obj = raw as Record<string, unknown>;
  if (obj.success && obj.data) return obj.data as HostingData;
  return null;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

const DOMAINS = ['augur.run', 'guriqo.com', 'danit-design.com'];

// ── Component ────────────────────────────────────────────────────────────────

export default function WebsitesHostingPage() {
  const [activeTab, setActiveTab] = useState('augur.run');
  const { runAction } = useActionRunner();

  const { data, loading, refetch } = useMcpQuery<HostingData>(
    ['website-hosting', activeTab],
    'get-website-hosting',
    'realtime',
    {
      args: { domain: activeTab },
      select: (raw) => unwrap(raw),
    },
  );

  const handleDeploy = () => {
    runAction({
      id: `deploy-${activeTab}`,
      label: `Deploy ${activeTab}`,
      description: `Package local files and deploy ${activeTab} to Hostinger via SCP`,
      dispatch: 'ide',
      page: '/websites/hosting',
      args: { domain: activeTab },
    } as ActionDef);
  };

  const handleRollback = (version: VersionEntry) => {
    runAction({
      id: `rollback-${activeTab}-${version.version}`,
      label: `Rollback ${activeTab} to ${version.version}`,
      description: `Redeploy ${version.filename} to ${activeTab}`,
      dispatch: 'ide',
      page: '/websites/hosting',
      args: { domain: activeTab, zip_path: version.filename },
    } as ActionDef);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Hosting</h1>
        <p className="text-sm text-muted-foreground">Deploy, versions, SSL, and uptime</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {DOMAINS.map((d) => (
            <TabsTrigger key={d} value={d}>{d}</TabsTrigger>
          ))}
        </TabsList>

        {DOMAINS.map((domain) => (
          <TabsContent key={domain} value={domain} className="space-y-4 mt-4">
            {loading ? (
              <GlassCard color="blue">
                <div className="h-48 animate-pulse bg-white/5 rounded" />
              </GlassCard>
            ) : !data ? (
              <GlassCard color="blue">
                <p className="text-muted-foreground">No data available</p>
              </GlassCard>
            ) : (
              <>
                {/* Status */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <GlassCard color="cyan" title="HTTP Status" icon={Globe}>
                    <div className="flex items-center gap-2">
                      <span className={`w-2.5 h-2.5 rounded-full ${data.http?.ok ? 'bg-emerald-400' : 'bg-red-400'}`} />
                      <span className="text-lg font-mono">{data.http?.status || '—'}</span>
                      <Badge variant={data.http?.ok ? 'default' : 'destructive'}>
                        {data.http?.ok ? 'Online' : 'Down'}
                      </Badge>
                    </div>
                  </GlassCard>

                  <GlassCard color="emerald" title="SSL Certificate" icon={Shield}>
                    <div className="space-y-1">
                      <div className="text-lg font-mono">
                        {data.ssl?.days_left != null ? `${data.ssl.days_left} days` : '—'}
                      </div>
                      {data.ssl?.expiry && (
                        <div className="text-xs text-muted-foreground">
                          Expires {formatDate(data.ssl.expiry)}
                        </div>
                      )}
                    </div>
                  </GlassCard>

                  <GlassCard color="purple" title="Disk Usage" icon={HardDrive}>
                    <div className="text-lg font-mono">{data.disk?.size || '—'}</div>
                  </GlassCard>
                </div>

                {/* Deploy or Links */}
                {data.deploy_method === 'scp' ? (
                  <>
                    <GlassCard color="blue" title="Deploy" icon={Upload}>
                      <div className="flex items-center justify-between">
                        <div className="space-y-1">
                          <div className="text-sm">
                            Current: <span className="font-mono font-semibold">{data.versions?.[0]?.version || '—'}</span>
                          </div>
                          {data.versions?.[0]?.modified && (
                            <div className="text-xs text-muted-foreground">
                              Last deployed {formatDate(data.versions[0].modified)}
                            </div>
                          )}
                          {data.waitlist_count != null && (
                            <div className="text-xs text-muted-foreground">
                              Waitlist signups: {data.waitlist_count}
                            </div>
                          )}
                        </div>
                        <Button onClick={handleDeploy}>
                          <Upload className="w-3.5 h-3.5 mr-1.5" />
                          Package & Deploy
                        </Button>
                      </div>
                    </GlassCard>

                    <GlassCard color="amber" title="Version History" icon={History}>
                      {!data.versions || data.versions.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No versions found</p>
                      ) : (
                        <div className="space-y-2">
                          {data.versions.map((v) => (
                            <div key={v.version} className="flex items-center justify-between text-sm border-b border-white/5 pb-2 last:border-0">
                              <div className="flex items-center gap-3">
                                <span className="font-mono font-semibold">{v.version}</span>
                                <span className="text-muted-foreground">{v.size_mb}M</span>
                                <span className="text-muted-foreground">{formatDate(v.modified)}</span>
                              </div>
                              <Button size="sm" variant="outline" onClick={() => handleRollback(v)}>
                                Rollback
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </GlassCard>
                  </>
                ) : (
                  <GlassCard color="blue" title="Site Management" icon={ExternalLink}>
                    <div className="space-y-3">
                      <p className="text-sm text-muted-foreground">
                        This site is managed via the Hostinger Website Builder.
                      </p>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" asChild>
                          <a href={`https://${domain}`} target="_blank" rel="noopener noreferrer">
                            <Globe className="w-3.5 h-3.5 mr-1.5" />
                            Open Site
                          </a>
                        </Button>
                        <Button size="sm" variant="outline" asChild>
                          <a href={data.builder_url || 'https://hpanel.hostinger.com'} target="_blank" rel="noopener noreferrer">
                            <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                            Hostinger Panel
                          </a>
                        </Button>
                      </div>
                    </div>
                  </GlassCard>
                )}
              </>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/dashboard/features/pages/websites/hosting/page.tsx
git commit -m "feat(websites): add Hosting dashboard page with deploy and versions"
```

---

### Task 7: Dashboard Page — SEO

**Files:**
- Create: `apps/dashboard/features/pages/websites/seo/page.tsx`

- [ ] **Step 1: Create SEO page**

```tsx
'use client';

import { useState } from 'react';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { useActionRunner } from '@/hooks/useActionRunner';
import type { ActionDef } from '@/lib/actions/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertTriangle,
  BarChart3,
  Bot,
  FileCode2,
  Globe2,
  Megaphone,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Type,
} from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────────────

interface SeoScores {
  overall: number | null;
  technical: number | null;
  content: number | null;
  schema: number | null;
  ai_visibility: number | null;
  platform_readiness: {
    google_aio: number | null;
    chatgpt: number | null;
    perplexity: number | null;
    gemini: number | null;
    copilot: number | null;
  } | null;
  brand_authority: number | null;
  date: string | null;
}

interface Finding {
  priority: string;
  description: string;
  category: string;
}

interface SeoData {
  domain: string;
  scores: SeoScores | null;
  findings: Finding[];
  audit_file?: string;
  message?: string;
}

interface AuditEntry {
  filename: string;
  date: string | null;
  overall_score: number | null;
  size_kb: number;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function unwrapSeo(raw: unknown): SeoData | null {
  if (!raw || typeof raw !== 'object') return null;
  const obj = raw as Record<string, unknown>;
  if (obj.success && obj.data) return obj.data as SeoData;
  return null;
}

function unwrapAudits(raw: unknown): AuditEntry[] {
  if (!raw || typeof raw !== 'object') return [];
  const obj = raw as Record<string, unknown>;
  if (obj.success && Array.isArray(obj.data)) return obj.data as AuditEntry[];
  return [];
}

function scoreColor(score: number | null | undefined): string {
  if (score == null) return 'text-zinc-500';
  if (score >= 75) return 'text-emerald-400';
  if (score >= 50) return 'text-amber-400';
  return 'text-red-400';
}

function scoreBg(score: number | null | undefined): string {
  if (score == null) return 'bg-zinc-500/10';
  if (score >= 75) return 'bg-emerald-500/10';
  if (score >= 50) return 'bg-amber-500/10';
  return 'bg-red-500/10';
}

function priorityColor(p: string): 'destructive' | 'default' | 'secondary' | 'outline' {
  const lower = p.toLowerCase();
  if (lower === 'critical' || lower === 'high') return 'destructive';
  if (lower === 'medium') return 'default';
  return 'outline';
}

const DOMAINS = ['augur.run', 'guriqo.com', 'danit-design.com'];

const SCORE_DIMENSIONS = [
  { key: 'technical', label: 'Technical', icon: ShieldCheck },
  { key: 'content', label: 'Content', icon: Type },
  { key: 'schema', label: 'Schema', icon: FileCode2 },
  { key: 'ai_visibility', label: 'AI Visibility', icon: Bot },
] as const;

// ── Component ────────────────────────────────────────────────────────────────

export default function WebsitesSeoPage() {
  const [activeTab, setActiveTab] = useState('augur.run');
  const { runAction } = useActionRunner();

  const { data: seoData, loading } = useMcpQuery<SeoData>(
    ['website-seo', activeTab],
    'get-website-seo',
    'user-data',
    { args: { domain: activeTab }, select: (raw) => unwrapSeo(raw) },
  );

  const { data: audits } = useMcpQuery<AuditEntry[]>(
    ['website-audits', activeTab],
    'list-website-audits',
    'user-data',
    { args: { domain: activeTab }, select: (raw) => unwrapAudits(raw) },
  );

  const handleRunAudit = (type: string = 'full') => {
    const commands: Record<string, string> = {
      full: `/geo-audit ${activeTab}`,
      technical: `/geo-technical ${activeTab}`,
      content: `/geo-content ${activeTab}`,
      schema: `/geo-schema ${activeTab}`,
      crawlers: `/geo-crawlers ${activeTab}`,
      citability: `/geo-citability ${activeTab}`,
      platforms: `/geo-platform-optimizer ${activeTab}`,
      brand: `/geo-brand-mentions ${activeTab}`,
      llmstxt: `/geo-llmstxt ${activeTab}`,
    };
    runAction({
      id: `seo-${type}-${activeTab}`,
      label: `Run ${type} audit on ${activeTab}`,
      description: commands[type] || commands.full,
      dispatch: 'ide',
      page: '/websites/seo',
      args: { domain: activeTab, audit_type: type },
    } as ActionDef);
  };

  const scores = seoData?.scores;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">SEO</h1>
        <p className="text-sm text-muted-foreground">Audit scores, findings, and trends</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {DOMAINS.map((d) => (
            <TabsTrigger key={d} value={d}>{d}</TabsTrigger>
          ))}
        </TabsList>

        {DOMAINS.map((domain) => (
          <TabsContent key={domain} value={domain} className="space-y-4 mt-4">
            {loading ? (
              <GlassCard color="blue">
                <div className="h-48 animate-pulse bg-white/5 rounded" />
              </GlassCard>
            ) : (
              <>
                {/* Scores */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  {/* Overall */}
                  <GlassCard color="blue">
                    <div className="text-center space-y-1">
                      <div className="text-xs text-muted-foreground uppercase">Overall</div>
                      <div className={`text-3xl font-mono font-bold ${scoreColor(scores?.overall)}`}>
                        {scores?.overall ?? '—'}
                      </div>
                      {scores?.date && (
                        <div className="text-xs text-muted-foreground">{scores.date}</div>
                      )}
                    </div>
                  </GlassCard>
                  {/* Dimensions */}
                  {SCORE_DIMENSIONS.map(({ key, label, icon: Icon }) => (
                    <GlassCard key={key} color="cyan">
                      <div className="text-center space-y-1">
                        <div className="flex items-center justify-center gap-1">
                          <Icon className="w-3.5 h-3.5 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground uppercase">{label}</span>
                        </div>
                        <div className={`text-2xl font-mono font-bold ${scoreColor(scores?.[key])}`}>
                          {scores?.[key] ?? '—'}
                        </div>
                      </div>
                    </GlassCard>
                  ))}
                </div>

                {/* Platform Readiness */}
                <GlassCard color="purple" title="AI Platform Readiness" icon={Globe2}>
                  <div className="grid grid-cols-5 gap-3">
                    {[
                      { key: 'google_aio', label: 'Google AIO' },
                      { key: 'chatgpt', label: 'ChatGPT' },
                      { key: 'perplexity', label: 'Perplexity' },
                      { key: 'gemini', label: 'Gemini' },
                      { key: 'copilot', label: 'Copilot' },
                    ].map(({ key, label }) => {
                      const val = scores?.platform_readiness?.[key as keyof NonNullable<SeoScores['platform_readiness']>];
                      return (
                        <div key={key} className="text-center">
                          <div className="text-xs text-muted-foreground">{label}</div>
                          <div className={`text-xl font-mono font-bold ${scoreColor(val)}`}>
                            {val ?? '—'}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </GlassCard>

                {/* Brand Authority */}
                <GlassCard color="rose" title="Brand Authority" icon={Megaphone}>
                  <div className="flex items-center gap-4">
                    <div className={`text-3xl font-mono font-bold ${scoreColor(scores?.brand_authority)}`}>
                      {scores?.brand_authority ?? '—'}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Presence across Wikipedia, LinkedIn, YouTube, Reddit, and platforms AI models use for entity recognition.
                    </div>
                  </div>
                </GlassCard>

                {/* Run Audit */}
                <GlassCard color="blue" title="Run Audit" icon={Search}>
                  <div className="space-y-2">
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" onClick={() => handleRunAudit('full')}>
                        <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                        Full Audit
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleRunAudit('technical')}>
                        Technical
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleRunAudit('content')}>
                        Content
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleRunAudit('schema')}>
                        Schema
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleRunAudit('crawlers')}>
                        Crawlers
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleRunAudit('citability')}>
                        Citability
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => handleRunAudit('platforms')}>
                        <Globe2 className="w-3.5 h-3.5 mr-1.5" />
                        Platform Optimization
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleRunAudit('brand')}>
                        <Megaphone className="w-3.5 h-3.5 mr-1.5" />
                        Brand Mentions
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleRunAudit('llmstxt')}>
                        <Bot className="w-3.5 h-3.5 mr-1.5" />
                        Generate llms.txt
                      </Button>
                    </div>
                  </div>
                </GlassCard>

                {/* Findings */}
                <GlassCard color="amber" title="Findings" icon={AlertTriangle}>
                  {!seoData?.findings || seoData.findings.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {scores ? 'No issues found' : 'Run an audit to see findings'}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {seoData.findings.map((f, i) => (
                        <div key={i} className="flex items-start gap-2 text-sm">
                          <Badge variant={priorityColor(f.priority)} className="text-xs shrink-0">
                            {f.priority}
                          </Badge>
                          <span>{f.description}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </GlassCard>

                {/* Audit History */}
                <GlassCard color="cyan" title="Audit History" icon={TrendingUp}>
                  {!audits || audits.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No audit history</p>
                  ) : (
                    <div className="space-y-2">
                      {audits.map((a) => (
                        <div key={a.filename} className="flex items-center justify-between text-sm border-b border-white/5 pb-2 last:border-0">
                          <div className="flex items-center gap-3">
                            <span className="text-muted-foreground">{a.date || a.filename}</span>
                            <span className={`font-mono font-semibold ${scoreColor(a.overall_score)}`}>
                              {a.overall_score ?? '—'}
                            </span>
                          </div>
                          <span className="text-xs text-muted-foreground">{a.size_kb}KB</span>
                        </div>
                      ))}
                    </div>
                  )}
                </GlassCard>
              </>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/dashboard/features/pages/websites/seo/page.tsx
git commit -m "feat(websites): add SEO dashboard page with scores, audit, and findings"
```

---

### Task 8: Dashboard Page — Reports

**Files:**
- Create: `apps/dashboard/features/pages/websites/reports/page.tsx`

- [ ] **Step 1: Create reports page**

```tsx
'use client';

import { useState } from 'react';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { useActionRunner } from '@/hooks/useActionRunner';
import type { ActionDef } from '@/lib/actions/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Download,
  FileText,
  Plus,
} from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────────────

interface Report {
  domain: string;
  filename: string;
  path: string;
  size_kb: number;
  modified: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function unwrapReports(raw: unknown): Report[] {
  if (!raw || typeof raw !== 'object') return [];
  const obj = raw as Record<string, unknown>;
  if (obj.success && Array.isArray(obj.data)) return obj.data as Report[];
  return [];
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  } catch { return iso; }
}

const DOMAINS = ['augur.run', 'guriqo.com', 'danit-design.com'];

const REPORT_TYPES = [
  { id: 'full', label: 'Full GEO Audit Report', command: '/geo-report-pdf' },
  { id: 'compare', label: 'Comparison Report', command: '/geo-compare' },
  { id: 'summary', label: 'Executive Summary', command: '/geo-report' },
  { id: 'proposal', label: 'Client Proposal', command: '/geo-proposal' },
  { id: 'brand', label: 'Brand Authority Report', command: '/geo-brand-mentions' },
];

// ── Component ────────────────────────────────────────────────────────────────

export default function WebsitesReportsPage() {
  const [selectedDomain, setSelectedDomain] = useState('augur.run');
  const { runAction } = useActionRunner();

  const { data: reports, loading } = useMcpQuery<Report[]>(
    'website-reports',
    'list-website-reports',
    'user-data',
    { select: (raw) => unwrapReports(raw) },
  );

  const handleGenerate = (type: typeof REPORT_TYPES[number]) => {
    runAction({
      id: `report-${type.id}-${selectedDomain}`,
      label: `Generate ${type.label} for ${selectedDomain}`,
      description: `${type.command} ${selectedDomain}`,
      dispatch: 'ide',
      page: '/websites/reports',
      args: { domain: selectedDomain, report_type: type.id },
    } as ActionDef);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Reports</h1>
        <p className="text-sm text-muted-foreground">Generate and download SEO reports</p>
      </div>

      {/* Generate Report */}
      <GlassCard color="purple" title="Generate Report" icon={Plus}>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-muted-foreground uppercase block mb-2">Site</label>
            <div className="flex gap-2">
              {DOMAINS.map((d) => (
                <Button
                  key={d}
                  size="sm"
                  variant={selectedDomain === d ? 'default' : 'outline'}
                  onClick={() => setSelectedDomain(d)}
                >
                  {d}
                </Button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground uppercase block mb-2">Report Type</label>
            <div className="flex flex-wrap gap-2">
              {REPORT_TYPES.map((type) => (
                <Button key={type.id} size="sm" variant="outline" onClick={() => handleGenerate(type)}>
                  <FileText className="w-3.5 h-3.5 mr-1.5" />
                  {type.label}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Report History */}
      <GlassCard color="cyan" title="Report History" icon={FileText}>
        {loading ? (
          <div className="h-24 animate-pulse bg-white/5 rounded" />
        ) : !reports || reports.length === 0 ? (
          <p className="text-sm text-muted-foreground">No reports generated yet. Use the form above to create one.</p>
        ) : (
          <div className="space-y-2">
            {reports.map((report) => (
              <div key={report.path} className="flex items-center justify-between text-sm border-b border-white/5 pb-2 last:border-0">
                <div className="flex items-center gap-3">
                  <FileText className="w-4 h-4 text-muted-foreground" />
                  <span className="font-mono">{report.filename}</span>
                  <Badge variant="outline" className="text-xs">{report.domain}</Badge>
                  <span className="text-muted-foreground">{report.size_kb}KB</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{formatDate(report.modified)}</span>
                  <Button size="sm" variant="ghost" asChild>
                    <a href={report.path} download>
                      <Download className="w-3.5 h-3.5" />
                    </a>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/dashboard/features/pages/websites/reports/page.tsx
git commit -m "feat(websites): add Reports dashboard page"
```

---

### Task 9: Mount Hub & Verify Build

- [ ] **Step 1: Run mount-plugins to discover the new hub**

```bash
cd apps/dashboard && pnpm run mount-plugins
```

Expected: Output shows `websites` hub discovered with 4 pages, `0 orphans`.

- [ ] **Step 2: Verify build**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -20
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Start dev server and verify pages load**

Use `/dev-build` to start the dev server, then navigate to:
- `http://localhost:3000/websites/overview`
- `http://localhost:3000/websites/hosting`
- `http://localhost:3000/websites/seo`
- `http://localhost:3000/websites/reports`

Verify each page renders without errors.

- [ ] **Step 4: Verify MCP tools respond**

```bash
curl -s http://localhost:3000/api/mcp/tool -X POST \
  -H 'Content-Type: application/json' \
  -d '{"tool":"get-websites-status","args":{}}' | python3 -m json.tool | head -20
```

Expected: JSON with `success: true` and status data for all 3 sites.

- [ ] **Step 5: Commit mount changes**

```bash
git add apps/dashboard/app/websites/
git commit -m "feat(websites): mount hub with catch-all registry and 4 pages"
```

---

### Task 10: Create Vault Directory Structure

- [ ] **Step 1: Create vault directories for audit and report storage**

```bash
vault_dir=$(python3 -c "from src.config.paths import get_vault_dir; print(get_vault_dir())")
mkdir -p "$vault_dir/websites/augur.run/audits"
mkdir -p "$vault_dir/websites/augur.run/reports"
mkdir -p "$vault_dir/websites/guriqo.com/audits"
mkdir -p "$vault_dir/websites/guriqo.com/reports"
mkdir -p "$vault_dir/websites/danit-design.com/audits"
mkdir -p "$vault_dir/websites/danit-design.com/reports"
echo '[]' > "$vault_dir/websites/activity.json"
```

- [ ] **Step 2: Verify vault structure**

```bash
find "$vault_dir/websites" -type d | sort
```

Expected:
```
.../websites
.../websites/augur.run
.../websites/augur.run/audits
.../websites/augur.run/reports
.../websites/danit-design.com
.../websites/danit-design.com/audits
.../websites/danit-design.com/reports
.../websites/guriqo.com
.../websites/guriqo.com/audits
.../websites/guriqo.com/reports
```

No commit needed — vault is external data, not tracked in git.
