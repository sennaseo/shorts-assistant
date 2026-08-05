from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

VIDEO_SIZE = (1080, 1920)
FPS = 24
BG_COLOR = (16, 16, 22)
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (255, 214, 90)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _find_font(root_dir: str | Path | None = None) -> str | None:
    if root_dir:
        fonts_dir = Path(root_dir) / "assets" / "fonts"
        if fonts_dir.exists():
            for candidate in sorted(fonts_dir.glob("*")):
                if candidate.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                    return str(candidate)
    for candidate in FONT_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def _load_font(font_path: str | None, size: int):
    from PIL import ImageFont

    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            # 단어 하나가 너무 길면 글자 단위로 자르기
            while draw.textlength(word, font=font) > max_width and len(word) > 1:
                cut = len(word)
                while cut > 1 and draw.textlength(word[:cut], font=font) > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
    if current:
        lines.append(current)
    return lines


def _build_frame(
    line_text: str,
    image_path: str | Path | None,
    product_name: str,
    font_path: str | None,
):
    from PIL import Image, ImageDraw

    width, height = VIDEO_SIZE
    frame = Image.new("RGB", VIDEO_SIZE, BG_COLOR)
    draw = ImageDraw.Draw(frame)

    # 제품 이미지 (상단 영역에 맞춰 배치)
    if image_path and Path(image_path).exists():
        try:
            product = Image.open(image_path).convert("RGB")
            max_box = (width - 160, int(height * 0.48))
            product.thumbnail(max_box)
            x = (width - product.width) // 2
            y = int(height * 0.30) - product.height // 2
            frame.paste(product, (x, max(140, y)))
        except Exception:
            pass

    # 상단 제품명
    if product_name:
        title_font = _load_font(font_path, 52)
        title_lines = _wrap_text(draw, product_name, title_font, width - 200)[:2]
        y = 60
        for row in title_lines:
            row_width = draw.textlength(row, font=title_font)
            draw.text(((width - row_width) / 2, y), row, font=title_font, fill=ACCENT_COLOR)
            y += 64

    # 하단 자막
    subtitle_font = _load_font(font_path, 64)
    rows = _wrap_text(draw, line_text, subtitle_font, width - 160)[:4]
    line_height = 84
    y = int(height * 0.66)
    for row in rows:
        row_width = draw.textlength(row, font=subtitle_font)
        x = (width - row_width) / 2
        draw.text((x, y), row, font=subtitle_font, fill=(0, 0, 0), stroke_width=6, stroke_fill=(0, 0, 0))
        draw.text((x, y), row, font=subtitle_font, fill=TEXT_COLOR)
        y += line_height

    import numpy as np

    return np.array(frame)


def _compat(clip, new_name: str, old_name: str, *args, **kwargs):
    """moviepy 2.x(with_*)와 1.x(set_*) 메서드 이름 차이를 흡수한다."""
    method = getattr(clip, new_name, None) or getattr(clip, old_name, None)
    if method is None:
        raise AttributeError(f"moviepy에서 {new_name}/{old_name}를 찾지 못했습니다.")
    return method(*args, **kwargs)


def _audio_duration(audio_path: str | Path | None) -> float | None:
    if not audio_path or not Path(audio_path).exists():
        return None
    try:
        from mutagen import File

        audio = File(audio_path)
        if audio and audio.info and getattr(audio.info, "length", None):
            return float(audio.info.length)
    except Exception:
        return None
    return None


def render_draft_video(
    lines: Sequence[str],
    output_path: str | Path,
    audio_path: str | Path | None = None,
    image_paths: Sequence[str | Path] | None = None,
    bgm_path: str | Path | None = None,
    product_name: str = "",
    target_length: int = 40,
    root_dir: str | Path | None = None,
) -> dict[str, Any]:
    """이미지 + TTS 음성 + 자막으로 9:16 초안 mp4를 렌더링한다."""
    try:
        try:
            from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips
        except ImportError:
            from moviepy.editor import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips

        usable_lines = [line.strip() for line in lines if line.strip()]
        if not usable_lines:
            return {"success": False, "path": None, "error": "렌더링할 자막 문장이 없습니다."}

        total = _audio_duration(audio_path) or float(max(10, target_length or 40))
        weights = [max(len(line), 8) for line in usable_lines]
        weight_sum = sum(weights)
        durations = [total * weight / weight_sum for weight in weights]

        font_path = _find_font(root_dir)
        images = [path for path in (image_paths or []) if Path(path).exists()]

        clips = []
        for index, (line, duration) in enumerate(zip(usable_lines, durations)):
            image = images[index % len(images)] if images else None
            frame = _build_frame(line, image, product_name, font_path)
            clip = _compat(ImageClip(frame), "with_duration", "set_duration", duration)
            clips.append(clip)

        video = concatenate_videoclips(clips, method="chain")

        audio_clips = []
        if audio_path and Path(audio_path).exists():
            audio_clips.append(AudioFileClip(str(audio_path)))
        if bgm_path and Path(bgm_path).exists():
            try:
                bgm = AudioFileClip(str(bgm_path))
                if bgm.duration and bgm.duration > total:
                    bgm = _compat(bgm, "subclipped", "subclip", 0, total)
                try:
                    bgm = _compat(bgm, "with_volume_scaled", "volumex", 0.12)
                except Exception:
                    pass
                audio_clips.append(bgm)
            except Exception:
                pass
        if audio_clips:
            audio = audio_clips[0] if len(audio_clips) == 1 else CompositeAudioClip(audio_clips)
            video = _compat(video, "with_audio", "set_audio", audio)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        video.write_videofile(
            str(output),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=2,
            logger=None,
        )
        video.close()
        return {"success": True, "path": output, "error": ""}
    except Exception as exc:
        return {"success": False, "path": None, "error": f"초안 영상 렌더링 실패: {exc}"}
