"""登录正向流程。失败截图由根目录 conftest.py 的 pytest_runtest_makereport 附加到 Allure。"""

from __future__ import annotations

import allure
import pytest

pytestmark = pytest.mark.ui


@allure.feature("登录")
@allure.story("正向登录")
class TestLoginFlow:
    @allure.title("使用 admin 账号登录并进入工作台")
    def test_admin_login_success(self, login_page, env):
        account = env["accounts"]["admin"]

        with allure.step("打开登录页"):
            login_page.open()
            assert login_page.visible(login_page.TITLE).text == "轻舟 LiteTrack"

        with allure.step("提交正确的用户名和密码"):
            login_page.login(account["username"], str(account["password"]))

        with allure.step("断言跳转到工作台且顶栏已展示登录用户"):
            display_name = login_page.wait_until_logged_in()
            assert "/dashboard" in login_page.driver.current_url
            assert display_name
            assert "未登录" not in display_name
