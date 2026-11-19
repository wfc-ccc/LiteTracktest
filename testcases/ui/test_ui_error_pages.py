import allure
import pytest
from selenium.webdriver.common.by import By

@allure.feature("UI 自动化")
@allure.story("异常路由与错误页")
class TestErrorPagesUI:

    @pytest.fixture
    def error_page(self, driver, env):
        from pages.error_page import ErrorPage
        return ErrorPage(driver, env["web_base_url"])

    @allure.title("验证 404 页面兜底与返回工作台")
    def test_404_page_not_found(self, error_page, driver, login):
        with allure.step("登录后访问一个乱码路由"):
            admin_token = login("admin")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{admin_token}')")
            error_page.open_path("/this-page-does-not-exist-123")

        with allure.step("验证 404 拦截与文案"):
            error_page.wait_url("/404")
            assert error_page.get_error_code() == "404"
            assert "抱歉，你访问的页面不存在" in error_page.get_subtitle()

        with allure.step("验证返回工作台"):
            error_page.click_back_dashboard()
            error_page.wait_url("/dashboard")

    @allure.title("验证 403 越权访问拦截")
    def test_403_forbidden_access(self, error_page, driver, login):
        with allure.step("使用 DEV 账号强行访问管理员专属路由 /users"):
            dev_token = login("dev01")["token"]
            driver.execute_script(f"window.localStorage.setItem('litetrack_token', '{dev_token}')")
            error_page.open_path("/users")

        with allure.step("验证 403 拦截与文案"):
            # 等待重定向到 403
            error_page.wait_url("/403")
            assert error_page.get_error_code() == "403"
            assert "抱歉，你没有访问该页面的权限" in error_page.get_subtitle()