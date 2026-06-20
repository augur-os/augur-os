# Source Extraction Implementation

## Overview

This directory contains implementations for extracting content from multiple source types to create unified skills.

## Files

- `source_extractor.py` - Extracts content from individual sources
- `source_combiner.py` - Combines multiple sources with conflict resolution

## Supported Sources

### 1. Notion Pages
- **API**: Uses Notion API v1
- **Features**:
  - Extracts page title and blocks
  - Parses requirements from content
  - Supports public and private pages (with API key)
- **Requirements**: Notion API key (optional for public pages)

### 2. Folders
- **Features**:
  - Recursive file scanning
  - File type analysis
  - Size calculation
  - Domain inference from folder name
- **Requirements**: Valid folder path

### 3. Git Repositories
- **Features**:
  - Clones repository (shallow clone)
  - Branch/tag support
  - Skill structure detection
  - File analysis
- **Requirements**: Valid Git URL, Git installed

### 4. Free Prompts
- **Features**:
  - LLM-based analysis
  - Extracts domain, patterns, requirements
  - Generates structured requirements
- **Requirements**: LLM configured (falls back to basic analysis)

### 5. Zip Files
- **Features**:
  - Supports .zip and .tar.gz
  - Extracts and analyzes contents
  - Skill structure detection
  - File listing
- **Requirements**: Valid archive file

## Usage

### Extract Single Source

```bash
python source_extractor.py config.json
```

Config format:
```json
{
  "type": "notion|folder|git|prompt|zip",
  "value": "source value (URL, path, text, etc.)",
  "api_key": "optional for Notion",
  "branch": "optional for Git (default: main)"
}
```

### Combine Multiple Sources

```bash
python source_combiner.py config.json
```

Config format:
```json
{
  "sources": [
    {
      "id": "1",
      "type": "notion",
      "value": "https://notion.so/page/...",
      "preview": { ... }
    },
    ...
  ],
  "skill_name": "optional override",
  "layer": "vertical|horizontal|factory"
}
```

## Conflict Resolution

Sources are prioritized:
1. Notion (highest)
2. Folder
3. Git
4. Prompt
5. Zip (lowest)

Conflicts are resolved by using the highest priority source's value.

## Error Handling

All functions return dictionaries with:
- `error`: Error message if extraction failed
- `extracted`: Boolean indicating success
- `preview`: Extracted content preview

Errors are non-fatal - the system will continue with available sources.

