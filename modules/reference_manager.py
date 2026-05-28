from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .file_utils import load_json, save_json, write_text


def recommend_search_keywords(product_info: Mapping[str, object]) -> list[str]:
    name = str(product_info.get("product_name") or "제품")
    category = str(product_info.get("category") or "카테고리")
    target = str(product_info.get("target_user") or "타겟")
    return [
        f"{name} 추천",
        f"{name} 후기",
        f"{name} 사용법",
        f"{category} 꿀템",
        f"{target} 추천템",
    ]


def save_references(
    references: list[Mapping[str, str]],
    product_info: Mapping[str, object],
    output_dir: str | Path,
    data_path: str | Path,
) -> dict[str, Path]:
    output = Path(output_dir)
    existing = load_json(data_path, default=[]) or []
    product_name = str(product_info.get("product_name") or "")
    normalized = []
    for item in references:
        url = str(item.get("url") or "").strip()
        memo = str(item.get("memo") or "").strip()
        if not url and not memo:
            continue
        record = {
            "product_name": product_name,
            "url": url,
            "memo": memo,
            "hook": str(item.get("hook") or ""),
            "good_scene": str(item.get("good_scene") or ""),
            "composition": str(item.get("composition") or ""),
            "subtitle_style": str(item.get("subtitle_style") or ""),
            "caution": str(item.get("caution") or ""),
        }
        normalized.append(record)
    save_json(data_path, [*existing, *normalized])

    keywords = recommend_search_keywords(product_info)
    sections = ["[TikTok/Reels 레퍼런스]"]
    if normalized:
        for index, ref in enumerate(normalized, start=1):
            sections.extend(
                [
                    f"{index}. {ref['url']}",
                    f"메모: {ref['memo']}",
                    f"후킹 문장: {ref['hook']}",
                    f"좋은 장면: {ref['good_scene']}",
                    f"따라할 구도: {ref['composition']}",
                    f"자막 스타일: {ref['subtitle_style']}",
                    f"주의할 점: {ref['caution']}",
                    "",
                ]
            )
    else:
        sections.append("저장된 레퍼런스가 없습니다.")
        sections.append("")
    sections.extend(["[검색 키워드 추천]", *[f"- {keyword}" for keyword in keywords]])
    txt = write_text(output / "tiktok_references.txt", "\n".join(sections))
    return {"tiktok_references": txt, "references_json": Path(data_path)}
