---
title: 'User Journey: LLM Configuration & Project Evolution'
type: design-note
skill: advisor
tags:
- advisor
- architecture
- llm
_relates_to:
- '[[advisor]]'
- '[[architecture]]'
- '[[llm]]'
---


# User Journey: LLM Configuration & Project Evolution

This journey maps how the **Master Configuration File (`llm.yaml`)** acts as the central nervous system for your project's intelligence, evolving from a simple global setup to a highly optimized, component-specific configuration.

## System Ecosystem Flow

This diagram illustrates how the Global Config and IDE interact across the three main layers of Augur: **Vertical Apps**, **Horizontal Capabilities**, and **System Agents**.

```mermaid
graph TD
    classDef config fill:#f9f,stroke:#333,stroke-width:2px;
    classDef dev fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef ops fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;

    User([User])
    GlobalConfig["Master Config (llm.yaml)"]:::config
    IDE_MCP["IDE / MCP Integration<br>(Cursor/VS Code)"]:::dev

    User -->|Edit Settings| GlobalConfig
    GlobalConfig -.->|Injects Profiles| System_Core

    subgraph System_Core ["Augur System Core"]
        direction TB

        subgraph Layer_System ["3. System Agents (Factory)"]
            style Layer_System fill:#fff3e0,stroke:#e65100
            Planner[Planner Agent]:::ops
            Builder[Builder Agent]:::ops
            
            Planner -->|1. Project Ops: Run Task| Builder
            Planner -->|2. Self-Dev: Improve Agent| IDE_MCP
        end

        subgraph Layer_Vertical ["1. Vertical Apps (Domain)"]
            style Layer_Vertical fill:#e3f2fd,stroke:#1565c0
            Marketing[Marketing App]:::ops
            Career[Career App]:::ops
            
            User -->|3. Operation: Use App| Marketing
            Builder -->|4. Dev: Refactor App| Marketing
        end

        subgraph Layer_Horizontal ["2. Horizontal Capabilities (Shared)"]
            style Layer_Horizontal fill:#f3e5f5,stroke:#4a148c
            Memory[Memory / RAG]:::ops
            Voice[Voice IO]:::ops
            
            Marketing -->|5. Operation: Retrieve| Memory
            Builder -->|6. Dev: Upgrade Cap| Memory
        end
    end

    IDE_MCP -->|Executes Code Changes| Layer_Vertical
    IDE_MCP -->|Executes Code Changes| Layer_Horizontal
    IDE_MCP -->|Executes Code Changes| Layer_System

    %% Legend
    linkStyle default stroke-width:2px,fill:none,stroke:gray;
```

## Detailed Flow Breakdown

### 1. Vertical App Usage (Operation & Dev)
**Context:** Domain-specific applications like Marketing or Career.
*   **Operation:** You (the User) interact directly with the app (e.g., "Generate LinkedIn Post"). The app uses the **Active LLM Profile** defined in `llm.yaml` to generate content.
*   **Development:** You notice a bug or want a new feature. You create a request. The **System Agents** (Planner/Builder) use the **IDE MCP** to modify the Vertical App's code safely.

### 2. Horizontal Capabilities (Operation & Dev)
**Context:** Shared powers like Memory (RAG), Voice, or Browser access.
*   **Operation:** Vertical Apps call these services in the background. For example, the Career App asks **Memory** for your resume data. This uses the storage/embedding configurations.
*   **Development:** If a capability is slow or inaccurate, the **System Agents** can refactor the underlying service code (e.g., "Switch RAG from Chroma to PGVector") via the **IDE MCP**.

### 3. System Agents (Project Ops & Self-Dev)
**Context:** The "Meta-Layer" that manages the codebase (Planner, Builder, Reviewer).
*   **Project Operation:** The **Planner** reads your backlog and assigns tasks to the **Builder**. They run nightly to keep the project moving.
*   **Agent Self-Dev**: The most powerful loop. The Agents can recognize their own limitations (e.g., "I failed to parse this file"). They then generate a self-improvement task, use the **IDE MCP** to rewrite their own logic, and restart with improved capabilities.

## The Role of `llm.yaml` in These Flows

| Layer | Configuration Impact | Example Override |
| :--- | :--- | :--- |
| **System** | Determines how smart the Planner is. | `factory/planner: { active_profile: "reasoning_model" }` |
| **Vertical** | Determines the creative voice of the app. | `vertical/marketing: { active_profile: "creative_model" }` |
| **Horizontal**| Determine embedding/search quality. | `horizontal/memory: { active_profile: "fast_model" }` |

This architecture ensures that **Configuration** (Brain) is decoupled from **Implementation** (Body), but the Body can rewrite itself using the Brain.
