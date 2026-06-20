"""Generic plugin utilities for skill MCP tools.

Provides SkillDataStore for YAML/JSON data operations and register_crud_tools()
for auto-registering CRUD MCP tools from skill frontmatter config.

Part of ADR-126: Generic Plugin Template Refactor — Claude-Native Skill Standard.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Use canonical MCP imports, with fallback for standalone mode.
try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations


logger = get_entity_logger("mcp.plugin_utils")


def _parse_skill_frontmatter(skill_path: Path) -> dict:
    """Read SKILL.md frontmatter, including optional sidecar config."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return {}
    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(frontmatter, dict):
        return {}

    config_file = frontmatter.get("x-augur-config-file")
    if config_file and "x-augur-config" not in frontmatter:
        sidecar_path = skill_path / str(config_file)
        if sidecar_path.exists():
            try:
                sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8")) or {}
                if isinstance(sidecar, dict):
                    frontmatter["x-augur-config"] = sidecar
            except yaml.YAMLError:
                pass

    return frontmatter


def _load_skill_config(skill_path: Path) -> dict:
    """Load canonical skill config from SKILL.md frontmatter."""
    frontmatter = _parse_skill_frontmatter(skill_path)
    config = frontmatter.get("x-augur-config", {})
    if not isinstance(config, dict):
        config = {}

    merged = dict(config)
    if "name" not in merged and isinstance(frontmatter.get("name"), str):
        merged["name"] = frontmatter["name"]
    if "description" not in merged and isinstance(frontmatter.get("description"), str):
        merged["description"] = frontmatter["description"]
    if "mcp_tools" not in merged and isinstance(frontmatter.get("x-augur-mcp-tools"), list):
        merged["mcp_tools"] = frontmatter["x-augur-mcp-tools"]
    if "mcp" not in merged and isinstance(frontmatter.get("x-augur-mcp-tiers"), dict):
        merged["mcp"] = {"tiers": frontmatter["x-augur-mcp-tiers"]}
    elif isinstance(merged.get("mcp"), dict) and isinstance(frontmatter.get("x-augur-mcp-tiers"), dict):
        merged["mcp"] = {**merged["mcp"], "tiers": frontmatter["x-augur-mcp-tiers"]}

    return merged


