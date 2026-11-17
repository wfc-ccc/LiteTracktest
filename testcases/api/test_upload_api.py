import allure
import pytest
from pathlib import Path
from api.upload_api import UploadApi

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"


@allure.feature("API - 文件上传")
class TestUploadApi:

    def _clean_upload_file(self, upload_api: UploadApi, file_url: str):
        """兜底清理：失败不阻断用例"""
        if not file_url:
            return
        try:
            upload_api.delete_by_url(file_url, skip_check=True)
        except Exception:
            pass

    @pytest.fixture
    def upload_api(self, admin_client, env):
        return UploadApi(admin_client, base_url=env["api_base_url"])

    @allure.story("图片上传接口 /image 正向上传")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("/image接口上传支持的文件类型，上传成功")
    @pytest.mark.parametrize("suffix, content, mime_type", [
        ("jpg", "fake jpg content", "image/jpeg"),
        ("png", "fake png content", "image/png"),
        ("txt", "txt文本内容", "text/plain"),
        ("pdf", "fake pdf content", "application/pdf"),
    ], ids=["jpg图片", "png图片", "txt文档", "pdf文档"])
    def test_upload_image_support_type(self, upload_api, tmp_path, suffix, content, mime_type):
        f = tmp_path / f"test.{suffix}"
        f.write_text(content, encoding="utf-8")
        file_url = ""
        with allure.step(f"{suffix} 文件上传 /image 接口，预期上传成功"):
            try:
                file_url = upload_api.upload_image(str(f), content_type=mime_type)
                assert file_url is not None and file_url.startswith("http"), "返回的url格式非法"
                allure.attach(file_url, "上传成功url", allure.attachment_type.TEXT)
            finally:
                self._clean_upload_file(upload_api, file_url)

    @allure.story("图片上传接口 /image 文件大小校验")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.title("/image接口上传超过10MB文件，预期拦截失败")
    def test_upload_image_over_size(self, upload_api, tmp_path):
        # 生成一个11MB的伪大文件
        f = tmp_path / "big.bin"
        # 11 * 1024 * 1024 byte
        f.write_bytes(b"0" * 11 * 1024 * 1024)
        file_url = ""
        with allure.step("上传大于10MB文件，预期拦截"):
            try:
                file_url = upload_api.upload_image(str(f), content_type="application/octet-stream")
                # 走到这里代表没有拦截，用例失败
                assert False, "超大文件没有被拦截，上传成功"
            except AssertionError as e:
                err_msg = str(e)
                allure.attach(err_msg, "异常详情", allure.attachment_type.TEXT)
                assert "大小" in err_msg or "超过" in err_msg or "limit" in err_msg
            finally:
                self._clean_upload_file(upload_api, file_url)
