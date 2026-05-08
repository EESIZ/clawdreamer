"""LanceDB read/write operations for memories."""

import logging
import time
import uuid

import lancedb

from config import LANCEDB_PATH, EMBEDDING_DIM

log = logging.getLogger("dreamer.store")

TABLE_NAME = "memories"


def _table_names(db) -> list[str]:
    if hasattr(db, "table_names"):
        return db.table_names()
    return db.list_tables()


def _create_memories_table(db):
    """Create a LanceDB table compatible with OpenClaw memory-lancedb.

    OpenClaw's JavaScript plugin creates the vector column from a sample row,
    which LanceDB stores as fixed_size_list<float>[dim]. Creating an empty table
    from a pyarrow list schema can produce list<float>, and OpenClaw will not
    recognize that as a searchable vector column.
    """
    table = db.create_table(TABLE_NAME, [{
        "id": "__schema__",
        "text": "",
        "vector": [0.0] * EMBEDDING_DIM,
        "importance": 0.0,
        "category": "other",
        "createdAt": 0.0,
    }])
    table.delete("id = '__schema__'")
    return table


def _validate_vector_schema(table) -> None:
    field = table.schema.field("vector")
    vector_type = field.type
    list_size = getattr(vector_type, "list_size", None)
    if list_size != EMBEDDING_DIM:
        raise RuntimeError(
            "Incompatible LanceDB memories.vector dimension: "
            f"expected {EMBEDDING_DIM}, got {list_size or vector_type}. "
            "Recreate or migrate the memories table with the current Dreamer setup."
        )
    if "fixed_size_list" not in str(vector_type):
        raise RuntimeError(
            "Incompatible LanceDB memories.vector schema: "
            f"expected fixed_size_list<float>[{EMBEDDING_DIM}], got {vector_type}. "
            "This table was likely created with an older Dreamer pyarrow schema. "
            "Recreate or migrate it so OpenClaw memory-lancedb can recall memories."
        )


def get_table():
    """Open the memories table."""
    db = lancedb.connect(LANCEDB_PATH)
    if TABLE_NAME in _table_names(db):
        table = db.open_table(TABLE_NAME)
    else:
        table = _create_memories_table(db)
    _validate_vector_schema(table)
    return table


def load_all_memories() -> list[dict]:
    """Load all memories as list of dicts."""
    t = get_table()
    df = t.to_pandas()
    memories = []
    for _, row in df.iterrows():
        memories.append({
            "id": row["id"],
            "text": row["text"],
            "vector": list(row["vector"]) if row["vector"] is not None else [],
            "importance": float(row["importance"]),
            "category": row["category"],
            "createdAt": float(row["createdAt"]),
        })
    return memories


def add_memory(text: str, vector: list[float], importance: float,
               category: str) -> str:
    """Add a new memory to LanceDB. Returns the new memory ID."""
    mem_id = str(uuid.uuid4())
    t = get_table()
    t.add([{
        "id": mem_id,
        "text": text,
        "vector": vector,
        "importance": importance,
        "category": category,
        "createdAt": time.time() * 1000,  # epoch ms
    }])
    log.info("Added memory %s (%.1f, %s): %s",
             mem_id[:8], importance, category, text[:80])
    return mem_id


def update_importance(mem_id: str, new_importance: float):
    """Update importance score for a memory."""
    t = get_table()
    t.update(
        where=f"id = '{mem_id}'",
        values={"importance": new_importance},
    )


def update_memory_text(mem_id: str, new_text: str, new_vector: list[float]):
    """Update the text and vector of an existing memory (for merge/consolidation)."""
    t = get_table()
    t.update(
        where=f"id = '{mem_id}'",
        values={"text": new_text, "vector": new_vector},
    )
    log.info("Updated memory text %s: %s", mem_id[:8], new_text[:80])


def delete_memory(mem_id: str):
    """Delete a memory by ID."""
    t = get_table()
    t.delete(f"id = '{mem_id}'")
    log.info("Deleted memory %s", mem_id[:8])


def search_similar(vector: list[float], top_k: int = 5,
                    threshold: float = 0.3) -> list[dict]:
    """Search for similar memories by vector."""
    t = get_table()
    results = (
        t.search(vector)
        .limit(top_k)
        .to_pandas()
    )
    matches = []
    for _, row in results.iterrows():
        matches.append({
            "id": row["id"],
            "text": row["text"],
            "importance": float(row["importance"]),
            "category": row["category"],
            "distance": float(row.get("_distance", 999)),
        })
    return matches
