from __future__ import annotations

import asyncio
from pathlib import Path


DEFAULT_VOICE = "ko-KR-SunHiNeural"


async def _save_tts(text: str, output_path: Path, voice: str, rate: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(str(output_path))


def generate_edge_tts(
    text: str,
    output_dir: str | Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> dict[str, object]:
    output_path = Path(output_dir) / "edge_tts_test.mp3"
    clean_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not clean_text:
        return {"path": None, "success": False, "error": "TTS로 변환할 문장이 없습니다."}
    try:
        asyncio.run(_save_tts(clean_text, output_path, voice, rate))
        return {"path": output_path, "success": True, "error": ""}
    except Exception as exc:
        return {"path": None, "success": False, "error": f"Edge TTS 생성 실패: {exc}"}
