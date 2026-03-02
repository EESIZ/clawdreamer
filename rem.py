"""REM Phase: Memory integration, pruning, and maintenance.

v0.2: 3-tier conflict resolution (merge/consolidate/retain) replacing simple delete.
Compares only new memories (M) against existing (N) for O(N*M) efficiency.

Like REM sleep:
1. Load all semantic memories from LanceDB
2. Detect conflicts between NEW and EXISTING memories
3. Classify: state_change / different_aspects / unrelated
4. Resolve: merge (state change) or consolidate (different aspects)
5. Apply importance decay (memories not recalled fade)
6. Soft-delete memories below threshold
7. Archive processed episode files
"""

import json
import logging
import os
import shutil
import time

from config import (
    ARCHIVE_DIR,
    CONTRADICTION_SIMILARITY,
    EPISODE_DIR,
    IMPORTANCE_DECAY_RATE,
    IMPORTANCE_FLOOR,
    MEMORY_ARCHIVE_DIR,
    MERGE_MIN_LENGTH,
    SOFT_DELETE_THRESHOLD,
)
from embedder import cosine_similarity, embed_texts
from lancedb_store import (
    add_memory,
    delete_memory,
    load_all_memories,
    update_importance,
    update_memory_text,
)
from llm import classify_relationship, consolidate_aspects, merge_state_change

log = logging.getLogger("dreamer.rem")


def archive_memory_backup(mem: dict):
    """Write a memory to archive before modifying/deleting it."""
    os.makedirs(MEMORY_ARCHIVE_DIR, exist_ok=True)
    filepath = os.path.join(MEMORY_ARCHIVE_DIR, f"{mem['id'][:8]}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "id": mem["id"],
            "text": mem["text"],
            "importance": mem.get("importance", 0),
            "category": mem.get("category", ""),
            "createdAt": mem.get("createdAt", 0),
            "archived_reason": "pre-merge-backup",
        }, f, ensure_ascii=False, indent=2)
    log.info("Archived memory backup: %s", mem["id"][:8])


def find_conflicts(memories: list[dict],
                   new_ids: set[str]) -> list[tuple[dict, dict, dict]]:
    """Find conflicts between NEW memories and ALL memories.

    Only compares each new memory against existing ones (not new vs new).
    Returns list of (mem_new, mem_existing, classification) tuples.
    """
    conflicts = []
    new_mems = [m for m in memories if m["id"] in new_ids]
    checked_pairs = set()

    for new_mem in new_mems:
        if not new_mem.get("vector"):
            continue
        for other in memories:
            if other["id"] == new_mem["id"]:
                continue
            if not other.get("vector"):
                continue
            # Skip new-vs-new (same batch protection)
            if other["id"] in new_ids:
                continue
            # Avoid duplicate pair checks
            pair_key = tuple(sorted([new_mem["id"], other["id"]]))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            sim = cosine_similarity(new_mem["vector"], other["vector"])
            if sim < CONTRADICTION_SIMILARITY:
                continue

            classification = classify_relationship(
                new_mem["text"], other["text"]
            )
            if classification["type"] != "unrelated":
                conflicts.append((new_mem, other, classification))
                log.info(
                    "Conflict (sim=%.3f, type=%s): '%s' vs '%s'",
                    sim, classification["type"],
                    new_mem["text"][:60], other["text"][:60],
                )

    log.info("Found %d conflicts (%d new vs %d total)",
             len(conflicts), len(new_mems), len(memories))
    return conflicts


def resolve_conflicts(conflicts: list[tuple[dict, dict, dict]]) -> dict:
    """Resolve conflicts using 3-tier strategy.

    Returns dict with:
        merged: list of {"before": [...], "after": str, "kept_id": str}
        consolidated: list of {"before": [...], "after": [...], "kept_id": str}
        deleted_ids: list of str
        created_ids: list of str (from split consolidation)
    """
    merged = []
    consolidated = []
    deleted_ids = []
    created_ids = []

    for mem_new, mem_existing, classification in conflicts:
        # Determine newer/older by timestamp
        ts_new = mem_new.get("createdAt", 0)
        ts_existing = mem_existing.get("createdAt", 0)
        if ts_new >= ts_existing:
            newer, older = mem_new, mem_existing
        else:
            newer, older = mem_existing, mem_new

        # Skip if either was already deleted in this run
        if newer["id"] in deleted_ids or older["id"] in deleted_ids:
            continue

        if classification["type"] == "state_change":
            archive_memory_backup(newer)
            archive_memory_backup(older)

            merged_text = merge_state_change(newer["text"], older["text"])

            if len(merged_text) < MERGE_MIN_LENGTH:
                log.warning("Merged text too short (%d chars), skipping",
                            len(merged_text))
                continue

            new_vector = embed_texts([merged_text])[0]
            update_memory_text(newer["id"], merged_text, new_vector)
            delete_memory(older["id"])
            deleted_ids.append(older["id"])

            merged.append({
                "before": [newer["text"], older["text"]],
                "after": merged_text,
                "kept_id": newer["id"],
            })
            log.info("Merged: '%s' (prev: '%s')",
                     newer["text"][:40], older["text"][:40])

        elif classification["type"] == "different_aspects":
            archive_memory_backup(mem_new)
            archive_memory_backup(mem_existing)

            result_texts = consolidate_aspects(
                mem_new["text"], mem_existing["text"]
            )

            if not result_texts or all(len(t) < MERGE_MIN_LENGTH for t in result_texts):
                log.warning("Consolidation produced empty/short result, skipping")
                continue

            if len(result_texts) == 1:
                cons_text = result_texts[0]
                new_vector = embed_texts([cons_text])[0]
                update_memory_text(newer["id"], cons_text, new_vector)
                delete_memory(older["id"])
                deleted_ids.append(older["id"])
            else:
                first_vector = embed_texts([result_texts[0]])[0]
                update_memory_text(newer["id"], result_texts[0], first_vector)
                for extra_text in result_texts[1:]:
                    extra_vector = embed_texts([extra_text])[0]
                    extra_id = add_memory(
                        text=extra_text,
                        vector=extra_vector,
                        importance=newer.get("importance", 0.5),
                        category=newer.get("category", "fact"),
                    )
                    created_ids.append(extra_id)
                delete_memory(older["id"])
                deleted_ids.append(older["id"])

            consolidated.append({
                "before": [mem_new["text"], mem_existing["text"]],
                "after": result_texts,
                "kept_id": newer["id"],
            })
            log.info("Consolidated 2 memories into %d", len(result_texts))

    return {
        "merged": merged,
        "consolidated": consolidated,
        "deleted_ids": deleted_ids,
        "created_ids": created_ids,
    }


