"""任务管理接口封装，对应 TaskController：/api/tasks 下的相关接口。"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any, List


class TaskApi:
    """任务管理接口封装类，复用传入的 Session。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        # 提取出该模块的基础路径
        self.api_base = f"{base_url.rstrip('/')}/api/tasks"

    def _request(
        self,
        method: str,
        path: str = "",
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        expect_data: bool = False
    ) -> Any:
        """内部统一请求方法，处理 URL 拼接、参数过滤、超时及业务校验。"""
        url = f"{self.api_base}{path}"

        if params:
            params = {k: v for k, v in params.items() if v is not None}

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json,
            timeout=15
        )

        response.raise_for_status()
        body = response.json()

        if body.get("code") != 200:
            raise AssertionError(f"接口业务异常 [{method} {path}]: {body}")

        data = body.get("data")
        if expect_data and data is None:
            raise AssertionError(f"接口返回数据为空 [{method} {path}]: {body}")

        return data

    # ================= 1. 查询类接口 =================

    def page(
        self,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        assignee_id: Optional[int] = None,
        keyword: Optional[str] = None,
        current: int = 1,
        size: int = 10
    ) -> Dict[str, Any]:
        """
        分页查询任务：GET /api/tasks
        """
        params = {
            "projectId": project_id,
            "status": status,
            "assigneeId": assignee_id,
            "keyword": keyword,
            "current": current,
            "size": size
        }
        return self._request("GET", "", params=params, expect_data=True)

    def get_by_id(self, task_id: int) -> Dict[str, Any]:
        """
        任务详情：GET /api/tasks/{id}
        """
        return self._request("GET", f"/{task_id}", expect_data=True)

    def get_audit_records(self, task_id: int) -> List[Dict[str, Any]]:
        """
        查询任务审核记录：GET /api/tasks/{id}/audit-records
        """
        return self._request("GET", f"/{task_id}/audit-records", expect_data=True)


    # ================= 2. 基础管理类接口（ADMIN/PM） =================

    def create(self, data: dict) -> None:
        """
        新增任务：POST /api/tasks
        """
        self._request("POST", "", json=data)

    def update(self, task_id: int, data: dict) -> None:
        """
        修改任务：PUT /api/tasks/{id}
        """
        self._request("PUT", f"/{task_id}", json=data)

    def assign(self, task_id: int, data: dict) -> None:
        """
        重新指派任务：PATCH /api/tasks/{id}/assign
        """
        self._request("PATCH", f"/{task_id}/assign", json=data)

    def delete(self, task_id: int) -> None:
        """
        删除任务：DELETE /api/tasks/{id}
        """
        self._request("DELETE", f"/{task_id}")


    # ================= 3. 状态流转与审核类接口 =================

    def accept(self, task_id: int) -> None:
        """
        接受任务 (TODO -> DOING)：PATCH /api/tasks/{id}/accept
        """
        self._request("PATCH", f"/{task_id}/accept")

    def reject(self, task_id: int, data: dict) -> None:
        """
        拒绝任务 (TODO -> REJECTED)：PATCH /api/tasks/{id}/reject
        :param data: 包含拒绝原因的数据字典
        """
        self._request("PATCH", f"/{task_id}/reject", json=data)

    def submit(self, task_id: int, data: dict) -> None:
        """
        提交任务 (DOING -> PENDING_REVIEW)：PATCH /api/tasks/{id}/submit
        :param data: 包含提交内容/工时等的字典
        """
        self._request("PATCH", f"/{task_id}/submit", json=data)

    def audit(self, task_id: int, data: dict) -> None:
        """
        审核任务 (PENDING_REVIEW -> DONE/DOING)：PATCH /api/tasks/{id}/audit
        :param data: 包含 auditResult 和 auditReason 的字典
        """
        self._request("PATCH", f"/{task_id}/audit", json=data)