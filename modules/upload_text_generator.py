from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .script_generator import DISCLOSURE
from .file_utils import write_text


def generate_upload_text(product_info: Mapping[str, object]) -> str:
    name = str(product_info.get("product_name") or "추천템")
    category = str(product_info.get("category") or "생활템")
    target = str(product_info.get("target_user") or "필요한 사람")
    link = str(product_info.get("profile_link") or product_info.get("affiliate_link") or "인포크/프로필 링크를 입력하세요")
    tone = str(product_info.get("tone") or "친구 추천형")
    include_disclosure = bool(product_info.get("include_partner_disclosure"))

    titles = [
        f"{target}에게 좋아 보이는 {name}",
        f"{category} 찾는다면 {name} 체크",
        f"{name} 장점 3가지 빠르게 정리",
        f"후기에서 보이는 {name} 포인트",
        f"{category} 추천 후보: {name}",
    ]
    hashtags = list(dict.fromkeys([f"#{category.replace(' ', '')}", "#쇼츠추천", "#생활템", "#추천템", "#제품추천"]))
    lines = [
            "[유튜브 쇼츠 제목 후보]",
            *[f"{index}. {title}" for index, title in enumerate(titles, start=1)],
            "",
            "[유튜브 설명란]",
            f"{name} 관련 정보: {link}",
            f"{target} 기준으로 볼 만한 {category} 추천 후보를 정리했습니다.",
            "",
            "[틱톡 캡션]",
            f"{name} 고민 중이면 장점이랑 주의점 같이 체크해봐요. 자세한 정보는 프로필 링크에 정리해둘게요.",
            "",
            "[해시태그]",
            " ".join(hashtags),
    ]
    if include_disclosure:
        lines.extend(["", "[제휴/파트너스 고지]", DISCLOSURE])
    else:
        lines.extend(["", "[고지 상태]", "현재 제휴/파트너스 고지 문구는 포함하지 않았습니다. 실제 제휴 링크를 사용할 때만 고지를 켜세요."])
    return "\n".join(lines)


def save_upload_text(product_info: Mapping[str, object], output_dir: str | Path) -> Path:
    return write_text(Path(output_dir) / "upload_info.txt", generate_upload_text(product_info))
