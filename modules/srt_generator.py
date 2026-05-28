from __future__ import annotations

from pathlib import Path

from .file_utils import write_text


def _format_time(seconds: float) -> str:
    millis = int(round((seconds - int(seconds)) * 1000))
    whole = int(seconds)
    hrs = whole // 3600
    mins = (whole % 3600) // 60
    secs = whole % 60
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"


def get_audio_duration_seconds(audio_path: str | Path | None) -> float | None:
    if not audio_path:
        return None
    path = Path(audio_path)
    if not path.exists():
        return None
    try:
        from mutagen import File

        audio = File(path)
        if audio and audio.info and getattr(audio.info, "length", None):
            return float(audio.info.length)
    except Exception:
        return None
    return None


def generate_srt(lines: list[str], target_length: int = 40, audio_path: str | Path | None = None) -> str:
    usable_lines = [line.strip() for line in lines if line.strip()]
    if not usable_lines:
        usable_lines = ["자막을 입력하세요."]
    duration = get_audio_duration_seconds(audio_path) or max(10, int(target_length or 40))
    per_line = duration / len(usable_lines)
    entries = []
    cursor = 0.0
    for index, line in enumerate(usable_lines, start=1):
        start = cursor
        end = min(duration, cursor + per_line)
        entries.append(f"{index}\n{_format_time(start)} --> {_format_time(end)}\n{line}")
        cursor = end
    return "\n\n".join(entries) + "\n"


def save_srt(lines: list[str], output_dir: str | Path, target_length: int = 40, audio_path: str | Path | None = None) -> Path:
    return write_text(Path(output_dir) / "subtitles.srt", generate_srt(lines, target_length, audio_path))
