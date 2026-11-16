"""任务阻塞接口封装，对应 TaskBlockController：/api/task-blocks 下的相关接口。"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any


class TaskBlockApi:
    """任务阻塞接口封装类，复用传入的 Session。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        # 提取基础路径，对应 @RequestMapping("/api")
        self.api_base = f"{base_url.rstrip('/')}/api"

    def _request(
            self,
            method: str,
            path: str,
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

    # ================= 具体接口定义 =================

    def block(self, task_id: int, data: dict) -> None:
        """
        提交任务阻塞：POST /api/task-blocks/{taskId}/block
        :param task_id: 任务主键
        :param data: 对应 TaskBlockDTO 字典，必填包含 blockReason, expectRestartTime, workHour
        """
        self._request("POST", f"/task-blocks/{task_id}/block", json=data)

    def delay(self, task_id: int, data: dict) -> None:
        """
        延期重启：POST /api/task-blocks/{taskId}/delay
        :param task_id: 任务主键
        :param data: 对应 TaskDelayDTO 字典，包含新的预计重启时间与延期原因
        """
        self._request("POST", f"/task-blocks/{task_id}/delay", json=data)

    def restart(self, task_id: int) -> None:
        """
        重启任务：POST /api/task-blocks/{taskId}/restart
        :param task_id: 任务主键
        """
        self._request("POST", f"/task-blocks/{task_id}/restart")

    def get_detail(self, task_id: int) -> Dict[str, Any]:
        """
        查询任务阻塞详情：GET /api/task-blocks/{taskId}/detail
        返回包含当前阻塞状态及历史记录的 TaskBlockDetailVO。
        :param task_id: 任务主键
        """
        return self._request("GET", f"/task-blocks/{task_id}/detail", expect_data=True)