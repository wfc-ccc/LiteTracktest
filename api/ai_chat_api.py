"""AI 对话接口封装，对应 AiChatController：/api/ai 下的相关接口。

契约来源：AiChatServiceImpl 源码。
- GET/POST /sessions、PUT/DELETE /sessions/{id}
- GET  /sessions/{sessionId}/messages
- POST /chat          produces=text/event-stream，每条事件是 {"content","isEnd"} 的 JSON
- POST /upload-temp   multipart: file → data 为纯文本（超 3000 字截断）
- POST /optimize-bug  JSON: rawText + projectId?
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import requests

from api.ai_knowledge_api import mime_of


# 会话里可能被塞了 Content-Type: application/json（conftest 的老写法就是这样），
# 那会让 multipart 请求体带着 JSON 头发出去，后端直接 MultipartException。
# 传 None 让 requests 把继承来的这个头删掉，由它自己生成 boundary。
_STRIP_CONTENT_TYPE = {"Content-Type": None}

# /chat 的 produces 只有 text/event-stream，Accept 必须是它，否则在 handler 匹配阶段
# 就抛 HttpMediaTypeNotAcceptableException（后端报 500/406），方法体都不会进。
# 同时声明 application/json 作为次选：正常时走事件流，抛业务异常时后端能正常回
# {code,message} 的 JSON 信封，客户端才读得到「消息为空 / 会话不存在」这类具体原因。
_SSE_ACCEPT = {"Accept": "text/event-stream, application/json;q=0.9"}


class AiChatApi:
    def __init__(self, session: requests.Session, base_url: str = ""):
        self.session = session
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.api_base = f"{self.base_url}/api/ai"

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """统一请求封装，直接返回 data 业务数据。

        非 200 抛 AssertionError，失败信息里带后端 code/message 原文，
        比只断言布尔值更好定位。
        """
        resp = self.session.request(
            method, f"{self.api_base}{path}", timeout=30, **kwargs
        )
        if resp.status_code != 200:
            raise AssertionError(
                f"AI 接口 HTTP {resp.status_code}（期望 200）→ {resp.text[:300]}"
            )
        try:
            body = resp.json()
        except ValueError:
            return resp.text
        code = body.get("code")
        if code is not None and code not in (200, 0):
            raise AssertionError(
                f"AI 接口业务失败 code={code}, message={body.get('message')!r}"
            )
        return body.get("data")

    # ---------------- 会话 ----------------
    def list_sessions(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/sessions") or []

    def create_session(self, title: Optional[str] = None) -> Dict[str, Any]:
        payload = {"title": title} if title is not None else {}
        return self._request("POST", "/sessions", json=payload) or {}

    def update_session(self, session_id: int, title: Optional[str] = None,
                       is_top: Optional[int] = None) -> None:
        payload: Dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if is_top is not None:
            payload["isTop"] = is_top
        self._request("PUT", f"/sessions/{session_id}", json=payload)

    def delete_session(self, session_id: int) -> None:
        self._request("DELETE", f"/sessions/{session_id}")

    def list_messages(self, session_id: int) -> List[Dict[str, Any]]:
        return self._request("GET", f"/sessions/{session_id}/messages") or []

    # ---------------- 对话（SSE） ----------------
    def chat(self, payload: dict) -> requests.Response:
        """发送对话请求（流式）：返回原始 Response 供用例手动消费流。

        注意：拿到 Response 后一定要把流读完再 close。中途 break 会让服务端
        Flux 收到 CANCEL，doFinally 里的落库可能在你下一次读取前还没写完。
        需要省事就直接用 chat_events()，它负责读完、解析、关闭。
        """
        return self.session.post(
            f"{self.api_base}/chat", json=payload, stream=True, timeout=60,
            headers=_SSE_ACCEPT,
        )

    def chat_events(self, payload: dict, timeout: float = 60) -> Dict[str, Any]:
        """读完整条 SSE 并解析，返回 {"text", "events", "ended"}。

        - 逐行按 bytes 读，再整体做一次 utf-8 解码，避免 requests 在 chunk
          边界按块解码把中文字符切坏；
        - 不中途 break，一直读到服务端断流，保证落库的 doFinally 已执行。
        """
        resp = self.chat(payload)
        if resp.status_code != 200:
            raise AssertionError(
                f"对话接口 HTTP {resp.status_code}（期望 200）→ {resp.text[:300]}"
            )
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            raise AssertionError(
                f"后端返回了 JSON 而非 SSE（说明请求在返回流之前就失败了）："
                f"{resp.text[:300]}"
            )

        events: List[dict] = []
        chunks: List[str] = []
        ended = False
        try:
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    evt = json.loads(data)
                except ValueError:
                    # 兼容后端只推纯文本片段的情况，不让解析失败掩盖流本身的问题
                    chunks.append(data)
                    continue
                events.append(evt)
                if evt.get("content"):
                    chunks.append(evt["content"])
                if evt.get("isEnd"):
                    ended = True
        finally:
            resp.close()
        return {"text": "".join(chunks), "events": events, "ended": ended}

    def wait_messages(self, session_id: int, min_count: int = 2,
                      timeout: float = 10) -> List[Dict[str, Any]]:
        """轮询等待消息条数达标（助手回复在流结束后由 doFinally 异步落库）。

        API 层没有 DOM 可等，只能短间隔轮询；UI 层的「禁止 sleep」不适用于这里。
        """
        deadline = time.time() + timeout
        while True:
            msgs = self.list_messages(session_id)
            if len(msgs) >= min_count or time.time() >= deadline:
                return msgs
            time.sleep(0.2)

    # ---------------- 对话内临时文件 ----------------
    def upload_temp(self, file_path: str, file_name: Optional[str] = None) -> str:
        """上传对话临时文件：POST /api/ai/upload-temp，返回解析后的纯文本。

        后端 extractTempText = readText + 3000 字截断，与知识库上传共用解析链路，
        所以这里的失败信息能直接反映整条链路是否正常。
        """
        path = os.path.abspath(file_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"文件不存在：{path}")
        name = file_name or os.path.basename(path)
        with open(path, "rb") as fh:
            return self._request(
                "POST", "/upload-temp",
                files={"file": (name, fh, mime_of(name))},
                headers=_STRIP_CONTENT_TYPE,
            )

    # ---------------- 缺陷一键润色 ----------------
    def optimize_bug(self, raw_text: str,
                     project_id: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"rawText": raw_text}
        if project_id is not None:
            payload["projectId"] = project_id
        return self._request("POST", "/optimize-bug", json=payload) or {}
