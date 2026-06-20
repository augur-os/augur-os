# Document Source Config

`sources.yaml` stores shared project document source references that can be
checked into git. It may include shared provider names, remote folder or file
ids, attachment brain ids, remote revision metadata, and short editable
source-level catalog summaries for Browse cards.

Do not add include/exclude patterns or catalog policy fields here yet. The
current loader accepts only the explicit shared-source and summary fields, and
rejects unsupported policy fields instead of silently dropping them.

Do not store credentials, local absolute paths, local cache paths, extracted
document bodies, chunks, embeddings, OCR output, BM25 data, or other generated
index artifacts here. Those belong in the local runtime, cache, or configured
external document roots, never in repo config.

Personal local defaults such as Documents, Desktop, and Downloads are resolved by
the local default source loader. Project sources in this directory must use
shared providers such as Google Drive, SharePoint, OneDrive, GitHub, Notion,
Confluence, or an explicitly shared folder provider.
