---
status: Implemented
date: '2025-01-01'
deciders:
- Core team
related: []
hub: null
tags:
- local
- first
- architecture
superseded_by: null
---

# ADR-006: Local-First Architecture

## Context

Augur manages sensitive personal data: medical records, financial information, job applications, contracts, personal notes. The system also aims to be a long-term personal knowledge base that outlives any particular service.

Cloud-first architectures pose risks:
- **Privacy**: Data stored on third-party servers
- **Availability**: Requires internet connection
- **Cost**: Ongoing subscription fees
- **Longevity**: Service shutdown means data loss
- **Vendor lock-in**: Proprietary formats and APIs

## Decision

Adopt a **local-first architecture**:

### Core Principles
1. **Data lives on your machine**: All user data stored in local files
2. **Works offline**: Core functionality requires no internet
3. **Human-readable formats**: YAML and Markdown, not proprietary databases
4. **Derived state is rebuildable**: Indexes and caches can be regenerated
5. **Cloud is optional enhancement**: Remote LLMs are opt-in, not required

### Implementation
```
Local Machine
├── augur/          # Code (can be offline)
├── augur-data/     # User data (always local)
├── Derived indexes     # Rebuildable from source
└── Local LLM (optional) # Ollama for offline reasoning
```

### Network Dependencies
| Component | Offline? | Notes |
|-----------|----------|-------|
| Dashboard | ✅ Yes | Runs locally on Next.js |
| Skills | ✅ Yes | Python scripts, local files |
| RAG Search | ✅ Yes | ripgrep on local markdown |
| Remote LLM | ❌ No | Requires internet |
| Local LLM | ✅ Yes | Ollama runs locally |
| GitHub sync | ❌ No | Optional, for backup |

## Consequences

### Positive

- **Privacy by design**: Sensitive data never leaves your machine
- **Always available**: Works without internet connection
- **No vendor lock-in**: Standard file formats, easy migration
- **Cost predictable**: No per-query fees (if using local LLM)
- **Long-term durability**: Files outlive services
- **Full control**: You own your data completely

### Negative

- **Device-bound**: Data lives on one machine (unless you sync manually)
- **Backup responsibility**: User must manage backups
- **Local resources**: Needs storage and compute on user machine
- **LLM quality tradeoff**: Local models less capable than cloud

### Neutral

- Cloud LLMs (GPT-4, Claude) remain available as opt-in enhancement
- Users can set up their own sync (iCloud, Syncthing, etc.)
- Multi-device support is not a first-class feature

## Alternatives Considered

### Alternative 1: Cloud-First with Local Cache

Primary storage in cloud, local cache for offline. Rejected because:
- Still dependent on cloud service availability
- Privacy concerns with primary cloud storage
- Sync conflicts between cloud and local
- Ongoing costs

### Alternative 2: Hybrid with Cloud Backup

Local-first with automatic cloud backup. Rejected (for now) because:
- Adds complexity to core architecture
- Privacy concerns with backup service
- User may not want any cloud exposure
- Can be added later as optional feature

### Alternative 3: Peer-to-Peer Sync

Local-first with P2P sync between user devices. Rejected (for now) because:
- Significant complexity
- Conflict resolution challenges
- Requires multiple devices always online
- Can be added later if needed

## References

- [ADR-002](./ADR-002-data-separation.md) - Data separation decision
- [ADR-004](./ADR-004-markdown-rag.md) - Markdown RAG (no external DB)
- [Local-First Software](https://www.inkandswitch.com/local-first/) - Ink & Switch paper
