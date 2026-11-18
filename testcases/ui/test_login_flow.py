"""登录正向流程。失败截图由根目录 conftest.py 的 pytest_runtest_makereport 附加到 Allure。"""
from __future__ import annotations

import allure
import pytest

pytestmark = pytest.mark.ui


@allure.feature("登录")
class TestLoginFlow:
    @allure.story("正向登录")
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

    @allure.story("正向登录")
    @allure.title("admin账号登录，密码框回车提交登录")
    def test_admin_login_by_enter(self, login_page, env):
        account = env["accounts"]["admin"]

        with allure.step("打开登录页"):
            login_page.open()
        with allure.step("输入账号密码，回车提交"):
            login_page.login_by_enter(account["username"], str(account["password"]))
        with allure.step("断言登录成功进入工作台"):
            display_name = login_page.wait_until_logged_in()
            assert "/dashboard" in login_page.driver.current_url
            assert display_name

    @allure.story("登录异常校验")
    @allure.title("密码错误，弹出全局错误提示")
    def test_login_wrong_password(self, login_page, env):
        admin_account = env["accounts"]["admin"]
        with allure.step("打开登录页"):
            login_page.open()
        with allure.step("输入正确账号、错误密码，提交登录"):
            login_page.login(admin_account["username"], "wrongpassword123")
        with allure.step("断言全局toast提示，不跳转工作台"):
            toast_msg = login_page.get_message_text()
            assert "用户名或密码错误" in toast_msg
            assert "/dashboard" not in login_page.driver.current_url

    @allure.story("登录异常校验")
    @allure.title("账号不存在，弹出全局错误提示")
    def test_login_user_not_exist(self, login_page, env):
        with allure.step("打开登录页"):
            login_page.open()
        with allure.step("输入不存在账号，提交登录"):
            login_page.login("notexist_user_001", "123456")
        with allure.step("断言全局toast提示，不跳转工作台"):
            toast_msg = login_page.get_message_text()
            assert "用户名或密码错误" in toast_msg
            assert "/dashboard" not in login_page.driver.current_url

    @allure.story("登录前端表单校验")
    @allure.title("用户名为空，触发表单必填校验")
    def test_login_empty_username(self, login_page, env):
        with allure.step("打开登录页"):
            login_page.open()
        with allure.step("用户名留空，输入密码提交"):
            login_page.login("", "123456")
        with allure.step("断言表单项下方必填提示"):
            error_text = login_page.get_form_error_text()
            assert "请输入用户名" in error_text
            assert "/dashboard" not in login_page.driver.current_url

    @allure.story("登录前端表单校验")
    @allure.title("密码为空，触发表单必填校验")
    def test_login_empty_password(self, login_page, env):
        admin_account = env["accounts"]["admin"]
        with allure.step("打开登录页"):
            login_page.open()
        with allure.step("输入账号，密码留空提交"):
            login_page.login(admin_account["username"], "")
        with allure.step("断言表单项下方必填提示"):
            error_text = login_page.get_form_error_text()
            assert "请输入密码" in error_text
            assert "/dashboard" not in login_page.driver.current_url

    @allure.story("登录退出")
    @allure.title("清除token回到登录页，路由守卫拦截")
    def test_login_logout_clear_token(self, login_page, env, logged_in_driver):
        """使用login_page自带的localStorage清除方法，模拟退出"""
        with allure.step("在已登录状态执行清除令牌，返回登录页"):
            login_page.logout()
        with allure.step("校验成功回到登录页面"):
            login_page.visible(login_page.TITLE)
            assert "/login" in logged_in_driver.current_url
