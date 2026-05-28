from __future__ import annotations

import re
from pathlib import Path

from .file_utils import write_text


SENTENCE_ENDINGS = re.compile(r"(?<=[.!?。！？요다까봐어야죠네음임야])\s+|\n+")


def _split_long_sentence(sentence: str, min_len: int = 20, max_len: int = 35) -> list[str]:
    sentence = sentence.strip()
    if len(sentence) <= max_len:
        return [sentence] if sentence else []

    chunks: list[str] = []
    remaining = sentence
    break_chars = [",", "，", "、", " ", "고 ", "데 ", "서 ", "면 "]
    while len(remaining) > max_len:
        window = remaining[: max_len + 1]
        break_at = -1
        for char in break_chars:
            pos = window.rfind(char)
            if pos >= min_len:
                break_at = pos + len(char)
                break
        if break_at < min_len:
            break_at = max_len
        chunks.append(remaining[:break_at].strip(" ,，、"))
        remaining = remaining[break_at:].strip()
    if remaining:
        chunks.append(remaining)
    return [chunk for chunk in chunks if chunk]


def format_for_typecast(script: str) -> tuple[list[str], list[str]]:
    raw_sentences = [part.strip() for part in SENTENCE_ENDINGS.split(script) if part.strip()]
    lines: list[str] = []
    for sentence in raw_sentences:
        lines.extend(_split_long_sentence(sentence))
    numbered = [f"{index}. {line}" for index, line in enumerate(lines, start=1)]
    return lines, numbered


def save_typecast_files(script: str, output_dir: str | Path) -> dict[str, Path]:
    lines, numbered = format_for_typecast(script)
    output = Path(output_dir)
    return {
        "typecast_lines": write_text(output / "typecast_lines.txt", "\n".join(lines)),
        "typecast_lines_numbered": write_text(output / "typecast_lines_numbered.txt", "\n".join(numbered)),
    }
