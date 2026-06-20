"""Cluster retained `/ask` outcomes for wiki compounding."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

_KIND_TAGS = {
    "decision",
    "preference",
    "inferred-pattern",
    "insight",
    "contradiction",
    "open-question",
    "synthesis",
}

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "best",
    "do",
    "for",
    "how",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "this",
    "to",
    "what",
    "with",
    "work",
}

_GENERIC_PAGE_TOKENS = {"overview", "index", "home", "summary", "general"}


def _question_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in _STOPWORDS}


def _item_kinds(item: dict[str, Any]) -> set[str]:
    kinds = {str(item.get("kind", "")).strip()} - {""}
    tags = {str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()}
    kinds.update(tags & _KIND_TAGS)
    return kinds


def _content_tags(item: dict[str, Any]) -> set[str]:
    tags = {str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()}
    return tags - _KIND_TAGS - {"ask"}


def _cluster_match(cluster: dict[str, Any], item: dict[str, Any]) -> bool:
    item_tags = _content_tags(item)
    item_kinds = _item_kinds(item)
    item_tokens = _question_tokens(str(item.get("question", "")))

    if item_tags & cluster["content_tags"]:
        return True
    if item_kinds & cluster["kinds"] and item_tokens & cluster["topic_tokens"]:
        return True
    return False


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "cluster"


def _cluster_label(cluster: dict[str, Any], ordinal: int) -> str:
    questions = [
        str(item.get("question", "")).strip() for item in cluster["items"] if str(item.get("question", "")).strip()
    ]
    for question in questions:
        lowered = question.lower().strip()
        if lowered.startswith("how do i "):
            return question[9:].strip(" ?")
        if lowered.startswith("how should i "):
            return question[13:].strip(" ?")
        if lowered.startswith("what should i "):
            return question[14:].strip(" ?")
        if lowered.startswith("what do i "):
            return question[10:].strip(" ?")
        if lowered.startswith("what pattern "):
            return question.strip(" ?")

    content_tags = sorted(cluster["content_tags"])
    if content_tags:
        if len(content_tags) >= 2:
            return f"{content_tags[0].replace('-', ' ')} {content_tags[1].replace('-', ' ')}"
        return content_tags[0].replace("-", " ")

    kind_counter = Counter(item["kind"] for item in cluster["items"])
    if kind_counter:
        kind = kind_counter.most_common(1)[0][0]
        tokens = sorted(cluster["topic_tokens"])
        if tokens:
            return f"{kind} {' '.join(tokens[:2])}".strip()
        return kind

        return f"ask cluster {ordinal}"


def _parse_created(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _confidence_value(value: str) -> float:
    return {"low": 0.35, "medium": 0.7, "high": 1.0}.get(str(value).lower(), 0.5)


def _deterministic_summary(items: list[dict[str, Any]], label: str) -> str:
    unique_points: list[str] = []
    for item in items:
        summary = str(item.get("summary", "")).strip()
        if summary and summary not in unique_points:
            unique_points.append(summary)
        if len(unique_points) >= 2:
            break
    if not unique_points:
        return f"Retained /ask outcomes around {label}."
    if len(unique_points) == 1:
        return f"{label} centers on {_clip_sentence(unique_points[0])}"
    return (
        f"{label} centers on {_clip_sentence(unique_points[0])}; "
        f"it also highlights {_clip_sentence(unique_points[1], lowercase_first=True)}"
    )


def _clip_sentence(text: str, *, lowercase_first: bool = False, limit: int = 110) -> str:
    normalized = " ".join(text.split()).rstrip(".")
    if len(normalized) > limit:
        normalized = normalized[: limit - 1].rstrip() + "…"
    if lowercase_first and normalized:
        normalized = normalized[0].lower() + normalized[1:]
    return normalized


def _infer_hub(cluster: dict[str, Any]) -> str | None:
    item_hubs = [str(item.get("hub", "")).strip() for item in cluster["items"] if str(item.get("hub", "")).strip()]
    if item_hubs:
        return Counter(item_hubs).most_common(1)[0][0]

    content_tags = sorted(cluster["content_tags"])
    tag_to_hub = {
        "career": "career",
        "job": "career",
        "launch": "career",
        "health": "life",
        "fitness": "life",
        "morning": "brain",
        "deep-work": "brain",
        "focus": "brain",
        "creative": "studio",
        "writing": "studio",
        "automation": "command",
        "workflow": "command",
    }
    for tag in content_tags:
        if tag in tag_to_hub:
            return tag_to_hub[tag]
    return None


def _score_cluster(cluster: dict[str, Any]) -> dict[str, float]:
    items = cluster["items"]
    item_count = len(items)
    recurrence_score = min(item_count / 3.0, 1.0)

    confidence_values = [_confidence_value(item.get("confidence", "medium")) for item in items]
    confidence_score = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0

    created_values = [_parse_created(str(item.get("created", ""))) for item in items]
    created_values = [value for value in created_values if value is not None]
    if created_values:
        newest = max(created_values)
        age_days = max((datetime.now(tz=timezone.utc) - newest).total_seconds() / 86400.0, 0.0)
        freshness_score = max(0.0, 1.0 - min(age_days / 14.0, 1.0))
    else:
        freshness_score = 0.5

    kinds = {item.get("kind", "") for item in items}
    kind_mix_score = min(len({kind for kind in kinds if kind}) / 3.0, 1.0)

    base_score = recurrence_score * 0.45 + confidence_score * 0.30 + freshness_score * 0.15 + kind_mix_score * 0.10

    singleton = item_count == 1
    if singleton:
        only_item = items[0]
        if (
            only_item.get("kind") in {"decision", "preference"}
            and _confidence_value(only_item.get("confidence", "medium")) >= 0.95
        ):
            base_score = max(base_score, 0.78)

    priority_score = round(base_score, 3)
    return {
        "priority_score": priority_score,
        "recurrence_score": round(recurrence_score, 3),
        "confidence_score": round(confidence_score, 3),
        "freshness_score": round(freshness_score, 3),
        "kind_mix_score": round(kind_mix_score, 3),
    }


def cluster_ask_outcomes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group retained ask outcomes into cluster candidates for wiki updates."""
    clusters: list[dict[str, Any]] = []
    for item in items:
        assigned = False
        for cluster in clusters:
            if _cluster_match(cluster, item):
                cluster["items"].append(item)
                cluster["content_tags"].update(_content_tags(item))
                cluster["kinds"].update(_item_kinds(item))
                cluster["topic_tokens"].update(_question_tokens(str(item.get("question", ""))))
                assigned = True
                break
        if assigned:
            continue
        clusters.append(
            {
                "items": [item],
                "content_tags": set(_content_tags(item)),
                "kinds": set(_item_kinds(item)),
                "topic_tokens": set(_question_tokens(str(item.get("question", "")))),
            }
        )

    results: list[dict[str, Any]] = []
    for index, cluster in enumerate(clusters, start=1):
        label = _cluster_label(cluster, index)
        items_in_cluster = sorted(
            cluster["items"],
            key=lambda item: str(item.get("created", "")),
            reverse=True,
        )
        tag_sets = [{str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()} for item in items_in_cluster]
        kind_sets = [_item_kinds(item) for item in items_in_cluster]
        shared_tags = sorted(set.intersection(*tag_sets)) if tag_sets else []
        shared_kinds = sorted(set.intersection(*kind_sets)) if kind_sets else []
        if not shared_kinds:
            shared_kinds = sorted(cluster["kinds"])

        score = _score_cluster({"items": items_in_cluster})
        results.append(
            {
                "cluster_id": f"{_slug(label)}-{index}",
                "label": " ".join(label.split()).capitalize(),
                "summary": _deterministic_summary(items_in_cluster, label),
                "hub": _infer_hub({"items": items_in_cluster, "content_tags": cluster["content_tags"]}),
                "shared_tags": shared_tags,
                "shared_kinds": shared_kinds,
                "items": items_in_cluster,
                "item_count": len(items_in_cluster),
                "singleton": len(items_in_cluster) == 1,
                **score,
            }
        )

    results.sort(
        key=lambda cluster: (
            cluster["priority_score"],
            cluster["item_count"],
            cluster["freshness_score"],
        ),
        reverse=True,
    )
    return results


