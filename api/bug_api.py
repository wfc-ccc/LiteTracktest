"""缺陷管理接口封装，对应 BugController：/api/bugs 下的相关接口。"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any, List


class BugApi:
    """缺陷管理接口封装类，复用传入的 Session。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        # 提取出该模块的基础路径
        self.api_base = f"{base_url.rstrip('/')}/api/bugs"

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

        # 过滤掉值为 None 的查询参数，避免请求出现 ?status=None 这样的脏数据
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

    # ================= 具体接口定义 =================

    def page(
            self,
            project_id: Optional[int] = None,
            status: Optional[str] = None,
            severity: Optional[str] = None,
            assignee_id: Optional[int] = None,
            keyword: Optional[str] = None,
            current: int = 1,
            size: int = 10
    ) -> Dict[str, Any]:
        """
        分页查询缺陷：GET /api/bugs
        对应 Controller 中的 page 方法，支持多条件组合筛选。
        """
        params = {
            "projectId": project_id,
            "status": status,
            "severity": severity,
            "assigneeId": assignee_id,
            "keyword": keyword,
            "current": current,
            "size": size
        }
        return self._request("GET", "", params=params, expect_data=True)

    def get_by_id(self, bug_id: int) -> Dict[str, Any]:
        """
        获取缺陷详情：GET /api/bugs/{id}
        """
        return self._request("GET", f"/{bug_id}", expect_data=True)

    def create(self, data: dict) -> None:
        """
        提交缺陷：POST /api/bugs
        :param data: 对应后端的 BugCreateDTO 字典
        """
        self._request("POST", "", json=data)

    def assign(self, bug_id: int, data: dict) -> None:
        """
        指派缺陷处理人：PATCH /api/bugs/{id}/assign
        :param data: 对应后端的 BugAssignDTO 字典
        """
        self._request("PATCH", f"/{bug_id}/assign", json=data)

    def fix(self, bug_id: int, data: dict) -> None:
        """
        修复缺陷：PATCH /api/bugs/{id}/fix
        :param data: 对应后端的 BugFixDTO 字典
        """
        self._request("PATCH", f"/{bug_id}/fix", json=data)

    def close(self, bug_id: int, data: dict) -> None:
        """
        验证关闭缺陷：PATCH /api/bugs/{id}/close
        :param data: 对应后端的 BugCloseDTO 字典
        """
        self._request("PATCH", f"/{bug_id}/close", json=data)

    def reopen(self, bug_id: int, data: dict) -> None:
        """
        重新激活缺陷：PATCH /api/bugs/{id}/reopen
        :param data: 对应后端的 BugReopenDTO 字典
        """
        self._request("PATCH", f"/{bug_id}/reopen", json=data)

    def get_logs(self, bug_id: int) -> List[Dict[str, Any]]:
        """
        获取缺陷操作日志：GET /api/bugs/{id}/logs
        """
        return self._request("GET", f"/{bug_id}/logs", expect_data=True)