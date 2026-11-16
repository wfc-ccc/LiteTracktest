"""认证模块接口封装，对应 AuthController：/api/auth 下的相关接口。"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any


class AuthApi:
    """认证接口封装类，复用传入的 Session 以保持连接池和 Cookie。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, *, json: Optional[dict] = None, expect_data: bool = False) -> Any:
        """
        内部统一请求方法，处理 URL 拼接、超时、HTTP 状态码校验、业务 code 校验。
        """
        url = f"{self.base_url}/api/auth{path}"
        response = self.session.request(method, url, json=json, timeout=15)

        # 1. HTTP 状态码断言（处理 4xx, 5xx）
        response.raise_for_status()

        # 2. 解析响应体
        body = response.json()

        # 3. 业务状态码校验（根据常规后端设计，code 为 200 代表成功）
        if body.get("code") != 200:
            raise AssertionError(f"接口业务异常 [{method} {path}]: {body}")

        data = body.get("data")

        # 4. 如果明确需要返回数据（如登录、获取用户信息），但 data 为空，则报错
        if expect_data and not data:
            raise AssertionError(f"接口返回数据为空 [{method} {path}]: {body}")

        return data

    # ================= 具体接口定义 =================

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        登录接口：POST /api/auth/login
        返回 data，包含 {token, user}
        """
        payload = {"username": username, "password": password}
        return self._request("POST", "/login", json=payload, expect_data=True)

    def logout(self) -> None:
        """
        退出登录接口：POST /api/auth/logout
        """
        self._request("POST", "/logout")

    def me(self) -> Dict[str, Any]:
        """
        获取当前登录用户信息接口：GET /api/auth/me
        返回 data，包含用户信息 (UserVO)
        """
        return self._request("GET", "/me", expect_data=True)

    def update_profile(self, real_name: Optional[str] = None, password: Optional[str] = None) -> None:
        """
        修改个人信息接口：PUT /api/auth/profile
        根据控制器注释，仅允许修改 realName 与 password，传 None 的字段不会被发送。
        """
        payload = {}
        if real_name is not None:
            payload["realName"] = real_name
        if password is not None:
            payload["password"] = password

        self._request("PUT", "/profile", json=payload)