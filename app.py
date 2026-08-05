from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from modules.file_utils import load_json, read_text, save_json
from modules.llm_script_generator import llm_available
from modules.project_manager import run_pipeline


ROOT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = ROOT_DIR / "outputs"
SETTINGS_PATH = ROOT_DIR / "data" / "settings.json"
PRODUCTS_PATH = ROOT_DIR / "data" / "products.json"
load_dotenv(ROOT_DIR / ".env")

st.set_page_config(page_title="Shorts Assistant", page_icon="SA", layout="wide")

# Streamlit Cloud 배포 시 st.secrets 값을 환경변수로 연결 (.env 대체)
try:
    for _key, _value in st.secrets.items():
        if isinstance(_value, str) and _key not in os.environ:
            os.environ[_key] = _value
except Exception:
    pass


def _check_password() -> None:
    """APP_PASSWORD가 설정된 경우에만 비밀번호를 요구한다 (서버 배포용)."""
    expected = os.getenv("APP_PASSWORD", "").strip()
    if not expected or st.session_state.get("auth_ok"):
        return
    st.title("Shorts Assistant")
    password = st.text_input("비밀번호", type="password")
    if password:
        if password == expected:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


_check_password()


def _zip_dir_bytes(directory: Path) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(directory))
    return buffer.getvalue()


def _zip_download_button(directory: Path | str | None, key: str) -> None:
    if not directory:
        return
    folder = Path(directory)
    if not folder.exists():
        return
    st.download_button(
        "전체 결과 zip 다운로드",
        data=_zip_dir_bytes(folder),
        file_name=f"{folder.name}.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
        key=key,
    )


def _download_button(label: str, path: Path | None, mime: str = "text/plain", key: str | None = None) -> None:
    if path and Path(path).exists():
        st.download_button(
            label=label,
            data=Path(path).read_bytes(),
            file_name=Path(path).name,
            mime=mime,
            use_container_width=True,
            key=key,
        )
    else:
        st.button(label, disabled=True, use_container_width=True, key=f"disabled_{key or label}")


settings = load_json(SETTINGS_PATH, default={}) or {}
saved_category_links = load_json(ROOT_DIR / "data" / "category_links.json", default={}) or {}

st.title("Shorts Assistant")
st.caption("제품 추천 쇼츠/틱톡 제작용 로컬 반자동 파이프라인")

with st.sidebar:
    st.header("설정")
    tts_voice = st.text_input("Edge TTS 음성", value=settings.get("default_tts_voice", "ko-KR-SunHiNeural"))
    tts_rate = st.text_input("Edge TTS 속도", value=settings.get("default_tts_rate", "+0%"))
    default_profile_link = st.text_input(
        "기본 인포크 메인 링크",
        value=settings.get("default_profile_link", ""),
        help="저장해두면 매번 다시 입력하지 않아도 됩니다.",
    )

    st.markdown("#### 대본 생성")
    env_key_exists = llm_available()
    use_llm = st.checkbox(
        "Claude API로 대본 생성",
        value=bool(settings.get("use_llm", False)) and env_key_exists,
        help="켜면 Claude가 제품 정보로 자연스러운 대본을 작성합니다. 실패하면 자동으로 기존 템플릿 대본을 사용합니다.",
    )
    anthropic_key_input = ""
    if use_llm and not env_key_exists:
        anthropic_key_input = st.text_input(
            "Anthropic API 키",
            type="password",
            placeholder=".env에 ANTHROPIC_API_KEY를 넣으면 비워도 됩니다.",
        )
    elif use_llm:
        st.caption(".env의 ANTHROPIC_API_KEY를 사용합니다.")

    if st.button("설정 저장", use_container_width=True):
        settings.update(
            {
                "default_tts_voice": tts_voice,
                "default_tts_rate": tts_rate,
                "default_profile_link": default_profile_link,
                "use_llm": use_llm,
            }
        )
        save_json(SETTINGS_PATH, settings)
        st.success("data/settings.json에 저장했습니다.")

    st.info("Edge TTS는 테스트용입니다. 최종 업로드 음성은 Typecast에서 생성한 파일로 교체하세요.")

