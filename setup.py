#!/usr/bin/env python3
"""Setup script for Dreamer.

Initializes the data directory structure and LanceDB table.

Usage:
    python setup.py                    # initialize with defaults
    python setup.py --home /path/to    # custom data directory
    python setup.py --example          # also create example episode
"""

import argparse
import os
import sys


def create_memories_table(db, dim: int):
    """Create a LanceDB table compatible with OpenClaw memory-lancedb."""
    table = db.create_table("memories", [{
        "id": "__schema__",
        "text": "",
        "vector": [0.0] * dim,
        "importance": 0.0,
        "category": "other",
        "createdAt": 0.0,
    }])
    table.delete("id = '__schema__'")
    return table


def validate_vector_schema(table, dim: int) -> None:
    field = table.schema.field("vector")
    vector_type = field.type
    list_size = getattr(vector_type, "list_size", None)
    if list_size != dim or "fixed_size_list" not in str(vector_type):
        raise RuntimeError(
            "Existing LanceDB 'memories' table has an OpenClaw-incompatible "
            f"vector schema: {vector_type}. Expected fixed_size_list<float>[{dim}]. "
            "Back it up, recreate the table with this setup script, then migrate rows."
        )


def main():
    parser = argparse.ArgumentParser(description="Initialize Dreamer data directory")
    parser.add_argument("--home", default=os.environ.get("DREAMER_HOME", os.path.expanduser("~/.dreamer")),
                        help="Data directory path (default: ~/.dreamer)")
    parser.add_argument("--example", action="store_true",
                        help="Create an example episode file")
    args = parser.parse_args()

    home = os.path.abspath(args.home)
    print(f"Dreamer home: {home}")

    # 1. Create directory structure
    dirs = [
        os.path.join(home, "episodes"),
        os.path.join(home, "episodes", "archive"),
        os.path.join(home, "lancedb"),
        os.path.join(home, "dream-log"),
        os.path.join(home, "memory-archive"),
        os.path.join(home, "workspace"),
        os.path.join(home, "workspace", "docs"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"  Created: {d}")

    # 2. Initialize LanceDB table
    try:
        import lancedb
    except ImportError:
        print("\nError: lancedb is required.")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)

    lancedb_path = os.path.join(home, "lancedb")
    db = lancedb.connect(lancedb_path)

    table_names = db.table_names() if hasattr(db, "table_names") else db.list_tables()
    if "memories" in table_names:
        t = db.open_table("memories")
        dim = int(os.environ.get("DREAMER_EMBEDDING_DIM", "1536"))
        validate_vector_schema(t, dim)
        count = t.count_rows()
        print(f"\n  LanceDB 'memories' table already exists ({count} rows)")
    else:
        dim = int(os.environ.get("DREAMER_EMBEDDING_DIM", "1536"))
        create_memories_table(db, dim)
        print(f"\n  Created LanceDB 'memories' table ({dim}-dim vectors)")

    # 3. Create example episode (optional)
    if args.example:
        from datetime import datetime, timezone, timedelta

        today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
        episode_path = os.path.join(home, "episodes", f"{today}.md")

        if os.path.exists(episode_path):
            print(f"\n  Episode already exists: {episode_path}")
        else:
            example = f"""# Session Notes - {today}

## Project Setup
Discussed deployment strategy. Decided on Docker Compose with nginx reverse proxy.
Database: PostgreSQL 16 with pgvector extension for embeddings.

## API Integration
Connected to the payment gateway API.
- Endpoint: POST /v1/charges
- Rate limit: 100 req/min
- Auth: Bearer token in header
- Webhook URL configured for payment confirmations.

## User Preferences
User prefers dark mode UI. Font size: 14px.
Keyboard shortcut for save: Ctrl+S (not Cmd+S).
"""
            with open(episode_path, "w", encoding="utf-8") as f:
                f.write(example)
            print(f"\n  Created example episode: {episode_path}")

    # 4. Check API key
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        print(f"\n  OPENAI_API_KEY: set ({api_key[:8]}...)")
    else:
        print("\n  WARNING: OPENAI_API_KEY not set. Required for embeddings.")
        print("  Set it in your .env file or environment.")

    print(f"\nSetup complete! Run: DREAMER_HOME={home} python dreamer.py --verbose")


if __name__ == "__main__":
    main()
