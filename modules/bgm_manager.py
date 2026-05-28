from __future__ import annotations

from pathlib import Path

from .file_utils import copy_file


BGM_RULES = {
    "빠른 리뷰형": ["fast", "upbeat", "review"],
    "감성 자취템형": ["cozy", "soft", "daily"],
    "직장인 현실 공감형": ["calm", "minimal", "office"],
}


def scan_bgm(asset_bgm_dir: str | Path) -> list[Path]:
    root = Path(asset_bgm_dir)
    if not root.exists():
        return []
    return sorted([*root.glob("*.mp3"), *root.glob("*.wav"), *root.glob("*.m4a")])


def choose_bgm(asset_bgm_dir: str | Path, tone: str = "", mood: str = "") -> Path | None:
    files = scan_bgm(asset_bgm_dir)
    if not files:
        return None
    keywords = [mood.lower()] if mood else []
    keywords.extend(BGM_RULES.get(tone, []))
    for keyword in [k for k in keywords if k]:
        for file in files:
            if keyword in file.name.lower():
                return file
    return files[0]


def copy_selected_bgm(asset_bgm_dir: str | Path, output_dir: str | Path, tone: str = "", mood: str = "") -> dict[str, object]:
    selected = choose_bgm(asset_bgm_dir, tone, mood)
    if not selected:
        return {"path": None, "source": None, "message": "assets/bgm 폴더에 BGM 파일이 없어 건너뜁니다."}
    destination = Path(output_dir) / "selected_bgm.mp3"
    copied = copy_file(selected, destination)
    return {"path": copied, "source": selected, "message": f"선택된 BGM: {selected.name}"}


def bgm_edit_guide() -> str:
    return "\n".join(
        [
            "BGM 설정 추천",
            "- TTS 또는 Typecast 음성 기준 볼륨: 8~15%",
            "- 페이드인: 0.3초",
            "- 페이드아웃: 0.5초",
            "- 말소리가 묻히면 BGM을 먼저 8%까지 낮춘 뒤 구간별로 조절하세요.",
        ]
    )
