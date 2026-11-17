import allure
import os


@allure.feature("API - 文件上传")
class TestUploadApi:

    def test_upload_image(self, admin_client, tmp_path):
        from api.upload_api import UploadApi
        upload_api = UploadApi(admin_client, base_url="")

        # 造一个假图片文件
        fake_img = tmp_path / "test.png"
        fake_img.write_bytes(b"fake image content")

        with allure.step("上传文件并获取 URL"):
            url = upload_api.upload_image(str(fake_img))
            assert url.startswith("http")
            assert "test" in url or ".png" in url