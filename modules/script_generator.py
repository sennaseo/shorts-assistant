from __future__ import annotations

from typing import Mapping


DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."


TONE_OPENERS = {
    "친구 추천형": "{target}이면 {name} 한 번 봐.",
    "정보 전달형": "{category} 찾는 분들이 확인할 만한 {name}입니다.",
    "빠른 리뷰형": "{name}, 핵심만 빠르게 정리해볼게.",
    "감성 자취템형": "작은 불편을 줄여주는 {category}, {name}을 소개할게요.",
    "직장인 현실 공감형": "퇴근할 때마다 지치는 {target}이라면 이거 체크해봐.",
}


def _value(info: Mapping[str, object], key: str, default: str = "") -> str:
    return str(info.get(key) or default).strip()


def generate_script(product_info: Mapping[str, object]) -> dict[str, str]:
    name = _value(product_info, "product_name", "추천템")
    category = _value(product_info, "category", "제품")
    price_range = _value(product_info, "price_range", "가격대 확인 필요")
    target = _value(product_info, "target_user", "이런 제품이 필요한 사람")
    tone = _value(product_info, "tone", "친구 추천형")
    advantages = [
        _value(product_info, "advantage_1", "사용하기 편해 보이는 점"),
        _value(product_info, "advantage_2", "공간을 많이 차지하지 않는 점"),
        _value(product_info, "advantage_3", "후기에서 자주 언급되는 만족 포인트"),
    ]
    caution = _value(product_info, "caution", "구매 전 크기와 사용 환경은 꼭 확인해봐.")
    link = _value(product_info, "affiliate_link", "쿠팡 파트너스 링크를 입력하세요.")

    opener_template = TONE_OPENERS.get(tone, TONE_OPENERS["친구 추천형"])
    opener = opener_template.format(name=name, category=category, target=target)

    if tone == "정보 전달형":
        body = [
            opener,
            f"상세페이지와 후기 기준으로 보면, {target}에게 특히 맞는 포인트가 있어요.",
            f"첫 번째는 {advantages[0]}입니다.",
            f"두 번째는 {advantages[1]}이고,",
            f"세 번째는 {advantages[2]}라는 점이에요.",
            f"가격대는 {price_range}라서 비교할 때 부담도 같이 체크하면 좋습니다.",
            f"다만 {caution}",
            f"{category}를 찾고 있었다면 후보에 넣어볼 만해요.",
            "자세한 정보는 고정 댓글이나 설명란 링크에서 확인해보세요.",
        ]
    elif tone == "빠른 리뷰형":
        body = [
            opener,
            f"{target} 기준으로 볼 포인트는 딱 세 가지야.",
            f"하나, {advantages[0]}.",
            f"둘, {advantages[1]}.",
            f"셋, {advantages[2]}.",
            f"대신 {caution}",
            f"가격대는 {price_range}, 상세페이지랑 후기를 같이 보고 결정하는 걸 추천해.",
            "링크는 설명란에 정리해둘게.",
        ]
    elif tone == "감성 자취템형":
        body = [
            opener,
            f"{target}에게는 매일 반복되는 작은 불편이 은근 크게 느껴지잖아요.",
            f"{name}은 {advantages[0]} 점이 먼저 눈에 들어와요.",
            f"그리고 {advantages[1]} 부분도 자취 공간에서 좋아 보입니다.",
            f"후기에서 보이는 포인트는 {advantages[2]}예요.",
            f"다만 {caution}",
            "내 공간에 맞는지 사이즈와 옵션을 확인하고 고르면 더 좋아요.",
            "제품 정보는 설명란 링크에 남겨둘게요.",
        ]
    elif tone == "직장인 현실 공감형":
        body = [
            opener,
            f"하루 종일 버티다 보면 {category} 하나도 꽤 현실적인 차이를 만들 때가 있잖아.",
            f"이 제품은 {advantages[0]} 점이 좋아 보이고,",
            f"{advantages[1]} 부분도 직장인 입장에서 체크할 만해.",
            f"또 {advantages[2]}라는 후기도 자주 볼 수 있어.",
            f"단, {caution}",
            f"{price_range} 정도 예산에서 찾는다면 비교 후보로 넣어봐.",
            "자세한 링크는 설명란에 있어.",
        ]
    else:
        body = [
            opener,
            f"{target}이면 평소에 {category} 고를 때 은근 고민 많잖아.",
            f"{name}은 상세페이지 기준으로 {advantages[0]} 점이 먼저 보이고,",
            f"{advantages[1]} 부분도 좋아 보이는 포인트야.",
            f"후기에서 많이 보이는 장점은 {advantages[2]} 쪽이야.",
            f"다만 {caution}",
            f"가격대는 {price_range}니까 비슷한 제품이랑 같이 비교해봐.",
            "궁금하면 설명란 링크에서 더 확인해봐.",
        ]

    script = "\n".join(body)
    return {
        "script": script,
        "disclosure": DISCLOSURE,
        "affiliate_link": link,
    }
