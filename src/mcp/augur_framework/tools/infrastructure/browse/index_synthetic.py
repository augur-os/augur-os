"""Synthetic (non-RAG) browse entries assembled per category/journey."""

from datetime import datetime, timezone

from src.config.paths import get_vault_dir

from .index_email import _email_drop_inbox_entries
from .index_sweep import _staged_leftover_draft_entries, _sweep_archive_entries


def _synthetic_entries_for_category(category: str, journey_category: str | None) -> list[dict]:
    if category == "vault" and journey_category == "inbox":
        return _email_drop_inbox_entries()
    if category == "vault" and journey_category == "archive":
        return _sweep_archive_entries()
    if category == "vault" and journey_category == "drafts":
        return _staged_leftover_draft_entries()
    if category == "profile":
        vault_dir = get_vault_dir()
        languages = ("en", "he")
        completed: list[str] = []
        in_progress: list[str] = []
        latest_profile_path = ""
        latest_updated = ""
        latest_profile_mtime = 0.0
        for language in languages:
            profile_dir = vault_dir / "profile" / language
            about_me = profile_dir / "about-me.md"
            state = profile_dir / "interview-in-progress.yaml"
            if about_me.exists() and about_me.stat().st_size > 0:
                completed.append(language.upper())
                mtime = about_me.stat().st_mtime
                if mtime >= latest_profile_mtime:
                    latest_profile_mtime = mtime
                    latest_profile_path = str(about_me)
                    latest_updated = (
                        datetime.fromtimestamp(
                            mtime,
                            tz=timezone.utc,
                        )
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
            if state.exists():
                in_progress.append(language.upper())

        if len(completed) == 2:
            completed_label = "2/2 languages"
        elif len(completed) == 1:
            completed_label = "1/2 languages"
        elif in_progress:
            completed_label = "In progress"
        else:
            completed_label = "Not yet started"

        parts = []
        if completed:
            parts.append(f"Completed: {', '.join(completed)}")
        if in_progress:
            parts.append(f"In progress: {', '.join(in_progress)}")
        description = " / ".join(parts) if parts else "Create a voice profile in English or Hebrew."

        return [
            {
                "id": "voice-profile",
                "type": "profile",
                "name": "Voice Profile",
                "title": "Voice Profile",
                "description": description,
                "hub": "workspace",
                "source_path": latest_profile_path,
                "completed_languages": completed_label,
                "profile_languages": ",".join(completed),
                "profileLanguages": ",".join(completed),
                "dashboardPath": "/brain/profile",
                "status": "ready" if completed else "in-progress" if in_progress else "not-started",
                "updated_at": latest_updated,
                "metadata": {
                    "completed_languages": completed_label,
                    "profileLanguages": ",".join(completed),
                    "dashboardPath": "/brain/profile",
                    "status": "ready" if completed else "in-progress" if in_progress else "not-started",
                },
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    return []
