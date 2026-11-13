"""任务接口封装，对应 TaskController（/api/tasks）。

接受 / 提交：PATCH，负责人和 ADMIN/PM 可调用。
审核：PATCH /{id}/audit，仅 ADMIN/PM（@RequireRole）。角色不够时 HTTP 仍为 200，
业务码 code=403，见 RoleAspect 与 GlobalExceptionHandler。
"""

from __future__ import annotations

import requests


class TaskApi:
    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        self.base_url = base_url.rstrip("/")

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def create(self, token: str, payload: dict) -> requests.Response:
        """POST /api/tasks。成功时 data 为空，任务 ID 需要再查询。"""
        return self.session.post(
            f"{self.base_url}/api/tasks",
            json=payload,
            headers=self._headers(token),
            timeout=15,
        )

    def page(self, token: str, **params) -> requests.Response:
        """GET /api/tasks。分页 data 结构为 {records, total, current, size}。"""
        return self.session.get(
            f"{self.base_url}/api/tasks",
            params=params,
            headers=self._headers(token),
            timeout=15,
        )

    def accept(self, token: str, task_id: int) -> requests.Response:
        """PATCH /api/tasks/{id}/accept，TODO -> DOING，无请求体。"""
        return self.session.patch(
            f"{self.base_url}/api/tasks/{task_id}/accept",
            headers=self._headers(token),
            timeout=15,
        )

    def submit(self, token: str, task_id: int, payload: dict) -> requests.Response:
        """PATCH /api/tasks/{id}/submit，DOING -> PENDING_REVIEW。"""
        return self.session.patch(
            f"{self.base_url}/api/tasks/{task_id}/submit",
            json=payload,
            headers=self._headers(token),
            timeout=15,
        )

    def audit(self, token: str, task_id: int, audit_result: str = "PASS", audit_reason: str = "") -> requests.Response:
        """PATCH /api/tasks/{id}/audit。auditResult=PASS 时 auditReason 可空。"""
        return self.session.patch(
            f"{self.base_url}/api/tasks/{task_id}/audit",
            json={"auditResult": audit_result, "auditReason": audit_reason},
            headers=self._headers(token),
            timeout=15,
        )

    def delete(self, token: str, task_id: int) -> requests.Response:
        """DELETE /api/tasks/{id}，仅 ADMIN/PM。"""
        return self.session.delete(
            f"{self.base_url}/api/tasks/{task_id}",
            headers=self._headers(token),
            timeout=15,
        )

    def find_id_by_title(self, token: str, title: str, project_id: int) -> int:
        """创建接口不返回 ID，按唯一标题回查。"""
        response = self.page(token, projectId=project_id, keyword=title, current=1, size=10)
        body = response.json()
        if body.get("code") != 200:
            raise AssertionError(f"查询任务失败: {body}")
        records = (body.get("data") or {}).get("records") or []
        matched = [item for item in records if item.get("title") == title]
        if len(matched) != 1:
            raise AssertionError(f"期望唯一任务标题 {title!r}，实际匹配 {len(matched)} 条")
        return int(matched[0]["id"])

    @staticmethod
    def raise_if_business_failed(response: requests.Response, action: str) -> dict:
        body = response.json()
        if response.status_code != 200 or body.get("code") != 200:
            raise AssertionError(f"{action} 失败: http={response.status_code}, body={body}")
        return body