def apply_importance_decay(memories: list[dict],
                           deleted_ids: set) -> dict:
    """Decay importance of old, unrecalled memories.

    Returns {"decayed": int, "soft_deleted": int, "soft_deleted_ids": [...]}.
    """
    now_ms = time.time() * 1000
    decayed = 0
    soft_deleted = 0
    soft_deleted_ids = []

    for mem in memories:
        if mem["id"] in deleted_ids:
            continue

        created_ms = mem.get("createdAt", now_ms)
        age_days = (now_ms - created_ms) / (1000 * 60 * 60 * 24)

        if age_days < 1:
            continue

        current = mem["importance"]
        decay = IMPORTANCE_DECAY_RATE * (age_days ** 0.5)
        new_importance = max(IMPORTANCE_FLOOR, current - decay)

        if new_importance < current:
            update_importance(mem["id"], new_importance)
            decayed += 1

            if new_importance <= SOFT_DELETE_THRESHOLD:
                log.info(
                    "Soft-deleting memory (importance=%.3f): %s",
                    new_importance, mem["text"][:60],
                )
                delete_memory(mem["id"])
                soft_deleted += 1
                soft_deleted_ids.append(mem["id"])

    log.info("Decay: %d updated, %d soft-deleted", decayed, soft_deleted)
    return {
        "decayed": decayed,
        "soft_deleted": soft_deleted,
        "soft_deleted_ids": soft_deleted_ids,
    }


def archive_episodes(processed_dates: list[str]) -> int:
    """Move processed episode files to archive directory."""
    if not processed_dates:
        return 0

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    archived = 0

    for date in processed_dates:
        src = os.path.join(EPISODE_DIR, f"{date}.md")
        dst = os.path.join(ARCHIVE_DIR, f"{date}.md")
        if os.path.exists(src):
            shutil.move(src, dst)
            archived += 1
            log.info("Archived %s", src)

    log.info("Archived %d episode files", archived)
    return archived


def run_rem(nrem_result: dict) -> dict:
    """Execute the REM phase."""
    log.info("=== REM Phase: Starting memory integration ===")

    # 1. Load all semantic memories
    memories = load_all_memories()
    log.info("Loaded %d semantic memories", len(memories))

    # 2. Get new memory IDs from NREM
    new_ids = set(nrem_result.get("created_ids", []))
    log.info("New memories from NREM: %d", len(new_ids))

    # 3. Find conflicts (O(N*M))
    if len(memories) >= 2 and new_ids:
        conflicts = find_conflicts(memories, new_ids)
    else:
        conflicts = []
        log.info("Skipping conflict detection (need new + existing memories)")

    # 4. Resolve conflicts (3-tier)
    resolution = resolve_conflicts(conflicts)
    all_deleted = set(resolution["deleted_ids"])

    # 5. Apply importance decay
    decay_result = apply_importance_decay(memories, all_deleted)

    # 6. Archive processed episodes
    processed_dates = nrem_result.get("processed_dates", [])
    archived = archive_episodes(processed_dates)

    summary = {
        "total_memories": len(memories),
        "conflicts_found": len(conflicts),
        "merged": len(resolution["merged"]),
        "consolidated": len(resolution["consolidated"]),
        "deleted": len(resolution["deleted_ids"]),
        "split_created": len(resolution["created_ids"]),
        "decayed": decay_result["decayed"],
        "soft_deleted": decay_result["soft_deleted"],
        "archived": archived,
        "merge_details": resolution["merged"],
        "consolidation_details": resolution["consolidated"],
    }
    log.info("REM complete: conflicts=%d, merged=%d, consolidated=%d, deleted=%d",
             len(conflicts), len(resolution["merged"]),
             len(resolution["consolidated"]), len(resolution["deleted_ids"]))
    return summary
