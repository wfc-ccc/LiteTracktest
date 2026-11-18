import allure
import pytest
from pathlib import Path
from api.upload_api import UploadApi

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "uplodedata"

@allure.feature("API - 文件上传")
class TestUploadApi:

    @staticmethod
    def _clean_upload_file(upload_api: UploadApi, file_url: str):
        """兜底清理：删除上传文件记录，失败不阻断用例"""
        if not file_url:
            return
        try:
            upload_api._request(
                "DELETE",
                "/delete",
                json={"url": file_url},
                skip_code_check=True
            )
        except Exception:
            pass

    @allure.story("通用附件上传接口 /file")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("正向：上传各类附件，上传成功后删除记录")
    @pytest.mark.parametrize(
        "file_name, mime_type",
        [
            ("img.png", "image/png"),
            ("img2.gif", "image/gif"),
            ("文档 (2).docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("新建 .pdf", "application/pdf"),
            ("知识库.txt", "text/plain"),
        ],
        ids=["png图片", "gif动图", "word文档", "pdf文档", "txt文本"]
    )
    def test_upload_all_valid_file(self, admin_client, env, file_name, mime_type):
        upload_api = UploadApi(admin_client, env["api_base_url"])
        file_path = DATA_DIR / file_name
        print(f"读取文件：{file_path.resolve()}")
        assert file_path.exists(), f"文件不存在：{file_name}"
        file_url = ""
        with allure.step(f"上传 {file_name}"):
            try:
                file_url = upload_api.upload_file(str(file_path), content_type=mime_type)
                assert file_url and file_url.startswith("http"), "返回url异常"
                allure.attach(file_url, "上传url", allure.attachment_type.TEXT)
            finally:
                self._clean_upload_file(upload_api, file_url)