class SkillDataStore:
    """Generic YAML/JSON data store for any skill's MCP tools.

    Reads SKILL.md x-augur-config metadata to understand entity structure.
    User data lives in the skill's vault directory with assets/seeds
    as the default fallback for migrated ADR-270 skills.

    Example usage in a plugin's mcp/__init__.py::

        store = SkillDataStore(Path(__file__).parent.parent)
        symptoms = store.list_entities("symptoms.yaml", "symptoms")
        new_entry = store.add_entity("symptoms.yaml", "symptoms", {"name": "Headache", "severity": 5})
    """

    def __init__(self, skill_path: Path):
        """Initialize store pointing to a skill directory.

        Args:
            skill_path: Path to the skill root.
        """
        self.skill_path = Path(skill_path)
        self.assets_seed_dir = self.skill_path / "assets" / "seeds"
        self.data_dir = self._resolve_data_dir()
        self._config: dict | None = None

    def _resolve_data_dir(self) -> Path:
        """Resolve the data directory — vault first, seeds fallback."""
        try:
            from src.config.paths import get_skill_data_dir

            return get_skill_data_dir(self.skill_path.name)
        except Exception:
            # Standalone mode: no vault configured, use seeds as working dir
            return self.assets_seed_dir

    @property
    def config(self) -> dict:
        """Load canonical skill config lazily from SKILL.md frontmatter."""
        if self._config is None:
            self._config = _load_skill_config(self.skill_path)
        return self._config

    def _resolve_path(self, filename: str) -> Path:
        """Resolve the writable path for a data filename under the vault."""
        return self.data_dir / filename

    def _resolve_read_path(self, filename: str) -> Path:
        """Resolve a readable path using vault-first, assets fallback."""
        path = self._resolve_path(filename)
        if path.exists():
            return path

        asset_path = self.assets_seed_dir / filename
        if asset_path.exists():
            return asset_path

        return path

    def _ensure_data_dir(self) -> None:
        """Create the data directory if it does not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def read(self, filename: str) -> dict:
        """Read a YAML or JSON data file.

        Supports .yaml, .yml, and .json extensions. Returns an empty
        dict if the file does not exist.

        Args:
            filename: Filename relative to the skill's user data directory
                      (e.g. "symptoms.yaml" or "entries.json").

        Returns:
            Parsed file contents as a dict, or {} if file is missing/empty.
        """
        path = self._resolve_read_path(filename)
        if not path.exists():
            return {}
        try:
            content = path.read_text(encoding="utf-8")
            suffix = path.suffix.lower()
            if suffix in (".yaml", ".yml"):
                return yaml.safe_load(content) or {}
            elif suffix == ".json":
                return json.loads(content) if content.strip() else {}
            else:
                # Default to YAML for unknown extensions
                return yaml.safe_load(content) or {}
        except Exception as e:
            logger.error(f"Failed to read data file {filename}: {e}")
            return {}

    def write(self, filename: str, data: dict) -> None:
        """Write data to a YAML or JSON file.

        The file format is determined by the extension. The data directory
        is created automatically if it does not exist.

        Args:
            filename: Filename relative to the skill's user data directory.
            data: Dict to serialize and write.

        Raises:
            OSError: If the file cannot be written.
        """
        self._ensure_data_dir()
        path = self._resolve_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            suffix = path.suffix.lower()
            if suffix == ".json":
                content = json.dumps(data, indent=2, default=str)
            else:
                # Default to YAML for .yaml, .yml, and unknown extensions
                content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
            path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to write data file {filename}: {e}")
            raise

    def list_entities(self, filename: str, key: str) -> list:
        """List all entities from a data file under the given top-level key.

        Entities are returned sorted by 'created_at' descending (most recent
        first). Entities that lack the 'created_at' field sort to the end.

        Args:
            filename: Data filename (e.g. "symptoms.yaml").
            key: Top-level key in the file that holds the entity list
                 (e.g. "symptoms").

        Returns:
            List of entity dicts, sorted by created_at descending.
        """
        data = self.read(filename)
        entities = data.get(key, [])
        if not isinstance(entities, list):
            logger.warning(f"Expected list at key '{key}' in {filename}, got {type(entities).__name__}")
            return []
        return sorted(entities, key=lambda e: e.get("created_at", ""), reverse=True)

    def add_entity(self, filename: str, key: str, entity: dict) -> dict:
        """Add a new entity with auto-generated id and timestamps.

        Automatically injects the following fields before saving:
        - ``id``: First 8 characters of a fresh UUID4.
        - ``created_at``: ISO 8601 timestamp of the current moment.
        - ``updated_at``: Same value as ``created_at`` on creation.

        Args:
            filename: Data filename (e.g. "symptoms.yaml").
            key: Top-level key that holds the entity list.
            entity: Entity data dict (without id/timestamps).

        Returns:
            The newly created entity dict including id and timestamps.
        """
        data = self.read(filename)
        if key not in data or not isinstance(data[key], list):
            data[key] = []

        now = datetime.now().isoformat()
        new_entity: dict = {
            "id": str(uuid.uuid4())[:8],
            "created_at": now,
            "updated_at": now,
            **entity,
        }
        data[key].insert(0, new_entity)
        self.write(filename, data)
        return new_entity

    def update_entity(self, filename: str, key: str, entity_id: str, updates: dict) -> dict:
        """Update an existing entity by id.

        Merges ``updates`` into the matched entity and refreshes ``updated_at``.

        Args:
            filename: Data filename.
            key: Top-level key that holds the entity list.
            entity_id: The ``id`` field value to match.
            updates: Fields to merge into the entity.

        Returns:
            The updated entity dict.

        Raises:
            KeyError: If no entity with the given id is found.
        """
        data = self.read(filename)
        entities: list = data.get(key, [])

        for idx, entity in enumerate(entities):
            if entity.get("id") == entity_id:
                updated = {**entity, **updates, "updated_at": datetime.now().isoformat()}
                entities[idx] = updated
                data[key] = entities
                self.write(filename, data)
                return updated

        raise KeyError(f"Entity with id '{entity_id}' not found in {key} ({filename})")

    def delete_entity(self, filename: str, key: str, entity_id: str) -> dict:
        """Delete an entity by id.

        Args:
            filename: Data filename.
            key: Top-level key that holds the entity list.
            entity_id: The ``id`` field value to remove.

        Returns:
            A dict with ``{"ok": True, "deleted_id": entity_id}``.

        Raises:
            KeyError: If no entity with the given id is found.
        """
        data = self.read(filename)
        entities: list = data.get(key, [])
        original_count = len(entities)

        filtered = [e for e in entities if e.get("id") != entity_id]
        if len(filtered) == original_count:
            raise KeyError(f"Entity with id '{entity_id}' not found in {key} ({filename})")

        data[key] = filtered
        self.write(filename, data)
        return {"ok": True, "deleted_id": entity_id}


def register_crud_tools(
    mcp: FastMCP,
    store: SkillDataStore,
    entity_name: str,
    fields: list,
) -> None:
    """Auto-register list/add/update/delete MCP tools for an entity.

    Reads the entity schema from skill config and registers four FastMCP tools
    for standard CRUD operations using the SkillDataStore backend.

    The four tools registered are:
    - ``list-{plural}``   — returns all entities sorted by created_at desc
    - ``add-{name}``      — creates a new entity with auto id + timestamps
    - ``update-{name}``   — merges updates into an existing entity by id
    - ``delete-{name}``   — removes an entity by id

    Where ``{plural}`` is derived from the skill schema entity definition
    (``schema.entities[].plural``) if available, otherwise ``{name}s``.

    Args:
        mcp: FastMCP server instance to register tools on.
        store: SkillDataStore instance for this skill.
        entity_name: Singular name of the entity (e.g. "symptom").
        fields: List of field definition dicts from skill schema
                (``schema.entities[].fields``). Each dict should have at
                minimum a ``name`` key.

    Example::

        store = SkillDataStore(skill_path)
        entity_cfg = store.config.get("schema", {}).get("entities", [])
        for entity in entity_cfg:
            register_crud_tools(mcp, store, entity["name"], entity.get("fields", []))
    """
    # Derive plural form and storage filename from skill schema if available
    plural_name = f"{entity_name}s"
    storage_file = f"{plural_name}.yaml"

    schema_entities: list = store.config.get("schema", {}).get("entities", [])
    for entity_cfg in schema_entities:
        if entity_cfg.get("name") == entity_name:
            plural_name = entity_cfg.get("plural", plural_name)
            storage_key = plural_name
            # Prefer explicit file from schema, else derive from plural
            storage_file = entity_cfg.get("file", f"{plural_name}.yaml")
            break
    else:
        storage_key = plural_name

    # ------------------------------------------------------------------
    # Tool: list-{plural}
    # ------------------------------------------------------------------
    list_tool_name = f"list-{plural_name}"

    @mcp.tool(
        name=list_tool_name,
        annotations=tool_annotations(
            {
                "title": f"List {plural_name.capitalize()}",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def _list_tool() -> str:
        try:
            entities = store.list_entities(storage_file, storage_key)
            return json.dumps(entities, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to list {plural_name}: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    _list_tool.__doc__ = f"""List all {plural_name} sorted by creation date (most recent first).

    Returns:
        str: JSON array of {entity_name} objects.
    """

    # Rename the function to avoid closure collisions when registering multiple entities
    _list_tool.__name__ = f"_list_{plural_name}_tool"

    # ------------------------------------------------------------------
    # Tool: add-{name}
    # ------------------------------------------------------------------
    add_tool_name = f"add-{entity_name}"
    field_names = [f.get("name", "") for f in fields if f.get("name")]

    @mcp.tool(
        name=add_tool_name,
        annotations=tool_annotations(
            {
                "title": f"Add {entity_name.capitalize()}",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def _add_tool(entity: dict) -> str:
        try:
            new_entity = store.add_entity(storage_file, storage_key, entity)
            return json.dumps(new_entity, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to add {entity_name}: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    _add_tool.__doc__ = f"""Add a new {entity_name}.

    Automatically assigns an id (8-char UUID) and sets created_at/updated_at
    to the current timestamp.

    Args:
        entity: {entity_name.capitalize()} data without id or timestamps.
                Expected fields: {', '.join(field_names) if field_names else 'see schema'}.

    Returns:
        str: JSON of the created {entity_name} including id and timestamps.
    """

    _add_tool.__name__ = f"_add_{entity_name}_tool"

    # ------------------------------------------------------------------
    # Tool: update-{name}
    # ------------------------------------------------------------------
    update_tool_name = f"update-{entity_name}"

    @mcp.tool(
        name=update_tool_name,
        annotations=tool_annotations(
            {
                "title": f"Update {entity_name.capitalize()}",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def _update_tool(id: str, updates: dict) -> str:
        try:
            updated = store.update_entity(storage_file, storage_key, id, updates)
            return json.dumps(updated, indent=2, default=str)
        except KeyError as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            logger.error(f"Failed to update {entity_name} {id}: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    _update_tool.__doc__ = f"""Update an existing {entity_name} by id.

    Merges the provided fields into the existing {entity_name} record
    and refreshes updated_at to the current timestamp.

    Args:
        id: The {entity_name} id to update (8-char UUID prefix).
        updates: Fields to merge into the {entity_name}.

    Returns:
        str: JSON of the updated {entity_name}, or error if not found.
    """

    _update_tool.__name__ = f"_update_{entity_name}_tool"

    # ------------------------------------------------------------------
    # Tool: delete-{name}
    # ------------------------------------------------------------------
    delete_tool_name = f"delete-{entity_name}"

    @mcp.tool(
        name=delete_tool_name,
        annotations=tool_annotations(
            {
                "title": f"Delete {entity_name.capitalize()}",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def _delete_tool(id: str) -> str:
        try:
            result = store.delete_entity(storage_file, storage_key, id)
            return json.dumps(result, indent=2)
        except KeyError as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            logger.error(f"Failed to delete {entity_name} {id}: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    _delete_tool.__doc__ = f"""Delete a {entity_name} by id.

    Args:
        id: The {entity_name} id to delete (8-char UUID prefix).

    Returns:
        str: JSON with {{"ok": true, "deleted_id": "<id>"}}, or error if not found.
    """

    _delete_tool.__name__ = f"_delete_{entity_name}_tool"

    logger.debug(
        f"Registered CRUD tools for '{entity_name}': "
        f"{list_tool_name}, {add_tool_name}, {update_tool_name}, {delete_tool_name}"
    )


__all__ = ["SkillDataStore", "register_crud_tools"]
