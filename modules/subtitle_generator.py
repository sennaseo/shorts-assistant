from __future__ import annotations

from collections import Counter
from pathlib import Path

from .file_utils import write_text


STOPWORDS = {"이", "그", "저", "것", "수", "때", "좀", "더", "한", "및", "그리고", "하지만", "정도", "기준"}


def split_subtitle_line(text: str, max_len: int = 16) -> list[str]:
    text = text.strip()
    if len(text) <= max_len:
        return [text] if text else []
    words = text.split()
    if len(words) == 1:
        return [text[:max_len], text[max_len:]]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_capcut_subtitles(typecast_lines: list[str]) -> dict[str, object]:
    blocks: list[str] = []
    for line in typecast_lines:
        rows = split_subtitle_line(line)
        for index in range(0, len(rows), 2):
            blocks.append("\n".join(rows[index : index + 2]))

    tokens = []
    for line in typecast_lines:
        for token in line.replace(",", " ").replace(".", " ").split():
            cleaned = token.strip("!?~.,")
            if len(cleaned) >= 2 and cleaned not in STOPWORDS:
                tokens.append(cleaned)
    keywords = [word for word, _ in Counter(tokens).most_common(10)]
    return {"subtitle_text": "\n\n".join(blocks), "keywords": keywords}


def save_capcut_subtitles(typecast_lines: list[str], output_dir: str | Path) -> dict[str, Path | list[str]]:
    result = generate_capcut_subtitles(typecast_lines)
    path = write_text(Path(output_dir) / "capcut_subtitles.txt", str(result["subtitle_text"]))
    return {"capcut_subtitles": path, "keywords": result["keywords"]}
