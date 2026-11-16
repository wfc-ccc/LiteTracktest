"""用户管理接口封装，对应 UserController：/api/users 下的相关接口。"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any, List


class UserApi:
    """用户管理接口封装类，复用传入的 Session。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        # 提取出该模块的基础路径
        self.api_base = f"{base_url.rstrip('/')}/api/users"

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

    def page(
            self,
            username: Optional[str] = None,
            role: Optional[str] = None,
            status: Optional[int] = None,
            current: int = 1,
            size: int = 10
    ) -> Dict[str, Any]:
        """
        分页查询用户：GET /api/users
        """
        params = {
            "username": username,
            "role": role,
            "status": status,
            "current": current,
            "size": size
        }
        return self._request("GET", "", params=params, expect_data=True)

    def get_options(self) -> List[Dict[str, Any]]:
        """
        用户下拉选项：GET /api/users/options
        返回所有状态正常的用户列表，供负责人/成员选择使用。
        """
        return self._request("GET", "/options", expect_data=True)

    def page_deleted(self, current: int = 1, size: int = 10) -> Dict[str, Any]:
        """
        分页查询已删除用户（回收站）：GET /api/users/deleted
        """
        params = {
            "current": current,
            "size": size
        }
        return self._request("GET", "/deleted", params=params, expect_data=True)

    # ================= 2. 基础写操作接口（仅 ADMIN） =================

    def create(self, data: dict) -> None:
        """
        新增用户：POST /api/users
        """
        self._request("POST", "", json=data)

    def update(self, user_id: int, data: dict) -> None:
        """
        修改用户完整信息：PUT /api/users/{id}
        """
        self._request("PUT", f"/{user_id}", json=data)

    def update_status(self, user_id: int, data: dict) -> None:
        """
        修改用户状态（启用/禁用）：PATCH /api/users/{id}/status
        :param data: 包含 status 字段的字典
        """
        self._request("PATCH", f"/{user_id}/status", json=data)

    # ================= 3. 删除与回收站操作接口（仅 ADMIN） =================

    def delete(self, user_id: int) -> None:
        """
        逻辑删除用户：DELETE /api/users/{id}
        用户进入回收站，可通过 restore 接口还原。
        """
        self._request("DELETE", f"/{user_id}")

    def restore(self, user_id: int) -> None:
        """
        恢复已删除用户：PUT /api/users/{id}/restore
        将回收站中的用户恢复为正常状态。
        """
        self._request("PUT", f"/{user_id}/restore")

    def permanent_delete(self, user_id: int) -> None:
        """
        彻底删除用户：DELETE /api/users/{id}/permanent
        物理删除 + 级联清理关联数据，不可恢复。
        """
        self._request("DELETE", f"/{user_id}/permanent")