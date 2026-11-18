import requests
import logging
from pathlib import Path
from typing import Optional

from conftest import RoleClient

logger = logging.getLogger(__name__)


class UploadApi:
    def __init__(self, client: RoleClient, base_url: str, timeout: int = 10):
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _upload(self, api_path: str, file_path: str, content_type: Optional[str] = None) -> str:
        """
        通用上传方法
        :param api_path: 上传接口路径
        :param file_path: 本地文件路径
        :param content_type: mime类型，不传默认 image/jpeg
        :return: 文件url字符串
        """
        url = f"{self.base_url}{api_path}"
        fp = Path(file_path)
        if content_type is None:
            content_type = "image/jpeg"

        # 核心：删掉header里的Content-Type，交给requests自动生成multipart/form-data
        old_content_type = self.client.headers.pop("Content-Type", None)
        try:
            with fp.open("rb") as f:
                files = {"file": (fp.name, f, content_type)}
                resp = self.client.post(url, files=files, timeout=self.timeout)

            resp_json = resp.json()
            logger.info(f"[上传返回] {resp_json}")
            if resp_json.get("code") != 200:
                raise AssertionError(f"上传失败：{resp_json}")
            # data直接是url字符串
            return resp_json.get("data")

        finally:
            # 恢复原来的header，不影响其他接口
            if old_content_type is not None:
                self.client.headers["Content-Type"] = old_content_type

    # 唯一上传入口，对接 /api/upload/file
    def upload_file(self, file_path: str, content_type: Optional[str] = None) -> str:
        return self._upload("/api/upload/file", file_path, content_type=content_type)


    def delete_by_url(self, file_url: str, skip_check: bool = False):
        url = f"{self.base_url}/api/upload/delete"
        payload = {"url": file_url}

        logger.info(f"[删除请求] url={url}, body={payload}")
        resp = self.client.delete(url, json=payload, timeout=self.timeout)

        if skip_check:
            return resp.json()
        resp.raise_for_status()
        res_json = resp.json()
        logger.info(f"[删除返回] {res_json}")

        if res_json.get("code") != 200:
            raise AssertionError(f"删除失败：{res_json}")
        return res_json
