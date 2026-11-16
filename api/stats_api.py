"""统计接口封装，对应 StatsController：/api/stats 下的相关接口。"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any, List


class StatsApi:
    """统计接口封装类，复用传入的 Session。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        # 提取出该模块的基础路径
        self.api_base = f"{base_url.rstrip('/')}/api/stats"

    def _request(
            self,
            method: str,
            path: str = "",
            *,
            params: Optional[dict] = None,
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
            timeout=15
        )

        response.raise_for_status()
        body = response.json()

        if body.get("code") != 200:
            raise AssertionError(f"接口业务异常 [{method} {path}]: {body}")

        data = body.get("data")
        # 根据后端 VO 的设计，这里返回的可能是 Dict，也可能是空 Dict，甚至 List
        if expect_data and data is None:
            raise AssertionError(f"接口返回数据为空 [{method} {path}]: {body}")

        return data

    # ================= 具体接口定义 =================

    def get_overview(self, project_id: int) -> Dict[str, Any]:
        """
        统计概览：GET /api/stats/overview
        返回指定项目的概览统计 (OverviewVO)。
        """
        params = {"projectId": project_id}
        return self._request("GET", "/overview", params=params, expect_data=True)

    def get_bug_status(self, project_id: int) -> List[Dict[str, Any]]:
        """
        缺陷状态分布：GET /api/stats/bug-status
        按待处理 / 已修复 / 已关闭返回缺陷数量分布 (List<BugStatusVO>)。
        """
        params = {"projectId": project_id}
        return self._request("GET", "/bug-status", params=params, expect_data=True)

    def get_task_member(self, project_id: int) -> Dict[str, Any]:
        """
        项目成员任务统计：GET /api/stats/task-member
        返回 members / done / undone 三个对齐数组 (TaskMemberVO)。
        """
        params = {"projectId": project_id}
        return self._request("GET", "/task-member", params=params, expect_data=True)

    def get_bug_trend(self, project_id: int, days: int = 7) -> Dict[str, Any]:
        """
        缺陷趋势：GET /api/stats/bug-trend
        统计近 days 天的缺陷趋势，默认 7 天 (BugTrendVO)。
        """
        params = {
            "projectId": project_id,
            "days": days
        }
        return self._request("GET", "/bug-trend", params=params, expect_data=True)