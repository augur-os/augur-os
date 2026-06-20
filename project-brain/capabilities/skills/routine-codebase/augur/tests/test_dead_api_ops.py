from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "dead_api_ops.py"
)
_SPEC = importlib.util.spec_from_file_location("dead_api_ops_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
dead_api_ops = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dead_api_ops)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _shared_skills(tmp_path: Path) -> Path:
    return tmp_path / "project-brain" / "capabilities" / "skills"


def test_collect_api_consumers_reads_skill_config_routes(tmp_path: Path) -> None:
    _write(
        _shared_skills(tmp_path) / "advisor" / "SKILL.md",
        """---
name: advisor
x-augur-hub: dev
x-augur-config:
  contributions:
    pages:
      - id: overview
        data_source:
          api_route: /api/dev/advisor/analytics
    actions:
      - endpoint: /api/dev/skill-health
      - submitTool: /api/dev/audit-chains
---
Body
""",
    )

    refs = dead_api_ops._collect_api_consumers(tmp_path)

    assert "/api/dev/advisor/analytics" in refs
    assert "/api/dev/skill-health" in refs
    assert "/api/dev/audit-chains" in refs


def test_collect_api_consumers_reads_skill_frontmatter_routes(tmp_path: Path) -> None:
    _write(
        _shared_skills(tmp_path) / "smb-client-template" / "SKILL.md",
        """---
name: smb-client-template
x-augur-config:
  contributions:
    actions:
      - id: refresh-posts
        submitTool: /api/career/smb-client-template/content-pipeline/posts
    views:
      - id: docs
        tool: /api/life/google-workspace/docs
---
Body
""",
    )

    refs = dead_api_ops._collect_api_consumers(tmp_path)

    assert "/api/career/smb-client-template/content-pipeline/posts" in refs
    assert "/api/life/google-workspace/docs" in refs


def test_collect_api_consumers_reads_route_to_route_probes(tmp_path: Path) -> None:
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "api" / "settings" / "layout" / "pulse" / "route.ts",
        """
        const DEEP_ENDPOINTS = [
          "/api/agents/available",
          "/api/assets/relevant",
        ];
        """,
    )

    refs = dead_api_ops._collect_api_consumers(tmp_path)

    assert "/api/agents/available" in refs
    assert "/api/assets/relevant" in refs


def test_collect_api_consumers_ignores_route_doc_comments(tmp_path: Path) -> None:
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "api" / "agents" / "available" / "route.ts",
        """
        /**
         * GET /api/agents/available
         */
        export async function GET() {
          return Response.json({ ok: true });
        }
        """,
    )

    refs = dead_api_ops._collect_api_consumers(tmp_path)

    assert "/api/agents/available" not in refs


def test_collect_api_consumers_normalizes_query_string_refs(tmp_path: Path) -> None:
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "productivity" / "page.tsx",
        """
        const reminders = '/api/productivity/apple/reminders?filter=today';
        await fetch(`/api/data/browse?${params}`);
        """,
    )

    refs = dead_api_ops._collect_api_consumers(tmp_path)

    assert "/api/productivity/apple/reminders" in refs
    assert "/api/data/browse" in refs


def test_collect_api_consumers_reads_template_literal_endpoint_constants(tmp_path: Path) -> None:
    _write(
        _shared_skills(tmp_path) / "career" / "augur" / "dashboard" / "ProfileDocPanel.tsx",
        """
        export function panel(doc: string) {
          const endpoint = `/api/career/career/profile/docs/${encodeURIComponent(doc)}`;
          return endpoint;
        }
        """,
    )

    refs = dead_api_ops._collect_api_consumers(tmp_path)

    assert "/api/career/career/profile/docs" in refs


def test_collect_api_consumers_infers_matching_page_routes(tmp_path: Path) -> None:
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "admin" / "updater" / "releases" / "page.tsx",
        "export default function Page() { return null; }\n",
    )

    refs = dead_api_ops._collect_api_consumers(tmp_path)

    assert "/api/admin/updater/releases" in refs


