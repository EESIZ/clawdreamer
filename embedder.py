"""Embedding generator using OpenAI API."""

import json
import logging
import urllib.request

from config import OPENAI_API_KEY, EMBEDDING_MODEL

log = logging.getLogger("dreamer.embedder")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts via OpenAI API.

    Returns list of float vectors, one per input text.
    """
    if not texts:
        return []

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

    # Sort by index to maintain order
    embeddings = sorted(data["data"], key=lambda x: x["index"])
    return [e["embedding"] for e in embeddings]


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
