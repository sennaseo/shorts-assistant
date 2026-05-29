from __future__ import annotations

from pathlib import Path
from typing import Any

from .bgm_manager import bgm_edit_guide, copy_selected_bgm
from .capcut_package_builder import build_capcut_package, build_edit_guide
from .edge_tts_generator import generate_edge_tts
from .file_utils import copy_file, ensure_dir, load_json, safe_filename, save_json, timestamp, write_text
from .image_prompt_generator import save_image_prompts
from .link_hub_generator import save_link_hub_files
from .notion_publisher import append_markdown_to_notion_page
from .reference_manager import save_references
from .script_generator import generate_script
from .srt_generator import save_srt
from .subtitle_generator import save_capcut_subtitles
from .typecast_formatter import format_for_typecast, save_typecast_files
from .upload_text_generator import save_upload_text


ROOT_DIR = Path(__file__).resolve().parents[1]


def create_output_dir(product_name: str, outputs_root: str | Path | None = None) -> Path:
    root = Path(outputs_root) if outputs_root else ROOT_DIR / "outputs"
    folder = f"{safe_filename(product_name, 'shorts_project')}_{timestamp()}"
    return ensure_dir(root / folder)


def _save_uploaded_sources(files: list[Any] | None, target_dir: Path) -> list[Path]:
    saved: list[Path] = []
    ensure_dir(target_dir)
    for file in files or []:
        name = safe_filename(Path(getattr(file, "name", "uploaded_file")).stem, "uploaded")
        suffix = Path(getattr(file, "name", "")).suffix
        destination = target_dir / f"{name}{suffix}"
        if hasattr(file, "getbuffer"):
            destination.write_bytes(file.getbuffer())
        else:
            copied = copy_file(file, destination)
            if copied:
                destination = copied
        saved.append(destination)
    return saved


def run_pipeline(
    product_info: dict[str, Any],
    product_image_files: list[Any] | None = None,
    source_video_files: list[Any] | None = None,
    references: list[dict[str, str]] | None = None,
    category_links_text: str = "",
    product_items_text: str = "",
    publish_to_notion: bool = False,
    notion_api_token: str = "",
    notion_page_id: str = "",
    tts_voice: str = "ko-KR-SunHiNeural",
    tts_rate: str = "+0%",
    root_dir: str | Path | None = None,
) -> dict[str, Any]:
    base = Path(root_dir) if root_dir else ROOT_DIR
    output_dir = create_output_dir(str(product_info.get("product_name") or "shorts_project"), base / "outputs")
    result: dict[str, Any] = {"output_dir": output_dir, "errors": [], "files": {}}

    try:
        image_dir = ensure_dir(output_dir / "source_product_images")
        video_dir = ensure_dir(output_dir / "source_videos")
        saved_images = _save_uploaded_sources(product_image_files, image_dir)
        saved_videos = _save_uploaded_sources(source_video_files, video_dir)

        link_hub_paths = save_link_hub_files(
            product_info,
            output_dir,
            base / "data" / "category_links.json",
            raw_category_links=category_links_text,
            raw_product_items=product_items_text,
        )
        product_info["resolved_category_page_url"] = link_hub_paths.get("category_page_url", "")

        if publish_to_notion:
            notion_markdown = Path(link_hub_paths["notion_category_page"]).read_text(encoding="utf-8")
            notion_result = append_markdown_to_notion_page(notion_api_token, notion_page_id, notion_markdown)
            result["notion_publish"] = notion_result
            if not notion_result.get("success"):
                result["errors"].append(str(notion_result.get("message")))

        save_json(output_dir / "product_info.json", product_info)
        products_path = base / "data" / "products.json"
        products = load_json(products_path, default=[]) or []
        save_json(products_path, [*products, product_info])

        script_result = generate_script(product_info)
        script_path = write_text(output_dir / "script.txt", script_result["script"])
        result["files"]["script"] = script_path

        typecast_paths = save_typecast_files(script_result["script"], output_dir)
        typecast_lines, _ = format_for_typecast(script_result["script"])
        result["files"].update(typecast_paths)

        tts_text = "\n".join(typecast_lines)
        tts_result = generate_edge_tts(tts_text, output_dir, voice=tts_voice, rate=tts_rate)
        if tts_result["success"]:
            result["files"]["edge_tts_test"] = tts_result["path"]
        else:
            result["errors"].append(tts_result["error"])

        subtitle_result = save_capcut_subtitles(typecast_lines, output_dir)
        keywords = list(subtitle_result.get("keywords") or [])
        result["files"]["capcut_subtitles"] = subtitle_result["capcut_subtitles"]

        srt_path = save_srt(
            typecast_lines,
            output_dir,
            int(product_info.get("target_length") or 40),
            tts_result.get("path") if tts_result["success"] else None,
        )
        result["files"]["subtitles"] = srt_path

        bgm_result = copy_selected_bgm(
            base / "assets" / "bgm",
            output_dir,
            str(product_info.get("tone") or ""),
            str(product_info.get("bgm_mood") or ""),
        )
        if bgm_result["path"]:
            result["files"]["selected_bgm"] = bgm_result["path"]

        image_prompt_path = save_image_prompts(product_info, output_dir)
        upload_info_path = save_upload_text(product_info, output_dir)
        reference_paths = save_references(references or [], product_info, output_dir, base / "data" / "references.json")

        edit_guide = build_edit_guide(
            product_info,
            keywords,
            str(bgm_result["message"]),
            "생성 완료" if tts_result["success"] else str(tts_result["error"]),
        )
        edit_guide += "\n\n" + bgm_edit_guide()
        edit_guide_path = write_text(output_dir / "edit_guide.txt", edit_guide)

        package_path = build_capcut_package(output_dir, product_images=saved_images, source_videos=saved_videos)

        result["files"].update(
            {
                "product_info": output_dir / "product_info.json",
                "image_prompts": image_prompt_path,
                "upload_info": upload_info_path,
                "edit_guide": edit_guide_path,
                "tiktok_references": reference_paths["tiktok_references"],
                "notion_category_page": link_hub_paths["notion_category_page"],
                "inpock_link_guide": link_hub_paths["inpock_link_guide"],
            }
        )
        result["capcut_package"] = package_path
        result["product_images"] = saved_images
        result["source_videos"] = saved_videos
        result["script"] = script_result["script"]
        result["typecast_lines"] = "\n".join(typecast_lines)
        result["capcut_subtitles"] = Path(result["files"]["capcut_subtitles"]).read_text(encoding="utf-8")
        result["upload_info"] = Path(upload_info_path).read_text(encoding="utf-8")
        result["link_hub_guide"] = Path(link_hub_paths["inpock_link_guide"]).read_text(encoding="utf-8")
        result["notion_category_page"] = Path(link_hub_paths["notion_category_page"]).read_text(encoding="utf-8")
        return result
    except Exception as exc:
        result["errors"].append(f"파이프라인 실행 중 오류: {exc}")
        return result
