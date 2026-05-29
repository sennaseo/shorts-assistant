from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from modules.file_utils import load_json
from modules.project_manager import run_pipeline


ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

st.set_page_config(page_title="Shorts Assistant", page_icon="SA", layout="wide")


def _download_button(label: str, path: Path | None, mime: str = "text/plain") -> None:
    if path and Path(path).exists():
        st.download_button(
            label=label,
            data=Path(path).read_bytes(),
            file_name=Path(path).name,
            mime=mime,
            use_container_width=True,
        )
    else:
        st.button(label, disabled=True, use_container_width=True)


settings = load_json(ROOT_DIR / "data" / "settings.json", default={}) or {}
saved_category_links = load_json(ROOT_DIR / "data" / "category_links.json", default={}) or {}

st.title("Shorts Assistant")
st.caption("제품 추천 쇼츠/틱톡 제작용 로컬 반자동 파이프라인")

with st.sidebar:
    st.header("설정")
    tts_voice = st.text_input("Edge TTS 음성", value=settings.get("default_tts_voice", "ko-KR-SunHiNeural"))
    tts_rate = st.text_input("Edge TTS 속도", value=settings.get("default_tts_rate", "+0%"))
    st.info("Edge TTS는 테스트용입니다. 최종 업로드 음성은 Typecast에서 생성한 파일로 교체하세요.")

left, right = st.columns([0.95, 1.05], gap="large")

with left:
    st.subheader("A. 프로젝트 생성")
    product_name = st.text_input("제품명", placeholder="예: 접이식 발받침대")
    category = st.text_input("카테고리", placeholder="예: 사무실템, 자취템, 주방템")
    price_range = st.text_input("가격대", placeholder="예: 1만~3만원대")
    target_user = st.text_input("타겟 사용자", placeholder="예: 오래 앉아 일하는 직장인")
    advantage_1 = st.text_input("장점 1", placeholder="예: 접어서 보관하기 쉬움")
    advantage_2 = st.text_input("장점 2", placeholder="예: 책상 밑 공간 활용 가능")
    advantage_3 = st.text_input("장점 3", placeholder="예: 발을 올려두기 편한 각도")
    caution = st.text_input("단점/주의점", placeholder="예: 책상 높이와 발 공간을 확인해야 함")

    st.markdown("#### 인포크/카테고리 링크")
    profile_link = st.text_input("인포크 메인 링크", placeholder="https://link.inpock.co.kr/...")
    category_page_url = st.text_input(
        "현재 카테고리 페이지 링크",
        value=saved_category_links.get(category, "") if category else "",
        placeholder="예: Notion 카테고리 페이지 공유 링크",
        help="인포크의 카테고리 버튼이 연결될 Notion/페이지 링크입니다.",
    )
    product_detail_url = st.text_input(
        "제품 상세 링크 또는 임시 링크",
        placeholder="제품을 모아둔 페이지 안에 넣을 링크. 아직 없으면 비워둬도 됩니다.",
    )
    category_links_text = st.text_area(
        "카테고리별 링크 목록",
        value="\n".join([f"{name}={url}" for name, url in saved_category_links.items()]),
        placeholder="생활템=https://...\n주방템=https://...\n사무실템=https://...",
        help="한 줄에 `카테고리=링크` 형식으로 입력하면 data/category_links.json에 저장됩니다.",
        height=100,
    )
    product_items_text = st.text_area(
        "카테고리 페이지에 같이 넣을 제품 목록",
        placeholder="제품명 | 한줄 포인트 | 제품 링크 | 메모/주의점\n예: 미니 가습기 | 책상 위에 두기 좋음 | https://... | 용량 확인",
        help="현재 제품은 자동으로 목록 맨 위에 추가됩니다. 여기는 같은 카테고리의 추가 제품을 넣을 때 사용하세요.",
        height=100,
    )
    include_current_product_in_link_hub = st.checkbox("현재 제품을 카테고리 제품 목록에 포함", value=True)
    include_partner_disclosure = st.checkbox(
        "유료 제휴/파트너스 고지 문구 포함",
        value=False,
        help="아직 파트너스 활동 전이면 꺼두세요. 실제 유료 제휴 링크를 쓰기 시작할 때만 켜면 됩니다.",
    )

    with st.expander("Notion API로 카테고리 페이지에 바로 추가"):
        publish_to_notion = st.checkbox("생성 후 Notion 페이지에 자동 추가", value=False)
        notion_page_id = st.text_input(
            "Notion 페이지 URL 또는 ID",
            value=os.getenv("NOTION_TARGET_PAGE_ID", ""),
            placeholder="https://www.notion.so/...",
        )
        notion_api_token_input = st.text_input(
            "Notion API 토큰",
            value="",
            type="password",
            placeholder=".env에 NOTION_API_KEY가 있으면 비워도 됩니다.",
        )
        st.caption("Notion에서 해당 페이지의 ··· 메뉴 > Connections에 만든 integration을 먼저 연결해야 합니다.")

    tone = st.selectbox(
        "영상 톤",
        ["친구 추천형", "정보 전달형", "빠른 리뷰형", "감성 자취템형", "직장인 현실 공감형"],
    )
    target_length = st.slider(
        "목표 영상 길이(초)",
        min_value=20,
        max_value=60,
        value=int(settings.get("default_video_length", 40)),
        step=5,
    )
    bgm_mood = st.text_input("BGM 분위기", placeholder="예: upbeat, calm, cozy")

    product_images = st.file_uploader(
        "제품 이미지 업로드",
        type=["png", "jpg", "jpeg", "webp", "gif"],
        accept_multiple_files=True,
    )
    source_videos = st.file_uploader(
        "영상 소스 업로드",
        type=["mp4", "mov", "m4v", "avi", "mkv", "webm"],
        accept_multiple_files=True,
    )

    st.markdown("#### TikTok/릴스 레퍼런스")
    reference_urls = st.text_area("레퍼런스 URL 입력", placeholder="한 줄에 URL 하나씩 입력")
    reference_memos = st.text_area("레퍼런스별 메모 입력", placeholder="URL 순서와 같은 줄에 메모를 입력")
    reference_hook = st.text_input("후킹 문장 메모", placeholder="예: 첫 2초에 문제를 바로 던짐")
    reference_scene = st.text_input("좋은 장면", placeholder="예: 손으로 제품 펼치는 장면")
    reference_composition = st.text_input("따라할 구도", placeholder="예: 책상 아래 로우앵글")
    reference_subtitle = st.text_input("자막 스타일", placeholder="예: 굵은 흰색 + 노란 키워드")
    reference_caution = st.text_input("주의할 점", placeholder="예: 영상 자체 다운로드 대신 구도만 참고")

    create = st.button("쇼츠 패키지 생성", type="primary", use_container_width=True)

