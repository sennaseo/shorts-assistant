from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


NOTION_VERSION = "2026-03-11"


def extract_notion_page_id(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    match = re.search(r"([0-9a-fA-F]{32})", raw.replace("-", ""))
    if not match:
        return raw
    page_id = match.group(1)
    return f"{page_id[0:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:32]}"


def _rich_text(content: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": content[:2000]}}]


def markdown_to_notion_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": _rich_text(line[5:])}})
        elif line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": _rich_text(line[4:])}})
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": _rich_text(line[3:])}})
        elif line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": _rich_text(line[2:])}})
        elif line.startswith("- "):
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": _rich_text(line[2:])},
                }
            )
        elif re.match(r"^\d+\.\s+", line):
            text = re.sub(r"^\d+\.\s+", "", line)
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": _rich_text(text)},
                }
            )
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(line)}})
    return blocks


def _append_batch(token: str, page_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    payload = json.dumps({"children": children}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def append_markdown_to_notion_page(token: str, page_id_or_url: str, markdown: str) -> dict[str, Any]:
    page_id = extract_notion_page_id(page_id_or_url)
    if not token:
        return {"success": False, "message": "NOTION_API_KEY가 없습니다."}
    if not page_id:
        return {"success": False, "message": "Notion 페이지 ID 또는 URL이 없습니다."}

    blocks = markdown_to_notion_blocks(markdown)
    if not blocks:
        return {"success": False, "message": "Notion에 보낼 내용이 없습니다."}

    try:
        total = 0
        for index in range(0, len(blocks), 100):
            batch = blocks[index : index + 100]
            _append_batch(token, page_id, batch)
            total += len(batch)
        return {"success": True, "message": f"Notion 페이지에 {total}개 블록을 추가했습니다.", "page_id": page_id}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            hint = "페이지가 없거나 integration이 이 페이지에 공유되어 있지 않습니다."
        elif exc.code == 401:
            hint = "Notion API 토큰이 잘못되었거나 만료되었습니다."
        elif exc.code == 403:
            hint = "integration에 콘텐츠 삽입 권한이 없습니다."
        else:
            hint = "Notion API 요청이 실패했습니다."
        return {"success": False, "message": f"{hint} HTTP {exc.code}: {detail}", "page_id": page_id}
    except Exception as exc:
        return {"success": False, "message": f"Notion 발행 실패: {exc}", "page_id": page_id}
