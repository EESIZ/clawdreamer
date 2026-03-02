"""NREM Phase: Episode -> Semantic memory conversion.

Like NREM sleep:
1. Load episodic memories (md files = hippocampus)
2. Chunk into semantic units
3. Cluster similar chunks (sharp-wave ripple replay)
4. Analyze each cluster: extract key facts + link to existing docs/skills
5. If new procedure found, create reference doc in docs/
6. Deduplicate against existing semantic memories
7. Store smart memories in LanceDB (neocortex transfer)
"""

import glob
import logging
import os
import re

from config import (
    DOCS_DIR,
    EPISODE_DIR,
    CHUNK_MIN_LENGTH,
    CLUSTER_SIMILARITY,
    DEDUP_SIMILARITY,
    MAX_EPISODES_PER_RUN,
    MAX_NEW_MEMORIES,
    SKILLS_DIR,
    WORKSPACE_DIR,
)
from embedder import embed_texts, cosine_similarity
from lancedb_store import load_all_memories, add_memory
from llm import analyze_cluster

log = logging.getLogger("dreamer.nrem")


def load_episodes() -> list[dict]:
    """Load episode markdown files, sorted by date (oldest first).

    Returns list of {"path": str, "date": str, "content": str}.
    """
    pattern = os.path.join(EPISODE_DIR, "*.md")
    files = sorted(glob.glob(pattern))

    # Only include date-named files (YYYY-MM-DD.md)
    date_re = re.compile(r"\d{4}-\d{2}-\d{2}\.md$")
    files = [f for f in files if date_re.search(f)]

    episodes = []
    for path in files[:MAX_EPISODES_PER_RUN]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        date = os.path.basename(path).replace(".md", "")
        episodes.append({"path": path, "date": date, "content": content})

    log.info("Loaded %d episode files", len(episodes))
    return episodes


def scan_workspace_files() -> list[str]:
    """Scan workspace for existing docs, skills, and reference files.

    Returns list of relative file paths with optional descriptions.
    Used to give the LLM context about existing documentation.
    """
    files = []

    # Top-level .md files
    for f in glob.glob(os.path.join(WORKSPACE_DIR, "*.md")):
        name = os.path.basename(f)
        files.append(name)

    # Skills with their description from SKILL.md frontmatter
    for skill_md in glob.glob(os.path.join(SKILLS_DIR, "*/SKILL.md")):
        rel = os.path.relpath(skill_md, WORKSPACE_DIR)
        desc = ""
        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()[:60]
                        break
        except OSError:
            pass
        entry = f"{rel} -- {desc}" if desc else rel
        files.append(entry)

    # Docs
    for doc in glob.glob(os.path.join(DOCS_DIR, "*.md")):
        rel = os.path.relpath(doc, WORKSPACE_DIR)
        files.append(rel)

    log.info("Scanned %d workspace files for reference", len(files))
    return sorted(files)


