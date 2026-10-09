#!/usr/bin/env python3
"""Pure helpers for Silver extraction quality and section-aware chunking.

Dependency-free (stdlib only) so they can be unit-tested without pymupdf/trafilatura.
`build_silver.py` is the only caller in the pipeline.
"""
import re

# A heading: "Article 5", "§ 164.312", "AC-2", "1." / "1.2. Heading", "Section 4".
HEADING = re.compile(
    r"^\s*(?:"
    r"(?:Article|Art\.|Section|Sec\.|Rule|Chapter|Part|§)\s*\d+"
    r"|[A-Z]{2,5}-\d+"
    r"|\d+(?:\.\d+)*\.\s+\S"
    r")"
)

_MIN_WORDS = 50
_TABLE_SEP = re.compile(r"\S {2,}\S")
_ALPHA = re.compile(r"[A-Za-z]")


def chunk_window(text, size=512, overlap=50, min_words=_MIN_WORDS):
    """Fixed word-window chunker: ~512 tokens (size*0.75 words) with overlap. Unchanged default."""
    words = text.split()
    if not words:
        return []
    wsize = int(size * 0.75)
    woverlap = int(overlap * 0.75)
    wstep = wsize - woverlap
    chunks = []
    for i in range(0, len(words), wstep):
        c = " ".join(words[i:i + wsize])
        if len(c.split()) < min_words:
            continue
        chunks.append(c)
        if i + wsize >= len(words):
            break
    return chunks


def is_heading(line):
    return len(line.strip()) < 120 and bool(HEADING.match(line))


def split_sections(text):
    """Split text at heading lines into (heading, body) sections; heading may be None."""
    sections, head, buf = [], None, []
    for line in text.splitlines():
        if is_heading(line):
            if buf or head is not None:
                sections.append((head, "\n".join(buf)))
            head, buf = line.strip(), [line]
        else:
            buf.append(line)
    if buf or head is not None:
        sections.append((head, "\n".join(buf)))
    return sections


def chunk_sections(text, size=512, overlap=50):
    """Section-aware chunks, keeping each section intact (or windowing it when too long).

    Returns None when fewer than 3 headings are found, so the caller falls back to the
    fixed-window chunker — the default behavior is unchanged.
    """
    sections = split_sections(text)
    if sum(1 for h, _ in sections if h) < 3:
        return None
    wsize = int(size * 0.75)
    chunks = []
    for _, body in sections:
        body = body.strip()
        if not body:
            continue
        if len(body.split()) <= wsize:
            chunks.append(body)
        else:
            chunks.extend(chunk_window(body, size, overlap, min_words=1))
    return chunks


def quality_flags(text, kind):
    """Heuristic extraction-quality flags. Annotates documents; never drops them."""
    flags = []
    if len(text) < 500:
        flags.append("short")
    lines = [l for l in text.splitlines() if l.strip()]
    if lines:
        if sum(1 for l in lines if _TABLE_SEP.search(l)) / len(lines) > 0.25:
            flags.append("table_heavy")
        if sum(1 for l in lines if len(l.strip()) < 3) / len(lines) > 0.4:
            flags.append("fragmented")
    if text and len(_ALPHA.findall(text)) / len(text) < 0.55:
        flags.append("low_alpha")
    if "\ufffd" in text or text.count("(cid:") > 5:
        flags.append("garbled")
    return flags
