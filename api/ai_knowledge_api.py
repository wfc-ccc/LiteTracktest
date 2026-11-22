"""AI 知识库接口封装，对应 AiKnowledgeController：/api/ai/knowledge 下的相关接口。

契约来源：AiKnowledgeServiceImpl / KnowledgeUpdateDTO 源码，不要凭前端猜字段。
- POST  /upload     multipart: file + accessLevel(1/2/3)
- GET   /list       query: fileName?, current, size
- GET   /content    query: fileName
- PUT   ""          JSON Body: fileName + newContent   ← 不是 content
- DELETE ""         query: fileName
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests


# 上传时要带的 MIME：后端 DocumentParser 按文件名取扩展名，但带上标准 MIME
# 能让 multipart 解析器少一层猜测，也便于后端排错。
_MIME = {
    "txt": "text/plain",
    "md": "text/markdown",
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": ("application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document"),
}


def mime_of(file_name: str) -> str:
    ext = os.path.splitext(file_name)[1].lower().lstrip(".")
    return _MIME.get(ext, "application/octet-stream")


class AiKnowledgeApi:
    def __init__(self, session: requests.Session, base_url: str = ""):
        self.session = session
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.api_base = f"{self.base_url}/api/ai/knowledge"

    def _request(self, method: str, path: str = "", **kwargs) -> Any:
        resp = self.session.request(
            method, f"{self.api_base}{path}", timeout=30, **kwargs
        )
        if resp.status_code != 200:
            raise AssertionError(
                f"知识库接口 HTTP {resp.status_code}（期望 200）→ {resp.text[:300]}"
            )
        try:
            body = resp.json()
        except ValueError:
            return resp.text
        code = body.get("code")
        # 后端 Result 成功码是 200，兼容返回 0 的写法
        if code is not None and code not in (200, 0):
            raise AssertionError(
                f"知识库接口业务失败 code={code}, message={body.get('message')!r}"
            )
        return body.get("data")

    # ---------------- 写（仅 ADMIN） ----------------
    def upload_file(self, file_path: str, access_level: int = 1,
                    file_name: Optional[str] = None) -> Dict[str, Any]:
        """上传知识库文件（仅 ADMIN）：POST /api/ai/knowledge/upload。

        file_name 可覆盖 multipart 里的文件名（排错时用 ASCII 名对照）。
        """
        path = os.path.abspath(file_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"文件不存在：{path}")
        name = file_name or os.path.basename(path)
        with open(path, "rb") as fh:
            return self._request(
                "POST", "/upload",
                files={"file": (name, fh, mime_of(name))},
                data={"accessLevel": access_level},
            )

    def update_content(self, file_name: str, content: str) -> Dict[str, Any]:
        """修改文件内容（仅 ADMIN）：PUT /api/ai/knowledge。

        字段必须是 newContent：后端 KnowledgeUpdateDTO 读的是 getNewContent()，
        发 content 会被当成「没填正文」，接口直接报错。
        """
        return self._request(
            "PUT", "", json={"fileName": file_name, "newContent": content}
        )

    def delete_file(self, file_name: str) -> None:
        """删除文件（仅 ADMIN）：DELETE /api/ai/knowledge，fileName 走 Query。"""
        self._request("DELETE", "", params={"fileName": file_name})

    # ---------------- 读（登录即可） ----------------
    def list_files(self, file_name: Optional[str] = None, current: int = 1,
                   size: int = 10) -> Dict[str, Any]:
        """分页列表：GET /api/ai/knowledge/list。"""
        params = {"current": current, "size": size}
        if file_name:
            params["fileName"] = file_name
        return self._request("GET", "/list", params=params) or {}

    def file_names(self, file_name: Optional[str] = None, size: int = 100) -> List[str]:
        """列表里的文件名（断言「在/不在」时比翻 records 方便）。"""
        page = self.list_files(file_name=file_name, size=size)
        return [r.get("fileName") for r in (page.get("records") or [])]

    def get_content(self, file_name: str) -> str:
        """查看全文：GET /api/ai/knowledge/content。"""
        return self._request("GET", "/content", params={"fileName": file_name}) or ""

    # ---------------- 便利方法 ----------------
    def delete_if_exists(self, file_name: str) -> bool:
        """存在才删，返回是否真的删了（teardown 幂等清理用）。"""
        if file_name in self.file_names(file_name):
            self.delete_file(file_name)
            return True
        return False
