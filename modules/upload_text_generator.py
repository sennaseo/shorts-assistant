from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .script_generator import DISCLOSURE
from .file_utils import write_text


def generate_upload_text(product_info: Mapping[str, object]) -> str:
    name = str(product_info.get("product_name") or "추천템")
    category = str(product_info.get("category") or "생활템")
    target = str(product_info.get("target_user") or "필요한 사람")
    link = str(product_info.get("affiliate_link") or "링크를 입력하세요")
    tone = str(product_info.get("tone") or "친구 추천형")

    titles = [
        f"{target}이 보면 좋은 {name}",
        f"{category} 찾는다면 {name} 체크",
        f"{name} 장점 3가지 빠르게 정리",
        f"후기에서 보이는 {name} 포인트",
        f"{category} 추천 후보: {name}",
    ]
    hashtags = [f"#{category.replace(' ', '')}", "#쿠팡파트너스", "#쇼츠추천", "#생활템", "#추천템"]
    return "\n".join(
        [
            "[유튜브 쇼츠 제목 후보]",
            *[f"{index}. {title}" for index, title in enumerate(titles, start=1)],
            "",
            "[유튜브 설명란]",
            f"{name} 상세 정보: {link}",
            f"{target} 기준으로 볼 만한 {category} 추천 후보를 정리했습니다.",
            DISCLOSURE,
            "",
            "[틱톡 캡션]",
            f"{name} 고민 중이면 장점이랑 주의점 같이 체크해봐요. {tone}으로 빠르게 정리!",
            "",
            "[해시태그]",
            " ".join(hashtags),
            "",
            "[쿠팡 파트너스 고지]",
            DISCLOSURE,
        ]
    )


def save_upload_text(product_info: Mapping[str, object], output_dir: str | Path) -> Path:
    return write_text(Path(output_dir) / "upload_info.txt", generate_upload_text(product_info))
