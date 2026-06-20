"""Browse item promotion helpers."""

from __future__ import annotations

import getpass
import json
from pathlib import Path

from src.config.paths import get_project_brain_dir, get_vault_dir
from src.lib.vault_promotion import PromotionPacketRequest, create_promotion_packet

_ALLOWED_PROMOTION_CATEGORIES = {"notes", "sources", "wiki", "skills"}
_CATEGORY_SOURCE_ROOTS = {
    "notes": "notes",
    "sources": "sources",
    "wiki": "wiki",
    "skills": "skills",
}


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_source_brain(resolved_source: Path, private_vault: Path) -> tuple[str | None, Path | None]:
    """Resolve the brain that owns ``resolved_source`` (ADR-771).

    Private-vault items belong to the personal brain. Otherwise look up the
    registered brain whose ``data_root`` contains the source. Returns
    ``(brain_id, source_root)`` or ``(None, None)`` when no brain owns the path.
    """
    if _is_relative_to(resolved_source, private_vault):
        return "personal", private_vault

    try:
        from src.lib.brain_registry import get_registry

        registry = get_registry()
    except Exception:
        return None, None

    best: tuple[str, Path] | None = None
    for brain in registry.brains.values():
        root = Path(brain.data_root).expanduser().resolve(strict=False)
        if _is_relative_to(resolved_source, root):
            if best is None or len(root.parts) > len(best[1].parts):
                best = (brain.id, root)
    if best is None:
        return None, None
    return best


def _resolve_target_brain(target_brain_id: str):
    """Return the registered target brain, or ``None`` when not registered."""
    try:
        from src.lib.brain_registry import get_registry

        registry = get_registry()
    except Exception:
        return None
    return registry.get(target_brain_id)


def promote_browse_item_impl(
    category: str,
    title: str,
    source_path: str,
    description: str = "",
    roles: list[str] | str | None = None,
    domains: list[str] | str | None = None,
    to: str | None = None,
) -> str:
    """Create an append-only promotion packet for an item (ADR-771).

    Default (no ``to``): a project-brain promotion packet for a private-vault
    item. With an explicit ``to`` brain id: a source-contained
    ``<source-brain> -> <target-brain>`` propagation packet written into the
    target brain's promotions inbox.
    """
    normalized_category = category.strip().lower()
    if normalized_category not in _ALLOWED_PROMOTION_CATEGORIES:
        return json.dumps(
            {
                "success": False,
                "message": ("category must be one of: " f"{', '.join(sorted(_ALLOWED_PROMOTION_CATEGORIES))}"),
            }
        )

    source = Path(source_path).expanduser()
    private_vault = get_vault_dir().expanduser().resolve()
    try:
        resolved_source = source.resolve(strict=True)
    except FileNotFoundError:
        return json.dumps({"success": False, "message": "source_path does not exist"})

    if not resolved_source.is_file():
        return json.dumps({"success": False, "message": "source_path must be a file"})

    contributor = getpass.getuser() or "local-user"
    synthesis_body = description.strip() or f"Promotion packet for {title.strip()}."
    if to is None:
        # Legacy path: private vault -> project brain (ADR-770 moved the
        # shared-vault target into the project brain).
        if not _is_relative_to(resolved_source, private_vault):
            return json.dumps(
                {
                    "success": False,
                    "message": "source_path must be inside the private vault",
                }
            )
        source_reference = resolved_source.relative_to(private_vault).as_posix()
        expected_root = _CATEGORY_SOURCE_ROOTS[normalized_category]
        actual_root = source_reference.split("/", 1)[0] if source_reference else ""
        if actual_root != expected_root:
            return json.dumps(
                {
                    "success": False,
                    "message": (f"source_path does not match category: {normalized_category}"),
                }
            )
        synthesis = f"{synthesis_body}\n\nSource: {source_reference}"
        request = PromotionPacketRequest(
            topic=title,
            contributor=contributor,
            synthesis=synthesis,
            source_paths=[resolved_source],
            source_root=private_vault,
            roles=_as_string_list(roles),
            domains=_as_string_list(domains),
        )
        packet_root = get_project_brain_dir()
    else:
        # Explicit cross-brain propagation packet.
        target = _resolve_target_brain(to)
        if target is None:
            return json.dumps({"success": False, "message": f"brain not registered: {to}"})
        source_brain_id, source_root = _resolve_source_brain(resolved_source, private_vault)
        if source_root is None:
            return json.dumps(
                {
                    "success": False,
                    "message": "source_path is not inside any registered brain",
                }
            )
        source_reference = resolved_source.relative_to(source_root).as_posix()
        synthesis = f"{synthesis_body}\n\nSource: {source_reference}"
        request = PromotionPacketRequest(
            topic=title,
            contributor=contributor,
            synthesis=synthesis,
            source_paths=[resolved_source],
            source_brain_id=source_brain_id,
            target_brain_id=to,
            source_root=source_root,
            roles=_as_string_list(roles),
            domains=_as_string_list(domains),
        )
        packet_root = Path(target.data_root)

    try:
        packet = create_promotion_packet(packet_root, request)
    except ValueError as exc:
        return json.dumps({"success": False, "message": str(exc)})

    return json.dumps(
        {
            "success": True,
            "message": "Promotion packet created",
            "packet_path": str(packet.path),
            "manifest_path": str(packet.manifest_path),
            "synthesis_path": str(packet.synthesis_path),
        }
    )
