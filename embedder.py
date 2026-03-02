"""Embedding generator with multiple provider support.

Providers:
  - openai: OpenAI API (text-embedding-3-small, 1536-dim) [default]
  - ollama: Local Ollama server (nomic-embed-text, etc.)
  - sentence-transformers: Local HuggingFace models (all-MiniLM-L6-v2, etc.)
"""

import json
import logging
import urllib.request

from config import (
    OPENAI_API_KEY, EMBEDDING_MODEL, EMBEDDING_PROVIDER,
    OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL,
    ST_MODEL_NAME,
)

log = logging.getLogger("dreamer.embedder")

# Lazy-loaded sentence-transformers model
_st_model = None


def _embed_openai(texts: list[str]) -> list[list[float]]:
    body = json.dumps({
        "model": EMBEDDING_MODEL,
        "input": texts,
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    embeddings = sorted(data["data"], key=lambda x: x["index"])
    return [e["embedding"] for e in embeddings]


def _embed_ollama(texts: list[str]) -> list[list[float]]:
    results = []
    for text in texts:
        body = json.dumps({
            "model": OLLAMA_EMBEDDING_MODEL,
            "prompt": text,
        }).encode()

        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            data=body,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        results.append(data["embedding"])
    return results


def _embed_sentence_transformers(texts: list[str]) -> list[list[float]]:
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
        log.info("Loading sentence-transformers model: %s", ST_MODEL_NAME)
        _st_model = SentenceTransformer(ST_MODEL_NAME)

    embeddings = _st_model.encode(texts, show_progress_bar=False)
    return [e.tolist() for e in embeddings]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Provider is determined by DREAMER_EMBEDDING_PROVIDER env var.
    """
    if not texts:
        return []

    if EMBEDDING_PROVIDER == "ollama":
        return _embed_ollama(texts)
    elif EMBEDDING_PROVIDER == "sentence-transformers":
        return _embed_sentence_transformers(texts)
    else:
        return _embed_openai(texts)


def embed_single(text: str) -> list[float]:
    """Generate embedding for a single text."""
    return embed_texts([text])[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