with right:
    st.subheader("C. 결과 미리보기")
    result = st.session_state.get("last_result")
    if not result:
        st.write("제품 정보를 입력하고 버튼을 누르면 이곳에 생성 결과가 표시됩니다.")
    else:
        if result.get("errors"):
            for error in result["errors"]:
                st.warning(error)

        st.text_input("출력 폴더 경로", value=str(result.get("output_dir", "")), disabled=True)
        st.text_input("CapCut 패키지 폴더", value=str(result.get("capcut_package", "")), disabled=True)

        tabs = st.tabs(["대본", "Typecast", "CapCut 자막", "업로드 문구", "링크 허브", "파일 다운로드"])
        with tabs[0]:
            st.text_area("생성된 대본", value=result.get("script", ""), height=260)
        with tabs[1]:
            st.text_area("Typecast용 문장", value=result.get("typecast_lines", ""), height=260)
        with tabs[2]:
            st.text_area("CapCut 자막", value=result.get("capcut_subtitles", ""), height=260)
        with tabs[3]:
            st.text_area("업로드 문구", value=result.get("upload_info", ""), height=260)
        with tabs[4]:
            notion_publish = result.get("notion_publish")
            if notion_publish:
                if notion_publish.get("success"):
                    st.success(notion_publish.get("message"))
                else:
                    st.warning(notion_publish.get("message"))
            st.text_area("인포크 연결 가이드", value=result.get("link_hub_guide", ""), height=220)
            st.text_area("Notion 카테고리 페이지 템플릿", value=result.get("notion_category_page", ""), height=320)
        with tabs[5]:
            files = result.get("files", {})
            download_cols = st.columns(2)
            with download_cols[0]:
                _download_button("script.txt", files.get("script"))
                _download_button("typecast_lines.txt", files.get("typecast_lines"))
                _download_button("capcut_subtitles.txt", files.get("capcut_subtitles"))
                _download_button("upload_info.txt", files.get("upload_info"))
                _download_button("inpock_link_guide.txt", files.get("inpock_link_guide"))
            with download_cols[1]:
                _download_button("typecast_lines_numbered.txt", files.get("typecast_lines_numbered"))
                _download_button("subtitles.srt", files.get("subtitles"))
                _download_button("edit_guide.txt", files.get("edit_guide"))
                _download_button("image_prompts.txt", files.get("image_prompts"))
                _download_button("notion_category_page.md", files.get("notion_category_page"))

            audio_path = files.get("edge_tts_test")
            if audio_path and Path(audio_path).exists():
                st.audio(str(audio_path))
            else:
                st.caption("Edge TTS 테스트 음성이 없거나 생성에 실패했습니다. 나머지 파일은 그대로 사용할 수 있습니다.")


if create:
    if not product_name.strip():
        st.error("제품명은 꼭 입력해주세요.")
        st.stop()

    urls = [line.strip() for line in reference_urls.splitlines()]
    memos = [line.strip() for line in reference_memos.splitlines()]
    references = []
    for index, url in enumerate(urls):
        memo = memos[index] if index < len(memos) else ""
        if url or memo:
            references.append(
                {
                    "url": url,
                    "memo": memo,
                    "hook": reference_hook,
                    "good_scene": reference_scene,
                    "composition": reference_composition,
                    "subtitle_style": reference_subtitle,
                    "caution": reference_caution,
                }
            )

    product_info = {
        "product_name": product_name,
        "category": category,
        "price_range": price_range,
        "target_user": target_user,
        "advantage_1": advantage_1,
        "advantage_2": advantage_2,
        "advantage_3": advantage_3,
        "caution": caution,
        "profile_link": profile_link,
        "category_page_url": category_page_url,
        "product_detail_url": product_detail_url,
        "affiliate_link": profile_link,
        "include_partner_disclosure": include_partner_disclosure,
        "include_current_product_in_link_hub": include_current_product_in_link_hub,
        "tone": tone,
        "target_length": target_length,
        "bgm_mood": bgm_mood,
    }

    with st.spinner("쇼츠 제작 패키지를 생성하는 중입니다..."):
        st.session_state["last_result"] = run_pipeline(
            product_info=product_info,
            product_image_files=product_images,
            source_video_files=source_videos,
            references=references,
            category_links_text=category_links_text,
            product_items_text=product_items_text,
            publish_to_notion=publish_to_notion,
            notion_api_token=notion_api_token_input or os.getenv("NOTION_API_KEY", ""),
            notion_page_id=notion_page_id,
            tts_voice=tts_voice,
            tts_rate=tts_rate,
            root_dir=ROOT_DIR,
        )
    st.rerun()
