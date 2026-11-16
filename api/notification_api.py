"""站内通知接口封装，对应 NotificationController：/api/notifications 下的相关接口。"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any, List


class NotificationApi:
    """站内通知接口封装类，复用传入的 Session。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        # 提取出该模块的基础路径
        self.api_base = f"{base_url.rstrip('/')}/api/notifications"

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
        if expect_data and data is None:
            raise AssertionError(f"接口返回数据为空 [{method} {path}]: {body}")

        return data

    # ================= 具体接口定义 =================

    def unread_updates(self) -> Dict[str, Any]:
        """
        全局工作台未读变更：GET /api/notifications/unread
        返回当前用户的未读变更统计。
        """
        return self._request("GET", "/unread", expect_data=True)

    def list_recent(self) -> List[Dict[str, Any]]:
        """
        消息中心列表：GET /api/notifications/list
        返回当前用户最近的站内消息列表（非分页）。
        """
        return self._request("GET", "/list", expect_data=True)

    def delete_message(self, message_id: int) -> None:
        """
        删除单条消息：DELETE /api/notifications/{id}
        """
        self._request("DELETE", f"/{message_id}")

    def clear_all_messages(self) -> None:
        """
        清空全部消息：DELETE /api/notifications/clear
        注意：这是固定路径，与 /{id} 不同。
        """
        self._request("DELETE", "/clear")

    def mark_all_as_read(self) -> None:
        """
        全部标记为已读：PATCH /api/notifications/read-all
        """
        self._request("PATCH", "/read-all")

    def my_notifications(
            self,
            unread_only: Optional[bool] = None,
            current: int = 1,
            size: int = 10
    ) -> Dict[str, Any]:
        """
        分页查询当前登录用户的站内通知：GET /api/notifications
        可按是否未读过滤。
        """
        params = {
            "unreadOnly": unread_only,
            "current": current,
            "size": size
        }
        return self._request("GET", "", params=params, expect_data=True)

    def mark_read(self, message_id: int) -> None:
        """
        标记单条通知为已读：PATCH /api/notifications/{id}/read
        """
        self._request("PATCH", f"/{message_id}/read")