import allure
import pytest


@allure.feature("API - 认证模块")
class TestAuthApi:

    def test_login_success(self, api_session, env):
        from api.auth_api import AuthApi
        auth = AuthApi(api_session, env["api_base_url"])
        account = env["accounts"]["admin"]

        with allure.step("调用登录接口"):
            data = auth.login(account["username"], account["password"])
            assert "token" in data
            assert data["user"]["username"] == account["username"]

    def test_login_fail(self, api_session, env):
        from api.auth_api import AuthApi
        auth = AuthApi(api_session, env["api_base_url"])

        with allure.step("使用错误密码登录，期望抛出 AssertionError"):
            with pytest.raises(AssertionError, match="用户名或密码错误"):
                auth.login("admin", "wrong_password")

    def test_update_profile(self, admin_client, pm_task_api=None):
        from api.auth_api import AuthApi
        auth = AuthApi(admin_client, base_url="")
        original_name = None

        with allure.step("获取当前个人信息，记录原始姓名"):
            profile = auth._request("GET", "/me")
            original_name = profile["realName"]

        try:
            with allure.step("修改个人信息为测试姓名"):
                # 这个接口返回Result<Void>，_request成功返回None，不要拿res["code"]
                auth._request("PUT", "/profile", json={"realName": "系统管理员-API测试"})

            with allure.step("校验修改结果"):
                new_profile = auth._request("GET", "/me")
                assert new_profile["realName"] == "系统管理员-API测试", "姓名没有修改成功"
        finally:
            if original_name is not None:
                with allure.step("复原姓名"):
                    auth._request("PUT", "/profile", json={"realName": original_name})

