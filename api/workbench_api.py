"""工作台接口封装，对应 WorkbenchController：/api/workbench 下的工作台汇总接口。"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any, List


class WorkbenchApi:
    """工作台接口封装类，复用传入的 Session。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        # 提取基础路径，对应类上的 @RequestMapping("/api")
        self.api_base = f"{base_url.rstrip('/')}/api"

    def _request(
        self,
        method: str,
        path: str,
        *,
        expect_data: bool = False
    ) -> Any:
        """内部统一请求方法，处理 URL 拼接、超时及业务校验。"""
        url = f"{self.api_base}{path}"

        response = self.session.request(
            method=method,
            url=url,
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

    def get_pm_project_overview(self) -> List[Dict[str, Any]]:
        """
        PM 工作台 - 我负责的进行中项目汇总：GET /api/workbench/pm/projectOverview
        无入参，根据 Token 的角色返回不同数据：
        - PM 返回自己作为 owner 的进行中（ACTIVE）项目汇总
        - ADMIN 返回全部进行中项目汇总
        - DEV / QA 返回空数组
        """
        # 路径已经固定，直接请求
        return self._request("GET", "/workbench/pm/projectOverview", expect_data=True)