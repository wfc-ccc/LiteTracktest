"""通用上传接口封装，对应 UploadController：/api/upload 下的相关接口。"""

from __future__ import annotations

import os
import requests
from typing import Optional, Any, Union
from pathlib import Path


class UploadApi:
    """通用上传接口封装类，复用传入的 Session。"""

    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        # 提取出该模块的基础路径
        self.api_base = f"{base_url.rstrip('/')}/api/upload"

    def _request(
            self,
            method: str,
            path: str = "",
            *,
            files: Optional[dict] = None,
            expect_data: bool = False
    ) -> Any:
        """内部统一请求方法，处理 URL 拼接、超时及业务校验。"""
        url = f"{self.api_base}{path}"

        response = self.session.request(
            method=method,
            url=url,
            files=files,
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

    # ================= 内部工具方法 =================

    def _get_files_payload(self, file_path: Union[str, Path]) -> dict:
        """
        根据文件路径构造 requests 所需的 files 字典。
        注意：调用此方法时，文件句柄不能立即关闭，需要由外层 request 发送完毕后自动回收。
        """
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"待上传的文件不存在: {file_path}")

        # 以二进制模式打开文件
        file_obj = open(path, "rb")
        # requests 格式: {'file': (filename, file_obj)}
        return {"file": (path.name, file_obj)}

    # ================= 具体接口定义 =================

    def upload_image(self, file_path: Union[str, Path]) -> str:
        """
        上传图片/附件：POST /api/upload/image
        允许后缀：jpg / jpeg / png / gif / txt / log / pdf / doc / docx，单文件不超过 10MB。
        返回可直接访问的完整 URL。
        """
        files = self._get_files_payload(file_path)
        try:
            return self._request("POST", "/image", files=files, expect_data=True)
        finally:
            # 确保请求发送完毕后关闭文件句柄，释放系统资源
            files["file"][1].close()

    def upload_file(self, file_path: Union[str, Path]) -> str:
        """
        上传通用附件：POST /api/upload/file
        不限后缀（支持 .log / .txt 等测试日志），单文件不超过 10MB。
        返回可直接访问的完整 URL。
        """
        files = self._get_files_payload(file_path)
        try:
            return self._request("POST", "/file", files=files, expect_data=True)
        finally:
            # 确保请求发送完毕后关闭文件句柄，释放系统资源
            files["file"][1].close()