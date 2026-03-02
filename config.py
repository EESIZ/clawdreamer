"""Dreamer configuration."""

import os

# ── Paths ──
# Set DREAMER_HOME to your data root directory.
# Expected structure:
#   DREAMER_HOME/
#     episodes/          - episodic memory files (YYYY-MM-DD.md)
#     episodes/archive/  - processed episodes moved here
#     lancedb/           - LanceDB vector database
#     memory-archive/    - pre-merge backups
#     workspace/         - (optional) reference files for context linking
#     dream-log/         - generated dream log reports

DREAMER_HOME = os.environ.get("DREAMER_HOME", os.path.expanduser("~/.dreamer"))

LANCEDB_PATH = os.path.join(DREAMER_HOME, "lancedb")
EPISODE_DIR = os.path.join(DREAMER_HOME, "episodes")
ARCHIVE_DIR = os.path.join(DREAMER_HOME, "episodes", "archive")
DREAM_LOG_DIR = os.path.join(DREAMER_HOME, "dream-log")
WORKSPACE_DIR = os.path.join(DREAMER_HOME, "workspace")
DOCS_DIR = os.path.join(DREAMER_HOME, "workspace", "docs")
SKILLS_DIR = os.path.join(DREAMER_HOME, "workspace", "skills")
MEMORY_ARCHIVE_DIR = os.path.join(DREAMER_HOME, "memory-archive")

# ── API Keys (from environment variables) ──

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")

# Embedding provider: "openai", "ollama", or "sentence-transformers"
EMBEDDING_PROVIDER = os.environ.get("DREAMER_EMBEDDING_PROVIDER", "openai")

# OpenAI embedding
EMBEDDING_MODEL = "text-embedding-3-small"

# Ollama embedding (local)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

# Sentence-transformers embedding (local)
ST_MODEL_NAME = os.environ.get("ST_MODEL_NAME", "all-MiniLM-L6-v2")

# Vector dimension (must match your chosen model)
# - openai text-embedding-3-small: 1536
# - nomic-embed-text: 768
# - all-MiniLM-L6-v2: 384
EMBEDDING_DIM = int(os.environ.get("DREAMER_EMBEDDING_DIM", "1536"))

# LLM (for summarization/classification)
LLM_PROVIDER = os.environ.get("DREAMER_LLM_PROVIDER", "openai")  # openai or minimax
MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"

# NREM parameters
CHUNK_MIN_LENGTH = 20       # minimum chars per chunk
CLUSTER_SIMILARITY = 0.75   # cosine similarity threshold for clustering
DEDUP_SIMILARITY = 0.90     # skip if existing memory is this similar

# REM parameters
IMPORTANCE_DECAY_RATE = 0.05     # per day without recall
IMPORTANCE_FLOOR = 0.1           # minimum importance before soft-delete
SOFT_DELETE_THRESHOLD = 0.15     # below this = mark for deletion
CONTRADICTION_SIMILARITY = 0.70  # same-topic detection threshold
MERGE_MIN_LENGTH = 20            # minimum chars for a merged memory text
CONSOLIDATE_MAX_LENGTH = 300     # max chars before splitting consolidated memory

# Scheduling
MAX_EPISODES_PER_RUN = 7   # process up to N days of episodes
MAX_NEW_MEMORIES = 20       # cap on new semantic memories per run
