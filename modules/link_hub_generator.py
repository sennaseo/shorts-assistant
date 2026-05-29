from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .file_utils import load_json, save_json, write_text


def parse_category_links(raw_text: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for line in raw_text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if "=" in clean:
            category, url = clean.split("=", 1)
        elif "|" in clean:
            category, url = clean.split("|", 1)
        else:
            continue
        category = category.strip()
        url = url.strip()
        if category and url:
            links[category] = url
    return links


def parse_product_items(raw_text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in raw_text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        parts = [part.strip() for part in clean.split("|")]
        items.append(
            {
                "name": parts[0] if len(parts) > 0 else "",
                "description": parts[1] if len(parts) > 1 else "",
                "url": parts[2] if len(parts) > 2 else "",
                "memo": parts[3] if len(parts) > 3 else "",
            }
        )
    return [item for item in items if item["name"]]


def load_category_links(path: str | Path) -> dict[str, str]:
    data = load_json(path, default={}) or {}
    return {str(key): str(value) for key, value in data.items() if key and value}


def resolve_category_page_url(product_info: Mapping[str, object], category_links: Mapping[str, str]) -> str:
    direct = str(product_info.get("category_page_url") or "").strip()
    if direct:
        return direct
    category = str(product_info.get("category") or "").strip()
    return str(category_links.get(category) or product_info.get("profile_link") or "").strip()


def product_item_from_info(product_info: Mapping[str, object]) -> dict[str, str]:
    name = str(product_info.get("product_name") or "제품명")
    caution = str(product_info.get("caution") or "구매 전 상세페이지와 후기를 확인하세요.")
    advantages = [
        str(product_info.get("advantage_1") or "").strip(),
        str(product_info.get("advantage_2") or "").strip(),
        str(product_info.get("advantage_3") or "").strip(),
    ]
    description = " / ".join([item for item in advantages if item]) or "추천 후보로 정리한 제품입니다."
    return {
        "name": name,
        "description": description,
        "url": str(product_info.get("product_detail_url") or product_info.get("profile_link") or "").strip(),
        "memo": caution,
    }


def generate_notion_category_page(
    product_info: Mapping[str, object],
    category_links: Mapping[str, str],
    product_items: list[dict[str, str]],
) -> str:
    category = str(product_info.get("category") or "추천 제품").strip()
    target = str(product_info.get("target_user") or "필요한 사람").strip()
    price_range = str(product_info.get("price_range") or "가격대 확인 필요").strip()
    category_url = resolve_category_page_url(product_info, category_links)

    lines = [
        f"# {category} 추천 리스트",
        "",
        f"{target}에게 좋아 보이는 제품 후보를 모아두는 페이지입니다.",
        "영상에서 소개한 제품은 구매 전 상세페이지, 옵션, 배송비, 후기, 가격 변동을 꼭 다시 확인하세요.",
        "",
        "## 바로가기 안내",
        f"- 인포크 메인 링크: {product_info.get('profile_link') or '인포크 링크 입력 필요'}",
        f"- 이 카테고리 페이지 링크: {category_url or '카테고리 페이지 링크 입력 필요'}",
        f"- 기본 가격대: {price_range}",
        "",
        "## 제품 목록",
    ]

    if not product_items:
        product_items = [product_item_from_info(product_info)]

    for index, item in enumerate(product_items, start=1):
        lines.extend(
            [
                "",
                f"### {index}. {item.get('name') or '제품명'}",
                f"- 한줄 포인트: {item.get('description') or '제품 포인트 입력'}",
                f"- 제품 링크: {item.get('url') or '제품 링크 입력'}",
                f"- 메모/주의점: {item.get('memo') or '옵션, 사이즈, 후기 확인'}",
            ]
        )

    lines.extend(
        [
            "",
            "## 영상 CTA 문구",
            f"- 더 자세한 제품 목록은 프로필 링크의 `{category}`에서 확인해보세요.",
            "- 영상마다 제품 직링크를 바꾸기보다, 인포크에는 카테고리 페이지 링크를 고정해두고 이 페이지의 제품 목록을 업데이트하세요.",
            "",
            "## 운영 메모",
            "- 새 쇼츠를 만들 때마다 같은 카테고리 페이지에 제품 1개를 추가합니다.",
            "- 품절, 가격 변경, 링크 변경이 생기면 제품 목록에서 해당 줄만 수정합니다.",
            "- 유료 제휴 링크를 실제로 쓰기 시작하면 영상 설명과 페이지에 고지 문구를 추가합니다.",
        ]
    )
    return "\n".join(lines)


def generate_inpock_link_guide(product_info: Mapping[str, object], category_links: Mapping[str, str]) -> str:
    category = str(product_info.get("category") or "카테고리").strip()
    category_url = resolve_category_page_url(product_info, category_links)
    profile_link = str(product_info.get("profile_link") or "인포크 메인 링크 입력 필요").strip()
    categories = category_links or {category: category_url or "카테고리 페이지 링크 입력 필요"}

    lines = [
        "# 인포크 링크 연결 가이드",
        "",
        "## 추천 구조",
        "1. 인포크 메인 페이지에는 제품 직링크를 너무 많이 넣지 않습니다.",
        "2. 대신 카테고리 버튼을 만듭니다.",
        "3. 각 카테고리 버튼은 Notion 또는 공개 페이지의 제품 목록으로 연결합니다.",
        "4. 쇼츠에서는 `프로필 링크에서 카테고리명 눌러서 확인`이라고 안내합니다.",
        "",
        "## 현재 영상에서 쓸 CTA",
        f"- 자세한 제품 목록은 프로필 링크에서 `{category}` 카테고리로 확인해보세요.",
        f"- 인포크 메인: {profile_link}",
        f"- 연결할 카테고리 페이지: {category_url or '카테고리 페이지 링크 입력 필요'}",
        "",
        "## 인포크 버튼 예시",
    ]
    for name, url in categories.items():
        lines.append(f"- {name}: {url}")
    lines.extend(
        [
            "",
            "## Notion 페이지 구성",
            "- 맨 위: 카테고리명과 짧은 안내",
            "- 중간: 제품 목록",
            "- 각 제품: 제품명, 한줄 포인트, 제품 링크, 메모/주의점",
            "- 아래: 가격/품절/제휴 고지 업데이트 메모",
        ]
    )
    return "\n".join(lines)


def save_link_hub_files(
    product_info: Mapping[str, object],
    output_dir: str | Path,
    data_path: str | Path,
    raw_category_links: str = "",
    raw_product_items: str = "",
) -> dict[str, Path | str]:
    existing_links = load_category_links(data_path)
    incoming_links = parse_category_links(raw_category_links)
    merged_links = {**existing_links, **incoming_links}

    category = str(product_info.get("category") or "").strip()
    category_url = str(product_info.get("category_page_url") or "").strip()
    if category and category_url:
        merged_links[category] = category_url
    save_json(data_path, merged_links)

    product_items = parse_product_items(raw_product_items)
    if product_info.get("include_current_product_in_link_hub", True):
        current_item = product_item_from_info(product_info)
        product_items = [current_item, *product_items]

    output = Path(output_dir)
    notion_content = generate_notion_category_page(product_info, merged_links, product_items)
    guide_content = generate_inpock_link_guide(product_info, merged_links)
    return {
        "notion_category_page": write_text(output / "notion_category_page.md", notion_content),
        "inpock_link_guide": write_text(output / "inpock_link_guide.txt", guide_content),
        "category_page_url": resolve_category_page_url(product_info, merged_links),
    }
