from __future__ import annotations

import re

_LABEL_PATTERN = re.compile(
    r"\b(decision|decided|action|follow-up|follow up)\s*[:,]\s*",
    flags=re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def _strip_label(sentence: str, labels: tuple[str, ...]) -> str:
    pattern = "|".join(re.escape(label) for label in labels)
    return re.sub(
        rf"^({pattern})\s*[:,]\s*",
        "",
        sentence,
        flags=re.IGNORECASE,
    ).strip()


def _finish_item(text: str) -> str:
    item = text.strip(" ,;")
    if item and item[-1] not in ".!?":
        item += "."
    return item


def _extract_labeled_items(text: str, labels: tuple[str, ...]) -> list[str]:
    wanted = {label.lower() for label in labels}
    matches = list(_LABEL_PATTERN.finditer(text))
    items: list[str] = []
    for index, match in enumerate(matches):
        label = match.group(1).lower()
        if label not in wanted:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        item = _finish_item(text[match.end() : end])
        if item:
            items.append(item)
    return items


def build_meeting_memory(transcript_markdown: str) -> dict[str, list[str] | str]:
    text = re.sub(r"^# .*$", "", transcript_markdown, flags=re.MULTILINE)
    text = re.sub(
        r"^(Method|Backend|Confidence|Language|Duration seconds):.*$",
        "",
        text,
        flags=re.MULTILINE,
    )
    sentences = _sentences(re.sub(r"\s+", " ", text))
    summary = " ".join(sentences[:2]) if sentences else "No transcript summary was captured."
    decisions = _extract_labeled_items(text, ("decision", "decided"))
    next_actions = _extract_labeled_items(text, ("action", "follow-up", "follow up"))
    return {
        "summary": summary,
        "decisions": decisions,
        "next_actions": next_actions,
    }
