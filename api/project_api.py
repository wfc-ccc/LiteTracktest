"""项目管理接口封装，对应 ProjectController：/api/projects 下的相关接口。"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any, List


class ProjectApi:
    """项目管理接口封装类，复用传入的 Session。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        # 提取出该模块的基础路径
        self.api_base = f"{base_url.rstrip('/')}/api/projects"

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

        # 过滤掉值为 None 的查询参数
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

    def get_list(
            self,
            name: Optional[str] = None,
            status: Optional[str] = None,
            current: int = 1,
            size: int = 10
    ) -> Dict[str, Any]:
        """
        分页获取项目列表：GET /api/projects
        """
        params = {
            "name": name,
            "status": status,
            "current": current,
            "size": size
        }
        return self._request("GET", "", params=params, expect_data=True)

    def get_detail(self, project_id: int) -> Dict[str, Any]:
        """
        获取项目详情：GET /api/projects/{id}
        """
        return self._request("GET", f"/{project_id}", expect_data=True)

    def get_members(self, project_id: int) -> List[Dict[str, Any]]:
        """
        获取项目成员：GET /api/projects/{id}/members
        """
        return self._request("GET", f"/{project_id}/members", expect_data=True)

    # ================= 2. 基础写操作接口 =================

    def create(self, data: dict) -> None:
        """
        创建项目：POST /api/projects
        :param data: 对应 ProjectSaveDTO 字典
        """
        self._request("POST", "", json=data)

    def update(self, project_id: int, data: dict) -> None:
        """
        修改项目：PUT /api/projects/{id}
        :param data: 对应 ProjectSaveDTO 字典
        """
        self._request("PUT", f"/{project_id}", json=data)

    def delete(self, project_id: int) -> None:
        """
        物理删除项目：DELETE /api/projects/{id}
        """
        self._request("DELETE", f"/{project_id}")

    # ================= 3. 状态流转接口 =================

    def close(self, project_id: int) -> None:
        """
        关闭项目：PUT /api/projects/{id}/close
        """
        self._request("PUT", f"/{project_id}/close")

    def reopen(self, project_id: int) -> None:
        """
        重启项目：PUT /api/projects/{id}/reopen
        """
        self._request("PUT", f"/{project_id}/reopen")

    # ================= 4. 成员管理接口 =================

    def add_members(self, project_id: int, data: dict) -> None:
        """
        添加项目成员：POST /api/projects/{id}/members
        :param data: 对应 MemberAddDTO 字典
        """
        self._request("POST", f"/{project_id}/members", json=data)

    def remove_member(self, project_id: int, user_id: int) -> None:
        """
        移除项目成员：DELETE /api/projects/{id}/members/{userId}
        """
        self._request("DELETE", f"/{project_id}/members/{user_id}")