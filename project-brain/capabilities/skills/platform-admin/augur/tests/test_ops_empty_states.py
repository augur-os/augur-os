"""Tests for auto-empty-states dashboard scanner."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "ops" / "empty_states.py"
)
SPEC = importlib.util.spec_from_file_location("ops_empty_states_module", MODULE_PATH)
assert SPEC and SPEC.loader
ops_empty_states = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ops_empty_states)


def _write_page(tmp_path: Path, rel_path: str, content: str) -> None:
    page_path = tmp_path / rel_path
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(content, encoding="utf-8")


def _scan(tmp_path: Path, *, difficulty: int = 0):
    return ops_empty_states.scan(OpsContext(project_root=tmp_path, difficulty=difficulty))


def test_scan_flags_page_without_empty_state(tmp_path: Path):
    _write_page(
        tmp_path,
        "apps/dashboard/app/adaptive/foo/page.tsx",
        """
        import { useCachedFetch } from '@/lib/hooks/useCachedFetch';

        export default function Page() {
          const { data } = useCachedFetch(['foo'], '/api/foo', 'config');
          return <div>{data?.items?.map((item) => <div key={item.id}>{item.name}</div>)}</div>;
        }
        """,
    )

    result = _scan(tmp_path)

    assert len(result.issues) == 1
    assert result.issues[0]["file"].replace("\\", "/") == "apps/dashboard/app/adaptive/foo/page.tsx"


def test_scan_accepts_reusable_empty_component_copy(tmp_path: Path):
    _write_page(
        tmp_path,
        "apps/dashboard/app/life/attention/page.tsx",
        """
        import { useActionRunner } from '@/hooks/useActionRunner';

        function EmptySection({ label }: { label: string }) {
          return <p>No {label.toLowerCase()} items</p>;
        }

        export default function Page() {
          const items = [];
          const { runAction } = useActionRunner();
          return <div>{items.length > 0 ? items.map((item) => item.id) : <EmptySection label="Critical" />}</div>;
        }
        """,
    )

    result = _scan(tmp_path, difficulty=1)

    assert result.issues == []


def test_scan_accepts_inline_empty_state_text(tmp_path: Path):
    _write_page(
        tmp_path,
        "apps/dashboard/app/career/career/page.tsx",
        """
        import { useCachedFetch } from '@/lib/hooks/useCachedFetch';

        export default function Page() {
          const { data: status } = useCachedFetch(['career'], '/api/career', 'config');
          if (!status) {
            return <p>No career status data available</p>;
          }
          return <div>{status.stage}</div>;
        }
        """,
    )

    result = _scan(tmp_path)

    assert result.issues == []


def test_scan_accepts_domain_specific_empty_copy(tmp_path: Path):
    _write_page(
        tmp_path,
        "apps/dashboard/app/life/health/page.tsx",
        """
        import { useCachedFetch } from '@/lib/hooks/useCachedFetch';

        export default function Page() {
          const { data } = useCachedFetch(['health'], '/api/health', 'config');
          return (
            <div>
              <p>No symptoms recorded</p>
              <p>No medications recorded</p>
              <p>No history entries</p>
              {data?.history?.map((entry) => <div key={entry.id}>{entry.label}</div>)}
            </div>
          );
        }
        """,
    )

    result = _scan(tmp_path)

    assert result.issues == []


def test_scan_difficulty_one_checks_pages_using_consumed_data(tmp_path: Path):
    _write_page(
        tmp_path,
        "apps/dashboard/app/life/overview/page.tsx",
        """
        export default function Page({ items }: { items: { id: string }[] }) {
          return <div>{items.map((item) => <span key={item.id}>{item.id}</span>)}</div>;
        }
        """,
    )

    result = _scan(tmp_path, difficulty=1)

    assert len(result.issues) == 1


def test_scan_difficulty_one_ignores_static_constant_maps(tmp_path: Path):
    _write_page(
        tmp_path,
        "apps/dashboard/app/business/venture/gtm/page.tsx",
        """
        const GTM_SECTIONS = [{ id: 'marketing' }];

        export default function Page() {
          return <div>{GTM_SECTIONS.map((section) => <span key={section.id}>{section.id}</span>)}</div>;
        }
        """,
    )

    result = _scan(tmp_path, difficulty=1)

    assert result.issues == []


def test_scan_difficulty_one_ignores_utility_array_transforms(tmp_path: Path):
    _write_page(
        tmp_path,
        "apps/dashboard/app/settings/skills/[skill]/page.tsx",
        """
        export default async function Page() {
          const disabled = new Set(Array.from(['a', 'b']).map((value) => value.toUpperCase()));
          return <div>{disabled.size}</div>;
        }
        """,
    )

    result = _scan(tmp_path, difficulty=1)

    assert result.issues == []


def test_scan_accepts_delegation_to_local_grid_component(tmp_path: Path):
    # Pages that orchestrate state and delegate the empty branch to a sibling
    # rendering component (Grid/Content/List/View/...) should not be flagged
    # as missing empty-state handling.
    _write_page(
        tmp_path,
        "apps/dashboard/app/views/browse/BrowseContentGrid.tsx",
        """
        export function BrowseContentGrid({ items }: { items: any[] }) {
          if (items.length === 0) {
            return <div>No items found</div>;
          }
          return <div>{items.map((it) => <div key={it.id}>{it.name}</div>)}</div>;
        }
        """,
    )
    _write_page(
        tmp_path,
        "apps/dashboard/app/views/browse/page.tsx",
        """
        import { useCachedFetch } from '@/lib/hooks/useCachedFetch';
        import { BrowseContentGrid } from './BrowseContentGrid';

        export default function Page() {
          const { data } = useCachedFetch(['browse'], '/api/browse', 'config');
          return <BrowseContentGrid items={data?.items ?? []} />;
        }
        """,
    )

    result = _scan(tmp_path, difficulty=1)

    assert result.issues == []


def test_scan_still_flags_when_delegate_lacks_empty_state(tmp_path: Path):
    # If both the page and its delegate lack empty-state patterns, the scanner
    # must keep flagging — delegation is not a free pass.
    _write_page(
        tmp_path,
        "apps/dashboard/app/views/silent/SilentList.tsx",
        """
        export function SilentList({ items }: { items: any[] }) {
          return <ul>{items.map((it) => <li key={it.id}>{it.name}</li>)}</ul>;
        }
        """,
    )
    _write_page(
        tmp_path,
        "apps/dashboard/app/views/silent/page.tsx",
        """
        import { useCachedFetch } from '@/lib/hooks/useCachedFetch';
        import { SilentList } from './SilentList';

        export default function Page() {
          const { data } = useCachedFetch(['silent'], '/api/silent', 'config');
          return <SilentList items={data?.items ?? []} />;
        }
        """,
    )

    result = _scan(tmp_path, difficulty=1)

    assert len(result.issues) == 1
    assert result.issues[0]["file"].replace("\\", "/") == "apps/dashboard/app/views/silent/page.tsx"


def test_module_name():
    assert ops_empty_states.name == "auto-empty-states"