def test_external_entrypoint_routes_are_not_treated_as_orphans(tmp_path: Path) -> None:
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "api" / "setup" / "llm" / "config" / "route.ts",
        "export async function GET() { return Response.json({ ok: true }); }\n",
    )
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "api" / "agents" / "wizard" / "generate" / "route.ts",
        "export async function POST() { return Response.json({ ok: true }); }\n",
    )

    result = dead_api_ops.scan(dead_api_ops.OpsContext(project_root=tmp_path, difficulty=1))

    assert result.issues == []


def test_dynamic_api_route_matches_concrete_consumer_ref(tmp_path: Path) -> None:
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "api" / "career" / "career" / "profile" / "docs" / "[doc]" / "route.ts",
        "export async function GET() { return Response.json({ ok: true }); }\n",
    )
    _write(
        _shared_skills(tmp_path) / "career" / "augur" / "dashboard" / "ProfileDocPanel.tsx",
        """
        export async function loadDoc(doc: string) {
          return fetch(`/api/career/career/profile/docs/${encodeURIComponent(doc)}`);
        }
        """,
    )

    result = dead_api_ops.scan(dead_api_ops.OpsContext(project_root=tmp_path, difficulty=1))

    assert result.issues == []


def test_collect_api_routes_uses_shared_snapshot(tmp_path: Path) -> None:
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "api" / "setup" / "llm" / "config" / "route.ts",
        "export async function GET() { return Response.json({ ok: true }); }\n",
    )
    routes = dead_api_ops._collect_api_routes(
        tmp_path,
        {
            "api_routes": ["/api/setup/llm/config"],
            "api_route_paths": ["apps/dashboard/app/api/setup/llm/config/route.ts"],
        },
    )

    assert routes == {
        "/api/setup/llm/config": tmp_path / "apps" / "dashboard" / "app" / "api" / "setup" / "llm" / "config" / "route.ts",
    }


def test_scan_d2_does_not_flag_successful_delete_route_as_stub(tmp_path: Path) -> None:
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "api" / "views" / "[id]" / "route.ts",
        """
        import { NextResponse } from "next/server";
        import { ViewStorage } from "@/lib/blocks/view-storage";

        const storage = new ViewStorage();

        export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
          const { id } = await params;
          const deleted = storage.delete(id);
          if (!deleted) {
            return NextResponse.json({ error: "View not found" }, { status: 404 });
          }
          return NextResponse.json({ success: true });
        }
        """,
    )
    _write(
        tmp_path / "apps" / "dashboard" / "lib" / "webmcp" / "tools" / "views.ts",
        """
        export async function dropView(viewId: string) {
          return fetch(`/api/views/${viewId}`, { method: "DELETE" });
        }
        """,
    )

    result = dead_api_ops.scan(dead_api_ops.OpsContext(project_root=tmp_path, difficulty=2))

    assert result.issues == []


def test_scan_clears_stale_report_when_no_orphans(tmp_path: Path, monkeypatch) -> None:
    cleared: list[str] = []
    monkeypatch.setattr(dead_api_ops, "clear_report", lambda filename: cleared.append(filename))

    _write(
        tmp_path / "apps" / "dashboard" / "app" / "api" / "life" / "google-workspace" / "install" / "route.ts",
        "export async function POST() { return Response.json({ ok: true }); }\n",
    )
    _write(
        _shared_skills(tmp_path) / "google-workspace" / "augur" / "dashboard" / "InstallButton.tsx",
        "export const path = '/api/life/google-workspace/install';\n",
    )

    result = dead_api_ops.scan(dead_api_ops.OpsContext(project_root=tmp_path, difficulty=1))

    assert result.issues == []
    assert cleared == ["dead-api-latest.json"]
