from __future__ import annotations

import asyncio
import time
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
    last_error = ""
    # ponytail: 재시도 1회 고정 (일시적 네트워크 오류 대응). 더 필요하면 백오프 추가
    for attempt in range(2):
        try:
            asyncio.run(_save_tts(clean_text, output_path, voice, rate))
            if output_path.exists() and output_path.stat().st_size > 0:
                return {"path": output_path, "success": True, "error": ""}
            last_error = "생성된 파일이 비어 있습니다 (0바이트)."
        except Exception as exc:
            last_error = f"Edge TTS 생성 실패: {exc}"
        output_path.unlink(missing_ok=True)
        if attempt == 0:
            time.sleep(2.5)
    return {"path": None, "success": False, "error": last_error}
