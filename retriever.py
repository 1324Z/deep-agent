"""Lightweight local retrieval helpers for knowledge-grounded generation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_SUFFIXES = {".md", ".txt", ".json", ".csv"}
_CACHE_KEY: tuple[tuple[str, float], ...] | None = None
_CACHE_CHUNKS: list["KnowledgeChunk"] = []
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", "knowledge")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
RAG_MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "4000"))


@dataclass
class KnowledgeChunk:
    source: str
    chunk_id: int
    content: str


def _knowledge_root() -> Path:
    return Path(KNOWLEDGE_DIR).resolve()


def _iter_knowledge_files() -> list[Path]:
    root = _knowledge_root()
    if not root.exists() or not root.is_dir():
        return []

    files: list[Path] = []
    for path in root.rglob("*"):
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_SUFFIXES
            and path.name.lower() != "readme.md"
        ):
            files.append(path)
    return sorted(files)


def _build_cache_key(files: list[Path]) -> tuple[tuple[str, float], ...]:
    return tuple((str(path.resolve()), path.stat().st_mtime) for path in files)


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    if chunk_size <= 0:
        return [cleaned]

    overlap = max(0, min(chunk_overlap, max(chunk_size - 1, 0)))
    step = max(chunk_size - overlap, 1)

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        chunk = cleaned[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(cleaned):
            break
        start += step
    return chunks


def _build_chunks() -> list[KnowledgeChunk]:
    files = _iter_knowledge_files()
    chunks: list[KnowledgeChunk] = []

    for path in files:
        text = _read_file(path)
        rel_path = path.resolve().relative_to(_knowledge_root()).as_posix()
        for index, chunk in enumerate(_chunk_text(text, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP), start=1):
            chunks.append(
                KnowledgeChunk(
                    source=rel_path,
                    chunk_id=index,
                    content=chunk,
                )
            )
    return chunks


def _get_chunks() -> list[KnowledgeChunk]:
    global _CACHE_CHUNKS, _CACHE_KEY

    files = _iter_knowledge_files()
    cache_key = _build_cache_key(files)
    if _CACHE_KEY == cache_key:
        return _CACHE_CHUNKS

    _CACHE_CHUNKS = _build_chunks()
    _CACHE_KEY = cache_key
    return _CACHE_CHUNKS


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens: list[str] = re.findall(r"[a-z0-9_]{2,}", lowered)

    cjk_spans = re.findall(r"[\u4e00-\u9fff]{1,}", text)
    for span in cjk_spans:
        if len(span) == 1:
            tokens.append(span)
            continue

        tokens.append(span)
        for i in range(len(span)):
            tokens.append(span[i])
        for i in range(len(span) - 1):
            tokens.append(span[i : i + 2])

    return [token for token in tokens if token.strip()]


def _score_chunk(query: str, query_tokens: list[str], chunk: KnowledgeChunk) -> float:
    content = chunk.content
    lowered = content.lower()
    score = 0.0

    if query and query in content:
        score += 12.0

    seen: set[str] = set()
    for token in query_tokens:
        if token in seen:
            continue
        seen.add(token)

        if len(token) >= 2 and token in lowered:
            score += min(lowered.count(token), 3) * 3.0
        elif token in content:
            score += min(content.count(token), 3) * 2.0

    if query_tokens:
        score += min(len(set(query_tokens) & set(_tokenize(content))), 8) * 1.2

    return score


def retrieve_knowledge(query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    chunks = _get_chunks()
    if not chunks:
        return []

    query_tokens = _tokenize(cleaned_query)
    scored: list[tuple[float, KnowledgeChunk]] = []
    for chunk in chunks:
        score = _score_chunk(cleaned_query, query_tokens, chunk)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    limit = max(1, top_k or RAG_TOP_K)

    results: list[dict[str, Any]] = []
    for score, chunk in scored[:limit]:
        results.append(
            {
                "source": chunk.source,
                "chunk_id": chunk.chunk_id,
                "score": round(score, 3),
                "content": chunk.content,
            }
        )
    return results


def format_relevant_contents(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""

    blocks: list[str] = []
    total_chars = 0
    for index, item in enumerate(results, start=1):
        block = (
            f"[知识片段 {index}] 来源: {item['source']}#chunk-{item['chunk_id']}\n"
            f"{item['content'].strip()}"
        ).strip()
        if total_chars and total_chars + len(block) > RAG_MAX_CONTEXT_CHARS:
            break
        blocks.append(block)
        total_chars += len(block)

    return "\n\n".join(blocks)


def format_references(results: list[dict[str, Any]]) -> str:
    if not results:
        return "[]"

    references = [
        {
            "source": item["source"],
            "chunk_id": item["chunk_id"],
            "score": item["score"],
        }
        for item in results
    ]
    return json.dumps(references, ensure_ascii=False, indent=2)
