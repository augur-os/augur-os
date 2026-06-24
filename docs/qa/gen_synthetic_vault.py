#!/usr/bin/env python3
"""Generate a production-scale, fully-synthetic Augur vault for QA.

Mirrors the real Au-vault directory layout and per-file-type frontmatter schema,
but every value is generated lorem — zero real personal content. Deterministic
(seeded) so the dataset is reproducible for regression runs.

Usage: python3 gen_synthetic_vault.py /path/to/output-vault
"""
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20260624
random.seed(SEED)

WORDS = (
    "system signal pattern context vault harness skill agent memory concept "
    "routine index source insight cluster pipeline cadence anchor lattice "
    "ledger beacon prism cohort vector schema fixture parcel motif tenet "
    "horizon meridian quartz cobalt ember willow harbor summit cadence drift "
    "orbit canyon delta ravine thicket prairie glacier estuary plateau"
).split()
NAMES = ["Ada Quill", "Bram Vale", "Cleo Marsh", "Dorian Fen", "Esme Holt",
         "Finn Roe", "Greta Lume", "Hugo Past", "Iris Wend", "Jonas Kerr"]
ORGS = ["Northwind Labs", "Lumen Collective", "Vertex Forge", "Cobalt Works",
        "Harbor Analytics", "Prism Dynamics", "Thicket Systems"]

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def ts(i):
    return (T0 + timedelta(days=i % 170, hours=(i * 7) % 24, minutes=(i * 13) % 60)).isoformat()


def date(i):
    return (T0 + timedelta(days=i % 170)).date().isoformat()


def phrase(n=4):
    return " ".join(random.choice(WORDS) for _ in range(n))


def title_case(n=4):
    return " ".join(w.capitalize() for w in (random.choice(WORDS) for _ in range(n)))


def para(sentences=4):
    out = []
    for _ in range(sentences):
        s = " ".join(random.choice(WORDS) for _ in range(random.randint(8, 16)))
        out.append(s.capitalize() + ".")
    return " ".join(out)


def body(paras=3):
    chunks = [f"## {title_case(3)}\n\n{para(random.randint(3,6))}" for _ in range(paras)]
    return "\n\n".join(chunks) + "\n"


def slug(i, prefix):
    return f"{prefix}-{'-'.join(random.choice(WORDS) for _ in range(3))}-{i:03d}"


def fm(d):
    lines = ["---"]
    for k, v in d.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"- {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def tags(n=4):
    return [random.choice(WORDS) for _ in range(n)]


def links(n=3):
    return [f"'[[{random.choice(WORDS)}]]'" for _ in range(n)]