def write_reference_doc(new_doc: dict) -> str:
    """Write a new reference document to docs/.

    Args:
        new_doc: {"slug": str, "title": str, "content": str}

    Returns the relative path of the created file.
    """
    os.makedirs(DOCS_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9-]", "", new_doc["slug"].lower().replace(" ", "-"))
    filename = f"{slug}.md"
    filepath = os.path.join(DOCS_DIR, filename)

    # If file already exists, append new content
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            existing = f.read()
        content = existing.rstrip() + "\n\n---\n\n" + new_doc["content"]
        log.info("Appending to existing doc: %s", filename)
    else:
        content = new_doc["content"]
        log.info("Creating new doc: %s", filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return f"docs/{filename}"


def chunk_episode(content: str) -> list[str]:
    """Split episode content into semantic chunks.

    Strategy: split by markdown headers (##) and blank-line-separated
    paragraphs, then filter out tiny fragments.
    """
    sections = re.split(r"\n(?=## )", content)

    chunks = []
    for section in sections:
        paragraphs = re.split(r"\n\n+", section.strip())
        for para in paragraphs:
            text = para.strip()
            if len(text) >= CHUNK_MIN_LENGTH:
                chunks.append(text)

    return chunks


def cluster_chunks(chunks: list[str],
                   vectors: list[list[float]]) -> list[list[int]]:
    """Group similar chunks into clusters based on embedding similarity.

    Returns list of clusters, where each cluster is a list of chunk indices.
    Uses simple greedy agglomerative approach.
    """
    n = len(chunks)
    assigned = [False] * n
    clusters = []

    for i in range(n):
        if assigned[i]:
            continue
        cluster = [i]
        assigned[i] = True
        for j in range(i + 1, n):
            if assigned[j]:
                continue
            sim = cosine_similarity(vectors[i], vectors[j])
            if sim >= CLUSTER_SIMILARITY:
                cluster.append(j)
                assigned[j] = True
        clusters.append(cluster)

    multi = [c for c in clusters if len(c) > 1]
    log.info("Formed %d clusters (%d multi-chunk, %d singletons)",
             len(clusters), len(multi), len(clusters) - len(multi))

    return clusters


def is_duplicate(vector: list[float],
                 existing: list[dict]) -> bool:
    """Check if a vector is too similar to any existing memory."""
    for mem in existing:
        if not mem.get("vector"):
            continue
        sim = cosine_similarity(vector, mem["vector"])
        if sim >= DEDUP_SIMILARITY:
            log.debug("Duplicate found (sim=%.3f): %s", sim, mem["text"][:60])
            return True
    return False


def run_nrem() -> dict:
    """Execute the NREM phase.

    Returns summary dict with counts of processed/created/skipped.
    """
    log.info("=== NREM Phase: Starting episodic consolidation ===")

    # 1. Load episodes
    episodes = load_episodes()
    if not episodes:
        log.info("No episodes to process")
        return {"episodes": 0, "chunks": 0, "clusters": 0,
                "created": 0, "skipped_dup": 0, "docs_created": 0,
                "created_ids": [], "processed_dates": []}

    # 2. Scan workspace for existing reference files
    workspace_files = scan_workspace_files()

    # 3. Chunk all episodes
    all_chunks = []
    for ep in episodes:
        chunks = chunk_episode(ep["content"])
        for chunk in chunks:
            all_chunks.append({"text": chunk, "date": ep["date"]})
    log.info("Split into %d chunks from %d episodes",
             len(all_chunks), len(episodes))

    if not all_chunks:
        return {"episodes": len(episodes), "chunks": 0, "clusters": 0,
                "created": 0, "skipped_dup": 0, "docs_created": 0,
                "created_ids": [], "processed_dates": []}

    # 4. Embed all chunks (batch)
    chunk_texts = [c["text"] for c in all_chunks]
    log.info("Generating embeddings for %d chunks...", len(chunk_texts))
    vectors = embed_texts(chunk_texts)

    # 5. Cluster similar chunks
    clusters = cluster_chunks(chunk_texts, vectors)

    # 6. Load existing memories for dedup
    existing = load_all_memories()
    log.info("Loaded %d existing memories for dedup check", len(existing))

    # 7. For each cluster, analyze and store
    created = 0
    skipped_dup = 0
    docs_created = 0
    processed_files = set()
    created_ids = []

    for cluster_indices in clusters:
        if created >= MAX_NEW_MEMORIES:
            log.info("Reached max new memories (%d), stopping", MAX_NEW_MEMORIES)
            break

        cluster_texts = [chunk_texts[i] for i in cluster_indices]

        # Skip very small singleton clusters (< 50 chars)
        if len(cluster_indices) == 1 and len(cluster_texts[0]) < 50:
            continue

        # Use centroid vector for dedup check
        centroid = vectors[cluster_indices[0]]

        if is_duplicate(centroid, existing):
            skipped_dup += 1
            continue

        # Analyze cluster via LLM (with workspace file context)
        result = analyze_cluster(cluster_texts, workspace_files)

        if result is None:
            log.warning("Skipping cluster (LLM parse failure)")
            continue

        # Create reference doc if needed
        new_doc = result.get("new_doc")
        if new_doc and new_doc.get("slug") and new_doc.get("content"):
            doc_path = write_reference_doc(new_doc)
            docs_created += 1
            workspace_files.append(doc_path)

        # Generate embedding for the new semantic memory
        new_vector = embed_texts([result["text"]])[0]

        # Final dedup check on the summarized text
        if is_duplicate(new_vector, existing):
            skipped_dup += 1
            continue

        # Store in LanceDB
        mem_id = add_memory(
            text=result["text"],
            vector=new_vector,
            importance=result.get("importance", 0.5),
            category=result.get("category", "other"),
        )

        created_ids.append(mem_id)

        existing.append({
            "id": mem_id,
            "text": result["text"],
            "vector": new_vector,
            "importance": result.get("importance", 0.5),
        })

        created += 1
        for i in cluster_indices:
            processed_files.add(all_chunks[i]["date"])

    summary = {
        "episodes": len(episodes),
        "chunks": len(all_chunks),
        "clusters": len(clusters),
        "created": created,
        "skipped_dup": skipped_dup,
        "docs_created": docs_created,
        "processed_dates": sorted(processed_files),
        "created_ids": created_ids,
    }
    log.info("NREM complete: %s", summary)
    return summary
