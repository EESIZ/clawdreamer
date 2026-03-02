# Dreamer: Neuroscience-Inspired AI Memory Consolidation

## Background

Inspired by how the human brain consolidates memories during sleep,
Dreamer periodically compresses, integrates, and prunes an AI agent's
LanceDB memory store.

## Scientific Basis

### Complementary Learning Systems (McClelland, 1995)
- Hippocampus (fast learning, episodes) + Neocortex (slow learning, patterns/schemas)
- Transfer between the two systems during sleep is key to memory consolidation

### Sleep Stage Roles
- **NREM**: Hippocampus -> Neocortex memory transfer. Compressed replay via sharp-wave ripples.
  Synaptic Homeostasis Hypothesis (SHY): global downscaling with selective preservation.
- **REM**: Integration with existing knowledge, distant associations, synaptic pruning.

### Engram Lifecycle
- Encoding -> Consolidation -> Retrieval -> Forgetting
- Forgetting = reduced accessibility, not deletion (index decay)
- Episodic -> Semantic memory transformation (concrete -> abstract)

## Memory Architecture

### Layer 1: Episodic (Hippocampus)
- `episodes/YYYY-MM-DD.md` -- daily raw experiences
- Unstructured text flushed by the AI agent during conversation

### Layer 2: Semantic (Neocortex)
- `lancedb/memories.lance` -- LanceDB vector database
- Schema: id, text, vector(1536d), importance(0-1), category, createdAt

### Problems Solved
- No connection between the two layers (no consolidation process)
- No importance differentiation (all memories equal weight)
- Episodes accumulate without being converted to semantic memories
- Duplicate/contradictory memories not cleaned up

## Dream Process Design

### Phase 1: NREM (Stabilization + Transfer)

```
1. Load episodes (episodes/*.md)
2. Chunk into semantic units
3. Generate embeddings
4. Cluster similar chunks (cosine similarity > 0.75)
5. LLM summarization per cluster -> extract patterns/principles
6. Dedup check against existing LanceDB memories (similarity > 0.9)
7. Store new semantic memories (dynamic importance scoring)
```

### Phase 2: REM (Integration + Pruning)

```
8.  Load all semantic memories
9.  Detect conflicts between NEW and EXISTING (O(N*M), not O(N^2))
10. Classify: state_change / different_aspects / unrelated
11. Resolve: merge (state changes) or consolidate (different aspects)
12. Apply importance decay (unrecalled memories fade)
13. Soft-delete memories below threshold (0.15)
14. Archive processed episode files
```

### Phase 3: Dream Log

```
15. Generate summary report -> dream-log/YYYY-MM-DD_HHMM.md
    - New semantic memories created
    - Memories merged/consolidated
    - Memories soft-deleted
    - Conflicts found and resolved
```

## Execution

- Daily cron job (recommended: 3 AM)
- LLM: OpenAI gpt-4.1-nano (default) or MiniMax M2.5 (low-cost alternative)
- Embeddings: OpenAI text-embedding-3-small

## File Structure

```
dreamer/
├── DESIGN.md          # this document
├── config.py          # configuration
├── dreamer.py         # main entry point
├── nrem.py            # Phase 1: episode -> semantic conversion
├── rem.py             # Phase 2: integration + pruning
├── embedder.py        # OpenAI embedding generation
├── lancedb_store.py   # LanceDB read/write operations
├── llm.py             # LLM calls (summarization/classification)
├── dream_log.py       # dream log generation
└── requirements.txt
```