def write(root: Path, rel: str, content: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def gen_note(root, domain, i, sub=""):
    s = slug(i, domain)
    rel = f"{domain}/{sub + '/' if sub else ''}{s}.md"
    c = fm({
        "title": title_case(random.randint(2, 5)),
        "summary": para(2),
        "tags": tags(random.randint(3, 6)),
        "created": f"'{ts(i)}'",
        "_hub": random.choice(["life", "workspace", "dev", "brain", "command"]),
        "_relates_to": links(random.randint(2, 4)),
        "_entity_tier": random.randint(1, 3),
    }) + body(random.randint(2, 5))
    write(root, rel, c)


def gen_concept(root, i):
    s = slug(i, "concept")
    c = fm({
        "title": title_case(random.randint(2, 5)),
        "summary": para(3),
        "tags": tags(random.randint(4, 7)),
        "aliases": [phrase(2) for _ in range(random.randint(1, 3))],
        "related": [],
        "created": f"'{ts(i)}'",
        "_page_type": "concept",
        "_hub": random.choice(["life", "workspace", "dev"]),
        "_sources": [f"vault:notes/{random.choice(WORDS)}/{random.choice(WORDS)}.md"
                     for _ in range(random.randint(1, 3))],
    }) + body(random.randint(3, 6))
    write(root, f"wiki/concepts/{s}.md", c)


def gen_query(root, i):
    s = slug(i, "query")
    c = fm({
        "title": f"How should {title_case(3)} be used?",
        "summary": f"A reusable answer for applying [[concepts/{random.choice(WORDS)}]].",
        "tags": tags(random.randint(4, 6)),
        "_page_type": "query",
        "created": f"'{ts(i)}'",
    }) + body(2)
    write(root, f"wiki/queries/{s}.md", c)


def gen_source(root, i):
    s = slug(i, "src")
    c = fm({
        "title": title_case(random.randint(2, 4)),
        "canonical_url": f"https://example.test/{random.choice(WORDS)}/{i}",
        "content_hash": f"sha256:{''.join(random.choice('0123456789abcdef') for _ in range(64))}",
        "tags": tags(random.randint(3, 5)),
        "captured_at": f"'{ts(i)}'",
        "note": phrase(6),
        "source_type": "url",
        "_relates_to": links(random.randint(2, 4)),
    }) + body(random.randint(2, 4))
    write(root, f"sources/urls/{s}.md", c)


def gen_book(root, i):
    s = slug(i, "book")
    c = fm({
        "title": title_case(random.randint(1, 3)),
        "author": random.choice(NAMES),
        "tags": ["Literary Work", "Narrative Analysis", random.choice(WORDS)],
        "source": "notion-import",
        "imported": f"'{date(i)}'",
        "_authored_by": [f"'[[{random.choice(NAMES)}]]'"],
        "_relates_to": links(2),
        "_entity_tier": random.randint(2, 3),
    }) + body(random.randint(2, 4))
    write(root, f"books/{s}.md", c)


def gen_memory(root, i):
    s = slug(i, "mem")
    c = fm({
        "title": s,
        "name": s,
        "description": phrase(8),
        "brain_scope": random.choice(["project", "personal"]),
        "type": random.choice(["project", "personal", "reference"]),
        "status": "active",
        "source_client": random.choice(["claude-code", "codex", "gemini"]),
        "source_file": f"{s}.md",
        "source_hash": ''.join(random.choice('0123456789abcdef') for _ in range(16)),
        "_mentions": links(random.randint(1, 3)),
        "_entity_tier": random.randint(1, 3),
    }) + body(2)
    write(root, f"_augur/knowledge/memory/{s}.md", c)


def gen_inbox(root, i):
    s = slug(i, "capture")
    c = fm({
        "title": title_case(random.randint(2, 4)),
        "tags": tags(2),
        "captured_at": f"'{ts(i)}'",
        "source_type": random.choice(["thought", "url", "file"]),
        "status": "inbox",
    }) + para(random.randint(1, 3)) + "\n"
    write(root, f"inbox/{s}.md", c)


def gen_root_files(root):
    write(root, "BRAIN.yaml",
          "schema_version: 1\nid: qa-synthetic\ntype: personal\n"
          f"root: {root}\ndescription: Synthetic QA brain (generated, no real data)\n"
          "layout: domains\n")
    for name, head in [
        ("IDENTITY.md", "# Identity"), ("SOUL.md", "# Soul"), ("USER.md", "# User"),
        ("AGENTS.md", "# Agents"), ("TOOLS.md", "# Tools"), ("HEARTBEAT.md", "# Heartbeat"),
    ]:
        write(root, name, fm({"title": name[:-3], "tags": tags(2)}) + f"{head}\n\n{body(2)}")
    write(root, "MEMORY.md",
          fm({"title": "Memory Index", "tags": ["memory", "index"]}) +
          "# Memory\n\n" + "\n".join(f"- [{title_case(3)}](entry-{i}.md) — {phrase(5)}"
                                     for i in range(8)) + "\n")


def main():
    out = Path(sys.argv[1]).expanduser()
    if out.exists():
        import shutil
        shutil.rmtree(out)
    out.mkdir(parents=True)

    gen_root_files(out)

    # domain notes mirroring real-vault scale
    plan = {
        "career": (56, ["pipeline", "growth", "interview", "skills"]),
        "venture": (86, ["startups", "sales", "brand", "planning", "marketing",
                          "competition", "strategy"]),
        "lifestyle": (45, ["apple", "eisenhower", "recipes", "kids"]),
        "health": (9, ["virtual-doctor"]),
        "finance": (6, ["knowledge"]),
        "dev": (8, []),
        "general": (4, []),
        "danit-career": (10, []),
        "profile": (2, ["en"]),
    }
    i = 0
    for domain, (count, subs) in plan.items():
        for n in range(count):
            sub = random.choice(subs) if subs and random.random() < 0.6 else ""
            gen_note(out, domain, i, sub)
            i += 1

    for _ in range(50):
        gen_concept(out, i); i += 1
    for _ in range(12):
        gen_query(out, i); i += 1
    for _ in range(15):
        gen_source(out, i); i += 1
    for _ in range(21):
        gen_book(out, i); i += 1
    for _ in range(14):
        gen_memory(out, i); i += 1
    for _ in range(9):
        gen_inbox(out, i); i += 1

    total = sum(1 for _ in out.rglob("*.md"))
    print(f"Generated {total} markdown files under {out}")


if __name__ == "__main__":
    main()
