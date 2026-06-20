# LongMemEval Import Adapter Contract

`scripts/longmemeval.py` converts a LongMemEval-style JSONL corpus into the eval
harness's native `eval.query.v1` + `eval.judgment.v1` shapes. The repo never vendors
a corpus — the user drops a file in and runs `aug eval import-longmemeval`.

## Expected input format

One JSON object per line. The adapter reads these fields:

| Field | Type | Required | Maps to |
|---|---|---|---|
| `question` | string | yes | `query.v1.query` |
| `answer` | string | no | ignored (Augur never stores LLM responses) |
| `evidence_doc_ids` | list[string] | yes | `judgment.v1.relevant_doc_ids` |
| `corpus_id` | string | no | the `<corpus-id>` bucket; overridden by the CLI `--corpus-id` arg if given |
| `question_id` | string | no | used as a stable seed for the query id when present; otherwise the id is `sha1(question + source)[:12]` |

Lines missing `question` or `evidence_doc_ids` are skipped and counted in the import
summary's `skipped` count. The adapter never raises on a malformed line — it logs and
moves on.

## Output layout

```
get_documents_dir()/evals/external/<corpus-id>/
├── queries/
│   └── <corpus-id>.jsonl       # eval.query.v1 records, source = "external:<corpus-id>"
└── judgments/
    └── <query-id>.md           # eval.judgment.v1 frontmatter, one per query
```

Each emitted `query.v1` record carries:

- `source`: `"external:<corpus-id>"` — so the report buckets it separately
- `tool`: `"unified-search"` — the corpus is replayed through the default retrieval tool
- `mode`: `"hybrid"`, `top_k`: `10`, `scopes`: `null`, `project`: `null`
- `returned`: `[]` — external corpora have no capture-time returned set; replay fills it
- `retrieval_config`: `{augur_commit, vault_manifest_hash, rrf_k: null, rrf_weights: null}`
  captured at import time

## Why a contract doc, not just code

A future corpus in a different schema gets a *parallel* adapter that emits the same
`query.v1` + `judgment.v1` shapes — the core import code is never mutated to special-case
a new upstream format. This file is the single source of truth for what
`import-longmemeval` expects; a `import-<other-format>` adapter would get its own
sibling reference doc.
