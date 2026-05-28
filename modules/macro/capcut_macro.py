from __future__ import annotations

from pathlib import Path

from .macro_config import DEFAULT_CONFIG, MacroConfig


def open_capcut(config: MacroConfig = DEFAULT_CONFIG) -> str:
    if config.dry_run:
        return f"[dry-run] CapCut 실행 예정: {config.capcut_executable_path or '기본 실행 경로 미설정'}"
    import subprocess

    if not config.capcut_executable_path:
        return "CapCut 실행 경로가 macro_config.py에 설정되어 있지 않습니다."
    subprocess.Popen([config.capcut_executable_path])
    return "CapCut 실행 완료"


def create_new_project(config: MacroConfig = DEFAULT_CONFIG) -> str:
    return "[dry-run] 새 프로젝트 생성" if config.dry_run else "TODO: 새 프로젝트 단축키/좌표 설정 후 구현"


def _list_files(folder: Path) -> list[Path]:
    return sorted([path for path in folder.rglob("*") if path.is_file()]) if folder.exists() else []


def import_media(package_dir: str | Path, config: MacroConfig = DEFAULT_CONFIG) -> str:
    package = Path(package_dir)
    files = _list_files(package / "videos") + _list_files(package / "images")
    return "\n".join([f"[dry-run] 미디어 import: {file}" for file in files]) if config.dry_run else "TODO: 미디어 import 구현"


def import_audio(package_dir: str | Path, config: MacroConfig = DEFAULT_CONFIG) -> str:
    files = _list_files(Path(package_dir) / "audio")
    return "\n".join([f"[dry-run] 오디오 import: {file}" for file in files]) if config.dry_run else "TODO: 오디오 import 구현"


def import_subtitles(package_dir: str | Path, config: MacroConfig = DEFAULT_CONFIG) -> str:
    files = _list_files(Path(package_dir) / "subtitles")
    return "\n".join([f"[dry-run] 자막 import: {file}" for file in files]) if config.dry_run else "TODO: 자막 import 구현"


def arrange_timeline(config: MacroConfig = DEFAULT_CONFIG) -> str:
    return "[dry-run] 영상, 음성, BGM, 자막 순서로 타임라인 배치" if config.dry_run else "TODO: 타임라인 배치 구현"


def set_bgm_volume(config: MacroConfig = DEFAULT_CONFIG) -> str:
    return "[dry-run] BGM 볼륨 8~15%, 페이드 설정" if config.dry_run else "TODO: BGM 볼륨 설정 구현"


def prepare_export(config: MacroConfig = DEFAULT_CONFIG) -> str:
    return "[dry-run] 내보내기 직전 화면까지 준비" if config.dry_run else "TODO: 내보내기 준비 구현"


def run_capcut_macro(package_dir: str | Path, config: MacroConfig = DEFAULT_CONFIG) -> list[str]:
    return [
        open_capcut(config),
        create_new_project(config),
        import_media(package_dir, config),
        import_audio(package_dir, config),
        import_subtitles(package_dir, config),
        arrange_timeline(config),
        set_bgm_volume(config),
        prepare_export(config),
    ]
