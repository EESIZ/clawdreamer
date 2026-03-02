"""LLM calls for summarization and classification."""

import json
import logging
import urllib.request

from config import (
    LLM_PROVIDER,
    MINIMAX_API_KEY,
    MINIMAX_BASE_URL,
    OLLAMA_BASE_URL,
    OLLAMA_LLM_MODEL,
    OPENAI_API_KEY,
)

log = logging.getLogger("dreamer.llm")


def _call_openai(messages: list[dict], max_tokens: int = 1024) -> str:
    """Call OpenAI chat completions API."""
    body = json.dumps({
        "model": "gpt-4.1-nano",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    return data["choices"][0]["message"]["content"]


def _call_minimax(messages: list[dict], max_tokens: int = 1024) -> str:
    """Call MiniMax API (Anthropic-compatible)."""
    system = ""
    filtered = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            filtered.append(m)

    payload = {
        "model": "MiniMax-M2.5",
        "messages": filtered,
        "max_tokens": max_tokens,
    }
    if system:
        payload["system"] = system

    body = json.dumps(payload).encode()

    req = urllib.request.Request(
        f"{MINIMAX_BASE_URL}/v1/messages",
        data=body,
        headers={
            "x-api-key": MINIMAX_API_KEY,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    # MiniMax M2.5 returns thinking + text blocks; extract the text block
    for block in data["content"]:
        if block.get("type") == "text":
            return block["text"]
    return data["content"][-1].get("text", "")


def _call_ollama_llm(messages: list[dict], max_tokens: int = 1024) -> str:
    """Call Ollama OpenAI-compatible chat completions API."""
    body = json.dumps({
        "model": OLLAMA_LLM_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.3,
        },
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())

    return data["choices"][0]["message"]["content"]


def llm_call(prompt: str, system: str = "", max_tokens: int = 1024) -> str:
    """Call LLM with a prompt. Uses configured provider."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    if LLM_PROVIDER == "minimax":
        return _call_minimax(messages, max_tokens)
    elif LLM_PROVIDER == "ollama":
        return _call_ollama_llm(messages, max_tokens)
    return _call_openai(messages, max_tokens)


def summarize_cluster(chunks: list[str]) -> dict:
    """Legacy wrapper -- calls analyze_cluster for backwards compat."""
    result = analyze_cluster(chunks, [])
    return {
        "text": result["text"],
        "importance": result["importance"],
        "category": result["category"],
    }


def analyze_cluster(chunks: list[str],
                    existing_files: list[str]) -> dict:
    """Analyze episode chunks and produce a smart memory.

    Decides whether to:
    1. Point to an existing doc (if content matches)
    2. Create a new doc (if procedural/detailed and no existing doc)
    3. Store as memory only (simple facts)

    Args:
        chunks: related episode text chunks
        existing_files: list of existing workspace files for reference

    Returns dict with keys:
        text: memory text (core facts + optional file pointer)
        importance: 0.0-1.0
        category: fact|decision|preference|procedure|pattern
        new_doc: None or {"slug": str, "title": str, "content": str}
    """
    joined = "\n---\n".join(chunks)
    files_list = "\n".join(f"- {f}" for f in existing_files) if existing_files else "(none)"

    system = """You are a memory consolidation system for an AI assistant.
Your job: compress episodic memories into useful semantic memories.

CRITICAL RULES:
1. Memory text must contain KEY FACTS (names, numbers, settings, commands).
   BAD: "It's important to understand the specs for effective model operations"
   GOOD: "Installed Qwen2.5:3B on Ollama. Registered as qwen-local. Lightweight model under 4GB RAM."

2. TEMPORAL STATE: If the data describes a state that changes over time
   (positions, settings, prices, status), keep ONLY the latest state.
   BAD: storing both old and new states from different times
   GOOD: store only the most recent state with date

3. If the content matches an existing file, set existing_ref to that filepath.
   The memory itself should still have enough info to answer most questions.

4. If it's a detailed procedure/method NOT covered by existing files,
   set new_doc with slug/title/content to create a new doc in docs/.
   One method = one document. Keep docs focused.

5. If it's a simple fact or event, no file pointer needed.

6. SECURITY: Never include API keys, secrets, passwords, or tokens in memory text.

7. Output ONLY valid JSON, no markdown wrapping."""

    prompt = f"""The following are related episodic memories:

{joined}

Existing workspace files:
{files_list}

Output in JSON format:
{{
  "text": "memory with key facts (1-3 sentences, be specific)",
  "importance": 0.8,
  "category": "fact",
  "existing_ref": null,
  "new_doc": null
}}

existing_ref: set to a filepath from the list above if the content matches.
new_doc: only when detailed procedures not covered by existing files.
Example: "new_doc": {{"slug": "api-setup-guide", "title": "API Setup Guide", "content": "# API Setup\\n\\n..."}}

Most of the time, existing_ref or null is sufficient."""

    raw = llm_call(prompt, system=system, max_tokens=512)

    # Parse JSON from response
    result = _parse_llm_json(raw)
    if result is None:
        return None  # Signal to caller: skip this cluster

    # Normalize: build final text with pointer if applicable
    text = result.get("text", "")
    if not text or len(text) < 10:
        log.warning("LLM returned empty/short text, skipping")
        return None

    ref = result.get("existing_ref")
    new_doc = result.get("new_doc")

    if ref:
        text = f"{text} (ref: {ref})"
    elif new_doc and new_doc.get("slug"):
        doc_path = f"docs/{new_doc['slug']}.md"
        text = f"{text} (ref: {doc_path})"

    return {
        "text": text,
        "importance": result.get("importance", 0.5),
        "category": result.get("category", "other"),
        "new_doc": new_doc,
    }


def _parse_llm_json(raw: str) -> dict | None:
    """Robustly parse JSON from LLM output.

    Handles: markdown wrapping, trailing commas, truncated output.
    Returns None if parsing fails completely.
    """
    cleaned = raw.strip()

    # Strip markdown code block wrapping
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if "```" in cleaned:
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object from surrounding text
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Try fixing truncated JSON (missing closing braces)
    if start != -1 and end <= start:
        attempt = cleaned[start:] + "}"
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            pass

    log.warning("Failed to parse LLM JSON after all attempts: %s", raw[:200])
    return None


def classify_relationship(mem_a: str, mem_b: str) -> dict:
    """Classify the relationship between two memories.

    Returns dict with:
        type: "state_change" | "different_aspects" | "unrelated"
        explanation: brief reason
    """
    prompt = f"""Classify the relationship between these two memories.

Memory A: {mem_a}
Memory B: {mem_b}

Classification criteria:
1. "state_change": Same subject whose state changed over time
   e.g., "model set to gemini" vs "model changed to claude"
   e.g., "closed all positions" vs "holding 2 buy contracts"

2. "different_aspects": Different aspects of the same subject
   e.g., "API token caching setup" vs "API response field structure"
   e.g., "cron job 5-min interval" vs "cron job error handling"

3. "unrelated": High similarity but actually unrelated memories

Output JSON only:
{{"type": "state_change", "explanation": "reason"}}"""

    raw = llm_call(prompt, max_tokens=100)
    result = _parse_llm_json(raw)
    if result is None or "type" not in result:
        return {"type": "unrelated", "explanation": "classification failed"}
    if result["type"] not in ("state_change", "different_aspects", "unrelated"):
        return {"type": "unrelated", "explanation": "classification failed"}
    return result


def merge_state_change(newer_text: str, older_text: str) -> str:
    """Merge two state-change memories.

    Keeps newer state as main text, appends "(prev: ...)" suffix.
    Deterministic (no LLM call) to minimize failure risk.
    """
    old_summary = older_text[:60].rstrip(".")
    if len(older_text) > 60:
        old_summary += "..."
    return f"{newer_text} (prev: {old_summary})"


def consolidate_aspects(mem_a: str, mem_b: str) -> list[str]:
    """Consolidate two memories about different aspects of the same topic.

    Returns a list of 1-2 consolidated memory texts.
    If the result exceeds 300 chars, it's split into focused sub-memories.
    """
    prompt = f"""Consolidate these two memories into one comprehensive memory.
Both memories' key information must be preserved.

Memory A: {mem_a}
Memory B: {mem_b}

Rules:
1. Must include key facts (names, numbers, settings, commands)
2. If over 300 characters, split into 2 focused memories
3. Each memory must be independently understandable

Output JSON only:
{{"texts": ["consolidated memory text"]}}
Or if split:
{{"texts": ["memory 1", "memory 2"]}}"""

    raw = llm_call(prompt, max_tokens=400)
    result = _parse_llm_json(raw)
    if result is None or "texts" not in result:
        return [f"{mem_a} / {mem_b}"]
    texts = result["texts"]
    if not texts:
        return [f"{mem_a} / {mem_b}"]
    return texts


def detect_contradiction(mem_a: str, mem_b: str) -> bool:
    """Legacy wrapper. Returns True if memories are related (state_change or different_aspects)."""
    result = classify_relationship(mem_a, mem_b)
    return result["type"] != "unrelated"
