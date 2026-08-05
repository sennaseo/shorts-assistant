from __future__ import annotations

from pathlib import Path

from .file_utils import copy_file, ensure_dir


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def build_edit_guide(
    product_info: dict,
    keywords: list[str],
    bgm_message: str,
    tts_message: str,
    higgsfield_message: str = "",
) -> str:
    name = product_info.get("product_name") or "제품"
    tone = product_info.get("tone") or "친구 추천형"
    length = product_info.get("target_length") or 40
    category = product_info.get("category") or "카테고리"
    category_url = product_info.get("resolved_category_page_url") or product_info.get("category_page_url") or product_info.get("profile_link") or ""
    keyword_text = ", ".join(keywords[:8]) if keywords else "제품명, 핵심 장점, 주의점"
    return "\n".join(
        [
            f"# CapCut 편집 가이드 - {name}",
            "",
            "## 기본 구성",
            f"- 목표 길이: 약 {length}초",
            f"- 영상 톤: {tone}",
            "- 화면 비율: 9:16",
            "- 컷 편집: 문장 단위로 1.5~4초 템포 유지",
            "",
            "## CTA",
            f"- 영상 말미 문구: 자세한 제품 목록은 프로필 링크의 `{category}`에서 확인해보세요.",
            f"- 연결할 카테고리 페이지: {category_url or '카테고리 페이지 링크 입력 필요'}",
            "",
            "## 자막",
            "- capcut_subtitles.txt를 기준으로 한 화면 1~2줄 구성",
            f"- 강조 후보 키워드: {keyword_text}",
            "- 강조 색상은 1~2개만 사용하고, 주의점 문장은 과장 없이 표시",
            "",
            "## 오디오",
            "- edge_tts_test.mp3는 대본 길이 확인용입니다.",
            "- 최종 업로드용 음성은 Typecast에서 생성한 파일로 교체하세요.",
            "- TTS 또는 Typecast 음성 기준 BGM 볼륨: 8~15%",
            "- BGM 페이드인 0.3초, 페이드아웃 0.5초",
            f"- BGM 상태: {bgm_message}",
            f"- Edge TTS 상태: {tts_message}",
            f"- Higgsfield AI 영상 상태: {higgsfield_message or 'HIGGSFIELD_API_KEY 미설정 (건너뜀)'}",
            "",
            "## 패키지 사용 순서",
            "1. capcut_package/videos와 images의 소스를 CapCut에 가져옵니다.",
            "2. audio 폴더의 음성/BGM을 타임라인에 배치합니다.",
            "3. subtitles.srt를 불러오거나 capcut_subtitles.txt를 복사해 자막을 만듭니다.",
            "4. guide 폴더의 인포크 연결 가이드와 Notion 템플릿을 확인합니다.",
        ]
    )


def build_capcut_package(
    output_dir: str | Path,
    product_images: list[str | Path] | None = None,
    source_videos: list[str | Path] | None = None,
) -> Path:
    output = Path(output_dir)
    package = ensure_dir(output / "capcut_package")
    folders = {
        "videos": ensure_dir(package / "videos"),
        "images": ensure_dir(package / "images"),
        "audio": ensure_dir(package / "audio"),
        "subtitles": ensure_dir(package / "subtitles"),
        "guide": ensure_dir(package / "guide"),
    }

    for video in source_videos or []:
        src = Path(video)
        if src.suffix.lower() in VIDEO_EXTENSIONS:
            copy_file(src, folders["videos"] / src.name)

    for image in product_images or []:
        src = Path(image)
        if src.suffix.lower() in IMAGE_EXTENSIONS:
            copy_file(src, folders["images"] / src.name)

    for filename in ["edge_tts_test.mp3", "edge_tts_test.wav", "selected_bgm.mp3"]:
        copy_file(output / filename, folders["audio"] / filename)
    for filename in ["higgsfield_clip.mp4"]:
        copy_file(output / filename, folders["videos"] / filename)
    for filename in ["subtitles.srt", "capcut_subtitles.txt"]:
        copy_file(output / filename, folders["subtitles"] / filename)
    for filename in [
        "edit_guide.txt",
        "upload_info.txt",
        "image_prompts.txt",
        "tiktok_references.txt",
        "notion_category_page.md",
        "inpock_link_guide.txt",
    ]:
        copy_file(output / filename, folders["guide"] / filename)
    return package
