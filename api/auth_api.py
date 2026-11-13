"""认证接口封装，对应 AuthController：POST /api/auth/login。"""

from __future__ import annotations

import requests


class AuthApi:
    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        self.base_url = base_url.rstrip("/")

    def login(self, username: str, password: str) -> dict:
        """登录并返回 data：{token, user}。失败时抛出 AssertionError。"""
        response = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"username": username, "password": password},
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 200 or not (body.get("data") or {}).get("token"):
            raise AssertionError(f"登录失败 username={username}: {body}")
        return body["data"]
