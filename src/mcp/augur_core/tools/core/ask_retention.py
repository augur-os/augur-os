from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_runtime_dir

from .vault_ops import save_synthesis_impl

_DECISION_PATTERNS = (
    r"\byou decided\b",
    r"\bdecided to\b",
    r"\bthe decision is\b",
    r"\byou will\b",
    r"\byou['’]ll\b",
)
_CONTRADICTION_PATTERNS = (
    r"\bcontradiction\b",
    r"\btension\b",
    r"\bconflict\b",
    r"\bbut you also\b",
    r"\bon the one hand\b",
)
_OPEN_QUESTION_PATTERNS = (
    r"\bopen question\b",
    r"\bstill unresolved\b",
    r"\bunresolved\b",
    r"\bnot yet clear\b",
    r"\bneeds testing\b",
)


def _matches_any(text: str, patterns: Sequence[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _contains_explicit_preference_signal(text: str) -> bool:
    return _matches_any(
        text,
        (
            r"\bprefer\b",
            r"\bbest\b",
            r"\bworks best\b",
            r"\blike\b",
        ),
    )


def classify_ask_outcome(
    *,
    question: str,
    answer: str,
    explicit_signals: Sequence[str],
    inferred_signals: Sequence[str],
) -> dict[str, object]:
    kinds: list[str] = []
    explicit_text = " ".join(explicit_signals).lower()
    inferred_text = " ".join(inferred_signals).lower()
    combined_text = " ".join(part for part in (question, answer, explicit_text, inferred_text) if part).lower()

    heuristic_kind_added = False
    if _matches_any(combined_text, _DECISION_PATTERNS):
        kinds.append("decision")
        heuristic_kind_added = True
    if _matches_any(combined_text, _CONTRADICTION_PATTERNS):
        kinds.append("contradiction")
        heuristic_kind_added = True
    if _matches_any(combined_text, _OPEN_QUESTION_PATTERNS):
        kinds.append("open-question")
        heuristic_kind_added = True

    if explicit_signals:
        if _contains_explicit_preference_signal(explicit_text):
            kinds.append("preference")
        elif not heuristic_kind_added:
            kinds.append("insight")

    if inferred_signals:
        kinds.append("inferred-pattern")

    kinds = list(dict.fromkeys(kinds))
    should_retain = bool(kinds)
    confidence = "high" if explicit_signals else "medium" if inferred_signals or heuristic_kind_added else "low"

    return {
        "question": question,
        "answer": answer,
        "kinds": kinds or ["ephemeral"],
        "should_retain": should_retain,
        "confidence": confidence,
    }


def build_retention_footer(kinds: Sequence[str]) -> str:
    labels: list[str] = []
    for kind in kinds:
        if kind == "inferred-pattern":
            labels.append("inferred pattern")
        elif kind == "insight":
            labels.append("synthesis")
        elif kind == "open-question":
            labels.append("deferred")
        else:
            labels.append(kind)
    return f"retained: {' + '.join(labels)}"


def route_ask_retention(result: dict[str, object]) -> dict[str, object]:
    payload = {key: result[key] for key in ("question", "answer", "confidence", "should_retain") if key in result}
    routed_result = {
        "payload": payload,
        "kinds": list(result.get("kinds", [])),
        "decision": [],
        "preference": [],
        "synthesis": [],
        "contradictions": [],
        "deferred": [],
    }

    for kind in result.get("kinds", []):
        routed_entry = {"kind": kind, **payload}
        if kind == "decision":
            routed_result["decision"].append(routed_entry)
        elif kind == "preference":
            routed_result["preference"].append(routed_entry)
        elif kind == "open-question":
            routed_result["deferred"].append(routed_entry)
        elif kind == "contradiction":
            routed_result["contradictions"].append(routed_entry)
        elif kind != "ephemeral":
            # insight, inferred-pattern, and any caller-provided durable kind
            # (e.g. "synthesis", "outcome") persist via the synthesis path —
            # a durable kind must never drop out of routing silently.
            routed_result["synthesis"].append(routed_entry)

    return routed_result


def _normalize_kinds(kinds: Sequence[str]) -> list[str]:
    normalized = [kind.strip() for kind in kinds if kind and kind.strip()]
    normalized = list(dict.fromkeys(normalized))
    if not normalized:
        return ["ephemeral"]
    return normalized


def _flag_wiki_update_needed() -> str:
    flag_dir = get_runtime_dir() / "wiki"
    flag_dir.mkdir(parents=True, exist_ok=True)
    flag_path = flag_dir / "needs-update.flag"
    flag_path.write_text(datetime.now(tz=timezone.utc).isoformat(), encoding="utf-8")
    return str(flag_path)


def _derive_source_label(explicit_signals: Sequence[str], inferred_signals: Sequence[str]) -> str | None:
    if explicit_signals:
        return "Retained from /ask explicit conclusion"
    if inferred_signals:
        return "Retained from /ask inferred pattern"
    return "Retained from /ask"


async def retain_ask_outcome_impl(
    *,
    question: str,
    answer: str,
    explicit_signals: Sequence[str] | None = None,
    inferred_signals: Sequence[str] | None = None,
    kinds: Sequence[str] | None = None,
    retain_mode: str = "default",
    sources: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    surface_footer: bool = False,
    to: str | None = None,
    cwd: Path | None = None,
    registry_path: Path | None = None,
) -> str:
    """Classify and persist a durable /ask outcome.

    This is the live MCP-facing surface for `/ask` compounding. The AI session
    still produces the answer, but it can make one follow-up call to persist the
    durable result into the correct long-term layers.
    """
    explicit_signals = list(explicit_signals or [])
    inferred_signals = list(inferred_signals or [])
    write_target = None
    if to is not None or cwd is not None or registry_path is not None:
        from src.lib.brain_write_routing import resolve_write_target

        try:
            write_target = resolve_write_target(
                explicit_brain=to,
                cwd=cwd,
                registry_path=registry_path,
            )
        except KeyError as exc:
            return json.dumps({"success": False, "error": str(exc)})
        if write_target.mode == "packet":
            return json.dumps(
                {
                    "success": False,
                    "error": f"brain {write_target.brain.id} requires packet-based writes",
                    "brain": write_target.summary(),
                    "packet_root": str(write_target.packet_root),
                }
            )
    mode = (retain_mode or "default").strip().lower()
    if mode in {"no-retain", "no_retain", "skip"}:
        mode = "no-retain"
    elif mode in {"force", "retain"}:
        mode = "retain"
    elif mode not in {"default", "private"}:
        mode = "default"

    if mode in {"private", "no-retain"}:
        return json.dumps(
            {
                "success": True,
                "retained": False,
                "mode": mode,
                "skipped": True,
                "reason": "Retention disabled by /ask mode",
                "footer": None,
                "kinds": ["ephemeral"] if mode == "private" else [],
            }
        )

    if kinds:
        # Caller-provided kinds are an explicit retention instruction, not a
        # heuristic guess — classify them as high confidence.
        result = {
            "question": question,
            "answer": answer,
            "kinds": _normalize_kinds(kinds),
            "should_retain": "ephemeral" not in _normalize_kinds(kinds),
            "confidence": "high",
        }
    else:
        result = classify_ask_outcome(
            question=question,
            answer=answer,
            explicit_signals=explicit_signals,
            inferred_signals=inferred_signals,
        )

    if mode == "retain" and result["kinds"] == ["ephemeral"] and answer.strip():
        result = {
            **result,
            "kinds": ["insight"],
            "should_retain": True,
            "confidence": "medium",
        }

    if not result.get("should_retain"):
        return json.dumps(
            {
                "success": True,
                "retained": False,
                "mode": mode,
                "skipped": True,
                "reason": "No durable outcome detected",
                "footer": None,
                "kinds": result["kinds"],
                "classification": result,
            }
        )

    routed = route_ask_retention(result)
    persistence_summary: dict[str, object] = {
        "decisions_logged": 0,
        "preferences_logged": 0,
        "syntheses_saved": [],
        "wiki_update_flag": None,
    }

    from src.lib.knowledge import DailyLogger

    if write_target is not None:
        daily_logger = DailyLogger(
            memory_dir=write_target.memory_dir,
            daily_dir=write_target.memory_dir / "daily",
        )
    else:
        daily_logger = DailyLogger()
    reasoning = "\n".join(explicit_signals + inferred_signals) or None

    for entry in routed["decision"]:
        daily_logger.log_decision(
            topic=question,
            decision=answer,
            reasoning=reasoning,
            confidence=str(entry.get("confidence", "medium")),
            category="Ask",
        )
        persistence_summary["decisions_logged"] = int(persistence_summary["decisions_logged"]) + 1

    preference_source = _derive_source_label(explicit_signals, inferred_signals)
    for _entry in routed["preference"]:
        daily_logger.log_user_preference(
            preference=question,
            value=answer,
            source=preference_source,
        )
        persistence_summary["preferences_logged"] = int(persistence_summary["preferences_logged"]) + 1

    note_kinds = list(routed["kinds"])
    if any(routed[bucket] for bucket in ("synthesis", "contradictions", "deferred")):
        synthesis_tags = {"ask"}
        synthesis_tags.update(kind for kind in note_kinds if kind != "ephemeral")
        synthesis_tags.update(tags or [])
        synthesis_sources = list(dict.fromkeys([*(sources or []), "ask"]))
        saved = json.loads(
            await save_synthesis_impl(
                query=question,
                synthesis=answer,
                sources=synthesis_sources,
                tags=sorted(synthesis_tags),
                knowledge_dir=write_target.knowledge_dir if write_target is not None else None,
            )
        )
        if saved.get("success"):
            cast_paths = list(persistence_summary["syntheses_saved"])
            cast_paths.append(saved["path"])
            persistence_summary["syntheses_saved"] = cast_paths
        else:
            persistence_summary["synthesis_error"] = saved.get("error", "synthesis save failed")

    persisted_anything = bool(
        persistence_summary["decisions_logged"]
        or persistence_summary["preferences_logged"]
        or persistence_summary["syntheses_saved"]
    )
    if not persisted_anything:
        # A retain that retained nothing must not report success (the
        # 2026-06-11 /keep silent-evaporation bug).
        return json.dumps(
            {
                "success": False,
                "retained": False,
                "mode": mode,
                "error": "Retention was requested but nothing was persisted",
                "footer": None,
                "kinds": note_kinds,
                "classification": result,
                "routed": routed,
                "persistence": persistence_summary,
            }
        )

    footer = build_retention_footer(note_kinds) if surface_footer else None
    flag_path = _flag_wiki_update_needed()
    persistence_summary["wiki_update_flag"] = flag_path

    # ADR-738 — emit typed edges for the memory entries this retention wrote.
    # Best-effort: the graph layer never raises into the /ask retention path.
    try:
        import sys as _sys

        from src.config.paths import get_project_brain_skills_dir, get_project_root

        _graph_scripts = str(get_project_brain_skills_dir(get_project_root()) / "graph" / "scripts")
        if _graph_scripts not in _sys.path:
            _sys.path.insert(0, _graph_scripts)
        import graph_ops  # type: ignore[import-not-found]

        _cited = list(sources or [])
        if persistence_summary["decisions_logged"] or persistence_summary["preferences_logged"]:
            graph_ops.index_page_from_write_path(daily_logger._get_daily_file(), source_type="memory")
        for _synth_path in list(persistence_summary["syntheses_saved"] or []):  # type: ignore[arg-type]
            graph_ops.index_page_from_write_path(
                _synth_path,
                source_type="memory",
                known={"concepts": _cited} if _cited else None,
            )
    except Exception:  # noqa: BLE001 — graph is best-effort, never breaks /ask retention
        pass

    response = {
        "success": True,
        "retained": True,
        "mode": mode,
        "footer": footer,
        "kinds": note_kinds,
        "classification": result,
        "routed": routed,
        "persistence": persistence_summary,
    }
    if write_target is not None:
        response["brain"] = write_target.summary()
    return json.dumps(response)
