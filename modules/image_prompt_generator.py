from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .file_utils import write_text


def generate_image_prompts(product_info: Mapping[str, object]) -> str:
    name = str(product_info.get("product_name") or "제품")
    category = str(product_info.get("category") or "제품")
    target = str(product_info.get("target_user") or "사용자")
    tone = str(product_info.get("tone") or "깔끔한 쇼츠")
    advantages = [
        str(product_info.get("advantage_1") or "편리함"),
        str(product_info.get("advantage_2") or "공간 활용"),
        str(product_info.get("advantage_3") or "실용성"),
    ]

    prompts = [
        f"문제 상황 카드: 세로형 9:16 쇼츠 배경, 한국 일상 공간, {target}이 {category}를 찾게 되는 불편한 상황, 특정 제품은 직접 그리지 않음, 밝고 깔끔한 카드뉴스 스타일, 한글 텍스트를 넣기 좋은 여백",
        f"장점 카드 1: 세로형 9:16, {name} 관련 상황형 카드 이미지, 핵심 메시지 '{advantages[0]}', 실제 제품 실물 조작 없이 라이프스타일 배경 중심, {tone} 분위기",
        f"장점 카드 2: 세로형 9:16, {category} 비교 장면을 연상시키는 미니멀 카드, 핵심 메시지 '{advantages[1]}', 깔끔한 조명, 과장 없는 추천 콘텐츠 느낌",
        f"장점 카드 3: 세로형 9:16, 후기에서 많이 언급되는 포인트를 표현하는 배경 이미지, 핵심 메시지 '{advantages[2]}', 제품은 직접 묘사하지 않음",
        f"썸네일: 세로형 9:16 쇼츠 썸네일, {name} 추천 후보 느낌, 큰 한글 제목을 얹을 수 있는 중앙 여백, 선명한 대비, 클릭을 유도하지만 과장 광고처럼 보이지 않게",
        f"CTA 카드: 세로형 9:16, 설명란 링크 확인을 자연스럽게 안내하는 깔끔한 마무리 카드, 쿠팡 파트너스 고지와 함께 쓰기 좋은 심플한 구성",
        f"분위기 배경: 세로형 9:16, {tone} 톤의 한국형 일상 배경, {category} 콘텐츠에 어울리는 밝고 정돈된 분위기, 자막 가독성을 위한 여백",
    ]
    return "\n\n".join(prompts)


def save_image_prompts(product_info: Mapping[str, object], output_dir: str | Path) -> Path:
    return write_text(Path(output_dir) / "image_prompts.txt", generate_image_prompts(product_info))
