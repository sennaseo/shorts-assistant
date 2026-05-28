from __future__ import annotations

import time
from pathlib import Path

from .macro_config import DEFAULT_CONFIG, MacroConfig


def load_typecast_lines(path: str | Path) -> list[str]:
    target = Path(path)
    if not target.exists():
        return []
    return [line.strip() for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]


def copy_line_to_clipboard(line: str, dry_run: bool = True) -> str:
    if dry_run:
        return f"[dry-run] 클립보드 복사 예정: {line}"
    import pyperclip

    pyperclip.copy(line)
    return f"클립보드 복사 완료: {line}"


def open_typecast(config: MacroConfig = DEFAULT_CONFIG) -> str:
    if config.dry_run:
        return f"[dry-run] Typecast 열기: {config.typecast_url}"
    import webbrowser

    webbrowser.open(config.typecast_url)
    return f"Typecast 열기: {config.typecast_url}"


def paste_line(config: MacroConfig = DEFAULT_CONFIG) -> str:
    if config.dry_run:
        return "[dry-run] 텍스트 영역 클릭 후 붙여넣기"
    import pyautogui

    pyautogui.hotkey(*config.hotkeys["paste"])
    return "붙여넣기 완료"


def click_generate(config: MacroConfig = DEFAULT_CONFIG) -> str:
    if config.dry_run:
        return "[dry-run] 생성 버튼 클릭"
    import pyautogui

    pyautogui.click(*config.coordinates["typecast_generate_button"])
    return "생성 버튼 클릭 완료"


def wait_for_generation(config: MacroConfig = DEFAULT_CONFIG) -> str:
    if config.dry_run:
        return f"[dry-run] 생성 대기 {config.wait_seconds}초"
    time.sleep(config.wait_seconds)
    return "생성 대기 완료"


def download_audio(config: MacroConfig = DEFAULT_CONFIG) -> str:
    if config.dry_run:
        return "[dry-run] 오디오 다운로드 버튼 클릭 예정"
    return "TODO: 사용자 PC의 Typecast 다운로드 버튼 좌표를 설정한 뒤 구현하세요."


def run_typecast_macro(project_dir: str | Path, config: MacroConfig = DEFAULT_CONFIG) -> list[str]:
    project = Path(project_dir)
    lines = load_typecast_lines(project / "typecast_lines.txt")
    logs = [open_typecast(config), f"총 {len(lines)}개 문장 처리 예정"]
    for line in lines:
        logs.append(copy_line_to_clipboard(line, config.dry_run))
        logs.append(paste_line(config))
        logs.append(click_generate(config))
        logs.append(wait_for_generation(config))
    logs.append(download_audio(config))
    return logs