def suggest_page_targets(
    clusters: list[dict[str, Any]],
    wiki_tags_manifest: dict[str, Any],
    *,
    max_targets: int = 3,
) -> list[dict[str, Any]]:
    """Attach heuristic wiki page target suggestions to each cluster."""
    pages = wiki_tags_manifest.get("pages", {}) if isinstance(wiki_tags_manifest, dict) else {}
    enriched: list[dict[str, Any]] = []

    for cluster in clusters:
        cluster_tags = {tag for tag in cluster.get("shared_tags", []) if tag and tag not in {"ask"}}
        if not cluster_tags:
            for item in cluster.get("items", []):
                cluster_tags.update(_content_tags(item))
        cluster_hubs = {
            str(item.get("hub", "")).strip() for item in cluster.get("items", []) if str(item.get("hub", "")).strip()
        }
        if cluster.get("hub"):
            cluster_hubs.add(str(cluster["hub"]))
        cluster_tokens = set()
        for item in cluster.get("items", []):
            cluster_tokens.update(_question_tokens(str(item.get("question", ""))))

        targets: list[dict[str, Any]] = []
        for page, meta in pages.items():
            page_tags = {str(tag).strip() for tag in meta.get("tags", []) if str(tag).strip()}
            tag_overlap = cluster_tags & page_tags

            title = str(meta.get("title", ""))
            page_tokens = _question_tokens(page.replace("/", " ") + " " + title)
            token_overlap = cluster_tokens & page_tokens
            page_parts = [part for part in page.split("/") if part]
            page_hub = page_parts[0] if page_parts else ""
            generic_penalty = 0
            if (
                any(token in _GENERIC_PAGE_TOKENS for token in page_tokens)
                or page.endswith("/overview")
                or page.endswith("/index")
            ):
                generic_penalty = 2
            hub_bonus = 1 if cluster_hubs and page_hub in cluster_hubs else 0

            score = len(tag_overlap) * 3 + len(token_overlap) + hub_bonus - generic_penalty
            if score <= 0:
                continue

            reasons: list[str] = []
            if tag_overlap:
                reasons.append(f"tag overlap: {', '.join(sorted(tag_overlap)[:3])}")
            if token_overlap:
                reasons.append(f"title/page overlap: {', '.join(sorted(token_overlap)[:3])}")
            if hub_bonus:
                reasons.append(f"hub match: {page_hub}")
            if generic_penalty:
                reasons.append("generic page penalty applied")

            targets.append(
                {
                    "page": page,
                    "title": title or page.split("/")[-1].replace("-", " ").title(),
                    "score": score,
                    "reasons": reasons,
                }
            )

        targets.sort(key=lambda item: (item["score"], item["title"]), reverse=True)
        enriched.append({**cluster, "page_targets": targets[:max_targets]})

    return enriched
