# Knowledge Base Management & RAG Architecture

## Overview

This document describes the workflow for building and maintaining knowledge bases using RAG (Retrieval-Augmented Generation) architecture.

---

## RAG Architecture Principles

### Core Concepts
1. **Indexing**: Transform documents into searchable representations
2. **Retrieval**: Find relevant information based on query
3. **Augmentation**: Provide retrieved context to LLM
4. **Generation**: LLM generates response using context

### When to Use RAG
- Large corpus of documentation (>100 files)
- Need semantic search (not just keyword matching)
- Dynamic content that changes frequently
- Privacy-sensitive content (use local embeddings)

### When NOT to Use RAG
- Small documentation (<20 files) → Use file search
- Static content → Pre-summarize once
- Structured data with known schema → Use database queries

---

## RAG Implementation Approaches

### Option 1: File-Based Search (Simplest)

**Best for**: Small to medium documentation, fast prototyping

**Tools**: ripgrep, fzf, basic text search

**Implementation**:
```python
import subprocess

def search_docs(query: str, path: str) -> list:
    """Simple file-based search using ripgrep."""
    result = subprocess.run(
        ['rg', '--json', query, path],
        capture_output=True,
        text=True
    )
    # Parse and return results
    return parse_ripgrep_json(result.stdout)
```

**Pros**:
- No dependencies
- Fast for small datasets
- Easy to debug

**Cons**:
- No semantic understanding
- Keyword-only matching
- Doesn't scale well

---

### Option 2: Local Embeddings + FAISS

**Best for**: Privacy-focused, medium-scale, semantic search

**Tools**: sentence-transformers, FAISS

**Implementation**:
```python
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# Initialize model (one-time setup)
model = SentenceTransformer('all-MiniLM-L6-v2')

# Index documents
documents = load_all_docs()
embeddings = model.encode(documents)
index = faiss.IndexFlatL2(embeddings.shape[1])
index.add(np.array(embeddings))

# Save index
faiss.write_index(index, 'docs.index')

# Search
query_embedding = model.encode([query])
distances, indices = index.search(query_embedding, k=5)
results = [documents[i] for i in indices[0]]
```

**Pros**:
- Semantic understanding
- Completely local (no API calls)
- Fast retrieval

**Cons**:
- Requires ML dependencies
- Initial embedding time
- ~100MB model size

---

### Option 3: ChromaDB

**Best for**: Medium to large scale, persistent storage

**Tools**: ChromaDB

**Implementation**:
```python
import chromadb
from chromadb.config import Settings

# Initialize
client = chromadb.Client(Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="./chroma_db"
))

# Create collection
collection = client.create_collection("skill_docs")

# Add documents
collection.add(
    documents=["doc1 text", "doc2 text"],
    metadatas=[{"skill": "job-analyzer"}, {"skill": "reading-list"}],
    ids=["doc1", "doc2"]
)

# Query
results = collection.query(
    query_texts=["how to analyze jobs"],
    n_results=5
)
```

**Pros**:
- Persistent storage
- Built-in metadata filtering
- Scales well

**Cons**:
- Additional dependency
- More complex setup
- Heavier than FAISS

---

### Option 4: API-Based Embeddings

**Best for**: Large scale, cloud-based, budget available

**Tools**: OpenAI embeddings, Pinecone/Weaviate

**Implementation**:
```python
import openai

# Generate embedding
response = openai.Embedding.create(
    model="text-embedding-ada-002",
    input="document text"
)
embedding = response['data'][0]['embedding']

# Store in vector DB (Pinecone example)
import pinecone
index = pinecone.Index("skill-docs")
index.upsert([("doc1", embedding, {"skill": "job-analyzer"})])

# Query
query_embedding = openai.Embedding.create(
    model="text-embedding-ada-002",
    input="how to analyze jobs"
)['data'][0]['embedding']
results = index.query(query_embedding, top_k=5)
```

**Pros**:
- Best quality embeddings
- Scales infinitely
- Managed infrastructure

**Cons**:
- API costs
- Privacy concerns
- Requires internet

---

## Documentation Indexing Workflow

### Step 1: Document Discovery
```python
from pathlib import Path

def find_skill_docs() -> list:
    """Find all skill documentation files."""
    skills_dir = Path("plugins/")
    docs = []

    for skill_dir in skills_dir.glob("*/"):
        # Core files
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            docs.append(skill_md)

        # Reference docs
        refs_dir = skill_dir / "references"
        if refs_dir.exists():
            docs.extend(refs_dir.glob("*.md"))

    return docs
```

