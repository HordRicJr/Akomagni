"""Text chunking for RAG ingestion."""

from __future__ import annotations


def chunk_text(text: str, *, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into overlapping chunks sized for retrieval."""
    cleaned = text.strip()
    if not cleaned:
        return []

    if len(cleaned) <= chunk_size:
        return [cleaned]

    paragraphs = [part.strip() for part in cleaned.split("\n\n") if part.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) <= chunk_size:
            buffer = candidate
            continue
        if buffer:
            chunks.extend(_window(buffer, chunk_size=chunk_size, overlap=overlap))
        buffer = paragraph

    if buffer:
        if len(buffer) <= chunk_size:
            chunks.append(buffer)
        else:
            chunks.extend(_window(buffer, chunk_size=chunk_size, overlap=overlap))

    return [chunk for chunk in chunks if chunk.strip()]


def _window(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    step = max(chunk_size - overlap, 1)
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + chunk_size].strip())
        start += step
    return [part for part in parts if part]
