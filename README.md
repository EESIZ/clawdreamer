# Dreamer

**Neuroscience-inspired memory consolidation for AI agents.**

Dreamer mimics how the human brain consolidates memories during sleep. It runs a nightly cycle that converts raw episodic memories into compressed semantic memories, resolves conflicts, and prunes stale information.

## How It Works

Like a sleeping brain, Dreamer runs three phases:

### Phase 1: NREM (Episode -> Semantic)
- Loads daily episode files (`YYYY-MM-DD.md`)
- Chunks text into semantic units
- Clusters similar chunks via embedding similarity
- LLM summarizes each cluster into key facts
- Deduplicates against existing memories
- Stores new semantic memories in LanceDB

### Phase 2: REM (Integration + Pruning)
- Detects conflicts between **new** and **existing** memories (O(N*M), not O(N^2))
- Classifies conflicts: `state_change` / `different_aspects` / `unrelated`
- **State changes**: merges newer state with historical context
- **Different aspects**: consolidates into comprehensive memory
- Applies importance decay (unrecalled memories fade over time)
- Soft-deletes memories below importance threshold
- Archives processed episodes

### Phase 3: Dream Log
- Generates a markdown report of what happened during the dream cycle

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env with your OpenAI API key

# 3. Create data directory
export DREAMER_HOME=~/.dreamer
mkdir -p $DREAMER_HOME/{episodes,lancedb,dream-log}

# 4. Add episode files
# Place markdown files as $DREAMER_HOME/episodes/YYYY-MM-DD.md

# 5. Run
python dreamer.py --verbose
```

## Configuration

All settings are in `config.py` and can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DREAMER_HOME` | `~/.dreamer` | Root data directory |
| `OPENAI_API_KEY` | (required) | For embeddings |
| `MINIMAX_API_KEY` | (optional) | If using MiniMax LLM |
| `DREAMER_LLM_PROVIDER` | `openai` | `openai` or `minimax` |

### Tunable Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CLUSTER_SIMILARITY` | 0.75 | Threshold for grouping chunks |
| `DEDUP_SIMILARITY` | 0.90 | Skip if existing memory is this similar |
| `CONTRADICTION_SIMILARITY` | 0.70 | Conflict detection threshold |
| `IMPORTANCE_DECAY_RATE` | 0.05 | Daily decay rate |
| `SOFT_DELETE_THRESHOLD` | 0.15 | Below this = memory deleted |
| `MAX_EPISODES_PER_RUN` | 7 | Max days processed per cycle |
| `MAX_NEW_MEMORIES` | 20 | Cap on new memories per cycle |

## Episode File Format

Episodes are markdown files named `YYYY-MM-DD.md` placed in the episodes directory. Content is free-form -- any markdown text that represents the AI agent's daily experiences:

```markdown
# Session Notes - 2024-03-15

## User asked about deployment
Discussed Docker setup. User prefers docker-compose over raw Docker commands.
Decided to use nginx as reverse proxy.

## API Integration
Connected to the payment API. Key endpoint: POST /v1/charges
Rate limit: 100 req/min. Auth via Bearer token.
```

## Running as a Cron Job

```bash
# Example: run daily at 3 AM
0 3 * * * cd /path/to/dreamer && python3 dreamer.py --verbose >> dream-log/cron.log 2>&1
```

Or use the provided systemd timer (see `examples/`).

## Architecture

```
Episode Files (YYYY-MM-DD.md)
        │
        ▼
   ┌─────────┐
   │  NREM   │  Chunk → Embed → Cluster → Summarize → Store
   └────┬────┘
        │ created_ids
        ▼
   ┌─────────┐
   │   REM   │  Conflict Detection → Merge/Consolidate → Decay → Prune
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │Dream Log│  Generate report
   └─────────┘
```

## Requirements

- Python 3.10+
- OpenAI API key (for embeddings)
- LLM API key (OpenAI or MiniMax)

## License

MIT