tab_create, tab_history, tab_products = st.tabs(["패키지 생성", "히스토리", "제품 관리"])

with tab_create:
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
        profile_link = st.text_input(
            "인포크 메인 링크",
            value=settings.get("default_profile_link", ""),
            placeholder="https://link.inpock.co.kr/...",
        )
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
        product_image_url = st.text_input(
            "제품 이미지 URL",
            placeholder="Notion에 표시할 대표 이미지 URL이 있으면 입력",
        )
        option_memo = st.text_input(
            "옵션/사이즈 메모",
            placeholder="예: 색상, 규격, 호환 여부, 책상 높이 확인",
        )
        shipping_memo = st.text_input(
            "배송/품절 메모",
            placeholder="예: 로켓배송 여부, 배송비, 품절 가능성",
        )
        review_memo = st.text_input(
            "후기 메모",
            placeholder="예: 후기에서 자주 보이는 장점/아쉬운 점",
        )
        status_memo = st.selectbox(
            "제품 상태",
            ["검토중", "쇼츠 제작 예정", "업로드 완료", "링크 확인 필요", "숨김"],
        )
        personal_note = st.text_area(
            "개인 메모",
            placeholder="예: 영상에서 강조할 장면, 썸네일 문구, 나중에 확인할 점",
            height=80,
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
            placeholder="제품명 | 한줄 포인트 | 제품 링크 | 메모/주의점 | 가격대 | 추천 대상 | 이미지 URL | 상태\n예: 미니 가습기 | 책상 위에 두기 좋음 | https://... | 용량 확인 | 2만원대 | 자취생 | https://...jpg | 검토중",
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
        render_video = st.checkbox(
            "초안 영상 자동 렌더링 (mp4)",
            value=bool(settings.get("render_video", False)),
            help="업로드한 제품 이미지 + TTS 음성 + 자막으로 9:16 초안 영상을 만듭니다. 대본/타이밍 확인용이며, 최종본은 CapCut에서 다듬는 것을 추천합니다.",
        )

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

            if result.get("script_source") == "llm":
                st.caption("대본: Claude API 생성")
            elif result.get("script_source") == "template":
                st.caption("대본: 템플릿 생성")

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
                _zip_download_button(result.get("output_dir"), key="result_zip")
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

                draft_video = files.get("draft_video")
                if draft_video and Path(draft_video).exists():
                    st.video(str(draft_video))
                    _download_button("draft_video.mp4", Path(draft_video), mime="video/mp4", key="result_dl_draft_video")

with tab_history:
    st.subheader("과거 생성 프로젝트")
    project_dirs = sorted(
        [path for path in OUTPUTS_DIR.glob("*") if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not project_dirs:
        st.write("아직 생성된 프로젝트가 없습니다.")
    else:
        def _label(path: Path) -> str:
            info = load_json(path / "product_info.json", default={}) or {}
            name = str(info.get("product_name") or path.name)
            when = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            return f"{name} ({when})"

        selected_dir = st.selectbox("프로젝트 선택", project_dirs, format_func=_label)
        if selected_dir:
            info = load_json(selected_dir / "product_info.json", default={}) or {}
            meta_cols = st.columns(4)
            meta_cols[0].metric("카테고리", str(info.get("category") or "-"))
            meta_cols[1].metric("가격대", str(info.get("price_range") or "-"))
            meta_cols[2].metric("톤", str(info.get("tone") or "-"))
            meta_cols[3].metric("목표 길이", f"{info.get('target_length') or '-'}초")
            st.text_input("폴더 경로", value=str(selected_dir), disabled=True, key="history_dir")

            history_tabs = st.tabs(["대본", "Typecast", "CapCut 자막", "업로드 문구", "링크 허브", "파일 다운로드"])
            with history_tabs[0]:
                st.text_area("대본", value=read_text(selected_dir / "script.txt"), height=260, key="history_script")
            with history_tabs[1]:
                st.text_area("Typecast용 문장", value=read_text(selected_dir / "typecast_lines.txt"), height=260, key="history_typecast")
            with history_tabs[2]:
                st.text_area("CapCut 자막", value=read_text(selected_dir / "capcut_subtitles.txt"), height=260, key="history_subtitles")
            with history_tabs[3]:
                st.text_area("업로드 문구", value=read_text(selected_dir / "upload_info.txt"), height=260, key="history_upload")
            with history_tabs[4]:
                st.text_area("인포크 연결 가이드", value=read_text(selected_dir / "inpock_link_guide.txt"), height=220, key="history_linkhub")
                st.text_area("Notion 카테고리 페이지 템플릿", value=read_text(selected_dir / "notion_category_page.md"), height=320, key="history_notion")
            with history_tabs[5]:
                _zip_download_button(selected_dir, key="history_zip")
                filenames = [
                    "script.txt",
                    "typecast_lines.txt",
                    "typecast_lines_numbered.txt",
                    "capcut_subtitles.txt",
                    "subtitles.srt",
                    "upload_info.txt",
                    "edit_guide.txt",
                    "image_prompts.txt",
                    "inpock_link_guide.txt",
                    "notion_category_page.md",
                ]
                download_cols = st.columns(2)
                for index, filename in enumerate(filenames):
                    with download_cols[index % 2]:
                        _download_button(filename, selected_dir / filename, key=f"history_dl_{filename}")

                for audio_name in ["edge_tts_test.mp3", "edge_tts_test.wav"]:
                    audio_path = selected_dir / audio_name
                    if audio_path.exists():
                        st.audio(str(audio_path))
                        break

                draft_video = selected_dir / "draft_video.mp4"
                if draft_video.exists():
                    st.video(str(draft_video))
                    _download_button("draft_video.mp4", draft_video, mime="video/mp4", key="history_dl_draft_video")

with tab_products:
    st.subheader("제품 DB (data/products.json)")
    products = load_json(PRODUCTS_PATH, default=[]) or []
    if not products:
        st.write("아직 저장된 제품이 없습니다. 패키지를 생성하면 자동으로 여기에 쌓입니다.")
    else:
        import pandas as pd

        preferred_columns = [
            "product_name",
            "category",
            "price_range",
            "status_memo",
            "target_user",
            "advantage_1",
            "advantage_2",
            "advantage_3",
            "caution",
            "product_detail_url",
            "personal_note",
        ]
        df = pd.DataFrame(products)
        ordered = [col for col in preferred_columns if col in df.columns]
        remaining = [col for col in df.columns if col not in ordered]
        df = df[ordered + remaining]

        edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="products_editor")

        save_cols = st.columns([1, 1, 2])
        with save_cols[0]:
            if st.button("변경사항 저장", type="primary", use_container_width=True):
                records = edited.where(pd.notnull(edited), None).to_dict("records")
                save_json(PRODUCTS_PATH, records)
                st.success(f"{len(records)}개 제품을 저장했습니다.")
        with save_cols[1]:
            st.download_button(
                "CSV 다운로드",
                data=edited.to_csv(index=False).encode("utf-8-sig"),
                file_name="products.csv",
                mime="text/csv",
                use_container_width=True,
            )
        st.caption("행을 추가/삭제하거나 셀을 수정한 뒤 '변경사항 저장'을 누르면 data/products.json에 반영됩니다.")


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
        "product_image_url": product_image_url,
        "option_memo": option_memo,
        "shipping_memo": shipping_memo,
        "review_memo": review_memo,
        "status_memo": status_memo,
        "personal_note": personal_note,
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
            use_llm=use_llm,
            anthropic_api_key=anthropic_key_input,
            render_video=render_video,
            root_dir=ROOT_DIR,
        )
    st.rerun()