### Step 2: Document Chunking
```python
def chunk_document(content: str, chunk_size: int = 500) -> list:
    """Split document into chunks for embedding."""
    # Option 1: Fixed-size chunks
    chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]

    # Option 2: Semantic chunks (better)
    sections = content.split('\n## ')
    return [f"## {s}" for s in sections if s.strip()]
```

### Step 3: Metadata Extraction
```python
def extract_metadata(file_path: Path) -> dict:
    """Extract metadata from skill file."""
    content = file_path.read_text()

    # Parse frontmatter
    if content.startswith('---'):
        frontmatter = content.split('---')[1]
        metadata = parse_yaml(frontmatter)

    return {
        'skill': file_path.parent.name,
        'file': str(file_path),
        'type': 'SKILL' if 'SKILL.md' in str(file_path) else 'reference',
        **metadata
    }
```

### Step 4: Index Building
```python
def build_index():
    """Build complete knowledge base index."""
    docs = find_skill_docs()

    for doc in docs:
        content = doc.read_text()
        chunks = chunk_document(content)
        metadata = extract_metadata(doc)

        for i, chunk in enumerate(chunks):
            add_to_index(
                text=chunk,
                metadata={**metadata, 'chunk': i},
                id=f"{doc.stem}_{i}"
            )

    save_index()
```

---

## Search and Retrieval

### Basic Search
```python
def search(query: str, top_k: int = 5) -> list:
    """Search knowledge base."""
    results = index.query(query, n_results=top_k)

    return [
        {
            'text': r['document'],
            'file': r['metadata']['file'],
            'skill': r['metadata']['skill'],
            'score': r['distance']
        }
        for r in results
    ]
```

### Contextual Retrieval
```python
def retrieve_context(query: str, skill_filter: str = None) -> str:
    """Retrieve context for LLM augmentation."""
    filters = {'skill': skill_filter} if skill_filter else None
    results = search(query, filters=filters, top_k=3)

    context = "\n\n---\n\n".join([
        f"From {r['file']}:\n{r['text']}"
        for r in results
    ])

    return context
```

---

## Cross-Reference Tracking

### Building Cross-Reference Map
```python
import re

def find_references(content: str) -> list:
    """Find references to other skills in content."""
    # Pattern: skill-name or plugins/skill-name
    pattern = r'`([a-z-]+)`|plugins/([a-z-]+)/'
    matches = re.findall(pattern, content)

    skills = set()
    for match in matches:
        skill = match[0] or match[1]
        if is_valid_skill(skill):
            skills.add(skill)

    return list(skills)

def build_cross_reference_map():
    """Build map of skill dependencies."""
    refs = {}

    for skill_file in find_skill_docs():
        skill = skill_file.parent.name
        content = skill_file.read_text()
        referenced_skills = find_references(content)

        refs[skill] = {
            'references': referenced_skills,
            'referenced_by': []
        }

    # Build reverse references
    for skill, data in refs.items():
        for ref_skill in data['references']:
            refs[ref_skill]['referenced_by'].append(skill)

    return refs
```

---

## Performance Optimization

### Caching
- Cache embeddings to avoid recomputation
- Use incremental indexing (only index changed files)
- Store index on disk, load on startup

### Parallel Processing
```python
from concurrent.futures import ThreadPoolExecutor

def parallel_index(docs: list):
    """Index documents in parallel."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        embeddings = list(executor.map(embed_document, docs))
    return embeddings
```

### Incremental Updates
```python
def incremental_index(changed_files: list):
    """Only re-index changed files."""
    for file_path in changed_files:
        # Remove old entries
        remove_from_index(file_path)

        # Add new entries
        content = file_path.read_text()
        chunks = chunk_document(content)
        add_to_index(chunks, file_path)
```

---

## Recommendation

**Start with Option 1 (File-Based Search)**:
- Use ripgrep for initial implementation
- Measure performance and coverage
- Upgrade to FAISS/ChromaDB only when file search is insufficient

**Upgrade to Option 2 (FAISS) when**:
- Keyword search misses relevant docs
- Documentation grows beyond 100 files
- Semantic understanding becomes important

**Consider Option 3/4 (ChromaDB/API) when**:
- Need persistent storage
- Documentation exceeds 500 files
- Budget allows for API costs
